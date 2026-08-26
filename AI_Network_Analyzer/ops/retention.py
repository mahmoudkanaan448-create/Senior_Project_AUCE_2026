"""Data retention + capture health metrics."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from database.database import SessionLocal
from database.models import NetworkFlow, SystemLog, Alert
from database.queries import get_setting, set_setting


def retention_days() -> int:
    db = SessionLocal()
    try:
        raw = get_setting(db, "retention_days") or "30"
        return max(1, int(raw))
    except Exception:
        return 30
    finally:
        db.close()


def purge_old() -> Dict[str, int]:
    days = retention_days()
    cutoff = datetime.utcnow() - timedelta(days=days)
    db = SessionLocal()
    deleted = {"flows": 0, "logs": 0}
    try:
        qf = db.query(NetworkFlow).filter(NetworkFlow.timestamp < cutoff)
        deleted["flows"] = qf.count()
        qf.delete(synchronize_session=False)
        ql = db.query(SystemLog).filter(SystemLog.timestamp < cutoff)
        deleted["logs"] = ql.count()
        ql.delete(synchronize_session=False)
        db.commit()
        return deleted
    finally:
        db.close()


def capture_health() -> Dict[str, Any]:
    from monitoring.sensors import list_sensors
    sensors = list_sensors()
    dropped = sum(int(s.get("Dropped") or 0) for s in sensors)
    pps = sum(float(s.get("pkt/s") or 0) for s in sensors)
    db = SessionLocal()
    try:
        flows = db.query(NetworkFlow).count()
        alerts = db.query(Alert).count()
    finally:
        db.close()
    return {
        "sensors": len(sensors),
        "packets_sec": pps,
        "dropped_packets": dropped,
        "flows_stored": flows,
        "alerts_stored": alerts,
        "retention_days": retention_days(),
    }
