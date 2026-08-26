"""Distributed sensor registry – agents POST flows to /api/v1/sensors/ingest."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any, Dict, List

from database.database import SessionLocal
from database.orm import ensure_models

_m = ensure_models()
Sensor = _m.Sensor


def register_sensor(name: str, site: str = "hq", interfaces: str = "") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        key = secrets.token_hex(16)
        row = Sensor(name=name, site=site, interfaces=interfaces, api_key=key, status="Online")
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"sensor_id": row.sensor_id, "api_key": key, "name": name, "site": site}
    finally:
        db.close()


def heartbeat(api_key: str, packets_sec: float = 0.0, dropped: int = 0, interfaces: str = "") -> bool:
    db = SessionLocal()
    try:
        row = db.query(Sensor).filter(Sensor.api_key == api_key).first()
        if not row:
            return False
        row.last_seen = datetime.utcnow()
        row.status = "Online"
        row.packets_sec = packets_sec
        row.dropped_packets = dropped
        if interfaces:
            row.interfaces = interfaces
        db.commit()
        return True
    finally:
        db.close()


def list_sensors() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        ensure_local(db)
        rows = db.query(Sensor).order_by(Sensor.sensor_id.asc()).all()
        return [
            {
                "ID": r.sensor_id,
                "Name": r.name,
                "Site": r.site,
                "Interfaces": r.interfaces or "",
                "Status": r.status,
                "pkt/s": r.packets_sec,
                "Dropped": r.dropped_packets,
                "Last Seen": str(r.last_seen),
            }
            for r in rows
        ]
    finally:
        db.close()


def ensure_local(db=None) -> None:
    close = False
    if db is None:
        db = SessionLocal()
        close = True
    try:
        if db.query(Sensor).filter(Sensor.name == "local-gateway").first():
            return
        db.add(Sensor(name="local-gateway", site="lab", interfaces="auto", status="Online", api_key="local"))
        db.commit()
    finally:
        if close:
            db.close()
