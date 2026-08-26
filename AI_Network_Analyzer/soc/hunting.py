"""Threat hunting / historical search across flows, alerts, assets."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from database.database import SessionLocal
from database.models import NetworkFlow, Alert, Prediction


def hunt(
    ip: str = "",
    attack: str = "",
    protocol: str = "",
    limit: int = 200,
) -> Dict[str, List[Dict[str, Any]]]:
    db = SessionLocal()
    try:
        fq = db.query(NetworkFlow)
        if ip:
            fq = fq.filter((NetworkFlow.source_ip == ip) | (NetworkFlow.destination_ip == ip))
        if protocol:
            fq = fq.filter(NetworkFlow.protocol == protocol)
        flows = fq.order_by(NetworkFlow.flow_id.desc()).limit(limit).all()

        aq = db.query(Alert)
        if attack:
            aq = aq.filter(Alert.alert_type.contains(attack))
        if ip:
            aq = aq.filter(Alert.message.contains(ip))
        alerts = aq.order_by(Alert.alert_id.desc()).limit(limit).all()

        pq = db.query(Prediction)
        if attack:
            pq = pq.filter(Prediction.prediction_label.contains(attack))
        preds = pq.order_by(Prediction.prediction_id.desc()).limit(limit).all()

        return {
            "flows": [
                {
                    "id": f.flow_id,
                    "src": f.source_ip,
                    "dst": f.destination_ip,
                    "sport": f.source_port,
                    "dport": f.destination_port,
                    "proto": f.protocol,
                    "bytes": f.bytes_total,
                    "pkts": f.packets,
                    "time": str(f.timestamp),
                }
                for f in flows
            ],
            "alerts": [
                {"id": a.alert_id, "type": a.alert_type, "priority": a.priority, "status": a.status, "msg": (a.message or "")[:120], "time": str(a.created_at)}
                for a in alerts
            ],
            "predictions": [
                {"id": p.prediction_id, "label": p.prediction_label, "severity": p.severity, "score": p.threat_score, "time": str(p.prediction_time)}
                for p in preds
            ],
        }
    finally:
        db.close()
