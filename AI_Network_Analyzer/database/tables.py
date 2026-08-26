"""ORM table classes – defined once per process (Streamlit-safe)."""

from __future__ import annotations

import sys
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from database.database import Base, heal_mapper_registry

_CACHE = "_aindr_table_classes"
_READY = "_aindr_tables_initialized"
_NEEDED = (
    "User", "NetworkFlow", "Prediction", "Alert", "ThreatIntelligence",
    "BlockedIP", "Notification", "AIModel", "ModelHistory", "IncidentReport",
    "SystemLog", "Setting", "Sensor", "Asset", "IOC", "Allowlist",
    "SocIncident", "AlertFeedback", "PendingAction", "Webhook",
    "PcapEvidence", "HostBaseline",
)


class _Model(Base):
    """Shared declarative base – extend_existing avoids duplicate-table crashes."""

    __abstract__ = True
    __table_args__ = {"extend_existing": True}


def _registry_by_name() -> dict:
    found: dict = {}
    for mapper in list(Base.registry.mappers):
        name = mapper.class_.__name__
        if name not in found:
            found[name] = mapper.class_
    return found


def _load_classes() -> dict:
    heal_mapper_registry()
    cached = getattr(sys, _CACHE, None)
    if isinstance(cached, dict) and all(name in cached for name in _NEEDED):
        return cached

    existing = _registry_by_name()
    if all(name in existing for name in _NEEDED):
        out = {name: existing[name] for name in _NEEDED}
        setattr(sys, _CACHE, out)
        return out

    # MetaData already has tables (Streamlit rerun) – never register classes again.
    if Base.metadata.tables:
        if existing:
            out = {name: existing[name] for name in _NEEDED if name in existing}
            if out:
                setattr(sys, _CACHE, out)
                return out
        if isinstance(cached, dict) and cached:
            return cached

    out = _build()
    setattr(sys, _CACHE, out)
    return out


def _build() -> dict:
    class User(_Model):
        __tablename__ = "users"
        user_id = Column(Integer, primary_key=True, autoincrement=True)
        full_name = Column(String(120), nullable=False)
        username = Column(String(60), unique=True, nullable=False)
        email = Column(String(120), unique=True, nullable=False)
        password_hash = Column(String(256), nullable=False)
        role = Column(String(30), default="Viewer")
        created_at = Column(DateTime, default=datetime.utcnow)
        last_login = Column(DateTime, nullable=True)
        status = Column(String(20), default="active")

    class NetworkFlow(_Model):
        __tablename__ = "network_flows"
        flow_id = Column(Integer, primary_key=True, autoincrement=True)
        timestamp = Column(DateTime, default=datetime.utcnow)
        source_ip = Column(String(45))
        destination_ip = Column(String(45))
        source_port = Column(Integer)
        destination_port = Column(Integer)
        protocol = Column(String(10))
        duration = Column(Float, default=0.0)
        packets = Column(Integer, default=0)
        bytes_total = Column(Integer, default=0)
        packet_rate = Column(Float, default=0.0)
        flow_rate = Column(Float, default=0.0)
        features_json = Column(Text, nullable=True)

    class Prediction(_Model):
        __tablename__ = "predictions"
        prediction_id = Column(Integer, primary_key=True, autoincrement=True)
        flow_id = Column(Integer, ForeignKey("network_flows.flow_id"))
        model_name = Column(String(60))
        prediction_label = Column(String(60))
        confidence = Column(Float, default=0.0)
        anomaly_score = Column(Float, nullable=True)
        threat_score = Column(Float, default=0.0)
        severity = Column(String(20), default="Low")
        attack_type = Column(String(60), nullable=True)
        recommendation = Column(Text, nullable=True)
        explanation_json = Column(Text, nullable=True)
        prediction_time = Column(DateTime, default=datetime.utcnow)

    class Alert(_Model):
        __tablename__ = "alerts"
        alert_id = Column(Integer, primary_key=True, autoincrement=True)
        prediction_id = Column(Integer, ForeignKey("predictions.prediction_id"))
        alert_type = Column(String(60))
        priority = Column(String(20), default="Low")
        status = Column(String(20), default="New")
        message = Column(Text, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class ThreatIntelligence(_Model):
        __tablename__ = "threat_intelligence"
        threat_id = Column(Integer, primary_key=True, autoincrement=True)
        prediction_id = Column(Integer, ForeignKey("predictions.prediction_id"), nullable=True)
        ip_address = Column(String(45))
        country = Column(String(60), nullable=True)
        city = Column(String(60), nullable=True)
        isp = Column(String(120), nullable=True)
        asn = Column(String(30), nullable=True)
        reputation = Column(String(30), nullable=True)
        threat_score = Column(Float, default=0.0)
        reports = Column(Integer, default=0)
        blacklisted = Column(Boolean, default=False)
        first_seen = Column(DateTime, default=datetime.utcnow)
        last_seen = Column(DateTime, default=datetime.utcnow)

    class BlockedIP(_Model):
        __tablename__ = "blocked_ips"
        block_id = Column(Integer, primary_key=True, autoincrement=True)
        ip_address = Column(String(45), nullable=False)
        attack_type = Column(String(60), nullable=True)
        blocked_at = Column(DateTime, default=datetime.utcnow)
        duration = Column(String(30), default="permanent")
        blocked_by = Column(String(60), default="system")
        status = Column(String(20), default="Active")
        reason = Column(Text, nullable=True)

    class Notification(_Model):
        __tablename__ = "notifications"
        notification_id = Column(Integer, primary_key=True, autoincrement=True)
        alert_id = Column(Integer, ForeignKey("alerts.alert_id"), nullable=True)
        notif_type = Column(String(30))
        recipient = Column(String(120), nullable=True)
        message = Column(Text, nullable=True)
        delivery_status = Column(String(20), default="Pending")
        sent_at = Column(DateTime, default=datetime.utcnow)

    class AIModel(_Model):
        __tablename__ = "ai_models"
        model_id = Column(Integer, primary_key=True, autoincrement=True)
        model_name = Column(String(60), unique=True, nullable=False)
        version = Column(String(20), default="1.0")
        accuracy = Column(Float, default=0.0)
        precision_score = Column(Float, default=0.0)
        recall = Column(Float, default=0.0)
        f1_score = Column(Float, default=0.0)
        training_date = Column(DateTime, default=datetime.utcnow)
        status = Column(String(20), default="Active")

    class ModelHistory(_Model):
        __tablename__ = "model_history"
        history_id = Column(Integer, primary_key=True, autoincrement=True)
        model_id = Column(Integer, ForeignKey("ai_models.model_id"), nullable=True)
        model_name = Column(String(60))
        dataset = Column(String(120), nullable=True)
        epochs = Column(Integer, nullable=True)
        training_time = Column(Float, nullable=True)
        accuracy = Column(Float, default=0.0)
        precision_score = Column(Float, default=0.0)
        recall = Column(Float, default=0.0)
        f1_score = Column(Float, default=0.0)
        trained_at = Column(DateTime, default=datetime.utcnow)

    class IncidentReport(_Model):
        __tablename__ = "incident_reports"
        incident_id = Column(Integer, primary_key=True, autoincrement=True)
        prediction_id = Column(Integer, ForeignKey("predictions.prediction_id"), nullable=True)
        summary = Column(Text, nullable=True)
        investigation = Column(Text, nullable=True)
        resolution = Column(Text, nullable=True)
        analyst = Column(String(60), nullable=True)
        status = Column(String(30), default="Open")
        created_at = Column(DateTime, default=datetime.utcnow)
        closed_at = Column(DateTime, nullable=True)

    class SystemLog(_Model):
        __tablename__ = "system_logs"
        log_id = Column(Integer, primary_key=True, autoincrement=True)
        user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
        event = Column(String(200))
        details = Column(Text, nullable=True)
        timestamp = Column(DateTime, default=datetime.utcnow)

    class Setting(_Model):
        __tablename__ = "settings"
        setting_id = Column(Integer, primary_key=True, autoincrement=True)
        setting_name = Column(String(100), unique=True, nullable=False)
        setting_value = Column(Text, nullable=True)
        last_modified = Column(DateTime, default=datetime.utcnow)

    class Sensor(_Model):
        __tablename__ = "sensors"
        sensor_id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String(80), nullable=False)
        site = Column(String(80), default="hq")
        interfaces = Column(String(200), default="")
        api_key = Column(String(80), unique=True, nullable=True)
        status = Column(String(20), default="Online")
        last_seen = Column(DateTime, default=datetime.utcnow)
        packets_sec = Column(Float, default=0.0)
        dropped_packets = Column(Integer, default=0)

    class Asset(_Model):
        __tablename__ = "assets"
        asset_id = Column(Integer, primary_key=True, autoincrement=True)
        ip_address = Column(String(45), unique=True, nullable=False)
        hostname = Column(String(120), nullable=True)
        device_type = Column(String(40), default="Unknown")
        criticality = Column(String(20), default="Normal")
        risk_score = Column(Float, default=0.0)
        first_seen = Column(DateTime, default=datetime.utcnow)
        last_seen = Column(DateTime, default=datetime.utcnow)
        tags = Column(String(200), nullable=True)
        notes = Column(Text, nullable=True)

    class IOC(_Model):
        __tablename__ = "iocs"
        ioc_id = Column(Integer, primary_key=True, autoincrement=True)
        ioc_type = Column(String(20), nullable=False)
        value = Column(String(255), nullable=False)
        source = Column(String(80), default="manual")
        severity = Column(String(20), default="High")
        description = Column(Text, nullable=True)
        active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class Allowlist(_Model):
        __tablename__ = "allowlist"
        allow_id = Column(Integer, primary_key=True, autoincrement=True)
        entry_type = Column(String(20), default="ip")
        value = Column(String(255), nullable=False)
        reason = Column(String(200), default="trusted")
        created_at = Column(DateTime, default=datetime.utcnow)

    class SocIncident(_Model):
        __tablename__ = "soc_incidents"
        incident_id = Column(Integer, primary_key=True, autoincrement=True)
        title = Column(String(200), nullable=False)
        severity = Column(String(20), default="High")
        status = Column(String(30), default="Open")
        owner = Column(String(60), nullable=True)
        source_ip = Column(String(45), nullable=True)
        attack_chain = Column(String(200), nullable=True)
        alert_ids = Column(Text, nullable=True)
        summary = Column(Text, nullable=True)
        notes = Column(Text, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class AlertFeedback(_Model):
        __tablename__ = "alert_feedback"
        feedback_id = Column(Integer, primary_key=True, autoincrement=True)
        alert_id = Column(Integer, nullable=True)
        verdict = Column(String(20), nullable=False)
        analyst = Column(String(60), nullable=True)
        comment = Column(Text, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class PendingAction(_Model):
        __tablename__ = "pending_actions"
        action_id = Column(Integer, primary_key=True, autoincrement=True)
        action_type = Column(String(40), default="block_ip")
        target = Column(String(120), nullable=False)
        reason = Column(Text, nullable=True)
        status = Column(String(20), default="Pending")
        requested_by = Column(String(60), default="system")
        created_at = Column(DateTime, default=datetime.utcnow)

    class Webhook(_Model):
        __tablename__ = "webhooks"
        webhook_id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String(80), nullable=False)
        url = Column(Text, nullable=False)
        event = Column(String(40), default="alert")
        enabled = Column(Boolean, default=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class PcapEvidence(_Model):
        __tablename__ = "pcap_evidence"
        evidence_id = Column(Integer, primary_key=True, autoincrement=True)
        path = Column(String(260), nullable=False)
        source_ip = Column(String(45), nullable=True)
        alert_id = Column(Integer, nullable=True)
        packet_count = Column(Integer, default=0)
        created_at = Column(DateTime, default=datetime.utcnow)

    class HostBaseline(_Model):
        __tablename__ = "host_baselines"
        baseline_id = Column(Integer, primary_key=True, autoincrement=True)
        ip_address = Column(String(45), unique=True, nullable=False)
        avg_packet_rate = Column(Float, default=0.0)
        avg_byte_rate = Column(Float, default=0.0)
        typical_ports = Column(Text, nullable=True)
        samples = Column(Integer, default=0)
        drift_score = Column(Float, default=0.0)
        updated_at = Column(DateTime, default=datetime.utcnow)

    # No User↔SystemLog ORM link (was causing duplicate SystemLog registry errors).
    NetworkFlow.prediction = relationship(Prediction, back_populates="flow", uselist=False)
    Prediction.flow = relationship(NetworkFlow, back_populates="prediction")
    Prediction.alerts = relationship(Alert, back_populates="prediction")
    Prediction.threat_intel = relationship(ThreatIntelligence, back_populates="prediction", uselist=False)
    Prediction.incident = relationship(IncidentReport, back_populates="prediction", uselist=False)
    Alert.prediction = relationship(Prediction, back_populates="alerts")
    Alert.notifications = relationship(Notification, back_populates="alert")
    ThreatIntelligence.prediction = relationship(Prediction, back_populates="threat_intel")
    Notification.alert = relationship(Alert, back_populates="notifications")
    IncidentReport.prediction = relationship(Prediction, back_populates="incident")

    return {
        "User": User,
        "NetworkFlow": NetworkFlow,
        "Prediction": Prediction,
        "Alert": Alert,
        "ThreatIntelligence": ThreatIntelligence,
        "BlockedIP": BlockedIP,
        "Notification": Notification,
        "AIModel": AIModel,
        "ModelHistory": ModelHistory,
        "IncidentReport": IncidentReport,
        "SystemLog": SystemLog,
        "Setting": Setting,
        "Sensor": Sensor,
        "Asset": Asset,
        "IOC": IOC,
        "Allowlist": Allowlist,
        "SocIncident": SocIncident,
        "AlertFeedback": AlertFeedback,
        "PendingAction": PendingAction,
        "Webhook": Webhook,
        "PcapEvidence": PcapEvidence,
        "HostBaseline": HostBaseline,
    }


if getattr(sys, _READY, False) and isinstance(getattr(sys, _CACHE, None), dict):
    heal_mapper_registry()
    _loaded = getattr(sys, _CACHE)
else:
    _loaded = _load_classes()
    setattr(sys, _READY, True)

globals().update(_loaded)
