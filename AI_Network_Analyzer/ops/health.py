"""
Ops health helpers – used by API health endpoint and supervisor.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from config import BASE_DIR, LOGS_DIR, MODELS_DIR


def collect_health() -> Dict[str, Any]:
    """Aggregate readiness checks for server / watchdog."""
    checks: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "status": "ok",
        "components": {},
    }

    # Database
    try:
        from database.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            checks["components"]["database"] = {"status": "ok"}
        finally:
            db.close()
    except Exception as exc:
        checks["components"]["database"] = {"status": "error", "detail": str(exc)}
        checks["status"] = "degraded"

    # Core models
    required = ["random_forest.pkl", "xgboost_model.pkl", "isolation_forest.pkl"]
    missing = [f for f in required if not (MODELS_DIR / f).exists()]
    if missing:
        checks["components"]["ai_models"] = {
            "status": "warn",
            "detail": f"missing: {', '.join(missing)}",
        }
        if checks["status"] == "ok":
            checks["status"] = "degraded"
    else:
        online = (MODELS_DIR / "online_sgd.pkl").exists()
        checks["components"]["ai_models"] = {
            "status": "ok",
            "online_learning": online,
        }

    # Telegram config (presence only)
    try:
        from alerts.runtime_config import telegram_configured
        checks["components"]["telegram"] = {
            "status": "ok" if telegram_configured() else "warn",
            "configured": bool(telegram_configured()),
        }
    except Exception as exc:
        checks["components"]["telegram"] = {"status": "warn", "detail": str(exc)}

    # Disk paths
    for name, path in (("logs", LOGS_DIR), ("models", MODELS_DIR), ("base", BASE_DIR)):
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            checks["components"][f"path_{name}"] = {"status": "ok", "path": str(path)}
        except Exception as exc:
            checks["components"][f"path_{name}"] = {"status": "error", "detail": str(exc)}
            checks["status"] = "degraded"

    # MITRE / SOAR modules
    try:
        from threat_intelligence.mitre_map import map_attack_to_mitre
        from soar.playbooks import list_playbooks
        checks["components"]["mitre"] = {"status": "ok", "sample": map_attack_to_mitre("PortScan")["primary_technique"]}
        checks["components"]["soar"] = {"status": "ok", "playbooks": len(list_playbooks())}
    except Exception as exc:
        checks["components"]["mitre_soar"] = {"status": "error", "detail": str(exc)}
        checks["status"] = "degraded"

    # Online learning
    try:
        from training.online_learning import get_online_status
        checks["components"]["online_learning"] = {"status": "ok", **get_online_status()}
    except Exception as exc:
        checks["components"]["online_learning"] = {"status": "warn", "detail": str(exc)}

    try:
        from ops.retention import capture_health
        checks["components"]["capture"] = {"status": "ok", **capture_health()}
    except Exception as exc:
        checks["components"]["capture"] = {"status": "warn", "detail": str(exc)}

    return checks


def try_auto_heal() -> Dict[str, Any]:
    """
    Lightweight self-heal actions safe to run on a server:
    - ensure dirs exist
    - re-init DB schema
    - clear stale pycache if import issues suspected
    """
    actions = []
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        actions.append("dirs_ok")
    except Exception as exc:
        actions.append(f"dirs_fail:{exc}")

    try:
        from database.database import init_db, SessionLocal, heal_mapper_registry
        heal_mapper_registry()
        init_db()
        from database.models import Alert, NetworkFlow, User
        db = SessionLocal()
        try:
            db.query(NetworkFlow).limit(1).count()
            db.query(Alert).limit(1).count()
            db.query(User).limit(1).count()
        finally:
            db.close()
        actions.append("db_init_ok")
        actions.append("orm_queries_ok")
    except Exception as exc:
        actions.append(f"db_init_fail:{exc}")

    return {"healed_at": datetime.utcnow().isoformat() + "Z", "actions": actions}
