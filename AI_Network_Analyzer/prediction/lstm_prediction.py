"""
Future attack prediction using a pre-trained LSTM model.

Feeds a sliding window of recent flows into the LSTM and returns
attack probability, risk level, traffic trend, and confidence.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, List, Optional

import numpy as np

from config import FEATURE_COLUMNS


def _flows_to_sequence(
    recent_flows: List[Dict[str, float]],
    scaler: Any = None,
) -> np.ndarray:
    """Convert flow dicts into a 3-D array (1, timesteps, features)."""
    rows = []
    for flow in recent_flows:
        row = [flow.get(col, 0.0) for col in FEATURE_COLUMNS]
        rows.append(row)
    arr = np.array(rows, dtype=np.float32)
    if scaler is not None:
        arr = scaler.transform(arr)
    return arr.reshape(1, arr.shape[0], arr.shape[1])


def predict_future(
    recent_flows: List[Dict[str, float]],
    lstm_model: Any,
    scaler: Any = None,
    *,
    window: int = 10,
) -> Dict[str, Any]:
    """Predict future attack risk from the most recent network flows."""
    if not recent_flows:
        return {
            "future_risk_level": "Unknown",
            "attack_probability": 0.0,
            "predicted_trend": "insufficient_data",
            "confidence": 0.0,
            "flows_analysed": 0,
        }

    flows = recent_flows[-window:]

    try:
        sequence = _flows_to_sequence(flows, scaler)
        prediction = lstm_model.predict(sequence, verbose=0)

        if prediction.shape[-1] > 1:
            attack_prob = float(1.0 - prediction[0][0])  # index-0 assumed Normal
            confidence = float(np.max(prediction)) * 100
        else:
            attack_prob = float(prediction[0][0])
            confidence = abs(attack_prob - 0.5) * 200

        # Byte-count trend over the window (increasing / decreasing / stable)
        if len(flows) >= 3:
            early = flows[: len(flows) // 2]
            late = flows[len(flows) // 2 :]
            early_avg = np.mean([f.get("byte_count", 0) for f in early])
            late_avg = np.mean([f.get("byte_count", 0) for f in late])
            if late_avg > early_avg * 1.3:
                trend = "increasing"
            elif late_avg < early_avg * 0.7:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        if attack_prob > 0.8:
            risk = "Critical"
        elif attack_prob > 0.6:
            risk = "High"
        elif attack_prob > 0.4:
            risk = "Medium"
        elif attack_prob > 0.2:
            risk = "Low"
        else:
            risk = "Minimal"

        return {
            "future_risk_level": risk,
            "attack_probability": round(attack_prob, 4),
            "predicted_trend": trend,
            "confidence": round(confidence, 2),
            "flows_analysed": len(flows),
        }

    except Exception as exc:
        return {
            "future_risk_level": "Error",
            "attack_probability": 0.0,
            "predicted_trend": "error",
            "confidence": 0.0,
            "flows_analysed": len(flows),
            "error": str(exc),
        }
