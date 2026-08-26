"""Asset discovery, device classification, risk scoring, topology helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from database.database import SessionLocal
from database.orm import ensure_models
from monitoring.dpi import WELL_KNOWN

_m = ensure_models()
Asset, Alert, NetworkFlow = _m.Asset, _m.Alert, _m.NetworkFlow


def _classify(ports: List[int], ip: str) -> str:
    s = set(ports)
    if s & {80, 443, 8080, 8443} and s & {22, 3389}:
        return "Server"
    if s & {80, 443, 8080, 3306, 5432, 1433}:
        return "Server"
    if s & {22, 3389, 445}:
        return "Workstation"
    if s & {5060, 5061}:
        return "IoT"
    if ip.startswith(("8.", "9.", "1.", "2.", "3.")):
        return "External"
    return "Host"


def upsert_from_flow(source_ip: str, dest_ip: str, dest_port: int = 0) -> None:
    for ip, inbound_port in ((source_ip, 0), (dest_ip, dest_port)):
        if not ip or ip in ("unknown", "0.0.0.0"):
            continue
        db = SessionLocal()
        try:
            row = db.query(Asset).filter(Asset.ip_address == ip).first()
            now = datetime.utcnow()
            if row is None:
                dtype = _classify([inbound_port], ip)
                crit = "Critical" if dtype == "Server" else "Normal"
                row = Asset(
                    ip_address=ip,
                    device_type=dtype,
                    criticality=crit,
                    first_seen=now,
                    last_seen=now,
                )
                db.add(row)
            else:
                row.last_seen = now
                if inbound_port and row.device_type in ("Unknown", "Host"):
                    row.device_type = _classify([inbound_port], ip)
            db.commit()
        finally:
            db.close()


def recompute_risk(ip: str) -> float:
    db = SessionLocal()
    try:
        alerts = db.query(Alert).filter(Alert.message.contains(ip)).limit(50).all()
        score = 0.0
        for a in alerts:
            score += {"Critical": 25, "High": 15, "Medium": 8, "Low": 3}.get(a.priority or "", 5)
        score = min(100.0, score)
        row = db.query(Asset).filter(Asset.ip_address == ip).first()
        if row:
            if row.criticality == "Critical":
                score = min(100.0, score * 1.25)
            row.risk_score = round(score, 1)
            db.commit()
        return score
    finally:
        db.close()


def list_assets(limit: int = 200) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(Asset).order_by(Asset.risk_score.desc()).limit(limit).all()
        return [
            {
                "ID": r.asset_id,
                "IP": r.ip_address,
                "Hostname": r.hostname or "",
                "Type": r.device_type,
                "Criticality": r.criticality,
                "Risk": r.risk_score,
                "Last Seen": str(r.last_seen),
                "Tags": r.tags or "",
            }
            for r in rows
        ]
    finally:
        db.close()


def topology_edges(limit: int = 80) -> List[Dict[str, str]]:
    db = SessionLocal()
    try:
        flows = db.query(NetworkFlow).order_by(NetworkFlow.flow_id.desc()).limit(limit).all()
        edges = []
        seen = set()
        for f in flows:
            key = (f.source_ip, f.destination_ip)
            if key in seen or not f.source_ip or not f.destination_ip:
                continue
            seen.add(key)
            edges.append({
                "from": f.source_ip,
                "to": f.destination_ip,
                "port": str(f.destination_port or ""),
                "proto": f.protocol or "",
            })
        return edges
    finally:
        db.close()


def set_critical(ip: str, critical: bool = True) -> bool:
    db = SessionLocal()
    try:
        row = db.query(Asset).filter(Asset.ip_address == ip).first()
        if not row:
            return False
        row.criticality = "Critical" if critical else "Normal"
        db.commit()
        return True
    finally:
        db.close()
