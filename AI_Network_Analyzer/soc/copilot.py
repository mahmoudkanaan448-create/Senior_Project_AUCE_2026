"""
AI Security Copilot – offline investigation assistant.

Uses database + XAI + MITRE + playbooks. No external LLM required.
Supports natural-language hunting questions.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from database.database import SessionLocal
from database.orm import ensure_models

_m = ensure_models()
Alert, NetworkFlow, Asset, SocIncident, BlockedIP = (
    _m.Alert, _m.NetworkFlow, _m.Asset, _m.SocIncident, _m.BlockedIP
)
from threat_intelligence.mitre_map import map_attack_to_mitre, format_mitre_short
from detection.specialists import kill_chain_stage
from soar.playbooks import get_playbook


def summarize_incident(incident_id: int) -> str:
    from detection.correlation import list_incidents
    rows = [r for r in list_incidents(limit=200) if r["ID"] == incident_id]
    if not rows:
        return "Incident not found."
    r = rows[0]
    mitre = format_mitre_short(r["Title"].split(" ")[0])
    return (
        f"Incident #{r['ID']}: {r['Title']}\n"
        f"Severity: {r['Severity']} | Status: {r['Status']}\n"
        f"Source: {r['Source IP']}\n"
        f"Attack chain: {r['Attack Chain'] or 'n/a'}\n"
        f"Linked alerts: {r['Alerts']}\n"
        f"{mitre}\n"
        f"Summary: {r['Summary']}"
    )


def recommend_response(alert_type: str, severity: str, source_ip: str) -> Dict[str, Any]:
    pb = get_playbook(alert_type)
    mitre = map_attack_to_mitre(alert_type)
    action = "Investigate"
    if severity in ("Critical", "High") and alert_type in ("DDoS", "Ransomware", "Exfiltration", "C2"):
        action = "Block"
    elif severity == "Low":
        action = "Ignore"
    return {
        "action": action,
        "playbook": pb.get("name"),
        "steps": " → ".join(s["action"] for s in pb.get("steps", [])),
        "mitre": mitre.get("primary_technique"),
        "reason": f"{severity} {alert_type} from {source_ip}. Stage={kill_chain_stage(alert_type)}.",
    }


def explain_attack(alert_type: str, message: str = "") -> str:
    m = map_attack_to_mitre(alert_type)
    return (
        f"Detection: {alert_type}\n"
        f"Why: {m.get('summary')}\n"
        f"MITRE tactics: {', '.join(m.get('tactics') or [])}\n"
        f"Techniques: {', '.join(m.get('technique_ids') or [])}\n"
        f"Evidence: {message[:240]}\n"
        f"Suggested: {recommend_response(alert_type, 'High', '')['action']}"
    )


def explain_alert(alert_id: int) -> str:
    """Combine stored XAI + MITRE for a specific alert."""
    from database.models import Alert, Prediction
    from explainable_ai.xai import explanation_from_json

    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.alert_id == int(alert_id)).first()
        if not alert:
            return "Alert not found."
        pred = None
        if alert.prediction_id:
            pred = db.query(Prediction).filter(Prediction.prediction_id == alert.prediction_id).first()
        xai = explanation_from_json(getattr(pred, "explanation_json", None) if pred else None)
        mitre = explain_attack(alert.alert_type or "Unknown", alert.message or "")
        if not xai:
            return mitre
        local = xai.get("local_evidence") or []
        local_txt = "; ".join(
            f"{e.get('feature')}={e.get('value')}" for e in local[:5]
        )
        return (
            f"{xai.get('decision_explanation') or ''}\n"
            f"Recommended: {xai.get('recommended_action') or ''}\n"
            f"This-flow evidence: {local_txt or 'n/a'}\n"
            f"{mitre}"
        )
    finally:
        db.close()


def nl_query(question: str) -> Dict[str, Any]:
    """Very small NL hunter: IP / attack / status / top talkers."""
    q = (question or "").strip()
    ql = q.lower()
    db = SessionLocal()
    try:
        ip_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", q)
        if ip_match or "host" in ql or "ip" in ql:
            ip = ip_match.group(0) if ip_match else ""
            alerts = db.query(Alert).order_by(Alert.alert_id.desc()).limit(80).all()
            if ip:
                alerts = [a for a in alerts if ip in ((a.message or "") + (a.alert_type or ""))]
            return {
                "intent": "host_investigation",
                "answer": f"Found {len(alerts)} recent alerts" + (f" involving {ip}" if ip else "") + ".",
                "rows": [
                    {"ID": a.alert_id, "Type": a.alert_type, "Priority": a.priority, "Status": a.status, "Msg": (a.message or "")[:80]}
                    for a in alerts[:25]
                ],
            }
        if "critical" in ql or "high" in ql:
            alerts = db.query(Alert).filter(Alert.priority.in_(["High", "Critical"])).order_by(Alert.alert_id.desc()).limit(25).all()
            return {
                "intent": "priority",
                "answer": f"{len(alerts)} High/Critical alerts.",
                "rows": [{"ID": a.alert_id, "Type": a.alert_type, "Priority": a.priority} for a in alerts],
            }
        if "block" in ql:
            blocks = db.query(BlockedIP).filter(BlockedIP.status == "Active").all()
            return {"intent": "blocks", "answer": f"{len(blocks)} active blocks.", "rows": [{"IP": b.ip_address, "Reason": b.reason} for b in blocks]}
        if "asset" in ql or "device" in ql:
            assets = db.query(Asset).order_by(Asset.risk_score.desc()).limit(20).all()
            return {"intent": "assets", "answer": "Top risky assets.", "rows": [{"IP": a.ip_address, "Type": a.device_type, "Risk": a.risk_score} for a in assets]}
        if "incident" in ql:
            incs = db.query(SocIncident).order_by(SocIncident.incident_id.desc()).limit(15).all()
            return {"intent": "incidents", "answer": f"{len(incs)} recent incidents.", "rows": [{"ID": i.incident_id, "Title": i.title, "Status": i.status} for i in incs]}
        flows = db.query(NetworkFlow).order_by(NetworkFlow.flow_id.desc()).limit(15).all()
        return {
            "intent": "overview",
            "answer": "Showing latest flows. Try: 'show suspicious hosts', 'critical alerts', 'assets', 'blocks'.",
            "rows": [{"src": f.source_ip, "dst": f.destination_ip, "port": f.destination_port} for f in flows],
        }
    finally:
        db.close()
