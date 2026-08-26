"""
Load notification credentials at send-time.

Settings UI stores values in the database; config.py / env vars are fallback.
Always prefer DB so changes in Settings take effect without restarting.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import config as app_config


def _db_get(name: str) -> Optional[str]:
    try:
        from database.database import SessionLocal
        from database import queries
        db = SessionLocal()
        try:
            value = queries.get_setting(db, name)
            if value is None:
                return None
            value = str(value).strip()
            return value or None
        finally:
            db.close()
    except Exception:
        return None


def get_email_settings() -> Dict[str, Any]:
    """Return SMTP settings: DB first, then config/env."""
    return {
        "smtp_server": _db_get("smtp_server") or app_config.SMTP_SERVER or "smtp.gmail.com",
        "smtp_port": int(_db_get("smtp_port") or app_config.SMTP_PORT or 587),
        "smtp_username": _db_get("smtp_username") or app_config.SMTP_USERNAME or "",
        "smtp_password": _db_get("smtp_password") or app_config.SMTP_PASSWORD or "",
        "alert_email": _db_get("alert_email") or app_config.ALERT_EMAIL_TO or "",
    }


def get_telegram_settings() -> Dict[str, str]:
    """Return Telegram bot settings: DB first, then config/env."""
    return {
        "bot_token": _db_get("telegram_token") or app_config.TELEGRAM_BOT_TOKEN or "",
        "chat_id": _db_get("telegram_chat_id") or app_config.TELEGRAM_CHAT_ID or "",
    }


def email_configured() -> bool:
    s = get_email_settings()
    return bool(s["smtp_username"] and s["smtp_password"] and s["alert_email"])


def telegram_configured() -> bool:
    s = get_telegram_settings()
    return bool(s["bot_token"] and s["chat_id"])
