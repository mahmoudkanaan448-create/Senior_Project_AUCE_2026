"""
Composite risk-score calculation combining AI predictions with threat intel.

Produces a unified 0–10 score from AI confidence, attack category,
blacklist status, abuse report count, and intel threat score.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, Optional

_HIGH_RISK_ATTACKS = {"DDoS", "DoS", "Ransomware", "Malware", "Botnet", "Infiltration"}
_MEDIUM_RISK_ATTACKS = {"BruteForce", "PortScan", "SQLInjection", "WebAttack"}


def calculate_risk_score(
    ai_confidence: float,
    ai_prediction: str,
    threat_intel: Optional[Dict[str, Any]] = None,
) -> float:
    """Produce a unified 0–10 risk score from AI output and threat intel."""
    threat_intel = threat_intel or {}

    if ai_prediction == "Normal":
        base = max(0.0, (100.0 - ai_confidence) / 100.0 * 2.0)
    else:
        base = (ai_confidence / 100.0) * 4.0

    if ai_prediction in _HIGH_RISK_ATTACKS:
        attack_bonus = 2.0
    elif ai_prediction in _MEDIUM_RISK_ATTACKS:
        attack_bonus = 1.0
    else:
        attack_bonus = 0.0

    blacklist_bonus = 1.5 if threat_intel.get("blacklisted") else 0.0

    reports = threat_intel.get("reports", 0)
    report_bonus = min(reports / 100.0, 1.5)

    intel_score = threat_intel.get("threat_score", 0.0)
    intel_bonus = min(intel_score / 10.0, 1.0)

    total = base + attack_bonus + blacklist_bonus + report_bonus + intel_bonus
    return round(min(max(total, 0.0), 10.0), 2)
