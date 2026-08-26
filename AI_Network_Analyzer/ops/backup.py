"""Local backups for SQLite or PostgreSQL. Keep last N copies."""
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from config import BASE_DIR, DATABASE_URL

BACKUP_DIR = BASE_DIR / "backups"
KEEP = 14


def _stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def list_backups() -> List[Dict[str, Any]]:
    if not BACKUP_DIR.exists():
        return []
    rows = []
    for path in sorted(BACKUP_DIR.glob("aindr_backup_*"), reverse=True):
        rows.append({"name": path.name, "bytes": path.stat().st_size, "path": str(path)})
    return rows


def _prune() -> None:
    files = sorted(BACKUP_DIR.glob("aindr_backup_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for extra in files[KEEP:]:
        try:
            extra.unlink()
        except Exception:
            pass


def backup_now() -> Dict[str, Any]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    url = DATABASE_URL or ""
    if "sqlite" in url.lower():
        src = Path(url.split("///")[-1])
        if not src.is_absolute():
            src = BASE_DIR / src
        dest = BACKUP_DIR / f"aindr_backup_{stamp}.db"
        shutil.copy2(src, dest)
        _prune()
        return {"ok": True, "engine": "sqlite", "path": str(dest), "bytes": dest.stat().st_size}

    parsed = urlparse(url.replace("postgresql+psycopg2://", "postgresql://"))
    dest = BACKUP_DIR / f"aindr_backup_{stamp}.sql"
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    cmd = [
        "pg_dump",
        "-h", parsed.hostname or "127.0.0.1",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "aindr",
        "-d", (parsed.path or "/aindr").lstrip("/"),
        "-f", str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, env=env, timeout=120)
        _prune()
        return {"ok": True, "engine": "postgres", "path": str(dest), "bytes": dest.stat().st_size}
    except Exception as exc:
        return {"ok": False, "engine": "postgres", "error": str(exc)}
