"""
SOAR playbook engine – executes response steps for an alert context.

Designed to wrap (not replace) alert_manager.process_alert internals.
All steps are best-effort; failures are recorded, never crash the pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from soar.playbooks import get_playbook

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}


def _sev_ok(current: str, minimum: Optional[str]) -> bool:
    if not minimum:
        return True
    return _SEVERITY_RANK.get(current, 0) >= _SEVERITY_RANK.get(minimum, 0)


def run_playbook(
    *,
    attack_label: str,
    severity: str,
    source_ip: str,
    prediction_result: Dict[str, Any],
    db_session,
    alert_id: Optional[int] = None,
    apply_os_firewall: bool = True,
    send_notifications: bool = True,
    allow_db_block: bool = True,
) -> Dict[str, Any]:
    """
    Execute the playbook for attack_label.

    Returns a result dict with steps_run, mitre, ti, blocked, telegram, etc.
    Does NOT create the alert itself when called after alert creation –
    pass alert_id and skip create_alert via already_created flag in context.
    """
    playbook = get_playbook(attack_label)
    result: Dict[str, Any] = {
        "playbook": playbook.get("name"),
        "playbook_key": attack_label if attack_label in ("default",) or True else attack_label,
        "steps_run": [],
        "steps_skipped": [],
        "mitre": {},
        "ti": {},
        "telegram_sent": False,
        "telegram_detail": "",
        "ip_blocked": False,
        "online_queued": False,
    }

    # Attach resolved key
    from soar.playbooks import PLAYBOOKS
    result["playbook_key"] = attack_label if attack_label in PLAYBOOKS else "default"

    if not _sev_ok(severity, playbook.get("min_severity")):
        result["steps_skipped"].append("playbook_below_min_severity")
        return result

    ctx = {
        "attack_label": attack_label,
        "severity": severity,
        "source_ip": source_ip,
        "prediction_result": prediction_result,
        "db_session": db_session,
        "alert_id": alert_id,
        "apply_os_firewall": apply_os_firewall,
        "send_notifications": send_notifications,
        "allow_db_block": allow_db_block,
        "result": result,
    }

    for step in playbook.get("steps") or []:
        action = step.get("action")
        when = step.get("when_severity_at_least")
        if when and not _sev_ok(severity, when):
            result["steps_skipped"].append(f"{action}(severity)")
            continue
        try:
            handler = _HANDLERS.get(action)
            if not handler:
                result["steps_skipped"].append(f"{action}(unknown)")
                continue
            handler(ctx, step)
            result["steps_run"].append(action)
        except Exception as exc:
            logger.warning("SOAR step %s failed: %s", action, exc)
            result["steps_skipped"].append(f"{action}(error:{exc})")

    return result


def _step_create_alert(ctx: Dict[str, Any], step: Dict[str, Any]) -> None:
    # Alert is created by alert_manager; this is a no-op marker.
    return


def _step_enrich_mitre(ctx: Dict[str, Any], step: Dict[str, Any]) -> None:
    from threat_intelligence.mitre_map import map_attack_to_mitre
    ctx["result"]["mitre"] = map_attack_to_mitre(ctx["attack_label"])


def _step_enrich_ti(ctx: Dict[str, Any], step: Dict[str, Any]) -> None:
    ip = ctx.get("source_ip") or ""
    if not ip or ip in ("unknown", "0.0.0.0"):
        return
    try:
        from threat_intelligence.ip_lookup import lookup_ip
        info = lookup_ip(ip)
        ctx["result"]["ti"] = info if isinstance(info, dict) else {"raw": str(info)}
    except Exception:
        try:
            from threat_intelligence.geo_location import get_location
            ctx["result"]["ti"] = get_location(ip) or {}
        except Exception:
            ctx["result"]["ti"] = {"note": "TI lookup unavailable"}


def _step_local_notify(ctx: Dict[str, Any], step: Dict[str, Any]) -> None:
    from alerts.local_notify import notify_from_alert_fields
    notify_from_alert_fields(ctx["severity"], str(ctx["attack_label"]), str(ctx["source_ip"]))


def _step_send_telegram(ctx: Dict[str, Any], step: Dict[str, Any]) -> None:
    if not ctx.get("send_notifications"):
        return
    from alerts.telegram_alert import send_telegram_alert_detailed
    from threat_intelligence.mitre_map import format_mitre_short, map_attack_to_mitre
    from database.queries import insert_notification

    pred = ctx["prediction_result"] or {}
    confidence = pred.get("confidence", 0.0)
    conf_ratio = (
        confidence / 100.0
        if isinstance(confidence, (int, float)) and confidence > 1
        else float(confidence or 0)
    )
    threat_score = pred.get("threat_score", 0.0)
    mitre = ctx["result"].get("mitre") or map_attack_to_mitre(ctx["attack_label"])
    playbook_name = ctx["result"].get("playbook") or "Default"

    tg_msg = (
        f"AI-NDR ALERT [{ctx['severity']}]\n"
        f"Attack: {ctx['attack_label']}\n"
        f"Source IP: {ctx['source_ip']}\n"
        f"Confidence: {conf_ratio:.1%}\n"
        f"Threat Score: {threat_score}/10\n"
        f"{format_mitre_short(ctx['attack_label'])}\n"
        f"Playbook: {playbook_name}\n"
        f"MITRE URL: {mitre.get('mitre_url', '')}\n"
        f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    ok, detail = send_telegram_alert_detailed(tg_msg, verify_bot=False)
    ctx["result"]["telegram_sent"] = ok
    ctx["result"]["telegram_detail"] = detail
    try:
        insert_notification(
            db=ctx["db_session"],
            alert_id=ctx.get("alert_id"),
            notif_type="Telegram",
            message=tg_msg if ok else f"{tg_msg}\n\nERROR: {detail}",
            delivery_status="Sent" if ok else "Failed",
        )
    except Exception as exc:
        logger.warning("Failed to log telegram notification: %s", exc)


def _step_block_ip(ctx: Dict[str, Any], step: Dict[str, Any]) -> None:
    if not ctx.get("allow_db_block"):
        return
    ip = ctx.get("source_ip") or ""
    if not ip or ip in ("unknown", "0.0.0.0"):
        return
    attack_type = ctx["attack_label"]
    threat_score = (ctx["prediction_result"] or {}).get("threat_score", 0.0)
    reason = f"SOAR playbook block: {attack_type} (threat_score={threat_score})"
    duration = step.get("duration", "1h")
    try:
        from response.policy import queue_or_block
        result = queue_or_block(ip, reason=reason, duration=duration, blocked_by="soar_playbook")
        ctx["result"]["ip_blocked"] = bool(result.get("ok") and not result.get("pending") and not result.get("skipped"))
        ctx["result"]["block_meta"] = result
        if result.get("skipped") == "allowlisted":
            return
        if result.get("pending"):
            return
    except Exception:
        pass
    if ctx.get("apply_os_firewall") and ctx["result"].get("ip_blocked"):
        from firewall.ip_block import block_ip_address
        block_ip_address(ip, reason=reason)


def _step_queue_online_sample(ctx: Dict[str, Any], step: Dict[str, Any]) -> None:
    try:
        from training.online_learning import queue_labeled_sample
        features = (ctx["prediction_result"] or {}).get("features") or {}
        if not features:
            return
        queued = queue_labeled_sample(features, ctx["attack_label"])
        ctx["result"]["online_queued"] = bool(queued)
    except Exception as exc:
        logger.debug("online queue skipped: %s", exc)


def _step_webhook(ctx: Dict[str, Any], step: Dict[str, Any]) -> None:
    try:
        from alerts.webhooks import fire_webhooks
        fire_webhooks("alert", {
            "attack": ctx.get("attack_label"),
            "severity": ctx.get("severity"),
            "source_ip": ctx.get("source_ip"),
            "alert_id": ctx.get("alert_id"),
        })
    except Exception:
        pass


_HANDLERS = {
    "create_alert": _step_create_alert,
    "enrich_mitre": _step_enrich_mitre,
    "enrich_ti": _step_enrich_ti,
    "local_notify": _step_local_notify,
    "send_telegram": _step_send_telegram,
    "block_ip": _step_block_ip,
    "queue_online_sample": _step_queue_online_sample,
    "webhook": _step_webhook,
}
