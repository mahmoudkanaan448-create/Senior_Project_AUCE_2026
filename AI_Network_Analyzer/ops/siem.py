"""SIEM / Syslog export – JSONL + optional UDP syslog. No email."""

from __future__ import annotations

import json
import os
import socket
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from config import LOGS_DIR

SIEM_PATH = LOGS_DIR / "siem_events.jsonl"


def emit_event(event_type: str, payload: Dict[str, Any]) -> bool:
    rec = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "product": "AI-NDR",
        "event": event_type,
        **payload,
    }
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SIEM_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        return False
    rec["cef"] = cef_line(
        str(payload.get("label") or payload.get("alert_type") or event_type),
        str(payload.get("severity") or "Medium"),
        str(payload.get("source_ip") or ""),
        str(payload.get("message") or ""),
    )
    _syslog(rec)
    try:
        from ops.integrations import fanout
        fanout(event_type, rec)
    except Exception:
        pass
    return True


def _syslog(rec: Dict[str, Any]) -> None:
    host = os.getenv("SIEM_SYSLOG_HOST") or ""
    if not host:
        try:
            from database.database import SessionLocal
            from database.queries import get_setting
            db = SessionLocal()
            try:
                host = get_setting(db, "syslog_host") or ""
            finally:
                db.close()
        except Exception:
            host = ""
    if not host:
        return
    port = int(os.getenv("SIEM_SYSLOG_PORT") or 514)
    cef = rec.get("cef") or json.dumps(rec, default=str)[:900]
    msg = f"<134>AI-NDR: {cef}"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.5)
        sock.sendto(msg.encode("utf-8", errors="ignore"), (host, port))
        sock.close()
    except Exception:
        pass


def cef_line(alert_type: str, severity: str, source_ip: str, message: str = "") -> str:
    sev = {"Low": 3, "Medium": 5, "High": 8, "Critical": 10}.get(severity, 5)
    return (
        f"CEF:0|AUCE|AI-NDR|2.0|{alert_type}|{alert_type}|{sev}|"
        f"src={source_ip} msg={message[:120]}"
    )
