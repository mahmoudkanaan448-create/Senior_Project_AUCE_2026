"""Company / production-pilot helpers.

This is a hardening profile for a real office trial — not a full commercial NDR.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from config import DATABASE_URL, SECRET_KEY


def _truthy(raw: str) -> bool:
    return str(raw or "").strip().lower() in ("1", "true", "yes", "on")


def company_mode() -> bool:
    env = os.getenv("AINDR_COMPANY_MODE", "").strip()
    if env:
        return _truthy(env)
    try:
        from database.database import SessionLocal
        from database.queries import get_setting
        db = SessionLocal()
        try:
            return _truthy(get_setting(db, "company_mode") or "0")
        finally:
            db.close()
    except Exception:
        return False


def allow_forced_demo_labels() -> bool:
    """Lab-only: forcing attack labels is disabled in company mode."""
    return not company_mode()


def secret_is_default() -> bool:
    return SECRET_KEY in ("", "change-me-in-production-ai-ndr-2026")


def using_sqlite() -> bool:
    return "sqlite" in (DATABASE_URL or "").lower()


def min_password_len() -> int:
    return 12 if company_mode() else 6


def readiness() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    add(
        "company_mode",
        company_mode(),
        "ON" if company_mode() else "OFF (lab defaults still apply)",
    )
    add(
        "secret_key",
        not secret_is_default(),
        "Set SECRET_KEY in .env" if secret_is_default() else "Custom SECRET_KEY loaded",
    )
    add(
        "database",
        True,
        "PostgreSQL" if not using_sqlite() else "SQLite (fine for a small office; use Postgres for scale)",
    )
    syslog = os.getenv("SIEM_SYSLOG_HOST") or ""
    try:
        from database.database import SessionLocal
        from database.queries import get_setting
        db = SessionLocal()
        try:
            syslog = syslog or (get_setting(db, "syslog_host") or "")
        finally:
            db.close()
    except Exception:
        pass
    add("siem_syslog", bool(syslog), syslog or "Not configured")
    add("splunk_hec", bool(os.getenv("SPLUNK_HEC_URL") and os.getenv("SPLUNK_HEC_TOKEN")), "HEC URL+token")
    add("elastic", bool(os.getenv("ELASTIC_URL")), os.getenv("ELASTIC_URL") or "Not configured")
    add("jira", bool(os.getenv("JIRA_URL") and os.getenv("JIRA_TOKEN")), "Jira issue webhook")
    add(
        "telegram",
        bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")),
        "Telegram alerts",
    )
    score = sum(1 for c in checks if c["ok"])
    return {
        "company_mode": company_mode(),
        "ready_score": f"{score}/{len(checks)}",
        "checks": checks,
        "note": "A company trial needs 24/7 capture, backups, and SIEM/tickets. This is still a senior-project NDR, not Darktrace.",
    }
