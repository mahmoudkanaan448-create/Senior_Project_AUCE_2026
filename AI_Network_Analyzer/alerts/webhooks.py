"""Outbound webhooks for Slack/Teams/generic REST. Email is not used."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, List

from database.database import SessionLocal
from database.orm import ensure_models

_m = ensure_models()
Webhook = _m.Webhook


def add_webhook(name: str, url: str, event: str = "alert") -> None:
    db = SessionLocal()
    try:
        db.add(Webhook(name=name, url=url, event=event, enabled=True))
        db.commit()
    finally:
        db.close()


def list_webhooks() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(Webhook).order_by(Webhook.webhook_id.desc()).all()
        return [
            {"ID": r.webhook_id, "Name": r.name, "URL": r.url, "Event": r.event, "Enabled": r.enabled}
            for r in rows
        ]
    finally:
        db.close()


def fire_webhooks(event: str, payload: Dict[str, Any]) -> int:
    db = SessionLocal()
    sent = 0
    try:
        rows = db.query(Webhook).filter(Webhook.enabled.is_(True)).filter(Webhook.event.in_([event, "all"])).all()
        body = json.dumps({"event": event, "source": "AI-NDR", **payload}).encode("utf-8")
        for r in rows:
            try:
                req = urllib.request.Request(
                    r.url,
                    data=body,
                    headers={"Content-Type": "application/json", "User-Agent": "AI-NDR/1.0"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=6)
                sent += 1
            except Exception:
                continue
        return sent
    finally:
        db.close()
