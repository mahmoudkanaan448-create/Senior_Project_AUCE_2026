"""Immutable-style audit trail wrapper around SystemLog."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from database.database import SessionLocal
from database.models import SystemLog
from database.queries import add_log


def audit(event: str, details: str = "", user_id: Optional[int] = None) -> None:
    db = SessionLocal()
    try:
        add_log(db, event=event, user_id=user_id, details=details)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def list_audit(limit: int = 200) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(SystemLog).order_by(SystemLog.log_id.desc()).limit(limit).all()
        return [
            {
                "ID": r.log_id,
                "Event": r.event,
                "Details": (r.details or "")[:160],
                "User": r.user_id,
                "Time": str(r.timestamp),
            }
            for r in rows
        ]
    finally:
        db.close()
