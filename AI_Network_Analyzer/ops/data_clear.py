"""Password-protected selective data wipe (users/settings/models are never deleted)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.database import SessionLocal
from database.models import (
    Alert,
    AlertFeedback,
    Allowlist,
    Asset,
    BlockedIP,
    HostBaseline,
    IncidentReport,
    IOC,
    NetworkFlow,
    Notification,
    PcapEvidence,
    PendingAction,
    Prediction,
    SocIncident,
    SystemLog,
    ThreatIntelligence,
)
from ops.audit import audit

# FK-safe wipe order (children first).
_WIPE_ORDER = [
    AlertFeedback,
    Notification,
    Alert,
    ThreatIntelligence,
    IncidentReport,
    Prediction,
    PcapEvidence,
    NetworkFlow,
    BlockedIP,
    SocIncident,
    Asset,
    IOC,
    Allowlist,
    PendingAction,
    HostBaseline,
    SystemLog,
]

CLEAR_TARGETS: Dict[str, Tuple[str, list]] = {
    "alerts": ("Alerts & notifications", [AlertFeedback, Notification, Alert]),
    "predictions": ("AI predictions", [Prediction]),
    "flows": ("Network flows", [NetworkFlow]),
    "blocked_ips": ("Blocked IPs", [BlockedIP]),
    "incidents": ("Incidents", [SocIncident, IncidentReport]),
    "assets": ("Assets", [Asset]),
    "threat_intel": ("Threat intelligence", [ThreatIntelligence]),
    "iocs": ("IOCs", [IOC]),
    "allowlist": ("Allowlist", [Allowlist]),
    "pending": ("Pending response actions", [PendingAction]),
    "pcap": ("PCAP evidence", [PcapEvidence]),
    "baselines": ("Host baselines", [HostBaseline]),
    "logs": ("Audit / system logs", [SystemLog]),
}

# Parent selection also wipes children that would otherwise break FKs.
DEPENDENTS: Dict[str, List[str]] = {
    "flows": ["predictions", "alerts", "threat_intel", "pcap", "incidents"],
    "predictions": ["alerts", "threat_intel", "incidents"],
}


def count_rows(db: Session, models: list) -> int:
    total = 0
    for model in models:
        try:
            total += int(db.query(model).count() or 0)
        except Exception:
            pass
    return total


def preview_counts() -> Dict[str, int]:
    db = SessionLocal()
    try:
        return {key: count_rows(db, models) for key, (_label, models) in CLEAR_TARGETS.items()}
    finally:
        db.close()


def expand_selection(keys: List[str]) -> List[str]:
    selected = set(keys)
    if "all" in selected:
        return list(CLEAR_TARGETS.keys())
    extra: set[str] = set()
    for key in list(selected):
        extra.update(DEPENDENTS.get(key, []))
    selected.update(extra)
    selected.discard("all")
    return [k for k in CLEAR_TARGETS if k in selected]


def clear_selected(keys: List[str], *, username: str = "") -> Dict[str, int]:
    """Wipe selected operational tables. Never touches users, settings, or AI models."""
    ordered_keys = expand_selection(keys)
    wanted = set()
    for key in ordered_keys:
        wanted.update(CLEAR_TARGETS[key][1])

    db = SessionLocal()
    result: Dict[str, int] = {k: 0 for k in ordered_keys}
    try:
        try:
            db.execute(text("PRAGMA foreign_keys=OFF"))
        except Exception:
            pass
        for model in _WIPE_ORDER:
            if model not in wanted:
                continue
            try:
                n = int(db.query(model).delete(synchronize_session=False) or 0)
            except Exception:
                db.rollback()
                n = int(db.query(model).delete(synchronize_session=False) or 0)
            for key, (_label, models) in CLEAR_TARGETS.items():
                if model in models and key in result:
                    result[key] += n
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    audit(
        "data_clear",
        details=f"user={username} cleared={','.join(ordered_keys)} counts={result}",
    )
    return result
