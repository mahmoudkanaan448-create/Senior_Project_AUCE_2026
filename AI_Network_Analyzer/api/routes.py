"""
FastAPI REST API routes for the AI Network Analyzer.

All /api/v1 endpoints: auth, traffic, predictions, alerts, threat intel,
IP blocking, model performance, reports, dashboard stats, notifications,
health checks, and settings.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.database import get_db
from database import queries
from api.authentication import (
    verify_password, hash_password, create_access_token,
    get_current_user, require_role,
)
from database.models import User

router = APIRouter(prefix="/api/v1")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Login response with JWT and role."""
    status: str = "success"
    access_token: str
    token_type: str = "bearer"
    role: str

class UserCreate(BaseModel):
    """Registration request body."""
    full_name: str
    username: str
    email: str
    password: str
    role: str = "Viewer"

class PredictionRequest(BaseModel):
    """Network flow features submitted for AI classification."""
    source_ip: str = "0.0.0.0"
    destination_ip: str = "0.0.0.0"
    source_port: int = 0
    destination_port: int = 0
    protocol: str = "TCP"
    duration: float = 0.0
    packet_count: int = 0
    byte_count: int = 0
    features: Optional[dict] = None

class BlockIPRequest(BaseModel):
    """IP blocking request."""
    ip_address: str
    reason: str = ""

class NotifyRequest(BaseModel):
    """Notification dispatch request."""
    notif_type: str = "email"
    message: str = ""

class SettingUpdate(BaseModel):
    """System setting update request."""
    setting_name: str
    setting_value: str

class SimulateAttackRequest(BaseModel):
    """Launch a controlled threat campaign through the live detection pipeline."""
    scenario: str = "Mixed"
    count: int = 10
    create_alerts: bool = True
    block_critical: bool = True
    ensure_attack_labels: bool = True
    force_demo_label: Optional[bool] = None  # legacy alias
    send_notifications: bool = True


# ── Authentication ────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate and return a JWT access token."""
    user = queries.get_user_by_username(db, form.username)
    if not user or not verify_password(form.password, user.password_hash):
        # Generic message to avoid username enumeration
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user.last_login = datetime.utcnow()
    db.commit()
    token = create_access_token({"sub": user.username})
    queries.add_log(db, f"User {user.username} logged in", user_id=user.user_id)
    return TokenResponse(access_token=token, role=user.role)


@router.post("/auth/register")
def register(body: UserCreate, db: Session = Depends(get_db)):
    """Create a new user account."""
    if queries.get_user_by_username(db, body.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    user = queries.create_user(
        db, body.full_name, body.username, body.email,
        hash_password(body.password), body.role,
    )
    return {"status": "success", "user_id": user.user_id}


# ── Live Traffic ──────────────────────────────────────────────────────────────

@router.get("/traffic/live")
def get_live_traffic(limit: int = 50, db: Session = Depends(get_db),
                     _user: User = Depends(get_current_user)):
    """Return the most recent network flows."""
    flows = queries.get_recent_flows(db, limit)
    return [
        {
            "flow_id": f.flow_id,
            "timestamp": str(f.timestamp),
            "source_ip": f.source_ip,
            "destination_ip": f.destination_ip,
            "source_port": f.source_port,
            "destination_port": f.destination_port,
            "protocol": f.protocol,
            "duration": f.duration,
            "packets": f.packets,
            "bytes": f.bytes_total,
        }
        for f in flows
    ]


@router.post("/traffic/upload")
async def upload_traffic(file: UploadFile = File(...), db: Session = Depends(get_db),
                         _user: User = Depends(get_current_user)):
    """Ingest a CSV of historical network traffic into the database."""
    import pandas as pd, io, json
    contents = await file.read()

    if file.filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(contents))
        inserted = 0
        for _, row in df.iterrows():
            # Support both src_ip/source_ip naming conventions from capture tools
            queries.insert_flow(
                db,
                source_ip=str(row.get("src_ip", row.get("source_ip", "0.0.0.0"))),
                destination_ip=str(row.get("dst_ip", row.get("destination_ip", "0.0.0.0"))),
                source_port=int(row.get("src_port", row.get("source_port", 0))),
                destination_port=int(row.get("dst_port", row.get("destination_port", 0))),
                protocol=str(row.get("protocol", "TCP")),
                duration=float(row.get("duration", 0)),
                packets=int(row.get("packets", row.get("packet_count", 0))),
                bytes_total=int(row.get("bytes", row.get("byte_count", 0))),
                features_json=json.dumps(row.to_dict(), default=str),
            )
            inserted += 1
        return {"status": "success", "rows_inserted": inserted}

    raise HTTPException(status_code=400, detail="Only CSV files are supported currently")


# ── AI Prediction ─────────────────────────────────────────────────────────────

@router.post("/predict")
def predict(body: PredictionRequest, db: Session = Depends(get_db),
            _user: User = Depends(get_current_user)):
    """Classify a network flow using the ensemble AI models."""
    try:
        # Lazy import: avoid loading heavy ML modules at API startup
        from detection.attack_detector import load_models, predict_single
        from detection.decision_engine import fuse_decisions
        from config import MODELS_DIR

        models = load_models(str(MODELS_DIR))

        features = body.features or {
            "duration": body.duration,
            "protocol_type": 1 if body.protocol == "TCP" else 2,
            "src_bytes": body.byte_count // 2,
            "dst_bytes": body.byte_count // 2,
            "packet_count": body.packet_count,
            "byte_count": body.byte_count,
            "packet_rate": body.packet_count / max(body.duration, 0.001),
            "flow_rate": body.byte_count / max(body.duration, 0.001),
        }

        raw_predictions = predict_single(features, models)
        result = fuse_decisions(raw_predictions)
        result["source_ip"] = body.source_ip
        result["destination_ip"] = body.destination_ip

        flow = queries.insert_flow(
            db,
            source_ip=body.source_ip, destination_ip=body.destination_ip,
            source_port=body.source_port, destination_port=body.destination_port,
            protocol=body.protocol, duration=body.duration,
            packets=body.packet_count, bytes_total=body.byte_count,
        )
        from explainable_ai.xai import explain_with_models, explanation_to_json
        xai = explain_with_models(
            features,
            result["final_label"],
            models,
            model_name=str(result.get("best_model") or "random_forest"),
            confidence_score=float(result.get("confidence") or 0),
            threat_score=float(result.get("threat_score") or 0),
        )
        result["xai"] = xai
        queries.insert_prediction(
            db,
            flow_id=flow.flow_id,
            model_name=result.get("best_model", "Hybrid"),
            prediction_label=result["final_label"],
            confidence=result["confidence"],
            threat_score=result["threat_score"],
            severity=result["severity"],
            attack_type=result["final_label"],
            recommendation=xai.get("recommended_action") or result.get("recommendation", ""),
            explanation_json=explanation_to_json(xai),
        )
        return result
    except Exception as e:
        return {
            "final_label": "Unknown",
            "confidence": 0.0,
            "threat_score": 0.0,
            "severity": "Low",
            "error": str(e),
            "note": "Models may not be trained yet. Train models first.",
        }


@router.get("/predictions")
def get_predictions(limit: int = 50, db: Session = Depends(get_db),
                    _user: User = Depends(get_current_user)):
    """Return the most recent AI prediction results."""
    from explainable_ai.xai import explanation_from_json
    preds = queries.get_recent_predictions(db, limit)
    return [
        {
            "prediction_id": p.prediction_id,
            "flow_id": p.flow_id,
            "model_name": p.model_name,
            "prediction": p.prediction_label,
            "confidence": p.confidence,
            "threat_score": p.threat_score,
            "severity": p.severity,
            "attack_type": p.attack_type,
            "recommendation": p.recommendation,
            "xai": explanation_from_json(getattr(p, "explanation_json", None)),
            "time": str(p.prediction_time),
        }
        for p in preds
    ]


@router.post("/simulate-attack")
def simulate_attack(body: SimulateAttackRequest, db: Session = Depends(get_db),
                    _user: User = Depends(get_current_user)):
    """Run a Threat Simulation campaign through Hybrid AI (core SOC module)."""
    try:
        from detection.attack_simulator import list_scenarios, run_simulation
        scenario = body.scenario if body.scenario in list_scenarios() else "Mixed"
        ensure = body.ensure_attack_labels if body.force_demo_label is None else body.force_demo_label
        summary = run_simulation(
            db,
            scenario=scenario,
            count=body.count,
            create_alerts=body.create_alerts,
            block_critical=body.block_critical,
            force_demo_label=ensure,
            send_notifications=body.send_notifications,
        )
        return {
            "status": "success",
            "module": "Threat Simulation",
            "scenario": summary["scenario"],
            "flows_created": summary["flows_created"],
            "predictions": summary["predictions"],
            "attacks_detected": summary["attacks_detected"],
            "alerts_created": summary["alerts_created"],
            "ips_blocked": summary["ips_blocked"],
            "forced_labels": summary["forced_labels"],
            "results": summary["results"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get("/alerts")
def get_alerts(status: Optional[str] = None, limit: int = 100,
               db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Return alerts, optionally filtered by status."""
    alerts = queries.get_alerts(db, status=status, limit=limit)
    return [
        {
            "alert_id": a.alert_id,
            "alert_type": a.alert_type,
            "priority": a.priority,
            "status": a.status,
            "message": a.message,
            "created_at": str(a.created_at),
        }
        for a in alerts
    ]


@router.put("/alerts/{alert_id}/status")
def update_alert_status(alert_id: int, new_status: str, db: Session = Depends(get_db),
                        _user: User = Depends(get_current_user)):
    """Update an alert's investigation status."""
    from database.models import Alert
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = new_status
    db.commit()
    return {"status": "updated"}


# ── Threat Intelligence ───────────────────────────────────────────────────────

@router.get("/threat/{ip_address}")
def lookup_threat(ip_address: str, _user: User = Depends(get_current_user)):
    """Look up external threat intelligence for an IP address."""
    try:
        from threat_intelligence.ip_lookup import lookup_ip
        return lookup_ip(ip_address)
    except Exception as e:
        return {"ip": ip_address, "error": str(e)}


# ── IP Blocking ───────────────────────────────────────────────────────────────

@router.post("/block-ip")
def block_ip_endpoint(body: BlockIPRequest, db: Session = Depends(get_db),
                      _user: User = Depends(require_role(["Administrator", "Security Analyst"]))):
    """Block an IP address (Admin / Analyst only)."""
    blocked = queries.block_ip(db, body.ip_address, reason=body.reason,
                               blocked_by=_user.username)
    queries.add_log(db, f"IP {body.ip_address} blocked", user_id=_user.user_id)
    return {"status": "Blocked", "ip": body.ip_address, "block_id": blocked.block_id}


@router.delete("/unblock-ip/{ip_address}")
def unblock_ip_endpoint(ip_address: str, db: Session = Depends(get_db),
                        _user: User = Depends(require_role(["Administrator"]))):
    """Unblock an IP address (Administrator only)."""
    success = queries.unblock_ip(db, ip_address)
    if not success:
        raise HTTPException(status_code=404, detail="IP not found in active blocklist")
    queries.add_log(db, f"IP {ip_address} unblocked", user_id=_user.user_id)
    return {"status": "Removed", "ip": ip_address}


@router.get("/blocked-ips")
def get_blocked_ips(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Return all currently blocked IP addresses."""
    ips = queries.get_blocked_ips(db)
    return [
        {
            "block_id": b.block_id,
            "ip": b.ip_address,
            "attack_type": b.attack_type,
            "blocked_at": str(b.blocked_at),
            "status": b.status,
            "reason": b.reason,
        }
        for b in ips
    ]


# ── Model Performance ─────────────────────────────────────────────────────────

@router.get("/models/performance")
def get_models_performance(db: Session = Depends(get_db),
                           _user: User = Depends(get_current_user)):
    """Return performance metrics for all trained AI models."""
    models = queries.get_all_models(db)
    return [
        {
            "model_name": m.model_name,
            "version": m.version,
            "accuracy": m.accuracy,
            "precision": m.precision_score,
            "recall": m.recall,
            "f1_score": m.f1_score,
            "status": m.status,
        }
        for m in models
    ]


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get("/reports/export")
def export_report(report_type: str = "daily", db: Session = Depends(get_db),
                  _user: User = Depends(get_current_user)):
    """Generate and export a security report."""
    try:
        from reports.report_generator import generate_daily_report
        path = generate_daily_report(db)
        return {"status": "generated", "path": path}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ── Dashboard Stats ───────────────────────────────────────────────────────────

@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db),
                    _user: User = Depends(get_current_user)):
    """Return aggregated KPIs for the main dashboard."""
    from database.models import NetworkFlow, Prediction, Alert, BlockedIP

    total_flows = db.query(NetworkFlow).count()
    total_predictions = db.query(Prediction).count()
    total_alerts = db.query(Alert).count()
    active_alerts = db.query(Alert).filter(Alert.status == "New").count()
    blocked_count = db.query(BlockedIP).filter(BlockedIP.status == "Active").count()

    attack_preds = db.query(Prediction).filter(Prediction.prediction_label != "Normal").count()
    normal_preds = db.query(Prediction).filter(Prediction.prediction_label == "Normal").count()
    avg_threat = db.query(Prediction).with_entities(
        db.query(Prediction).session.query(
            __import__("sqlalchemy").func.avg(Prediction.threat_score)
        ).scalar()
    ) if total_predictions > 0 else 0

    from sqlalchemy import func
    avg_threat_val = db.query(func.avg(Prediction.threat_score)).scalar() or 0

    return {
        "total_flows": total_flows,
        "total_predictions": total_predictions,
        "total_alerts": total_alerts,
        "active_alerts": active_alerts,
        "blocked_ips": blocked_count,
        "attack_count": attack_preds,
        "normal_count": normal_preds,
        "average_threat_score": round(float(avg_threat_val), 2),
    }


# ── Notifications ─────────────────────────────────────────────────────────────

@router.post("/notify")
def send_notification(body: NotifyRequest, _user: User = Depends(get_current_user)):
    """Dispatch a notification through the specified channel."""
    try:
        from alerts.notification import notify
        success = notify(body.notif_type, body.message)
        return {"status": "sent" if success else "failed"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ── Health Check (unauthenticated) ────────────────────────────────────────────

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Return operational status of database, AI engine, SOAR, MITRE, online learning."""
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "Connected"
    except Exception:
        db_status = "Disconnected"

    ai_status = "Ready"
    try:
        from config import MODELS_DIR
        if not (MODELS_DIR / "random_forest.pkl").exists():
            ai_status = "Models not trained"
    except Exception:
        ai_status = "Unknown"

    payload = {
        "status": "online",
        "database": db_status,
        "ai_engine": ai_status,
        "timestamp": str(datetime.utcnow()),
    }
    try:
        from ops.health import collect_health
        payload["readiness"] = collect_health()
    except Exception as exc:
        payload["readiness_error"] = str(exc)
    return payload


@router.post("/ops/heal")
def ops_heal(_user: User = Depends(require_role(["Administrator"]))):
    """Run safe auto-heal actions (dirs + DB init). Admin only."""
    from ops.health import try_auto_heal
    return try_auto_heal()


@router.get("/soc/mitre")
def soc_mitre(_user: User = Depends(get_current_user)):
    """List MITRE ATT&CK mappings for attack labels."""
    from threat_intelligence.mitre_map import list_all_mappings
    return {"mappings": list_all_mappings()}


@router.get("/soc/playbooks")
def soc_playbooks(_user: User = Depends(get_current_user)):
    """List SOAR playbooks."""
    from soar.playbooks import list_playbooks
    return {"playbooks": list_playbooks()}


@router.get("/soc/online-learning")
def soc_online_learning(_user: User = Depends(get_current_user)):
    """Online learning buffer / model status."""
    from training.online_learning import get_online_status
    return get_online_status()


@router.post("/soc/online-learning/train")
def soc_online_train(_user: User = Depends(require_role(["Administrator", "Security Analyst"]))):
    """Force an incremental online train from the buffer."""
    from training.online_learning import maybe_incremental_train
    return maybe_incremental_train(force=True)


# ── Settings (Admin only) ─────────────────────────────────────────────────────

@router.get("/settings/{name}")
def get_setting(name: str, db: Session = Depends(get_db),
                _user: User = Depends(require_role(["Administrator"]))):
    """Retrieve a system setting by name."""
    val = queries.get_setting(db, name)
    return {"setting_name": name, "value": val}


@router.post("/settings")
def update_setting(body: SettingUpdate, db: Session = Depends(get_db),
                   _user: User = Depends(require_role(["Administrator"]))):
    """Create or update a system configuration setting."""
    queries.set_setting(db, body.setting_name, body.setting_value)
    return {"status": "updated"}


# ── NDR 2.0: sensors, hunt, incidents, IOC, assets, copilot, cloud ────────────

class SensorIngest(BaseModel):
    packets_sec: float = 0.0
    dropped: int = 0
    interfaces: str = ""
    flows: Optional[list] = None


class HuntRequest(BaseModel):
    ip: str = ""
    attack: str = ""
    protocol: str = ""
    limit: int = 100


class IOCCreate(BaseModel):
    ioc_type: str
    value: str
    source: str = "api"
    severity: str = "High"
    description: str = ""


class FeedbackBody(BaseModel):
    alert_id: int
    verdict: str
    comment: str = ""


class CopilotBody(BaseModel):
    question: str = ""
    incident_id: Optional[int] = None
    attack_type: str = ""
    severity: str = "High"
    source_ip: str = ""


@router.post("/sensors/ingest")
def ingest_sensor(body: SensorIngest, api_key: str, db: Session = Depends(get_db)):
    from monitoring.sensors import heartbeat
    if not heartbeat(api_key, body.packets_sec, body.dropped, body.interfaces):
        raise HTTPException(status_code=401, detail="invalid sensor key")
    inserted = 0
    for flow in body.flows or []:
        if not isinstance(flow, dict):
            continue
        queries.insert_flow(
            db,
            source_ip=str(flow.get("source_ip") or flow.get("src_ip") or "0.0.0.0"),
            destination_ip=str(flow.get("destination_ip") or flow.get("dst_ip") or "0.0.0.0"),
            source_port=int(flow.get("source_port") or flow.get("src_port") or 0),
            destination_port=int(flow.get("destination_port") or flow.get("dst_port") or 0),
            protocol=str(flow.get("protocol") or "TCP"),
            duration=float(flow.get("duration") or 0),
            packets=int(flow.get("packets") or flow.get("packet_count") or 0),
            bytes_total=int(flow.get("bytes_total") or flow.get("byte_count") or 0),
        )
        inserted += 1
    return {"status": "ok", "flows": inserted}


@router.get("/sensors")
def api_list_sensors(_user: User = Depends(get_current_user)):
    from monitoring.sensors import list_sensors
    return {"sensors": list_sensors()}


@router.post("/hunt")
def api_hunt(body: HuntRequest, _user: User = Depends(get_current_user)):
    from soc.hunting import hunt
    return hunt(ip=body.ip, attack=body.attack, protocol=body.protocol, limit=body.limit)


@router.get("/incidents")
def api_incidents(status: Optional[str] = None, _user: User = Depends(get_current_user)):
    from detection.correlation import list_incidents
    return {"incidents": list_incidents(status=status)}


@router.put("/incidents/{incident_id}")
def api_update_incident(incident_id: int, new_status: str, notes: str = "",
                        _user: User = Depends(require_role(["Administrator", "Security Analyst"]))):
    from detection.correlation import set_incident_status
    ok = set_incident_status(incident_id, new_status, owner=_user.username, notes=notes)
    if not ok:
        raise HTTPException(status_code=404, detail="incident not found")
    return {"status": "updated"}


@router.get("/assets")
def api_assets(_user: User = Depends(get_current_user)):
    from assets.inventory import list_assets
    return {"assets": list_assets()}


@router.get("/iocs")
def api_iocs(_user: User = Depends(get_current_user)):
    from threat_intelligence.ioc_manager import list_iocs
    return {"iocs": list_iocs(active_only=False)}


@router.post("/iocs")
def api_add_ioc(body: IOCCreate, _user: User = Depends(require_role(["Administrator", "Security Analyst"]))):
    from threat_intelligence.ioc_manager import add_ioc
    from ops.audit import audit
    rec = add_ioc(body.ioc_type, body.value, body.source, body.severity, body.description)
    audit("ioc_added", f"{body.ioc_type}:{body.value}", user_id=_user.user_id)
    return rec


@router.post("/alerts/{alert_id}/feedback")
def api_feedback(alert_id: int, body: FeedbackBody,
                 _user: User = Depends(require_role(["Administrator", "Security Analyst"]))):
    from soc.feedback import record_feedback
    return record_feedback(alert_id, body.verdict, analyst=_user.username, comment=body.comment)


@router.post("/copilot")
def api_copilot(body: CopilotBody, _user: User = Depends(get_current_user)):
    from soc.copilot import nl_query, summarize_incident, recommend_response, explain_attack
    out: dict = {}
    if body.question:
        out["hunt"] = nl_query(body.question)
    if body.incident_id:
        out["summary"] = summarize_incident(int(body.incident_id))
    if body.attack_type:
        out["recommend"] = recommend_response(body.attack_type, body.severity, body.source_ip)
        out["explain"] = explain_attack(body.attack_type)
    return out


@router.get("/webhooks")
def api_webhooks(_user: User = Depends(require_role(["Administrator"]))):
    from alerts.webhooks import list_webhooks
    return {"webhooks": list_webhooks()}


@router.post("/cloud/ingest")
async def api_cloud_ingest(file: UploadFile = File(...),
                           _user: User = Depends(require_role(["Administrator", "Security Analyst"]))):
    from cloud.ingest import parse_payload, ingest_rows
    text = (await file.read()).decode("utf-8", errors="ignore")
    rows = parse_payload(file.filename or "upload.csv", text)
    n = ingest_rows(rows)
    return {"status": "ok", "rows": n, "cloud_hint": file.filename}


@router.get("/forensics/pcap")
def api_pcap(_user: User = Depends(get_current_user)):
    from monitoring.pcap_store import list_evidence
    return {"evidence": list_evidence()}


@router.post("/response/block")
def api_temp_block(body: BlockIPRequest, duration: str = "1h",
                   _user: User = Depends(require_role(["Administrator", "Security Analyst"]))):
    from response.policy import queue_or_block
    return queue_or_block(body.ip_address, reason=body.reason, duration=duration, blocked_by=_user.username)


@router.post("/response/rollback/{ip_address}")
def api_rollback(ip_address: str, _user: User = Depends(require_role(["Administrator"]))):
    from response.policy import rollback_block
    ok = rollback_block(ip_address)
    if not ok:
        raise HTTPException(status_code=404, detail="not blocked")
    return {"status": "removed", "ip": ip_address}


@router.get("/metrics/realtime")
def api_realtime(_user: User = Depends(get_current_user)):
    from ops.retention import capture_health
    return capture_health()


@router.get("/audit")
def api_audit(_user: User = Depends(require_role(["Administrator"]))):
    from ops.audit import list_audit
    return {"logs": list_audit(200)}

