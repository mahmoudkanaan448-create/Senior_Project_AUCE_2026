"""
Unattended 24/7 capture loop for a company sensor / gateway host.

Writes real flows to the database. Optional auto-detect.
Usage:
  python -m monitoring.capture_daemon
  python -m monitoring.capture_daemon --iface "Wi-Fi" --detect
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import LOGS_DIR

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [capture] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "capture_daemon.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("capture")


def _save_flows(flows: list[dict]) -> int:
    from database.database import SessionLocal, init_db
    from database.models import NetworkFlow
    from monitoring.live_capture import protocol_name

    if not flows:
        return 0
    init_db()
    db = SessionLocal()
    saved = 0
    try:
        for flow in flows:
            proto = protocol_name(flow.get("protocol", 0))
            src_ip = str(flow.get("source_ip", "0.0.0.0"))
            dst_ip = str(flow.get("destination_ip", "0.0.0.0"))
            src_port = int(flow.get("source_port", 0) or 0)
            dst_port = int(flow.get("destination_port", 0) or 0)
            exists = (
                db.query(NetworkFlow)
                .filter(
                    NetworkFlow.source_ip == src_ip,
                    NetworkFlow.destination_ip == dst_ip,
                    NetworkFlow.source_port == src_port,
                    NetworkFlow.destination_port == dst_port,
                    NetworkFlow.protocol == proto,
                )
                .order_by(NetworkFlow.timestamp.desc())
                .first()
            )
            if exists and exists.timestamp and (datetime.utcnow() - exists.timestamp).total_seconds() < 30:
                exists.packets = int(flow.get("packet_count", exists.packets or 1))
                exists.bytes_total = int(flow.get("byte_count", exists.bytes_total or 0))
                exists.packet_rate = float(flow.get("packet_rate", 0) or 0)
                exists.flow_rate = float(flow.get("flow_rate", 0) or 0)
                exists.duration = float(flow.get("duration", 0) or 0)
                exists.timestamp = datetime.utcnow()
            else:
                db.add(NetworkFlow(
                    timestamp=datetime.utcnow(),
                    source_ip=src_ip,
                    destination_ip=dst_ip,
                    source_port=src_port,
                    destination_port=dst_port,
                    protocol=proto,
                    duration=float(flow.get("duration", 0) or 0),
                    packets=int(flow.get("packet_count", 1) or 1),
                    bytes_total=int(flow.get("byte_count", 0) or 0),
                    packet_rate=float(flow.get("packet_rate", 0) or 0),
                    flow_rate=float(flow.get("flow_rate", 0) or 0),
                    features_json=json.dumps(
                        {k: v for k, v in flow.items() if k != "packets"},
                        default=str,
                    ),
                ))
                saved += 1
            try:
                from assets.inventory import upsert_from_flow
                upsert_from_flow(src_ip, dst_ip, dst_port)
            except Exception:
                pass
        db.commit()
    finally:
        db.close()
    return saved


def _auto_detect(limit: int = 40) -> int:
    from config import MODELS_DIR
    from database.database import SessionLocal
    from database.models import NetworkFlow, Prediction
    from database import queries
    from detection.attack_detector import load_models, predict_single
    from detection.decision_engine import fuse_decisions
    from explainable_ai.xai import explain_with_models, explanation_to_json

    db = SessionLocal()
    counted = 0
    try:
        models = load_models(str(MODELS_DIR))
        unprocessed = (
            db.query(NetworkFlow)
            .filter(~NetworkFlow.flow_id.in_(
                db.query(Prediction.flow_id).filter(Prediction.flow_id.isnot(None))
            ))
            .limit(limit)
            .all()
        )
        for flow in unprocessed:
            features = {}
            if flow.features_json:
                try:
                    features = json.loads(flow.features_json)
                except Exception:
                    pass
            features.update({
                "duration": flow.duration or 0,
                "packet_count": flow.packets or 0,
                "byte_count": flow.bytes_total or 0,
                "packet_rate": (flow.packets or 0) / max(flow.duration or 0.001, 0.001),
                "flow_rate": (flow.bytes_total or 0) / max(flow.duration or 0.001, 0.001),
            })
            raw = predict_single(features, models)
            result = fuse_decisions(raw)
            xai = explain_with_models(
                features,
                result["final_label"],
                models,
                model_name=str(result.get("best_model") or "random_forest"),
                confidence_score=float(result.get("confidence") or 0),
                threat_score=float(result.get("threat_score") or 0),
            )
            pred = queries.insert_prediction(
                db,
                flow_id=flow.flow_id,
                model_name=result.get("best_model", "Hybrid"),
                prediction_label=result["final_label"],
                confidence=result["confidence"],
                threat_score=result["threat_score"],
                severity=result["severity"],
                attack_type=result["final_label"],
                recommendation=xai.get("recommended_action") or "",
                explanation_json=explanation_to_json(xai),
            )
            if str(result.get("severity")) in ("Medium", "High", "Critical"):
                try:
                    from alerts.alert_manager import process_alert
                    process_alert(
                        {
                            "severity": result["severity"],
                            "source_ip": flow.source_ip or "unknown",
                            "destination_ip": flow.destination_ip or "",
                            "destination_port": flow.destination_port or 0,
                            "prediction_label": result["final_label"],
                            "confidence": result["confidence"],
                            "attack_type": result["final_label"],
                            "threat_score": result["threat_score"],
                            "prediction_id": pred.prediction_id,
                            "features": features,
                            "xai": xai,
                        },
                        db,
                        apply_os_firewall=False,
                        send_notifications=True,
                    )
                except Exception:
                    pass
            counted += 1
        return counted
    finally:
        db.close()


def run(iface: str = "auto", timeout: float = 2.0, detect: bool = False) -> None:
    from monitoring.flow_builder import build_flows
    from monitoring.live_capture import capture_live

    logger.info("24/7 capture starting iface=%s detect=%s", iface, detect)
    cycle = 0
    while True:
        try:
            packets, mode = capture_live(interface=iface, timeout=timeout)
            flows = build_flows(packets) if packets else []
            saved = _save_flows(flows)
            if saved or packets:
                logger.info("mode=%s packets=%s flows_saved=%s", mode, len(packets), saved)
            try:
                from monitoring.sensors import heartbeat
                heartbeat("local", packets_sec=len(packets) / max(timeout, 0.001), interfaces=iface)
            except Exception:
                pass
            cycle += 1
            if detect and cycle % 5 == 0:
                n = _auto_detect()
                if n:
                    logger.info("auto-detected %s flows", n)
        except KeyboardInterrupt:
            logger.info("capture stopped")
            return
        except Exception as exc:
            logger.exception("capture cycle error: %s", exc)
            time.sleep(3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI-NDR 24/7 capture daemon")
    parser.add_argument("--iface", default="auto")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--detect", action="store_true")
    args = parser.parse_args()
    run(iface=args.iface, timeout=args.timeout, detect=args.detect)
