"""
Online / incremental learning buffer.

Stores confirmed attack/normal samples and periodically updates a
lightweight SGDClassifier (partial_fit) without touching the 5 core models.
When enough samples accumulate, the online model is saved as
models/online_sgd.pkl and optionally loaded by the attack detector.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np

from config import ATTACK_LABELS, CAPTURED_DATA_DIR, FEATURE_COLUMNS, MODELS_DIR

logger = logging.getLogger(__name__)

BUFFER_PATH = CAPTURED_DATA_DIR / "online_buffer.jsonl"
ONLINE_MODEL_PATH = MODELS_DIR / "online_sgd.pkl"
ONLINE_META_PATH = MODELS_DIR / "online_sgd_meta.json"
MIN_SAMPLES_TO_FIT = 40
_lock = threading.Lock()


def _ensure_dirs() -> None:
    CAPTURED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def queue_labeled_sample(features: Dict[str, Any], label: str) -> bool:
    """Append one labeled feature vector to the online buffer."""
    if not features or not label:
        return False
    try:
        _ensure_dirs()
        row = {col: float(features.get(col, 0.0) or 0.0) for col in FEATURE_COLUMNS}
        record = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "label": str(label),
            "features": row,
        }
        with _lock:
            with open(BUFFER_PATH, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        # Opportunistic train when buffer is large enough
        try:
            maybe_incremental_train()
        except Exception as exc:
            logger.debug("incremental train deferred: %s", exc)
        return True
    except Exception as exc:
        logger.warning("queue_labeled_sample failed: %s", exc)
        return False


def buffer_stats() -> Dict[str, Any]:
    """Return buffer size and label histogram."""
    if not BUFFER_PATH.exists():
        return {"count": 0, "labels": {}, "path": str(BUFFER_PATH)}
    labels: Dict[str, int] = {}
    count = 0
    try:
        with open(BUFFER_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                count += 1
                try:
                    lab = json.loads(line).get("label", "Unknown")
                    labels[lab] = labels.get(lab, 0) + 1
                except Exception:
                    pass
    except Exception:
        pass
    return {"count": count, "labels": labels, "path": str(BUFFER_PATH)}


def _load_buffer(max_rows: int = 5000) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    X_list: List[List[float]] = []
    y_list: List[str] = []
    if not BUFFER_PATH.exists():
        return np.zeros((0, len(FEATURE_COLUMNS))), np.array([]), []
    with open(BUFFER_PATH, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                feats = rec.get("features") or {}
                X_list.append([float(feats.get(c, 0.0) or 0.0) for c in FEATURE_COLUMNS])
                y_list.append(str(rec.get("label") or "Unknown"))
            except Exception:
                continue
            if len(X_list) >= max_rows:
                break
    if not X_list:
        return np.zeros((0, len(FEATURE_COLUMNS))), np.array([]), []
    return np.asarray(X_list, dtype=np.float32), np.asarray(y_list), sorted(set(y_list))


def maybe_incremental_train(force: bool = False) -> Dict[str, Any]:
    """
    Train / update SGDClassifier via partial_fit when buffer is large enough.
    Does not modify RandomForest / XGBoost / neural models.
    """
    stats = buffer_stats()
    if not force and stats["count"] < MIN_SAMPLES_TO_FIT:
        return {"trained": False, "reason": f"need>={MIN_SAMPLES_TO_FIT}", "buffer": stats["count"]}

    X, y, classes = _load_buffer()
    if len(X) < 10:
        return {"trained": False, "reason": "too_few_rows", "buffer": len(X)}

    # Ensure class set covers ATTACK_LABELS for stable partial_fit
    class_list = sorted(set(ATTACK_LABELS) | set(classes))

    from sklearn.linear_model import SGDClassifier
    from sklearn.preprocessing import StandardScaler

    with _lock:
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)

        if ONLINE_MODEL_PATH.exists():
            try:
                bundle = joblib.load(ONLINE_MODEL_PATH)
                clf = bundle.get("model")
                # Re-fit scaler each time for simplicity/stability on small buffers
            except Exception:
                clf = None
        else:
            clf = None

        if clf is None:
            clf = SGDClassifier(
                loss="log_loss",
                max_iter=25,
                tol=1e-3,
                random_state=42,
                class_weight="balanced",
            )

        try:
            clf.partial_fit(Xs, y, classes=np.array(class_list))
        except Exception as exc:
            # Fresh model if classes mismatch
            logger.warning("partial_fit retry with fresh model: %s", exc)
            clf = SGDClassifier(
                loss="log_loss",
                max_iter=25,
                tol=1e-3,
                random_state=42,
                class_weight="balanced",
            )
            clf.partial_fit(Xs, y, classes=np.array(class_list))

        # Quick accuracy on buffer (train-set estimate – informational only)
        try:
            acc = float(clf.score(Xs, y))
        except Exception:
            acc = 0.0

        bundle = {"model": clf, "scaler": scaler, "classes": class_list}
        _ensure_dirs()
        joblib.dump(bundle, ONLINE_MODEL_PATH)
        meta = {
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "samples": int(len(X)),
            "train_accuracy_est": round(acc, 4),
            "classes": class_list,
            "path": str(ONLINE_MODEL_PATH),
        }
        ONLINE_META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return {"trained": True, **meta}


def load_online_model() -> Optional[Dict[str, Any]]:
    """Load online SGD bundle if present."""
    if not ONLINE_MODEL_PATH.exists():
        return None
    try:
        return joblib.load(ONLINE_MODEL_PATH)
    except Exception as exc:
        logger.warning("load_online_model failed: %s", exc)
        return None


def predict_online(features: Dict[str, float]) -> Optional[Dict[str, Any]]:
    """Predict with online model; return None if unavailable."""
    bundle = load_online_model()
    if not bundle:
        return None
    clf = bundle.get("model")
    scaler = bundle.get("scaler")
    if clf is None:
        return None
    row = np.array([[float(features.get(c, 0.0) or 0.0) for c in FEATURE_COLUMNS]], dtype=np.float32)
    try:
        if scaler is not None:
            row = scaler.transform(row)
        pred = clf.predict(row)[0]
        conf = 50.0
        if hasattr(clf, "predict_proba"):
            proba = clf.predict_proba(row)[0]
            conf = float(np.max(proba)) * 100.0
        return {"label": str(pred), "confidence": conf, "raw_output": "online_sgd"}
    except Exception as exc:
        logger.debug("predict_online failed: %s", exc)
        return None


def get_online_status() -> Dict[str, Any]:
    """Dashboard-friendly status blob."""
    stats = buffer_stats()
    meta = {}
    if ONLINE_META_PATH.exists():
        try:
            meta = json.loads(ONLINE_META_PATH.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return {
        "buffer": stats,
        "model_exists": ONLINE_MODEL_PATH.exists(),
        "meta": meta,
        "min_samples": MIN_SAMPLES_TO_FIT,
    }
