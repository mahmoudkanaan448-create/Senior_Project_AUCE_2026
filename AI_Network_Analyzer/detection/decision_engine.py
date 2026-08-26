"""
Decision engine – fuses per-model predictions into one verdict.

Uses majority voting across models to produce final_label, confidence,
threat_score, and severity for the dashboard and alert pipeline.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, List


def _severity_from_threat_score(score: float) -> str:
    """Map a 0-10 threat score to Low/Medium/High/Critical."""
    if score < 4.0:
        return "Low"
    if score < 6.0:
        return "Medium"
    if score < 8.0:
        return "High"
    return "Critical"


def fuse_decisions(predictions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Combine model predictions via majority vote into a single decision."""
    if not predictions:
        return {
            "final_label": "Unknown",
            "confidence": 0.0,
            "threat_score": 0.0,
            "severity": "Low",
            "models_agreed": 0,
            "model_votes": {},
            "total_models": 0,
        }

    attack_votes: List[Dict[str, Any]] = []
    normal_votes: List[Dict[str, Any]] = []
    model_votes: Dict[str, str] = {}

    for model_name, pred in predictions.items():
        label = pred.get("label", "Unknown")
        conf = pred.get("confidence", 0.0)
        model_votes[model_name] = label

        if label.lower() == "normal":
            normal_votes.append({"model": model_name, "label": label, "confidence": conf})
        elif label.lower() != "error":
            attack_votes.append({"model": model_name, "label": label, "confidence": conf})

    total_models = len(attack_votes) + len(normal_votes)

    avg_confidence = (
        sum(p.get("confidence", 0.0) for p in predictions.values()) / len(predictions)
    )

    is_attack = len(attack_votes) > len(normal_votes)

    if is_attack:
        best = max(attack_votes, key=lambda v: v["confidence"])
        final_label = best["label"]
        confidence = best["confidence"]
        models_agreed = len(attack_votes)
        agreement_ratio = models_agreed / total_models if total_models else 0
        threat_score = min(confidence / 10.0 * agreement_ratio * 1.5, 10.0)
    else:
        final_label = "Normal"
        confidence = avg_confidence
        models_agreed = len(normal_votes)
        threat_score = max(0.0, (100.0 - confidence) / 20.0)

    severity = _severity_from_threat_score(threat_score)

    best_model = "Hybrid"
    if is_attack and attack_votes:
        best_model = best.get("model", "Hybrid")
    elif normal_votes:
        best_model = max(normal_votes, key=lambda v: v["confidence"]).get("model", "Hybrid")

    recommendation = (
        "Investigate and contain the source host."
        if is_attack
        else "Traffic appears normal; continue monitoring."
    )

    mitre = {}
    try:
        from threat_intelligence.mitre_map import map_attack_to_mitre
        mitre = map_attack_to_mitre(final_label)
        if is_attack and mitre.get("summary"):
            recommendation = f"{recommendation} MITRE: {mitre.get('primary_technique')} ({mitre.get('primary_technique_name')})."
    except Exception:
        mitre = {}

    return {
        "final_label": final_label,
        "confidence": round(confidence, 2),
        "threat_score": round(threat_score, 2),
        "severity": severity,
        "models_agreed": models_agreed,
        "model_votes": model_votes,
        "total_models": total_models,
        "best_model": best_model,
        "ensemble_method": "weighted_majority",
        "recommendation": recommendation,
        "mitre": mitre,
    }
