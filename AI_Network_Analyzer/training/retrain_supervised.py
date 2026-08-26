"""
Retrain Random Forest + XGBoost with one shared scaler/encoder.

Does not overwrite Isolation Forest, Autoencoder, or LSTM artifacts.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from config import FEATURE_COLUMNS, MODELS_DIR
from training.data_preprocessing import (
    clean_data,
    encode_labels,
    load_dataset,
    save_encoder,
    save_scaler,
    scale_features,
)
from training.dataset_registry import register_dataset


def retrain(dataset_path: str, models_dir: str | None = None) -> dict:
    models_dir = Path(models_dir) if models_dir else MODELS_DIR
    models_dir.mkdir(parents=True, exist_ok=True)

    df = clean_data(load_dataset(dataset_path))
    df, encoder = encode_labels(df, label_col="label")
    save_encoder(encoder, models_dir / "label_encoder.pkl")

    X = df[FEATURE_COLUMNS].values
    y = df["label"].values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    X_train, X_test, scaler = scale_features(X_train, X_test)
    save_scaler(scaler, models_dir / "scaler.pkl")

    rf = RandomForestClassifier(
        n_estimators=220, max_depth=18, min_samples_leaf=2,
        random_state=42, n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    joblib.dump(rf, models_dir / "random_forest.pkl")

    num_classes = len(encoder.classes_)
    objective = "binary:logistic" if num_classes == 2 else "multi:softprob"
    xgb = XGBClassifier(
        n_estimators=220,
        max_depth=7,
        learning_rate=0.08,
        objective=objective,
        eval_metric="mlogloss" if num_classes > 2 else "logloss",
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )
    xgb.fit(X_train, y_train)
    joblib.dump(xgb, models_dir / "xgboost_model.pkl")

    # Isolation Forest on Normal rows only — reuse the shared scaler (do not overwrite it)
    try:
        from sklearn.ensemble import IsolationForest
        normal_idx = encoder.inverse_transform(y_train) == "Normal"
        if normal_idx.any():
            iso = IsolationForest(
                n_estimators=200, contamination=0.12, random_state=42, n_jobs=-1
            )
            iso.fit(X_train[normal_idx])
            joblib.dump(iso, models_dir / "isolation_forest.pkl")
    except Exception:
        pass

    out = {"dataset": str(dataset_path), "n_train": int(len(X_train)), "n_test": int(len(X_test))}
    for name, model in (("RandomForest", rf), ("XGBoost", xgb)):
        pred = model.predict(X_test)
        out[name] = {
            "accuracy": float(accuracy_score(y_test, pred)),
            "precision": float(precision_score(y_test, pred, average="weighted", zero_division=0)),
            "recall": float(recall_score(y_test, pred, average="weighted", zero_division=0)),
            "f1": float(f1_score(y_test, pred, average="weighted", zero_division=0)),
        }
    register_dataset(dataset_path, note="supervised RF+XGB retrain (shared scaler)")
    return out


if __name__ == "__main__":
    from config import DATASETS_DIR
    print(retrain(str(DATASETS_DIR / "dataset.csv")))
