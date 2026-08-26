"""
Common database CRUD helpers.

Centralized Create/Read/Update/Delete operations for users, flows,
predictions, alerts, threat intel, blocked IPs, notifications, models,
incidents, logs, and settings. Used by API routes and startup scripts.
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from database.models import (
    User, NetworkFlow, Prediction, Alert, ThreatIntelligence,
    BlockedIP, Notification, AIModel, IncidentReport, SystemLog, Setting,
)


# ── Users ─────────────────────────────────────────────────────────────────────

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Look up a user by username, or None if not found."""
    return db.query(User).filter(User.username == username).first()


def list_users(db: Session) -> List[User]:
    return db.query(User).order_by(User.user_id.asc()).all()


def create_user(db: Session, full_name: str, username: str, email: str,
                password_hash: str, role: str = "Viewer") -> User:
    """Insert a new user and return the persisted record."""
    user = User(full_name=full_name, username=username, email=email,
                password_hash=password_hash, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_credentials(
    db: Session,
    current_username: str,
    new_username: str | None = None,
    new_password_hash: str | None = None,
) -> tuple[bool, str]:
    """
    Update username and/or password for an existing user.
    Returns (ok, message).
    """
    user = get_user_by_username(db, current_username)
    if user is None:
        return False, "Current user not found"

    if new_username:
        new_username = new_username.strip()
        if not new_username:
            return False, "New username cannot be empty"
        if new_username != current_username:
            existing = get_user_by_username(db, new_username)
            if existing is not None:
                return False, "Username already taken"
            user.username = new_username

    if new_password_hash:
        user.password_hash = new_password_hash

    db.commit()
    db.refresh(user)
    return True, "Account updated successfully"


# ── Network Flows ─────────────────────────────────────────────────────────────

def insert_flow(db: Session, **kwargs) -> NetworkFlow:
    """Insert a network flow record (pass any NetworkFlow fields as kwargs)."""
    flow = NetworkFlow(**kwargs)
    db.add(flow)
    db.commit()
    db.refresh(flow)
    return flow


def get_recent_flows(db: Session, limit: int = 50) -> List[NetworkFlow]:
    """Return the most recent network flows, newest first."""
    return db.query(NetworkFlow).order_by(NetworkFlow.timestamp.desc()).limit(limit).all()


# ── Predictions ───────────────────────────────────────────────────────────────

def insert_prediction(db: Session, **kwargs) -> Prediction:
    """Insert an AI prediction result."""
    pred = Prediction(**kwargs)
    db.add(pred)
    db.commit()
    db.refresh(pred)
    return pred


def get_recent_predictions(db: Session, limit: int = 50) -> List[Prediction]:
    """Return the most recent predictions, newest first."""
    return db.query(Prediction).order_by(Prediction.prediction_time.desc()).limit(limit).all()


# ── Alerts ────────────────────────────────────────────────────────────────────

def insert_alert(db: Session, **kwargs) -> Alert:
    """Create a new security alert."""
    alert = Alert(**kwargs)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def get_alerts(db: Session, status: Optional[str] = None, limit: int = 100) -> List[Alert]:
    """Return alerts, optionally filtered by status."""
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status)
    return q.order_by(Alert.created_at.desc()).limit(limit).all()


# ── Threat Intelligence ───────────────────────────────────────────────────────

def upsert_threat_intel(db: Session, ip_address: str, **kwargs) -> ThreatIntelligence:
    """Insert or update threat intelligence for an IP address."""
    existing = db.query(ThreatIntelligence).filter(
        ThreatIntelligence.ip_address == ip_address
    ).first()
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
        existing.last_seen = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    ti = ThreatIntelligence(ip_address=ip_address, **kwargs)
    db.add(ti)
    db.commit()
    db.refresh(ti)
    return ti


# ── Blocked IPs ───────────────────────────────────────────────────────────────

def block_ip(db: Session, ip_address: str, attack_type: str = "",
             blocked_by: str = "system", reason: str = "", duration: str = "permanent") -> BlockedIP:
    """Add an IP to the block list; returns existing record if already active."""
    existing = db.query(BlockedIP).filter(
        BlockedIP.ip_address == ip_address, BlockedIP.status == "Active"
    ).first()
    if existing:
        return existing
    b = BlockedIP(ip_address=ip_address, attack_type=attack_type,
                  blocked_by=blocked_by, reason=reason, duration=duration or "permanent")
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def unblock_ip(db: Session, ip_address: str) -> bool:
    """Soft-delete an active block (status → Removed). Returns True if found."""
    rec = db.query(BlockedIP).filter(
        BlockedIP.ip_address == ip_address, BlockedIP.status == "Active"
    ).first()
    if rec:
        rec.status = "Removed"
        db.commit()
        return True
    return False


def get_blocked_ips(db: Session) -> List[BlockedIP]:
    """Return all currently active blocked IPs."""
    return db.query(BlockedIP).filter(BlockedIP.status == "Active").all()


# ── Notifications ─────────────────────────────────────────────────────────────

def insert_notification(db: Session, **kwargs) -> Notification:
    """Record a sent or attempted notification."""
    n = Notification(**kwargs)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


# ── AI Models ─────────────────────────────────────────────────────────────────

def upsert_ai_model(db: Session, model_name: str, **kwargs) -> AIModel:
    """Insert a new AI model or update an existing one's metrics."""
    m = db.query(AIModel).filter(AIModel.model_name == model_name).first()
    if m:
        for k, v in kwargs.items():
            setattr(m, k, v)
        db.commit()
        db.refresh(m)
        return m
    m = AIModel(model_name=model_name, **kwargs)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def get_all_models(db: Session) -> List[AIModel]:
    """Return all registered AI models."""
    return db.query(AIModel).all()


# ── Incident Reports ──────────────────────────────────────────────────────────

def create_incident(db: Session, **kwargs) -> IncidentReport:
    """Create a new incident report."""
    inc = IncidentReport(**kwargs)
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


# ── System Logs ───────────────────────────────────────────────────────────────

def add_log(db: Session, event: str, user_id: int = None, details: str = None):
    """Append an event to the audit log (no refresh – write-and-forget)."""
    log = SystemLog(event=event, user_id=user_id, details=details)
    db.add(log)
    db.commit()


# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(db: Session, name: str) -> Optional[str]:
    """Retrieve a setting value by name, or None if missing."""
    s = db.query(Setting).filter(Setting.setting_name == name).first()
    return s.setting_value if s else None


def set_setting(db: Session, name: str, value: str):
    """Create or update a runtime setting."""
    s = db.query(Setting).filter(Setting.setting_name == name).first()
    if s:
        s.setting_value = value
        s.last_modified = datetime.utcnow()
    else:
        s = Setting(setting_name=name, setting_value=value)
        db.add(s)
    db.commit()
