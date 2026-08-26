"""
Confidence and threat-score calculation utilities.

Aggregates per-model confidences with a weighted average, and builds a
0–10 composite threat score from AI confidence, anomaly flags, threat
intel, and attack-type severity.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, Optional

_HIGH_RISK_ATTACKS = {"DDoS", "DoS", "Ransomware", "Malware", "Botnet"}


def compute_confidence(model_predictions: Dict[str, Dict[str, Any]]) -> float:
    """Weighted average of per-model confidences (0–100)."""
    weights: Dict[str, float] = {
        "random_forest": 1.5,
        "xgboost": 1.5,
        "isolation_forest": 1.0,
        "autoencoder": 0.8,
        "lstm": 1.2,
    }

    total_weight = 0.0
    weighted_sum = 0.0

    for model_name, pred in model_predictions.items():
        conf = pred.get("confidence", 0.0)
        w = weights.get(model_name, 1.0)
        weighted_sum += conf * w
        total_weight += w

    if total_weight == 0.0:
        return 0.0
    return round(min(weighted_sum / total_weight, 100.0), 2)


def compute_threat_score(
    confidence: float,
    is_anomaly: bool,
    threat_intel_score: float = 0.0,
    attack_type: Optional[str] = None,
) -> float:
    """Composite 0–10 threat score from confidence, anomaly, intel, and attack type."""
    base = (confidence / 100.0) * 5.0
    anomaly_bonus = 1.5 if is_anomaly else 0.0
    intel_bonus = min(threat_intel_score * 0.2, 2.0)

    attack_bonus = 0.0
    if attack_type and attack_type in _HIGH_RISK_ATTACKS:
        attack_bonus = 1.5

    score = base + anomaly_bonus + intel_bonus + attack_bonus
    return round(min(max(score, 0.0), 10.0), 2)
