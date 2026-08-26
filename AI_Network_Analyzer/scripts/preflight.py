"""Pre-start checks for desktop / server launchers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from scripts.verify_orm import main as verify
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
