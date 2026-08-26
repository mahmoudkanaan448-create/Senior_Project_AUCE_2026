"""
One-shot realistic defaults for a working SOC lab.

Called from init_db / dashboard / API startup. Idempotent. No email.
"""

from __future__ import annotations

from database.database import SessionLocal
from database.queries import get_setting, set_setting


_DEFAULTS = {
    "refresh_rate": "5",
    "confidence_threshold": "50",
    "threat_block_threshold": "7",
    "attack_sound_enabled": "1",
    "response_mode": "automatic",
    "retention_days": "30",
    "report_cadence": "off",
    "email_alerts": "0",
    "company_mode": "0",
}


def bootstrap() -> None:
    db = SessionLocal()
    try:
        for k, v in _DEFAULTS.items():
            if not get_setting(db, k):
                set_setting(db, k, v)
    finally:
        db.close()

    try:
        from monitoring.sensors import ensure_local
        ensure_local()
    except Exception:
        pass

    try:
        from response.policy import add_allow, expire_temp_blocks
        add_allow("127.0.0.1", "ip", "localhost")
        add_allow("::1", "ip", "localhost")
        expire_temp_blocks()
    except Exception:
        pass
