"""Alert dedup, incident correlation, and attack-chain assembly."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database.database import SessionLocal
from database.orm import ensure_models
from detection.specialists import kill_chain_stage

_m = ensure_models()
Alert, SocIncident = _m.Alert, _m.SocIncident


def fingerprint(alert_type: str, source_ip: str, message: str = "") -> str:
    msg = (message or "")[:40]
    return f"{alert_type}|{source_ip}|{msg}"


def is_duplicate(alert_type: str, source_ip: str, window_minutes: int = 5) -> bool:
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(minutes=window_minutes)
        q = (
            db.query(Alert)
            .filter(Alert.alert_type == alert_type)
            .filter(Alert.created_at >= since)
            .order_by(Alert.created_at.desc())
            .limit(20)
            .all()
        )
        for a in q:
            if source_ip and source_ip in (a.message or ""):
                return True
        return False
    finally:
        db.close()


def correlate_alert(
    *,
    alert_id: int,
    alert_type: str,
    severity: str,
    source_ip: str,
    message: str = "",
) -> Dict[str, Any]:
    """Attach alert to an open incident for the same source IP or create one."""
    stage = kill_chain_stage(alert_type)
    db = SessionLocal()
    try:
        open_inc = None
        if source_ip:
            open_inc = (
                db.query(SocIncident)
                .filter(SocIncident.source_ip == source_ip)
                .filter(SocIncident.status.in_(["Open", "In Progress"]))
                .order_by(SocIncident.incident_id.desc())
                .first()
            )
        if open_inc:
            ids = [x for x in (open_inc.alert_ids or "").split(",") if x]
            if str(alert_id) not in ids:
                ids.append(str(alert_id))
            open_inc.alert_ids = ",".join(ids)
            chain = [x for x in (open_inc.attack_chain or "").split(" → ") if x]
            if stage not in chain:
                chain.append(stage)
            open_inc.attack_chain = " → ".join(chain)
            rank = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
            if rank.get(severity, 0) > rank.get(open_inc.severity or "Low", 0):
                open_inc.severity = severity
            open_inc.updated_at = datetime.utcnow()
            db.commit()
            return {
                "incident_id": open_inc.incident_id,
                "title": open_inc.title,
                "chain": open_inc.attack_chain,
                "alerts": len(ids),
                "created": False,
            }

        title = f"{alert_type} from {source_ip or 'unknown'}"
        inc = SocIncident(
            title=title,
            severity=severity,
            status="Open",
            source_ip=source_ip,
            attack_chain=stage,
            alert_ids=str(alert_id),
            summary=message[:400] if message else title,
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)
        return {
            "incident_id": inc.incident_id,
            "title": inc.title,
            "chain": inc.attack_chain,
            "alerts": 1,
            "created": True,
        }
    finally:
        db.close()


def list_incidents(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        q = db.query(SocIncident)
        if status and status != "All":
            q = q.filter(SocIncident.status == status)
        rows = q.order_by(SocIncident.incident_id.desc()).limit(limit).all()
        return [
            {
                "ID": r.incident_id,
                "Title": r.title,
                "Severity": r.severity,
                "Status": r.status,
                "Owner": r.owner or "",
                "Source IP": r.source_ip or "",
                "Attack Chain": r.attack_chain or "",
                "Alerts": len([x for x in (r.alert_ids or "").split(",") if x]),
                "Summary": (r.summary or "")[:120],
                "Updated": str(r.updated_at),
            }
            for r in rows
        ]
    finally:
        db.close()


def set_incident_status(incident_id: int, status: str, owner: str = "", notes: str = "") -> bool:
    db = SessionLocal()
    try:
        row = db.query(SocIncident).filter(SocIncident.incident_id == incident_id).first()
        if not row:
            return False
        row.status = status
        if owner:
            row.owner = owner
        if notes:
            row.notes = ((row.notes or "") + "\n" + notes).strip()
        row.updated_at = datetime.utcnow()
        db.commit()
        return True
    finally:
        db.close()
