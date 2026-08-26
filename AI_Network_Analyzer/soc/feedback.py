"""Analyst true/false-positive feedback → continuous learning."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from database.database import SessionLocal
from database.orm import ensure_models

_m = ensure_models()
Alert, AlertFeedback, Prediction = _m.Alert, _m.AlertFeedback, _m.Prediction


def record_feedback(
    alert_id: int,
    verdict: str,
    analyst: str = "analyst",
    comment: str = "",
) -> Dict[str, Any]:
    verdict = "true_positive" if verdict in ("true_positive", "tp", "true") else "false_positive"
    db = SessionLocal()
    try:
        row = AlertFeedback(alert_id=alert_id, verdict=verdict, analyst=analyst, comment=comment)
        db.add(row)
        alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        if alert and verdict == "false_positive":
            alert.status = "Closed"
        db.commit()
        db.refresh(row)

        queued = False
        if alert and alert.prediction_id:
            pred = db.query(Prediction).filter(Prediction.prediction_id == alert.prediction_id).first()
            if pred and pred.flow_id:
                try:
                    from database.models import NetworkFlow
                    from training.online_learning import queue_labeled_sample
                    flow = db.query(NetworkFlow).filter(NetworkFlow.flow_id == pred.flow_id).first()
                    feats = {}
                    if flow and flow.features_json:
                        import json
                        feats = json.loads(flow.features_json) if isinstance(flow.features_json, str) else {}
                    label = "Normal" if verdict == "false_positive" else (alert.alert_type or "Unknown")
                    if feats:
                        queued = bool(queue_labeled_sample(feats, label))
                except Exception:
                    queued = False

        return {"id": row.feedback_id, "verdict": verdict, "queued": queued}
    finally:
        db.close()


def list_feedback(limit: int = 100) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(AlertFeedback).order_by(AlertFeedback.feedback_id.desc()).limit(limit).all()
        return [
            {
                "ID": r.feedback_id,
                "Alert": r.alert_id,
                "Verdict": r.verdict,
                "Analyst": r.analyst or "",
                "Comment": (r.comment or "")[:80],
                "Time": str(r.created_at),
            }
            for r in rows
        ]
    finally:
        db.close()


def fp_rate() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        rows = db.query(AlertFeedback).all()
        tp = sum(1 for r in rows if r.verdict == "true_positive")
        fp = sum(1 for r in rows if r.verdict == "false_positive")
        total = tp + fp
        return {
            "true_positive": tp,
            "false_positive": fp,
            "fp_rate": round(fp / total, 3) if total else None,
            "samples": total,
        }
    finally:
        db.close()
