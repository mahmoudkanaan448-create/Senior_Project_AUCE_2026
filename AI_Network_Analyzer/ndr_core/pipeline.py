"""
Post-detection NDR pipeline – runs after Hybrid AI / process_alert.

Adds specialists, baselines, assets, IOC match, correlation, webhooks,
PCAP evidence, XAI snippet. Never sends email.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def enrich_and_respond(
    *,
    flow: Dict[str, Any],
    prediction: Dict[str, Any],
    alert_id: Optional[int] = None,
    recent_flows: Optional[List[Dict[str, Any]]] = None,
    packets: Optional[list] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "specialists": [],
        "baseline": {},
        "ioc_hits": [],
        "incident": {},
        "webhooks": 0,
        "pcap": None,
        "xai": {},
        "duplicate": False,
    }
    src = str(flow.get("source_ip") or "")
    dst = str(flow.get("destination_ip") or "")
    dport = int(flow.get("destination_port") or 0)
    label = str(prediction.get("prediction_label") or prediction.get("attack_type") or "Unknown")
    severity = str(prediction.get("severity") or "Medium")
    message = str(prediction.get("recommendation") or "")

    try:
        from assets.inventory import upsert_from_flow, recompute_risk
        upsert_from_flow(src, dst, dport)
        recompute_risk(src)
        recompute_risk(dst)
    except Exception as exc:
        out["asset_error"] = str(exc)

    try:
        from detection.baselines import update_baseline
        out["baseline"] = update_baseline(
            src,
            float(flow.get("packet_rate") or 0),
            float(flow.get("flow_rate") or 0),
            dport,
        )
        if out["baseline"].get("drifted") and label.lower() == "normal":
            label = "Unknown"
            severity = "Medium"
            out["specialists"].append({
                "type": "ConceptDrift",
                "severity": "Medium",
                "reason": f"Host {src} drifted from baseline",
                "score": 6.0,
            })
    except Exception:
        pass

    try:
        from detection.specialists import detect_specialists
        extra = detect_specialists({**flow, **prediction}, recent_flows)
        out["specialists"] = extra
        if extra:
            top = max(extra, key=lambda x: x.get("score", 0))
            if label.lower() in ("normal", "unknown", "attack"):
                label = top["type"]
                severity = top["severity"]
    except Exception:
        pass

    try:
        from threat_intelligence.ioc_manager import match_flow
        hits = match_flow(src, dst, domain=str(flow.get("dns_query") or flow.get("tls_sni") or ""))
        out["ioc_hits"] = hits
        if hits and severity not in ("Critical",):
            severity = "High"
        ip_hits = [h for h in hits if h.get("type") == "ip"]
        if ip_hits and src:
            from response.policy import queue_or_block
            out["blacklist_block"] = queue_or_block(
                src, reason=f"IOC blacklist hit {ip_hits[0].get('value')}", duration="24h"
            )
            severity = "Critical"
    except Exception:
        pass

    try:
        from detection.correlation import is_duplicate, correlate_alert
        if alert_id and is_duplicate(label, src):
            out["duplicate"] = True
        if alert_id:
            out["incident"] = correlate_alert(
                alert_id=alert_id,
                alert_type=label,
                severity=severity,
                source_ip=src,
                message=message,
            )
    except Exception:
        pass

    try:
        from explainable_ai.xai import explain_features_only, explanation_from_json
        existing = prediction.get("xai") or explanation_from_json(prediction.get("explanation_json"))
        if existing:
            out["xai"] = existing
        else:
            feats = flow.get("features") if isinstance(flow.get("features"), dict) else {}
            out["xai"] = explain_features_only(
                feats,
                label,
                confidence_score=float(prediction.get("confidence") or 0),
                threat_score=float(prediction.get("threat_score") or 0),
            )
    except Exception:
        pass

    if severity in ("High", "Critical") and packets:
        try:
            from monitoring.pcap_store import save_packet_dicts
            out["pcap"] = save_packet_dicts(packets, source_ip=src, alert_id=alert_id)
        except Exception:
            pass

    try:
        from alerts.webhooks import fire_webhooks
        out["webhooks"] = fire_webhooks(
            "alert",
            {"label": label, "severity": severity, "source_ip": src, "destination_ip": dst, "alert_id": alert_id},
        )
    except Exception:
        pass

    try:
        from ops.siem import emit_event
        emit_event("alert", {"label": label, "severity": severity, "source_ip": src, "alert_id": alert_id})
    except Exception:
        pass

    out["final_label"] = label
    out["final_severity"] = severity
    return out
