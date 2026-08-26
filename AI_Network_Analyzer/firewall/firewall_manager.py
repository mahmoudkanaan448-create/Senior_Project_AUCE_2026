"""
Firewall rule management – query active rules and expire stale entries.

Provides dashboard-friendly rule lists and time-bounded cleanup of
non-permanent block records (default duration 24 hours).
"""
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.models import BlockedIP
from database.queries import get_blocked_ips

logger = logging.getLogger(__name__)

DEFAULT_BLOCK_DURATION_HOURS = 24


def get_active_rules(db_session) -> List[dict]:
    """Return all currently active blocked-IP rules as plain dicts."""
    try:
        blocked = get_blocked_ips(db_session)
        rules = []
        for b in blocked:
            rules.append({
                "ip_address": b.ip_address,
                "attack_type": b.attack_type,
                "blocked_at": b.blocked_at.isoformat() if b.blocked_at else None,
                "duration": b.duration,
                "blocked_by": b.blocked_by,
                "reason": b.reason,
            })
        logger.info("Retrieved %d active firewall rules", len(rules))
        return rules

    except Exception as exc:
        logger.error("Error fetching active firewall rules: %s", exc)
        return []


def cleanup_expired(db_session) -> int:
    """Expire block rules whose duration (hours) has elapsed; skip permanent."""
    removed = 0
    try:
        active = db_session.query(BlockedIP).filter(BlockedIP.status == "Active").all()
        now = datetime.utcnow()

        for rule in active:
            if rule.duration == "permanent":
                continue

            try:
                hours = float(rule.duration)
            except (ValueError, TypeError):
                hours = DEFAULT_BLOCK_DURATION_HOURS

            if rule.blocked_at and (now - rule.blocked_at) > timedelta(hours=hours):
                rule.status = "Expired"
                removed += 1
                logger.info("Expired block rule for %s (after %.1f h)", rule.ip_address, hours)

        if removed:
            db_session.commit()
        logger.info("Cleanup complete – %d rule(s) expired", removed)

    except Exception as exc:
        logger.error("Error during firewall cleanup: %s", exc)
        db_session.rollback()

    return removed
