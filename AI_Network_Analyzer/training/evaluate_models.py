"""
Holdout evaluation for the supervised hybrid models.

Writes models/eval_metrics.json and research_paper_assets/evaluation/metrics.json.
Honest about dataset origin (synthetic CICIDS-style vs imported public CSV).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from config import DATASETS_DIR, FEATURE_COLUMNS, MODELS_DIR, BASE_DIR

EVAL_DIR = BASE_DIR / "research_paper_assets" / "evaluation"


def _load_xy(dataset_path: Path):
    df = pd.read_csv(dataset_path)
    cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    X = df[cols].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).values
    y = df["label"].astype(str).values
    return df, X, y, cols


def _metrics(y_true, y_pred) -> Dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
    }


def _fpr_fnr(y_true, y_pred, labels: list[int]) -> tuple[float, float]:
    """Macro-averaged one-vs-rest FPR and FNR from a multi-class confusion matrix."""
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    fprs, fnrs = [], []
    for i in range(len(labels)):
        tp = int(cm[i, i])
        fn = int(cm[i, :].sum() - tp)
        fp = int(cm[:, i].sum() - tp)
        tn = int(cm.sum() - tp - fn - fp)
        fprs.append(fp / (fp + tn) if (fp + tn) else 0.0)
        fnrs.append(fn / (fn + tp) if (fn + tp) else 0.0)
    return float(np.mean(fprs)), float(np.mean(fnrs))


def _binary_fpr_fnr(y_true, y_pred) -> tuple[float, float]:
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    return float(fpr), float(fnr)


def evaluate(dataset_path: str | None = None) -> Dict[str, Any]:
    data_path = Path(dataset_path) if dataset_path else DATASETS_DIR / "dataset.csv"
    df, X, y, cols = _load_xy(data_path)
    scaler = joblib.load(MODELS_DIR / "scaler.pkl")
    encoder = joblib.load(MODELS_DIR / "label_encoder.pkl")
    classes = list(getattr(encoder, "classes_", []))
    mask = np.isin(y, classes) if classes else np.ones(len(y), dtype=bool)
    X, y = X[mask], y[mask]
    y_enc = encoder.transform(y)
    Xs = scaler.transform(X)

    Xtr, Xte, ytr, yte = train_test_split(
        Xs, y_enc, test_size=0.25, random_state=42, stratify=y_enc
    )

    note_path = DATASETS_DIR / "dataset_build_note.txt"
    source_note = note_path.read_text(encoding="utf-8") if note_path.exists() else ""

    payload: Dict[str, Any] = {
        "dataset": {
            "name": data_path.name,
            "rows": int(len(df)),
            "eval_rows": int(len(y)),
            "features": len(cols),
            "classes": df["label"].value_counts().to_dict(),
            "test_size": 0.25,
            "random_state": 42,
            "holdout": "stratified 25% test, random_state=42",
            "disclaimer": (
                "CICIDS-style 39-feature evaluation of the implemented trainer. "
                "Not claimed as an official CICIDS2017 leaderboard result unless "
                "a public CICIDS/UNSW CSV was imported."
            ),
            "build_note": source_note.strip(),
        },
        "labels": [str(c) for c in classes],
    }

    models = {
        "RandomForest": MODELS_DIR / "random_forest.pkl",
        "XGBoost": MODELS_DIR / "xgboost_model.pkl",
    }
    metrics: Dict[str, Any] = {}
    for name, path in models.items():
        if not path.exists():
            continue
        model = joblib.load(path)
        pred = model.predict(Xte)
        if getattr(pred, "dtype", None) is not None and pred.dtype.kind in ("U", "O", "S"):
            pred = encoder.transform(pred)
        hold = _metrics(yte, pred)
        present = sorted(set(yte.tolist()))
        names = [str(encoder.inverse_transform([i])[0]) for i in present]
        report = classification_report(
            yte, pred, labels=present, target_names=names,
            output_dict=True, zero_division=0,
        )
        cm = confusion_matrix(yte, pred, labels=present)
        hold["per_class"] = {
            k: v for k, v in report.items() if k not in ("accuracy", "macro avg", "weighted avg")
        }
        hold["confusion_matrix"] = cm.tolist()
        fpr, fnr = _fpr_fnr(yte, pred, present)
        hold["fpr"] = fpr
        hold["fnr"] = fnr
        if hasattr(model, "predict_proba"):
            try:
                proba = model.predict_proba(Xte)
                hold["roc_auc"] = float(
                    roc_auc_score(yte, proba, multi_class="ovr", average="weighted")
                )
            except Exception:
                pass
        metrics[name] = hold
        payload[name] = hold

    try:
        iso = joblib.load(MODELS_DIR / "isolation_forest.pkl")
        raw = iso.predict(Xte)
        y_bin = np.array([0 if encoder.inverse_transform([i])[0] == "Normal" else 1 for i in yte])
        pred_bin = np.array([1 if v == -1 else 0 for v in raw])
        iso_m = _metrics(y_bin, pred_bin)
        fpr, fnr = _binary_fpr_fnr(y_bin, pred_bin)
        iso_m["fpr"] = fpr
        iso_m["fnr"] = fnr
        try:
            scores = -iso.score_samples(Xte)
            iso_m["roc_auc"] = float(roc_auc_score(y_bin, scores))
        except Exception:
            pass
        iso_m["note"] = "Binary Normal vs Attack proxy on the same holdout/scaler as RF/XGB."
        metrics["IsolationForest"] = iso_m
        payload["IsolationForest"] = iso_m
    except Exception as exc:
        payload["IsolationForest"] = {"error": str(exc)}

    payload["metrics"] = metrics
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    (EVAL_DIR / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (MODELS_DIR / "eval_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        from datetime import datetime
        from database.database import SessionLocal, init_db
        from database.queries import upsert_ai_model
        init_db()
        db = SessionLocal()
        try:
            for name in ("RandomForest", "XGBoost", "IsolationForest"):
                m = payload.get(name) or {}
                if "accuracy" not in m:
                    continue
                upsert_ai_model(
                    db,
                    name,
                    version="1.0.0",
                    accuracy=float(m["accuracy"]),
                    precision_score=float(m.get("precision") or 0),
                    recall=float(m.get("recall") or 0),
                    f1_score=float(m.get("f1") or 0),
                    training_date=datetime.utcnow(),
                    status="Active",
                )
        finally:
            db.close()
    except Exception:
        pass
    return payload


if __name__ == "__main__":
    result = evaluate()
    summary = {k: result.get(k, {}) for k in ("RandomForest", "XGBoost", "IsolationForest", "dataset")}
    print(json.dumps(summary, indent=2, default=str)[:4000])
