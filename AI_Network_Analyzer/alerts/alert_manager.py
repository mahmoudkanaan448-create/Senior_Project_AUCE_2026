"""
Central alert management – evaluates predictions and dispatches responses.

Medium+ creates an alert, then runs the matching SOAR playbook
(Telegram, local notify, MITRE enrichment, optional IP block, online sample).
Critical / playbook rules may auto-block the source IP.
"""
import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.queries import insert_alert
from threat_intelligence.mitre_map import format_mitre_short, map_attack_to_mitre

logger = logging.getLogger(__name__)

SEVERITY_LEVELS = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}


def get_severity_actions(severity: str) -> dict:
    """Return action flags for a severity level (baseline before playbook)."""
    level = SEVERITY_LEVELS.get(severity, 0)
    return {
        "create_alert": level >= 2,    # Medium+
        "send_telegram": level >= 2,
        "block_ip": level >= 4,        # Critical baseline; playbooks may lower
    }


def process_alert(
    prediction_result: dict,
    db_session,
    *,
    apply_os_firewall: bool = True,
    send_notifications: bool = True,
    allow_db_block: bool = True,
) -> dict:
    """Process a fused prediction and trigger SOAR playbook responses."""
    outcome = {
        "alert_created": False,
        "telegram_sent": False,
        "telegram_detail": "",
        "ip_blocked": False,
        "playbook": "",
        "mitre": {},
        "steps_run": [],
    }

    try:
        severity = prediction_result.get("severity", "Low")
        actions = get_severity_actions(severity)
        source_ip = prediction_result.get("source_ip", "unknown")
        label = prediction_result.get("prediction_label", "Unknown")
        confidence = prediction_result.get("confidence", 0.0)
        conf_ratio = (
            confidence / 100.0
            if isinstance(confidence, (int, float)) and confidence > 1
            else float(confidence or 0)
        )
        attack_type = prediction_result.get("attack_type", label)
        threat_score = prediction_result.get("threat_score", 0.0)
        prediction_id = prediction_result.get("prediction_id")

        if not actions["create_alert"]:
            logger.debug("Severity %s – no alert needed", severity)
            return outcome

        mitre = map_attack_to_mitre(label)
        outcome["mitre"] = mitre
        alert_msg = (
            f"[{severity}] {label} detected from {source_ip} "
            f"(confidence: {conf_ratio:.1%}, threat_score: {threat_score:.1f}) "
            f"| {format_mitre_short(label)}"
        )
        alert = insert_alert(
            db=db_session,
            prediction_id=prediction_id,
            alert_type=attack_type,
            priority=severity,
            status="New",
            message=alert_msg,
        )
        outcome["alert_created"] = True
        logger.info("Alert #%s created – %s", alert.alert_id, alert_msg)

        # SOAR playbook (Telegram / local notify / block / online queue / MITRE)
        try:
            from soar.engine import run_playbook
            pb = run_playbook(
                attack_label=str(label),
                severity=str(severity),
                source_ip=str(source_ip),
                prediction_result=prediction_result,
                db_session=db_session,
                alert_id=alert.alert_id,
                apply_os_firewall=apply_os_firewall,
                send_notifications=send_notifications,
                allow_db_block=allow_db_block,
            )
            outcome["playbook"] = pb.get("playbook") or ""
            outcome["steps_run"] = pb.get("steps_run") or []
            outcome["telegram_sent"] = bool(pb.get("telegram_sent"))
            outcome["telegram_detail"] = pb.get("telegram_detail") or ""
            outcome["ip_blocked"] = bool(pb.get("ip_blocked"))
            if pb.get("mitre"):
                outcome["mitre"] = pb["mitre"]
            try:
                from ndr_core.pipeline import enrich_and_respond
                extra = enrich_and_respond(
                    flow={
                        "source_ip": source_ip,
                        "destination_ip": prediction_result.get("destination_ip", ""),
                        "destination_port": prediction_result.get("destination_port", 0),
                        "packet_rate": prediction_result.get("packet_rate", 0),
                        "flow_rate": prediction_result.get("flow_rate", 0),
                        "byte_count": prediction_result.get("byte_count", 0),
                        "packet_count": prediction_result.get("packet_count", 0),
                        "dns_query": prediction_result.get("dns_query", ""),
                        "features": prediction_result.get("features") or {},
                    },
                    prediction=prediction_result,
                    alert_id=alert.alert_id,
                    packets=prediction_result.get("packets"),
                )
                outcome["incident"] = extra.get("incident")
                outcome["specialists"] = extra.get("specialists")
                outcome["ioc_hits"] = extra.get("ioc_hits")
            except Exception as pipe_exc:
                logger.warning("NDR pipeline skipped: %s", pipe_exc)
        except Exception as exc:
            # Fallback to legacy path so alerts still notify if SOAR breaks
            logger.error("SOAR playbook failed, using legacy notify: %s", exc)
            outcome["telegram_detail"] = f"soar_error:{exc}"
            try:
                from alerts.local_notify import notify_from_alert_fields
                notify_from_alert_fields(severity, str(label), str(source_ip))
            except Exception:
                pass
            if send_notifications:
                try:
                    from alerts.telegram_alert import send_telegram_alert_detailed
                    from database.queries import insert_notification
                    tg_msg = (
                        f"AI-NDR ALERT [{severity}]\n"
                        f"Attack: {label}\n"
                        f"Source IP: {source_ip}\n"
                        f"Confidence: {conf_ratio:.1%}\n"
                        f"Threat Score: {threat_score:.1f}/10\n"
                        f"{format_mitre_short(label)}\n"
                        f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    )
                    ok, detail = send_telegram_alert_detailed(tg_msg, verify_bot=False)
                    outcome["telegram_sent"] = ok
                    outcome["telegram_detail"] = detail
                    insert_notification(
                        db=db_session,
                        alert_id=alert.alert_id,
                        notif_type="Telegram",
                        message=tg_msg if ok else f"{tg_msg}\n\nERROR: {detail}",
                        delivery_status="Sent" if ok else "Failed",
                    )
                except Exception as tg_exc:
                    logger.error("Legacy telegram failed: %s", tg_exc)
            if allow_db_block and actions["block_ip"]:
                try:
                    reason = f"Auto-blocked: {attack_type} (threat_score={threat_score:.1f})"
                    if apply_os_firewall:
                        from firewall.ip_block import block_ip_address
                        outcome["ip_blocked"] = block_ip_address(source_ip, reason=reason)
                    else:
                        from database.queries import block_ip
                        block_ip(
                            db_session,
                            ip_address=source_ip,
                            attack_type=attack_type,
                            blocked_by="alert_manager_fallback",
                            reason=reason + " [lab/safe]",
                        )
                        outcome["ip_blocked"] = True
                except Exception as blk_exc:
                    logger.error("Legacy block failed: %s", blk_exc)

    except Exception as exc:
        logger.error("Error processing alert: %s", exc)
        outcome["telegram_detail"] = str(exc)

    return outcome
