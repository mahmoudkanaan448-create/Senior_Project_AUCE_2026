"""IOC manager: IP / domain / hash indicators + match against traffic."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from database.database import SessionLocal
from database.orm import ensure_models

_m = ensure_models()
IOC = _m.IOC


def add_ioc(ioc_type: str, value: str, source: str = "manual", severity: str = "High", description: str = "") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        row = IOC(
            ioc_type=ioc_type.lower().strip(),
            value=value.strip(),
            source=source,
            severity=severity,
            description=description,
            active=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.ioc_id, "type": row.ioc_type, "value": row.value}
    finally:
        db.close()


def list_iocs(active_only: bool = True) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        q = db.query(IOC)
        if active_only:
            q = q.filter(IOC.active.is_(True))
        rows = q.order_by(IOC.ioc_id.desc()).limit(300).all()
        return [
            {
                "ID": r.ioc_id,
                "Type": r.ioc_type,
                "Value": r.value,
                "Source": r.source,
                "Severity": r.severity,
                "Active": r.active,
                "Description": r.description or "",
                "Created": str(r.created_at),
            }
            for r in rows
        ]
    finally:
        db.close()


def match_flow(source_ip: str, dest_ip: str, domain: str = "", file_hash: str = "") -> List[Dict[str, Any]]:
    hits = []
    db = SessionLocal()
    try:
        rows = db.query(IOC).filter(IOC.active.is_(True)).all()
        for r in rows:
            val = (r.value or "").lower()
            if r.ioc_type == "ip" and val in (source_ip.lower(), dest_ip.lower()):
                hits.append({"type": "ip", "value": r.value, "severity": r.severity, "source": r.source})
            if r.ioc_type == "domain" and domain and val in domain.lower():
                hits.append({"type": "domain", "value": r.value, "severity": r.severity, "source": r.source})
            if r.ioc_type == "hash" and file_hash and val == file_hash.lower():
                hits.append({"type": "hash", "value": r.value, "severity": r.severity, "source": r.source})
        return hits
    finally:
        db.close()


def deactivate(ioc_id: int) -> bool:
    db = SessionLocal()
    try:
        row = db.query(IOC).filter(IOC.ioc_id == ioc_id).first()
        if not row:
            return False
        row.active = False
        db.commit()
        return True
    finally:
        db.close()
