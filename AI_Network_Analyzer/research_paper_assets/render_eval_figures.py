"""Redraw Chapter 5 evaluation figures from stored metrics.json (do not retrain)."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split

from generate_evaluation_assets import save_bar_chart, save_confusion, save_dataset_stats

OUT = Path(__file__).resolve().parent / "evaluation"
METRICS = OUT / "metrics.json"
ROOT = Path(__file__).resolve().parent.parent


def font(size=14):
    for n in ("arial.ttf", "calibri.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            pass
    return ImageFont.load_default()


def save_roc_curve(y_true, y_score, path: Path, title: str) -> None:
    fpr, tpr, _ = roc_curve(y_true, y_score)
    auc = roc_auc_score(y_true, y_score)
    w, h = 720, 560
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 20), title, fill=(15, 23, 42), font=font(18))
    d.text((40, 48), f"AUC = {auc:.3f} (holdout test split)", fill=(71, 85, 105), font=font(13))
    ox, oy, pw, ph = 90, 480, 560, 380
    d.line((ox, oy, ox + pw, oy), fill=(30, 41, 59), width=2)
    d.line((ox, oy, ox, oy - ph), fill=(30, 41, 59), width=2)
    d.text((ox + pw // 2 - 40, oy + 15), "False Positive Rate", fill=(15, 23, 42), font=font(12))
    d.text((20, oy - ph // 2), "TPR", fill=(15, 23, 42), font=font(12))
    # diagonal
    d.line((ox, oy, ox + pw, oy - ph), fill=(200, 200, 200), width=1)
    pts = [(ox + float(f) * pw, oy - float(t) * ph) for f, t in zip(fpr, tpr)]
    for i in range(len(pts) - 1):
        d.line((*pts[i], *pts[i + 1]), fill=(29, 78, 216), width=3)
    img.save(path)


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT))
    from config import FEATURE_COLUMNS, MODELS_DIR

    data = json.loads(METRICS.read_text(encoding="utf-8"))
    ds = data["dataset"]
    classes = ds["classes"]
    rf = data["RandomForest"]
    xgb = data["XGBoost"]
    iso = data["IsolationForest"]

    rows = []
    for label, n in classes.items():
        rows.extend([label] * int(n))
    df = pd.DataFrame({"label": rows})
    save_dataset_stats(df, OUT / "fig_dataset_distribution.png")
    save_bar_chart(
        {"RandomForest": rf, "XGBoost": xgb, "IsolationForest": iso},
        OUT / "fig_model_performance.png",
    )
    labels = data.get("labels") or list(rf["per_class"].keys())
    cm = np.array(rf["confusion_matrix"], dtype=int)
    save_confusion(cm, labels, OUT / "fig_confusion_rf.png")

    # Real ROC from RF one-vs-rest (Normal class)
    try:
        raw = pd.read_csv(ROOT / "datasets" / "dataset.csv")
        cols = [c for c in FEATURE_COLUMNS if c in raw.columns]
        X = raw[cols].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).values
        y_raw = raw["label"].astype(str).values
        scaler = joblib.load(MODELS_DIR / "scaler.pkl")
        le = joblib.load(MODELS_DIR / "label_encoder.pkl")
        mask = np.isin(y_raw, le.classes_)
        X, y_raw = X[mask], y_raw[mask]
        y = le.transform(y_raw)
        Xs = scaler.transform(X)
        _, Xte, _, yte = train_test_split(Xs, y, test_size=0.25, random_state=42, stratify=y)
        model = joblib.load(MODELS_DIR / "random_forest.pkl")
        proba = model.predict_proba(Xte)
        normal_idx = list(le.classes_).index("Normal")
        y_bin = (yte != normal_idx).astype(int)
        attack_score = 1.0 - proba[:, normal_idx]
        save_roc_curve(
            y_bin,
            attack_score,
            OUT / "fig_roc_example.png",
            "ROC Curve — Random Forest (Attack vs Normal, holdout)",
        )
    except Exception as exc:
        print("ROC skip:", exc)

    print("Redrawn evaluation figures from", METRICS)
    print("RF", round(rf["accuracy"] * 100, 2), "XGB", round(xgb["accuracy"] * 100, 2))


if __name__ == "__main__":
    main()
