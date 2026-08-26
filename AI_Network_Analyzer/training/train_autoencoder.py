"""
Train an Autoencoder for anomaly detection on network traffic.

Learns to reconstruct normal traffic; high reconstruction MSE at
inference signals an anomaly. Uses PyTorch or sklearn MLP fallback.
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import AUTOENCODER_ERROR_THRESHOLD, FEATURE_COLUMNS, MODELS_DIR
from training.data_preprocessing import (
    clean_data,
    encode_labels,
    load_dataset,
    save_encoder,
    save_scaler,
)
from training.neural_models import save_neural_model, train_autoencoder_model


def train(dataset_path: str, models_dir: str | None = None) -> dict:
    """Train an Autoencoder on normal traffic only. Returns evaluation metrics."""
    models_dir = Path(models_dir) if models_dir else MODELS_DIR
    models_dir.mkdir(parents=True, exist_ok=True)

    df = load_dataset(dataset_path)
    df = clean_data(df)

    raw_labels = df["label"].astype(str)
    normal_mask = raw_labels.isin(["0", "Normal", "normal", "BENIGN"])

    df, label_encoder = encode_labels(df, label_col="label")
    save_encoder(label_encoder, models_dir / "label_encoder.pkl")

    normal_label = int(df.loc[normal_mask, "label"].iloc[0]) if normal_mask.any() else 0

    X = df[FEATURE_COLUMNS].values
    y = df["label"].values

    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    normal_idx = y_train_full == normal_label
    X_train_normal = X_train_full[normal_idx]

    scaler = StandardScaler()
    X_train_normal_scaled = scaler.fit_transform(X_train_normal)
    X_test_scaled = scaler.transform(X_test)
    save_scaler(scaler, models_dir / "scaler.pkl")

    autoencoder = train_autoencoder_model(
        X_train_normal_scaled, epochs=50, batch_size=256
    )

    reconstructions = autoencoder.predict(X_test_scaled)
    mse = np.mean(np.square(X_test_scaled - reconstructions), axis=1)

    threshold = AUTOENCODER_ERROR_THRESHOLD
    y_pred_binary = (mse > threshold).astype(int)
    y_true_binary = np.where(y_test == normal_label, 0, 1)

    metrics: dict = {
        "model": "Autoencoder",
        "accuracy": float(accuracy_score(y_true_binary, y_pred_binary)),
        "precision": float(precision_score(y_true_binary, y_pred_binary, zero_division=0)),
        "recall": float(recall_score(y_true_binary, y_pred_binary, zero_division=0)),
        "f1": float(f1_score(y_true_binary, y_pred_binary, zero_division=0)),
        "roc_auc": None,
    }

    model_path = models_dir / "autoencoder.pt"
    save_neural_model(model_path, autoencoder)
    print(f"[Autoencoder] Model saved to {model_path}")
    for k, v in metrics.items():
        if k != "model":
            print(f"  {k}: {v}")

    return metrics


if __name__ == "__main__":
    from config import DATASETS_DIR

    default_dataset = DATASETS_DIR / "dataset.csv"
    train(str(default_dataset))
