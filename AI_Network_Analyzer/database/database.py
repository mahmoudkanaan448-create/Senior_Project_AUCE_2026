"""
Database connection and session management using SQLAlchemy.

Base/engine are process singletons so Streamlit reruns cannot create a
second MetaData and redefine table 'users'.
"""

import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL

_STATE = "_AINDR_DB_SINGLETON"


class _DbState:
    def __init__(self):
        self.engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
            pool_pre_ping=True,
        )
        self._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.Base = declarative_base()

    def open_session(self):
        try:
            heal_mapper_registry()
        except Exception:
            pass
        return self._session_factory()


if not hasattr(sys, _STATE):
    setattr(sys, _STATE, _DbState())

_state = getattr(sys, _STATE)
engine = _state.engine
Base = _state.Base


def SessionLocal():
    """Return a DB session; heals ORM registry first (Streamlit-safe)."""
    return _state.open_session()


def heal_mapper_registry() -> None:
    """Undo Streamlit double-import of ORM classes (duplicate SystemLog, etc.)."""
    from sqlalchemy.orm.clsregistry import _MultipleClassMarker, remove_class

    cr = Base.registry._class_registry
    for key, val in list(cr.items()):
        if str(key).startswith("_"):
            continue
        if not isinstance(val, _MultipleClassMarker):
            continue
        classes = [c for c in val if c is not None]
        if not classes:
            continue
        keep = classes[0]
        for extra in classes[1:]:
            try:
                remove_class(extra.__name__, extra, cr)
            except Exception:
                pass
            try:
                Base.registry._dispose_cls(extra)
            except Exception:
                pass
        current = cr.get(key)
        if isinstance(current, _MultipleClassMarker):
            leftover = [c for c in current if c is not None]
            cr[key] = leftover[0] if leftover else keep
        elif current is None:
            cr[key] = keep

    for mapper in list(Base.registry.mappers):
        mapper.__dict__.pop("_configure_failed", None)
    try:
        Base.registry._new_mappers = True
    except Exception:
        pass


def get_db():
    """Yield a request-scoped DB session; always closed afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (idempotent). Safe on every Streamlit page."""
    try:
        heal_mapper_registry()
    except Exception:
        pass
    import database.models  # noqa: F401
    try:
        heal_mapper_registry()
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)
    try:
        ensure_schema_columns()
    except Exception:
        pass
    try:
        from ops.bootstrap import bootstrap
        bootstrap()
    except Exception:
        pass


def ensure_schema_columns() -> None:
    """Add columns introduced after the first SQLite create_all."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "predictions" not in tables:
        return
    existing = {c["name"] for c in insp.get_columns("predictions")}
    if "explanation_json" not in existing:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE predictions ADD COLUMN explanation_json TEXT"))
