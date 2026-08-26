"""
Train a temporal sequence classifier (LSTM when PyTorch works).

Uses sliding windows of consecutive flows to capture temporal attack
patterns. Falls back to sklearn MLP on flattened windows if needed.
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import FEATURE_COLUMNS, MODELS_DIR
from training.data_preprocessing import (
    clean_data,
    encode_labels,
    load_dataset,
    prepare_sequences,
    save_encoder,
    save_scaler,
)
from training.neural_models import save_neural_model, train_lstm_model

WINDOW_SIZE = 10


def train(dataset_path: str, models_dir: str | None = None) -> dict:
    """Train LSTM / sequence model on windowed flows. Returns metrics."""
    models_dir = Path(models_dir) if models_dir else MODELS_DIR
    models_dir.mkdir(parents=True, exist_ok=True)

    df = load_dataset(dataset_path)
    df = clean_data(df)
    df, label_encoder = encode_labels(df, label_col="label")
    save_encoder(label_encoder, models_dir / "label_encoder.pkl")

    X = df[FEATURE_COLUMNS].values
    y = df["label"].values
    num_classes = len(label_encoder.classes_)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    save_scaler(scaler, models_dir / "scaler.pkl")

    X_seq, y_seq = prepare_sequences(X_scaled, y, window_size=WINDOW_SIZE)

    X_train, X_test, y_train, y_test = train_test_split(
        X_seq, y_seq, test_size=0.2, random_state=42
    )

    model = train_lstm_model(
        X_train,
        y_train.astype(np.int64),
        num_classes=num_classes,
        window_size=WINDOW_SIZE,
        epochs=30,
        batch_size=256,
    )

    y_pred_proba = model.predict(X_test)
    y_pred = np.argmax(y_pred_proba, axis=1)
    y_true = y_test.astype(np.int64)

    average = "binary" if num_classes == 2 else "weighted"
    metrics: dict = {
        "model": "LSTM",
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, average=average, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, average=average, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, average=average, zero_division=0)),
    }

    try:
        if num_classes == 2:
            metrics["roc_auc"] = float(roc_auc_score(y_true, y_pred_proba[:, 1]))
        else:
            metrics["roc_auc"] = float(
                roc_auc_score(y_true, y_pred_proba, multi_class="ovr", average="weighted")
            )
    except ValueError:
        metrics["roc_auc"] = None

    model_path = models_dir / "lstm_model.pt"
    save_neural_model(model_path, model)
    print(f"[LSTM] Model saved to {model_path}")
    for k, v in metrics.items():
        if k != "model":
            print(f"  {k}: {v}")

    return metrics


if __name__ == "__main__":
    from config import DATASETS_DIR

    default_dataset = DATASETS_DIR / "dataset.csv"
    train(str(default_dataset))
