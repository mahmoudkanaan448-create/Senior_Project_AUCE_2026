"""
Response policy: allowlist, temp block, human approval, rollback.

Email is intentionally not used.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database.database import SessionLocal
from database.orm import ensure_models
from database.queries import block_ip, unblock_ip, get_setting

_m = ensure_models()
Allowlist, PendingAction, BlockedIP = _m.Allowlist, _m.PendingAction, _m.BlockedIP


def is_allowlisted(value: str) -> bool:
    if not value:
        return False
    db = SessionLocal()
    try:
        row = db.query(Allowlist).filter(Allowlist.value == value).first()
        return row is not None
    finally:
        db.close()


def add_allow(value: str, entry_type: str = "ip", reason: str = "trusted") -> None:
    db = SessionLocal()
    try:
        if db.query(Allowlist).filter(Allowlist.value == value).first():
            return
        db.add(Allowlist(value=value, entry_type=entry_type, reason=reason))
        db.commit()
    finally:
        db.close()


def list_allow() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(Allowlist).order_by(Allowlist.allow_id.desc()).all()
        return [{"ID": r.allow_id, "Type": r.entry_type, "Value": r.value, "Reason": r.reason} for r in rows]
    finally:
        db.close()


def response_mode() -> str:
    """automatic | ask"""
    try:
        db = SessionLocal()
        try:
            val = get_setting(db, "response_mode") or "automatic"
            return val if val in ("automatic", "ask") else "automatic"
        finally:
            db.close()
    except Exception:
        return "automatic"


def queue_or_block(ip: str, reason: str, duration: str = "1h", blocked_by: str = "system") -> Dict[str, Any]:
    """Respect allowlist + human approval. Duration: 5m/1h/24h/permanent."""
    if is_allowlisted(ip):
        return {"ok": False, "skipped": "allowlisted", "ip": ip}
    if response_mode() == "ask":
        db = SessionLocal()
        try:
            db.add(PendingAction(action_type="block_ip", target=ip, reason=f"{reason} [{duration}]", requested_by=blocked_by))
            db.commit()
            return {"ok": True, "pending": True, "ip": ip}
        finally:
            db.close()
    db = SessionLocal()
    try:
        block_ip(db, ip_address=ip, attack_type="auto", blocked_by=blocked_by, reason=reason, duration=duration)
        rec = db.query(BlockedIP).filter(BlockedIP.ip_address == ip, BlockedIP.status == "Active").first()
        if rec:
            rec.duration = duration
            db.commit()
        return {"ok": True, "pending": False, "ip": ip, "duration": duration}
    finally:
        db.close()


def expire_temp_blocks() -> int:
    """Auto-unblock expired timed blocks."""
    mapping = {"5m": 5, "1h": 60, "24h": 1440}
    n = 0
    db = SessionLocal()
    try:
        rows = db.query(BlockedIP).filter(BlockedIP.status == "Active").all()
        now = datetime.utcnow()
        for r in rows:
            mins = mapping.get((r.duration or "").lower())
            if not mins:
                continue
            if r.blocked_at and now - r.blocked_at >= timedelta(minutes=mins):
                r.status = "Expired"
                n += 1
        db.commit()
        return n
    finally:
        db.close()


def rollback_block(ip: str) -> bool:
    db = SessionLocal()
    try:
        return unblock_ip(db, ip)
    finally:
        db.close()


def list_pending() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(PendingAction).filter(PendingAction.status == "Pending").order_by(PendingAction.action_id.desc()).all()
        return [
            {"ID": r.action_id, "Action": r.action_type, "Target": r.target, "Reason": r.reason or "", "When": str(r.created_at)}
            for r in rows
        ]
    finally:
        db.close()


def decide_pending(action_id: int, approve: bool, actor: str = "admin") -> bool:
    db = SessionLocal()
    try:
        row = db.query(PendingAction).filter(PendingAction.action_id == action_id).first()
        if not row or row.status != "Pending":
            return False
        row.status = "Approved" if approve else "Rejected"
        if approve and row.action_type == "block_ip":
            block_ip(db, ip_address=row.target, attack_type="approved", blocked_by=actor, reason=row.reason or "approved")
        db.commit()
        return True
    finally:
        db.close()
