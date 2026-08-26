"""Verify all dashboard DB query paths work after ORM fixes."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODELS = (
    "User", "NetworkFlow", "Prediction", "Alert", "ThreatIntelligence",
    "BlockedIP", "Notification", "AIModel", "ModelHistory", "IncidentReport",
    "SystemLog", "Setting", "Sensor", "Asset", "IOC", "Allowlist",
    "SocIncident", "AlertFeedback", "PendingAction", "Webhook",
    "PcapEvidence", "HostBaseline",
)


def main() -> int:
    from collections import Counter

    from database.database import Base, SessionLocal, init_db, heal_mapper_registry
    import database.models as models

    init_db()
    db = SessionLocal()
    checks = {}
    try:
        for name in MODELS:
            cls = getattr(models, name)
            checks[name] = db.query(cls).count()
    finally:
        db.close()
    print("ORM queries:", checks)

    names = [m.class_.__name__ for m in Base.registry.mappers]
    dups = {k: v for k, v in Counter(names).items() if v > 1}
    if dups:
        print("FAIL duplicate mappers:", dups)
        return 1
    print("Mapper duplicates: NONE")

    # Same helpers every dashboard page uses
    from assets.inventory import list_assets, topology_edges
    from detection.baselines import list_drifted
    from detection.correlation import list_incidents
    from threat_intelligence.ioc_manager import list_iocs
    from response.policy import list_allow, list_pending, expire_temp_blocks
    from alerts.webhooks import list_webhooks
    from monitoring.sensors import list_sensors
    from soc.copilot import nl_query, summarize_incident
    from soc.hunting import hunt
    from identity.monitor import auth_anomalies
    from database import queries

    db = SessionLocal()
    try:
        queries.get_setting(db, "refresh_rate")
        queries.get_blocked_ips(db)
    finally:
        db.close()

    print(
        "Helpers OK:",
        len(list_assets()),
        len(list_incidents()),
        len(list_iocs(False)),
        len(list_allow()),
        len(list_sensors()),
        len(topology_edges()),
        len(list_drifted()),
    )
    print("NL:", nl_query("critical alerts")["answer"][:80])
    expire_temp_blocks()

    # Streamlit hot-reload storm (runOnSave)
    import database.tables as t
    import database.queries as q
    for i in range(10):
        heal_mapper_registry()
        importlib.reload(t)
        importlib.reload(models)
        importlib.reload(q)
        db = SessionLocal()
        db.query(models.Alert).count()
        db.query(models.NetworkFlow).count()
        db.query(models.User).count()
        db.close()
    print("10 reload cycles: OK")

    # Simulate desktop double-click (fresh interpreter would run verify again)
    heal_mapper_registry()
    db = SessionLocal()
    db.query(models.SystemLog).count()
    db.query(models.SocIncident).count()
    db.query(models.Prediction).count()
    db.close()
    print("Post-heal queries: OK")

    print("ALL_CHECKS_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
