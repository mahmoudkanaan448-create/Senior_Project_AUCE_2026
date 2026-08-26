"""
Train an XGBoost classifier for network traffic classification.

Supervised gradient boosting for known attack types. Complements
Random Forest in the hybrid engine; saves artifacts under MODELS_DIR.
"""

import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import FEATURE_COLUMNS, MODELS_DIR

from training.data_preprocessing import (
    clean_data,
    encode_labels,
    load_dataset,
    save_encoder,
    save_scaler,
    scale_features,
)


def train(dataset_path: str, models_dir: str | None = None) -> dict:
    """Train an XGBoost model; return evaluation metrics."""
    models_dir = Path(models_dir) if models_dir else MODELS_DIR
    models_dir.mkdir(parents=True, exist_ok=True)

    df = load_dataset(dataset_path)
    df = clean_data(df)
    df, label_encoder = encode_labels(df, label_col="label")
    save_encoder(label_encoder, models_dir / "label_encoder.pkl")

    X = df[FEATURE_COLUMNS].values
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    X_train, X_test, scaler = scale_features(X_train, X_test)
    save_scaler(scaler, models_dir / "scaler.pkl")

    num_classes = len(label_encoder.classes_)
    objective = "binary:logistic" if num_classes == 2 else "multi:softprob"

    clf = XGBClassifier(
        n_estimators=200,
        max_depth=8,
        learning_rate=0.1,
        objective=objective,
        eval_metric="logloss",
        use_label_encoder=False,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    average = "binary" if num_classes == 2 else "weighted"

    metrics: dict = {
        "model": "XGBoost",
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, average=average, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, average=average, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, average=average, zero_division=0)),
    }

    try:
        if num_classes == 2:
            y_proba = clf.predict_proba(X_test)[:, 1]
            metrics["roc_auc"] = float(roc_auc_score(y_test, y_proba))
        else:
            y_proba = clf.predict_proba(X_test)
            metrics["roc_auc"] = float(
                roc_auc_score(y_test, y_proba, multi_class="ovr", average="weighted")
            )
    except ValueError:
        metrics["roc_auc"] = None

    model_path = models_dir / "xgboost_model.pkl"
    joblib.dump(clf, model_path)
    print(f"[XGBoost] Model saved to {model_path}")
    for k, v in metrics.items():
        if k != "model":
            print(f"  {k}: {v}")

    return metrics


if __name__ == "__main__":
    from config import DATASETS_DIR

    default_dataset = DATASETS_DIR / "dataset.csv"
    train(str(default_dataset))
