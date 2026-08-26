"""Load ORM classes once. Never re-register tables on the same MetaData."""

from __future__ import annotations


def ensure_models():
    """Import database.models if needed; do not reload (that redefines tables)."""
    import database.models as m
    return m
