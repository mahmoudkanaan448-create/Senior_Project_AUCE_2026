"""
Attack detection engine – loads trained models and runs predictions.

Loads Random Forest, XGBoost, Isolation Forest, Autoencoder, and LSTM
from disk, prepares flow feature vectors, and returns per-model labels
with confidence scores for the Decision Engine to fuse.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, Optional

import numpy as np
import joblib

from config import MODELS_DIR, FEATURE_COLUMNS

# Model nickname → filename on disk
_MODEL_FILES: Dict[str, str] = {
    "random_forest": "random_forest.pkl",
    "xgboost": "xgboost_model.pkl",
    "isolation_forest": "isolation_forest.pkl",
    "autoencoder": "autoencoder.pt",
    "lstm": "lstm_model.pt",
}


def load_models(models_dir: Optional[str] = None) -> Dict[str, Any]:
    """Load all five trained models (plus scaler/encoder) from disk."""
    base = Path(models_dir) if models_dir else MODELS_DIR
    loaded: Dict[str, Any] = {}

    for name, filename in _MODEL_FILES.items():
        path = base / filename
        if not path.exists():
            print(f"[AttackDetector] WARNING – model not found: {path}")
            continue
        try:
            if filename.endswith(".pt"):
                from training.neural_models import load_neural_model
                loaded[name] = load_neural_model(path)
            else:
                loaded[name] = joblib.load(path)
            print(f"[AttackDetector] Loaded {name} from {path}")
        except Exception as exc:
            print(f"[AttackDetector] ERROR loading {name}: {exc}")

    scaler_path = base / "scaler.pkl"
    if scaler_path.exists():
        loaded["scaler"] = joblib.load(scaler_path)

    encoder_path = base / "label_encoder.pkl"
    if encoder_path.exists():
        loaded["label_encoder"] = joblib.load(encoder_path)

    # Optional online / incremental SGD model (never required)
    online_path = base / "online_sgd.pkl"
    if online_path.exists():
        try:
            loaded["online_sgd"] = joblib.load(online_path)
            print(f"[AttackDetector] Loaded online_sgd from {online_path}")
        except Exception as exc:
            print(f"[AttackDetector] online_sgd load skipped: {exc}")

    return loaded


def _prepare_features(features: Dict[str, float], scaler: Any = None) -> np.ndarray:
    """Convert a feature dict into a scaled numpy row vector."""
    row = np.array([[features.get(col, 0.0) for col in FEATURE_COLUMNS]], dtype=np.float32)
    if scaler is not None:
        row = scaler.transform(row)
    return row


def predict_single(features: Dict[str, float], models: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Run every loaded model on one feature vector; return label/confidence/raw_output."""
    scaler = models.get("scaler")
    label_encoder = models.get("label_encoder")
    row = _prepare_features(features, scaler)

    results: Dict[str, Dict[str, Any]] = {}

    for name in ("random_forest", "xgboost", "isolation_forest", "autoencoder", "lstm"):
        model = models.get(name)
        if model is None:
            continue
        try:
            if name in ("random_forest", "xgboost"):
                pred = model.predict(row)[0]
                proba = model.predict_proba(row)[0]
                confidence = float(np.max(proba)) * 100
                label = label_encoder.inverse_transform([int(pred)])[0] if label_encoder else str(int(pred))
                results[name] = {"label": label, "confidence": confidence, "raw_output": proba.tolist()}

            elif name == "isolation_forest":
                score = model.decision_function(row)[0]
                pred = model.predict(row)[0]
                is_anomaly = pred == -1
                confidence = min(abs(float(score)) * 100, 100.0)
                label = "Attack" if is_anomaly else "Normal"
                results[name] = {"label": label, "confidence": confidence, "raw_output": float(score)}

            elif name == "autoencoder":
                reconstruction = model.predict(row, verbose=0)
                mse = float(np.mean((row - reconstruction) ** 2))
                from config import AUTOENCODER_ERROR_THRESHOLD
                is_anomaly = mse > AUTOENCODER_ERROR_THRESHOLD
                confidence = min((mse / AUTOENCODER_ERROR_THRESHOLD) * 50, 100.0) if is_anomaly else max(100.0 - (mse / AUTOENCODER_ERROR_THRESHOLD) * 50, 0.0)
                label = "Attack" if is_anomaly else "Normal"
                results[name] = {"label": label, "confidence": confidence, "raw_output": mse}

            elif name == "lstm":
                row_3d = row.reshape((1, 1, row.shape[1]))
                pred = model.predict(row_3d, verbose=0)
                if pred.shape[-1] > 1:
                    class_idx = int(np.argmax(pred, axis=1)[0])
                    confidence = float(np.max(pred)) * 100
                    label = label_encoder.inverse_transform([class_idx])[0] if label_encoder else str(class_idx)
                else:
                    prob = float(pred[0][0])
                    is_attack = prob > 0.5
                    confidence = (prob if is_attack else 1.0 - prob) * 100
                    label = "Attack" if is_attack else "Normal"
                results[name] = {"label": label, "confidence": confidence, "raw_output": pred.tolist()}

        except Exception as exc:
            results[name] = {"label": "Error", "confidence": 0.0, "raw_output": str(exc)}

    # Optional 6th vote from online SGD (additive – does not replace core models)
    online_bundle = models.get("online_sgd")
    if online_bundle is not None:
        try:
            from training.online_learning import predict_online
            # predict_online loads from disk; prefer in-memory bundle if possible
            clf = online_bundle.get("model") if isinstance(online_bundle, dict) else None
            oscaler = online_bundle.get("scaler") if isinstance(online_bundle, dict) else None
            if clf is not None:
                orow = np.array([[features.get(col, 0.0) for col in FEATURE_COLUMNS]], dtype=np.float32)
                if oscaler is not None:
                    orow = oscaler.transform(orow)
                pred = clf.predict(orow)[0]
                conf = 50.0
                if hasattr(clf, "predict_proba"):
                    conf = float(np.max(clf.predict_proba(orow))) * 100.0
                results["online_sgd"] = {
                    "label": str(pred),
                    "confidence": conf,
                    "raw_output": "online_sgd",
                }
            else:
                online_pred = predict_online(features)
                if online_pred:
                    results["online_sgd"] = online_pred
        except Exception as exc:
            results["online_sgd"] = {"label": "Error", "confidence": 0.0, "raw_output": str(exc)}

    return results
