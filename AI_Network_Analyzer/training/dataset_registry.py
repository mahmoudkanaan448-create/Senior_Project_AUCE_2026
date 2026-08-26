"""Dataset versioning registry for reproducible training."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from config import DATASETS_DIR, MODELS_DIR

REG_PATH = MODELS_DIR / "dataset_registry.json"


def register_dataset(path: str, note: str = "") -> Dict[str, Any]:
    p = Path(path)
    digest = ""
    size = 0
    if p.exists() and p.is_file():
        size = p.stat().st_size
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        digest = h.hexdigest()[:16]
    rec = {
        "path": str(p),
        "sha256_16": digest,
        "bytes": size,
        "note": note,
        "registered_at": datetime.utcnow().isoformat() + "Z",
    }
    rows = list_datasets()
    rows.append(rec)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REG_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rec


def list_datasets() -> List[Dict[str, Any]]:
    if not REG_PATH.exists():
        return []
    try:
        return json.loads(REG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def scan_local() -> List[str]:
    if not DATASETS_DIR.exists():
        return []
    return [str(p) for p in DATASETS_DIR.glob("*") if p.is_file()]
