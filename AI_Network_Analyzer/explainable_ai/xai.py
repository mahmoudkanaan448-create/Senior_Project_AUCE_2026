"""
Explainable AI (XAI) – surfaces why a model flagged traffic.

Extracts top feature importances (Gini for trees, permutation otherwise),
builds a short natural-language explanation, and maps attack labels to
recommended response actions.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import FEATURE_COLUMNS

_TREE_MODELS = {"random_forest", "xgboost"}

_ACTION_MAP: Dict[str, str] = {
    "Normal": "No action required – traffic appears benign.",
    "DoS": "Rate-limit the source IP and alert the SOC team.",
    "DDoS": "Activate DDoS mitigation; consider upstream scrubbing.",
    "PortScan": "Block the source IP and review firewall rules.",
    "BruteForce": "Lock the targeted account and enforce MFA.",
    "SQLInjection": "Isolate the web server and inspect application logs.",
    "WebAttack": "Enable WAF rules and inspect HTTP payloads.",
    "Botnet": "Quarantine the infected host and scan for C2 indicators.",
    "Infiltration": "Isolate the affected segment and begin forensic analysis.",
    "Malware": "Quarantine the host, run AV scan, and alert the SOC.",
    "Ransomware": "Disconnect the host immediately and activate incident response.",
    "Exfiltration": "Block outbound channel and inspect destination reputation.",
    "LateralMovement": "Isolate the source host and review east-west admin protocols.",
    "C2": "Sinkhole/block the C2 destination and capture PCAP evidence.",
    "PrivilegeEscalation": "Review privileged internal sessions and reset credentials.",
    "ConceptDrift": "Compare host baseline and confirm whether the change is legitimate.",
    "Insider": "Review the trusted host/user profile and unusual outbound destinations.",
}


def _tree_feature_importances(
    model: Any,
    feature_names: List[str],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Extract feature importances from tree-based models."""
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1][:top_n]
    return [
        {"feature": feature_names[i], "importance": round(float(importances[i]), 6)}
        for i in indices
    ]


def _permutation_feature_importances(
    model: Any,
    features: Dict[str, float],
    feature_names: List[str],
    model_name: str,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Single-sample permutation importance (zero-out each feature)."""
    row = np.array([[features.get(col, 0.0) for col in feature_names]], dtype=np.float32)

    try:
        if model_name == "autoencoder":
            base_output = model.predict(row, verbose=0)
            base_score = float(np.mean((row - base_output) ** 2))
        elif model_name == "lstm":
            row_3d = row.reshape((1, 1, row.shape[1]))
            pred = model.predict(row_3d, verbose=0)
            base_score = float(np.max(pred))
        elif model_name == "isolation_forest":
            base_score = float(model.decision_function(row)[0])
        else:
            base_score = float(np.max(model.predict_proba(row)))
    except Exception:
        return [{"feature": feature_names[i], "importance": 0.0} for i in range(min(top_n, len(feature_names)))]

    deltas: List[Tuple[str, float]] = []
    for idx, col in enumerate(feature_names):
        perturbed = row.copy()
        perturbed[0, idx] = 0.0
        try:
            if model_name == "autoencoder":
                out = model.predict(perturbed, verbose=0)
                score = float(np.mean((perturbed - out) ** 2))
            elif model_name == "lstm":
                p3d = perturbed.reshape((1, 1, perturbed.shape[1]))
                score = float(np.max(model.predict(p3d, verbose=0)))
            elif model_name == "isolation_forest":
                score = float(model.decision_function(perturbed)[0])
            else:
                score = float(np.max(model.predict_proba(perturbed)))
        except Exception:
            score = base_score
        deltas.append((col, abs(base_score - score)))

    deltas.sort(key=lambda x: x[1], reverse=True)
    return [
        {"feature": name, "importance": round(delta, 6)}
        for name, delta in deltas[:top_n]
    ]


def explain_prediction(
    model: Any,
    features: Dict[str, float],
    prediction: str,
    model_name: str,
    *,
    confidence_score: float = 0.0,
    threat_score: float = 0.0,
    top_n: int = 10,
) -> Dict[str, Any]:
    """Explain a prediction with top features, text, and recommended action."""
    feature_names = FEATURE_COLUMNS

    try:
        if model_name in _TREE_MODELS:
            important_features = _tree_feature_importances(model, feature_names, top_n)
        else:
            important_features = _permutation_feature_importances(
                model, features, feature_names, model_name, top_n
            )
    except Exception:
        important_features = []

    explanation = generate_explanation_text(prediction, confidence_score, important_features)
    action = _ACTION_MAP.get(prediction, "Investigate the traffic and consult the SOC team.")

    return {
        "important_features": important_features,
        "confidence_score": round(confidence_score, 2),
        "threat_score": round(threat_score, 2),
        "decision_explanation": explanation,
        "recommended_action": action,
    }


def generate_explanation_text(
    prediction_label: str,
    confidence: float,
    top_features: List[Dict[str, Any]],
) -> str:
    """Produce a short human-readable explanation string."""
    if prediction_label == "Normal":
        text = (
            f"The traffic is classified as NORMAL with {confidence:.1f}% confidence. "
            "No malicious indicators were detected."
        )
    else:
        text = (
            f"The traffic is classified as {prediction_label.upper()} "
            f"with {confidence:.1f}% confidence. "
        )

    if top_features:
        names = ", ".join(f["feature"] for f in top_features[:5])
        text += f"Key contributing features: {names}."

    return text


# Typical benign ranges used for local (this-flow) evidence.
_NORMAL_RANGES: Dict[str, Tuple[float, float]] = {
    "packet_rate": (0.2, 40.0),
    "flow_rate": (50.0, 2.0e4),
    "syn_count": (0.0, 6.0),
    "serror_rate": (0.0, 0.12),
    "dst_host_serror_rate": (0.0, 0.15),
    "rst_count": (0.0, 8.0),
    "fin_count": (0.0, 8.0),
    "diff_srv_rate": (0.0, 0.35),
    "packet_count": (1.0, 400.0),
    "byte_count": (40.0, 8.0e4),
}

_SIGNATURE_HINTS: Dict[str, List[str]] = {
    "DoS": ["packet_rate", "syn_count", "serror_rate", "packet_count"],
    "DDoS": ["packet_rate", "flow_rate", "syn_count", "dst_host_count"],
    "PortScan": ["syn_count", "rst_count", "diff_srv_rate", "same_srv_rate"],
    "BruteForce": ["count", "same_srv_rate", "duration", "ack_count"],
    "SQLInjection": ["psh_count", "fwd_bytes", "same_srv_rate", "byte_count"],
    "WebAttack": ["psh_count", "fwd_bytes", "ack_count", "same_srv_rate"],
    "Botnet": ["idle_time", "inter_arrival_time", "packet_rate", "duration"],
    "Malware": ["psh_count", "serror_rate", "fwd_packets", "byte_count"],
    "C2": ["idle_time", "inter_arrival_time", "dst_bytes"],
    "Exfiltration": ["flow_rate", "bwd_bytes", "byte_count", "duration"],
    "Ransomware": ["flow_rate", "packet_count", "psh_count"],
    "Infiltration": ["duration", "fwd_bytes", "dst_host_count"],
    "LateralMovement": ["same_srv_rate", "dst_host_srv_count", "psh_count"],
}


def local_flow_evidence(
    features: Dict[str, float],
    prediction: str,
    *,
    top_n: int = 6,
) -> List[Dict[str, Any]]:
    """Explain THIS flow: values outside benign ranges, plus class signature hits."""
    evidence: List[Dict[str, Any]] = []
    for name, (lo, hi) in _NORMAL_RANGES.items():
        try:
            value = float(features.get(name, 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if value < lo or value > hi:
            evidence.append({
                "feature": name,
                "value": round(value, 4),
                "expected_normal": f"{lo:g}–{hi:g}",
                "why": "outside typical benign range",
            })
    sig = _SIGNATURE_HINTS.get(prediction, [])
    for name in sig:
        if any(e["feature"] == name for e in evidence):
            continue
        try:
            value = float(features.get(name, 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if value == 0.0:
            continue
        evidence.append({
            "feature": name,
            "value": round(value, 4),
            "expected_normal": "class signature",
            "why": f"matches {prediction} traffic pattern",
        })
    evidence.sort(key=lambda e: abs(float(e.get("value") or 0)), reverse=True)
    return evidence[:top_n]


def explain_features_only(
    features: Dict[str, float],
    prediction: str,
    *,
    confidence_score: float = 0.0,
    threat_score: float = 0.0,
    top_n: int = 8,
) -> Dict[str, Any]:
    """Fast explanation without loading a model (local evidence + action)."""
    local = local_flow_evidence(features or {}, prediction, top_n=top_n)
    important = [
        {"feature": e["feature"], "importance": round(abs(float(e["value"])), 6)}
        for e in local
    ]
    explanation = generate_explanation_text(prediction, confidence_score, important)
    if local:
        bits = [f"{e['feature']}={e['value']} ({e['why']})" for e in local[:4]]
        explanation += " This flow: " + "; ".join(bits) + "."
    action = _ACTION_MAP.get(prediction, "Investigate the traffic and consult the SOC team.")
    return {
        "important_features": important,
        "local_evidence": local,
        "confidence_score": round(float(confidence_score or 0), 2),
        "threat_score": round(float(threat_score or 0), 2),
        "decision_explanation": explanation,
        "recommended_action": action,
        "prediction_label": prediction,
    }


def explain_with_models(
    features: Dict[str, float],
    prediction: str,
    models: Optional[Dict[str, Any]] = None,
    *,
    model_name: str = "",
    confidence_score: float = 0.0,
    threat_score: float = 0.0,
) -> Dict[str, Any]:
    """Combine local flow evidence with tree importances when a model is loaded."""
    base = explain_features_only(
        features,
        prediction,
        confidence_score=confidence_score,
        threat_score=threat_score,
    )
    model = None
    chosen = model_name
    if models:
        for name in (model_name, "random_forest", "xgboost"):
            if name and models.get(name) is not None:
                model = models[name]
                chosen = name
                break
    if model is not None and chosen in _TREE_MODELS:
        try:
            tree_imp = _tree_feature_importances(model, FEATURE_COLUMNS, top_n=8)
            if tree_imp:
                base["important_features"] = tree_imp
                base["model_used"] = chosen
        except Exception:
            pass
    elif model is not None and chosen:
        try:
            perm = _permutation_feature_importances(
                model, features or {}, FEATURE_COLUMNS, chosen, top_n=6
            )
            if perm:
                base["important_features"] = perm
                base["model_used"] = chosen
        except Exception:
            pass
    return base


def explanation_to_json(payload: Dict[str, Any]) -> str:
    import json
    return json.dumps(payload, default=str)


def explanation_from_json(raw: Optional[str]) -> Dict[str, Any]:
    import json
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
