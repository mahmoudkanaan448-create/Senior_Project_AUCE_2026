"""
Neural models for Autoencoder and LSTM-style sequence learning.

Prefers PyTorch when available; falls back to scikit-learn MLP
networks on Python 3.14 / Windows when native torch DLLs fail to load.
Saved files use .pt (torch) or joblib payloads under the same paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np

_TORCH_OK = False
try:
    import torch
    import torch.nn as nn

    _ = torch.zeros(1)  # force native DLL load
    _TORCH_OK = True
except Exception as _torch_err:  # noqa: BLE001 – any failure → sklearn fallback
    torch = None  # type: ignore
    nn = None  # type: ignore
    print(f"[neural_models] PyTorch unavailable ({_torch_err}); using scikit-learn neural fallback.")


def torch_available() -> bool:
    """Return True if PyTorch imported and a simple tensor op succeeded."""
    return _TORCH_OK


if _TORCH_OK:

    class NetworkAutoencoder(nn.Module):
        """Symmetric dense AE: input → 64 → 32 → 16 → 32 → 64 → input."""

        def __init__(self, input_dim: int):
            super().__init__()
            self.input_dim = input_dim
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, 64), nn.ReLU(),
                nn.Linear(64, 32), nn.ReLU(),
                nn.Linear(32, 16), nn.ReLU(),
            )
            self.decoder = nn.Sequential(
                nn.Linear(16, 32), nn.ReLU(),
                nn.Linear(32, 64), nn.ReLU(),
                nn.Linear(64, input_dim),
            )

        def forward(self, x):
            return self.decoder(self.encoder(x))

    class NetworkLSTM(nn.Module):
        """Stacked LSTM classifier (batch_first)."""

        def __init__(self, num_features: int, num_classes: int, window_size: int = 10):
            super().__init__()
            self.num_features = num_features
            self.num_classes = num_classes
            self.window_size = window_size
            self.lstm1 = nn.LSTM(num_features, 64, batch_first=True)
            self.dropout = nn.Dropout(0.3)
            self.lstm2 = nn.LSTM(64, 32, batch_first=True)
            self.fc = nn.Linear(32, num_classes)

        def forward(self, x):
            out, _ = self.lstm1(x)
            out = self.dropout(out)
            out, _ = self.lstm2(out)
            return self.fc(out[:, -1, :])


class TorchPredictWrapper:
    """Expose Keras-like .predict(ndarray) → ndarray for the rest of the app."""

    def __init__(self, model: Any, model_type: str, meta: Optional[Dict[str, Any]] = None):
        self.model = model
        self.model_type = model_type
        self.meta = meta or {}
        self.backend = "torch"
        if _TORCH_OK:
            self.model.eval()

    def predict(self, x: np.ndarray, verbose: int = 0) -> np.ndarray:
        del verbose
        with torch.no_grad():
            tensor = torch.as_tensor(x, dtype=torch.float32)
            if self.model_type == "autoencoder":
                return self.model(tensor).cpu().numpy()
            logits = self.model(tensor)
            return torch.softmax(logits, dim=-1).cpu().numpy()


class SklearnAutoencoder:
    """MLPRegressor trained to reconstruct its input (64→32→16→32→64)."""

    def __init__(self, input_dim: int):
        from sklearn.neural_network import MLPRegressor

        self.input_dim = input_dim
        self.backend = "sklearn"
        self.model_type = "autoencoder"
        self.meta = {"input_dim": input_dim, "backend": "sklearn"}
        self.model = MLPRegressor(
            hidden_layer_sizes=(64, 32, 16, 32, 64),
            activation="relu",
            solver="adam",
            max_iter=50,
            batch_size=256,
            random_state=42,
            verbose=True,
        )

    def fit(self, X: np.ndarray) -> "SklearnAutoencoder":
        self.model.fit(X, X)
        return self

    def predict(self, x: np.ndarray, verbose: int = 0) -> np.ndarray:
        del verbose
        return self.model.predict(x)


class SklearnSequenceClassifier:
    """MLP on flattened sliding-window sequences when PyTorch is unavailable."""

    def __init__(self, num_features: int, num_classes: int, window_size: int = 10):
        from sklearn.neural_network import MLPClassifier

        self.num_features = num_features
        self.num_classes = num_classes
        self.window_size = window_size
        self.backend = "sklearn"
        self.model_type = "lstm"
        self.meta = {
            "num_features": num_features,
            "num_classes": num_classes,
            "window_size": window_size,
            "backend": "sklearn",
        }
        self.model = MLPClassifier(
            hidden_layer_sizes=(128, 64),
            activation="relu",
            solver="adam",
            max_iter=30,
            batch_size=256,
            random_state=42,
            verbose=True,
        )

    def fit(self, X_seq: np.ndarray, y: np.ndarray) -> "SklearnSequenceClassifier":
        X_flat = X_seq.reshape(X_seq.shape[0], -1)
        self.model.fit(X_flat, y)
        return self

    def predict(self, x: np.ndarray, verbose: int = 0) -> np.ndarray:
        """Return class probabilities; accepts 3-D (batch, T, F) like the LSTM API."""
        del verbose
        if x.ndim == 3:
            x = x.reshape(x.shape[0], -1)
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(x)
        labels = self.model.predict(x)
        out = np.zeros((len(labels), self.num_classes), dtype=np.float32)
        for i, lab in enumerate(labels):
            out[i, int(lab)] = 1.0
        return out


def train_autoencoder_model(X_train: np.ndarray, *, epochs: int = 50, batch_size: int = 256):
    """Train AE with PyTorch if possible, else sklearn MLPRegressor."""
    input_dim = X_train.shape[1]
    if _TORCH_OK:
        model = NetworkAutoencoder(input_dim)
        optimizer = torch.optim.Adam(model.parameters())
        criterion = nn.MSELoss()
        X_t = torch.as_tensor(X_train, dtype=torch.float32)
        model.train()
        for epoch in range(epochs):
            perm = torch.randperm(X_t.size(0))
            loss_sum, n_batches = 0.0, 0
            for start in range(0, X_t.size(0), batch_size):
                batch = X_t[perm[start : start + batch_size]]
                optimizer.zero_grad()
                loss = criterion(model(batch), batch)
                loss.backward()
                optimizer.step()
                loss_sum += float(loss.item())
                n_batches += 1
            print(f"  [Autoencoder/torch] epoch {epoch + 1}/{epochs} loss={loss_sum / max(n_batches, 1):.6f}")
        model.eval()
        return TorchPredictWrapper(model, "autoencoder", {"input_dim": input_dim, "backend": "torch"})

    print("  [Autoencoder/sklearn] training MLPRegressor reconstruction network…")
    ae = SklearnAutoencoder(input_dim)
    ae.model.max_iter = epochs
    ae.model.batch_size = batch_size
    ae.fit(X_train)
    return ae


def train_lstm_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    num_classes: int,
    window_size: int = 10,
    epochs: int = 30,
    batch_size: int = 256,
):
    """Train LSTM (torch) or flattened-window MLP (sklearn)."""
    num_features = X_train.shape[2]
    if _TORCH_OK:
        model = NetworkLSTM(num_features, num_classes, window_size)
        optimizer = torch.optim.Adam(model.parameters())
        criterion = nn.CrossEntropyLoss()
        X_t = torch.as_tensor(X_train, dtype=torch.float32)
        y_t = torch.as_tensor(y_train, dtype=torch.long)
        model.train()
        for epoch in range(epochs):
            perm = torch.randperm(X_t.size(0))
            loss_sum, correct, total, n_batches = 0.0, 0, 0, 0
            for start in range(0, X_t.size(0), batch_size):
                xb = X_t[perm[start : start + batch_size]]
                yb = y_t[perm[start : start + batch_size]]
                optimizer.zero_grad()
                logits = model(xb)
                loss = criterion(logits, yb)
                loss.backward()
                optimizer.step()
                loss_sum += float(loss.item())
                correct += int((torch.argmax(logits, 1) == yb).sum().item())
                total += yb.size(0)
                n_batches += 1
            print(
                f"  [LSTM/torch] epoch {epoch + 1}/{epochs} "
                f"loss={loss_sum / max(n_batches, 1):.6f} acc={correct / max(total, 1):.4f}"
            )
        model.eval()
        return TorchPredictWrapper(
            model,
            "lstm",
            {
                "num_features": num_features,
                "num_classes": num_classes,
                "window_size": window_size,
                "backend": "torch",
            },
        )

    print("  [Sequence/sklearn] training MLPClassifier on temporal windows…")
    clf = SklearnSequenceClassifier(num_features, num_classes, window_size)
    clf.model.max_iter = epochs
    clf.model.batch_size = batch_size
    clf.fit(X_train, y_train.astype(np.int64))
    return clf


def save_neural_model(path: Path, model: Any) -> None:
    """Save torch checkpoint (.pt) or sklearn wrapper via joblib."""
    path = Path(path)
    if isinstance(model, TorchPredictWrapper) and _TORCH_OK:
        payload = {
            "model_type": model.model_type,
            "state_dict": model.model.state_dict(),
            "meta": model.meta,
            "backend": "torch",
        }
        torch.save(payload, path)
    else:
        # Keep .pt extension for detector registry; payload is joblib
        joblib.dump(
            {
                "backend": "sklearn",
                "model_type": getattr(model, "model_type", "unknown"),
                "meta": getattr(model, "meta", {}),
                "model": model,
            },
            path,
        )


def load_neural_model(path: Path) -> Any:
    """Load either a PyTorch checkpoint or a sklearn joblib payload."""
    path = Path(path)
    if _TORCH_OK:
        try:
            payload = torch.load(path, map_location="cpu", weights_only=False)
            if isinstance(payload, dict) and payload.get("backend", "torch") == "torch" and "state_dict" in payload:
                model_type = payload["model_type"]
                meta = payload.get("meta", {})
                if model_type == "autoencoder":
                    m = NetworkAutoencoder(int(meta["input_dim"]))
                else:
                    m = NetworkLSTM(
                        int(meta["num_features"]),
                        int(meta["num_classes"]),
                        int(meta.get("window_size", 10)),
                    )
                m.load_state_dict(payload["state_dict"])
                m.eval()
                return TorchPredictWrapper(m, model_type, meta)
        except Exception:
            pass  # fall through to joblib

    payload = joblib.load(path)
    if isinstance(payload, dict) and "model" in payload:
        return payload["model"]
    return payload
