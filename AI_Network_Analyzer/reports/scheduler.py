"""Scheduled daily/weekly/monthly reports + JSON export."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from config import REPORTS_DIR
from database.database import SessionLocal
from database.queries import get_setting, set_setting
from reports.report_generator import generate_daily_report


def maybe_run_scheduled() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        cadence = (get_setting(db, "report_cadence") or "off").lower()
        if cadence not in ("daily", "weekly", "monthly"):
            return {"ran": False, "reason": "off"}
        last = get_setting(db, "last_scheduled_report") or ""
        now = datetime.utcnow()
        due = True
        if last:
            try:
                prev = datetime.fromisoformat(last.replace("Z", ""))
                delta = now - prev
                need = {"daily": 1, "weekly": 7, "monthly": 30}[cadence]
                due = delta >= timedelta(days=need)
            except Exception:
                due = True
        if not due:
            return {"ran": False, "reason": "not_due"}
        path = generate_daily_report(db)
        set_setting(db, "last_scheduled_report", now.isoformat() + "Z")
        return {"ran": True, "path": path, "cadence": cadence}
    finally:
        db.close()


def export_json(payload: Any, name: str = "export") -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"{name}_{ts}.json"
    path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    return str(path)


def compliance_summary() -> Dict[str, Any]:
    from database.models import Alert, BlockedIP, User, SystemLog
    db = SessionLocal()
    try:
        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "controls": {
                "authentication": db.query(User).count() > 0,
                "audit_logs": db.query(SystemLog).count(),
                "alerting": db.query(Alert).count(),
                "containment": db.query(BlockedIP).filter(BlockedIP.status == "Active").count(),
                "rbac": True,
            },
            "note": "Basic security audit snapshot for academic / SOC evidence packs.",
        }
    finally:
        db.close()
