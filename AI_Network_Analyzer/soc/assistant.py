"""
Context-aware AI Security Assistant (offline).

Roles: Help + Security Analyst + Investigation Assistant.
Uses live DB data, MITRE, playbooks, and page context — no external LLM.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from database.database import SessionLocal
from database.orm import ensure_models
from detection.specialists import kill_chain_stage
from soc.copilot import explain_attack, recommend_response, summarize_incident
from threat_intelligence.mitre_map import format_mitre_short, map_attack_to_mitre

_m = ensure_models()
(
    Alert, NetworkFlow, Prediction, ThreatIntelligence, BlockedIP,
    AIModel, Asset, SocIncident, IOC,
) = (
    _m.Alert, _m.NetworkFlow, _m.Prediction, _m.ThreatIntelligence, _m.BlockedIP,
    _m.AIModel, _m.Asset, _m.SocIncident, _m.IOC,
)

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _fmt_response(
    *,
    summary: str,
    threat_type: str = "",
    why_detected: str = "",
    evidence: Optional[List[str]] = None,
    mitre: str = "",
    severity: str = "",
    recommended_action: str = "",
    analyst_notes: str = "",
    help_hint: str = "",
) -> Dict[str, Any]:
    return {
        "summary": summary,
        "threat_type": threat_type,
        "why_detected": why_detected,
        "evidence": evidence or [],
        "mitre": mitre,
        "severity": severity,
        "recommended_action": recommended_action,
        "analyst_notes": analyst_notes,
        "help_hint": help_hint,
    }


def explain_threat_score(score: float) -> str:
    s = float(score or 0)
    if s >= 8.5:
        return (
            f"Threat score {s:.1f}/10 = CRITICAL. Multiple attack indicators or very high model confidence. "
            "Treat as active compromise risk; isolate host and block egress if confirmed."
        )
    if s >= 7:
        return (
            f"Threat score {s:.1f}/10 = HIGH. Strong anomaly/attack pattern. "
            "Prioritize investigation within minutes; temp block if policy allows."
        )
    if s >= 5:
        return (
            f"Threat score {s:.1f}/10 = MEDIUM. Suspicious but not definitive. "
            "Correlate with other alerts, TI, and baselines before blocking."
        )
    if s >= 3:
        return f"Threat score {s:.1f}/10 = LOW–MEDIUM. Monitor and enrich with TI."
    return f"Threat score {s:.1f}/10 = LOW. Likely benign or weak signal."


def _port_scan_reason(flow: NetworkFlow) -> str:
    ports = [flow.destination_port, flow.source_port]
    pkt = flow.packets or 0
    dur = flow.duration or 0
    reasons = []
    if flow.destination_port and flow.destination_port < 1024:
        reasons.append(f"destination port {flow.destination_port} is a sensitive/low port")
    if pkt >= 20 and dur < 5:
        reasons.append("high packet count in a short duration (scan-like burst)")
    if (flow.packet_rate or 0) > 50:
        reasons.append(f"elevated packet rate ({flow.packet_rate:.1f} pkt/s)")
    if not reasons:
        reasons.append("flow metadata matches horizontal/vertical scan heuristics in specialist detectors")
    return "; ".join(reasons)


def analyze_flow(flow_id: Optional[int] = None, flow_row: Optional[NetworkFlow] = None) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        flow = flow_row
        if flow is None and flow_id:
            flow = db.query(NetworkFlow).filter(NetworkFlow.flow_id == flow_id).first()
        if flow is None:
            flow = db.query(NetworkFlow).order_by(NetworkFlow.flow_id.desc()).first()
        if not flow:
            return _fmt_response(summary="No flows in database yet.", help_hint="Start Live Capture first.")

        pred = (
            db.query(Prediction)
            .filter(Prediction.flow_id == flow.flow_id)
            .order_by(Prediction.prediction_id.desc())
            .first()
        )
        label = pred.prediction_label if pred else "Unknown"
        score = pred.threat_score if pred else 0.0
        sev = pred.severity if pred else "Low"
        conf = pred.confidence if pred else 0.0

        why = []
        if label.lower() in ("portscan", "port scan"):
            why.append(_port_scan_reason(flow))
        if pred:
            why.append(f"Hybrid AI label={label}, confidence={conf:.1f}%, threat_score={score:.1f}")
        why.append(explain_threat_score(score))

        mitre = format_mitre_short(label)
        rec = recommend_response(label, sev, flow.source_ip or "")
        evidence = [
            f"{flow.source_ip}:{flow.source_port} → {flow.destination_ip}:{flow.destination_port} ({flow.protocol})",
            f"packets={flow.packets}, bytes={flow.bytes_total}, duration={flow.duration:.3f}s",
            f"packet_rate={flow.packet_rate or 0:.2f}, flow_rate={flow.flow_rate or 0:.2f}",
        ]
        if pred and pred.recommendation:
            evidence.append(f"Model recommendation: {pred.recommendation[:200]}")

        risky = label != "Normal" or float(score or 0) >= 6
        summary = (
            f"Flow #{flow.flow_id} is {'SUSPICIOUS' if risky else 'likely normal'} "
            f"({label}, severity {sev})."
        )
        return _fmt_response(
            summary=summary,
            threat_type=label,
            why_detected=" ".join(why),
            evidence=evidence,
            mitre=mitre,
            severity=sev,
            recommended_action=rec.get("action", "Investigate"),
            analyst_notes=rec.get("reason", ""),
            help_hint="Ask: 'why port scan?' or 'explain threat score 8.7'",
        )
    finally:
        db.close()


def analyze_alert(alert_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        if not alert:
            return _fmt_response(summary=f"Alert #{alert_id} not found.")

        pred = None
        if alert.prediction_id:
            pred = db.query(Prediction).filter(Prediction.prediction_id == alert.prediction_id).first()

        label = alert.alert_type or (pred.prediction_label if pred else "Unknown")
        sev = alert.priority or (pred.severity if pred else "Medium")
        msg = alert.message or ""
        ip_m = _IP_RE.search(msg)
        src_ip = ip_m.group(0) if ip_m else ""

        mitre = format_mitre_short(label)
        rec = recommend_response(label, sev, src_ip)
        explain = explain_attack(label, msg)

        evidence = [msg[:300]] if msg else []
        if pred:
            evidence.append(
                f"Prediction: {pred.prediction_label}, confidence={pred.confidence:.1f}%, "
                f"threat_score={pred.threat_score:.1f}"
            )
            if pred.flow_id:
                flow = db.query(NetworkFlow).filter(NetworkFlow.flow_id == pred.flow_id).first()
                if flow:
                    evidence.append(
                        f"Flow: {flow.source_ip} → {flow.destination_ip}:{flow.destination_port}"
                    )

        return _fmt_response(
            summary=f"Alert #{alert_id}: {label} ({sev}) — status {alert.status}.",
            threat_type=label,
            why_detected=explain,
            evidence=evidence,
            mitre=mitre,
            severity=sev,
            recommended_action=f"{rec.get('action')} — {rec.get('playbook')}: {rec.get('steps')}",
            analyst_notes=f"Kill-chain stage: {kill_chain_stage(label)}",
        )
    finally:
        db.close()


def analyze_ip(ip: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        ti = (
            db.query(ThreatIntelligence)
            .filter(ThreatIntelligence.ip_address == ip)
            .order_by(ThreatIntelligence.threat_id.desc())
            .first()
        )
        blocked = db.query(BlockedIP).filter(BlockedIP.ip_address == ip, BlockedIP.status == "Active").first()
        ioc = db.query(IOC).filter(IOC.ioc_type == "ip", IOC.value == ip, IOC.active.is_(True)).first()
        alerts = (
            db.query(Alert)
            .filter(Alert.message.contains(ip))
            .order_by(Alert.alert_id.desc())
            .limit(10)
            .all()
        )
        asset = db.query(Asset).filter(Asset.ip_address == ip).first()

        lookup = {}
        try:
            from threat_intelligence.ip_lookup import lookup_ip
            from threat_intelligence.geo_location import get_location
            lookup = {"reputation": lookup_ip(ip), "geo": get_location(ip)}
        except Exception:
            pass

        score = float((ti.threat_score if ti else 0) or lookup.get("reputation", {}).get("threat_score", 0) or 0)
        should_block = score >= 7 or bool(blocked) or bool(ioc) or any(a.priority in ("High", "Critical") for a in alerts)
        action = "Block" if should_block and not asset else ("Investigate" if should_block else "Monitor")

        evidence = []
        if ti:
            evidence.append(f"TI: score={ti.threat_score}, country={ti.country}, reports={ti.reports}, blacklisted={ti.blacklisted}")
        if lookup.get("reputation"):
            evidence.append(f"Live lookup: {lookup['reputation']}")
        if blocked:
            evidence.append(f"Already blocked: {blocked.reason or blocked.attack_type}")
        if ioc:
            evidence.append(f"Active IOC: {ioc.severity} — {ioc.description or ioc.source}")
        if alerts:
            evidence.append(f"{len(alerts)} related alerts (latest: {alerts[0].alert_type})")
        if asset:
            evidence.append(f"Asset: {asset.device_type}, risk={asset.risk_score}, criticality={asset.criticality}")

        return _fmt_response(
            summary=f"IP {ip}: threat score {score:.1f}/10 — recommend {action}.",
            threat_type=alerts[0].alert_type if alerts else ("Malicious IP" if score >= 6 else "Unknown"),
            why_detected=explain_threat_score(score),
            evidence=evidence,
            mitre=format_mitre_short(alerts[0].alert_type) if alerts else "",
            severity="Critical" if score >= 8 else ("High" if score >= 6 else "Medium"),
            recommended_action=action,
            analyst_notes="Do not block if this is an internal critical asset without approval.",
        )
    finally:
        db.close()


def compare_models() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        models = db.query(AIModel).order_by(AIModel.accuracy.desc()).all()
        if not models:
            return _fmt_response(
                summary="No trained models registered yet.",
                help_hint="Train models from AI Models page, then ask again.",
            )
        best = models[0]
        lines = []
        for m in models:
            lines.append(
                f"{m.model_name}: acc={m.accuracy*100:.1f}% prec={m.precision_score*100:.1f}% "
                f"rec={m.recall*100:.1f}% f1={m.f1_score*100:.1f}%"
            )
        why = (
            f"Best overall by accuracy: **{best.model_name}** ({best.accuracy*100:.1f}%). "
            "Random Forest / XGBoost usually win on tabular NSL-KDD-style features (fast, interpretable). "
            "LSTM helps sequential/time-series traffic but needs more temporal data and trains slower — "
            "lower F1 here often means insufficient sequence length or class imbalance, not that LSTM is useless."
        )
        return _fmt_response(
            summary=f"Top model: {best.model_name} (accuracy {best.accuracy*100:.1f}%).",
            why_detected=why,
            evidence=lines,
            recommended_action="Use hybrid fusion (RF+XGB+IF+AE) for production; keep LSTM for drift/sequence anomalies.",
            help_hint="Ask: 'why is XGBoost better than LSTM?'",
        )
    finally:
        db.close()


def build_page_context(page: str) -> Dict[str, Any]:
    db = SessionLocal()
    ctx: Dict[str, Any] = {"page": page, "highlights": []}
    try:
        if page == "Live Monitoring":
            flows = db.query(NetworkFlow).order_by(NetworkFlow.flow_id.desc()).limit(5).all()
            ctx["highlights"] = [
                f"#{f.flow_id} {f.source_ip}→{f.destination_ip}:{f.destination_port} ({f.protocol})"
                for f in flows
            ]
            ctx["flow_count"] = db.query(NetworkFlow).count()
        elif page == "AI Detection":
            ctx["predictions"] = db.query(Prediction).count()
            ctx["attacks"] = db.query(Prediction).filter(Prediction.prediction_label != "Normal").count()
            latest = db.query(Prediction).order_by(Prediction.prediction_id.desc()).limit(3).all()
            ctx["highlights"] = [f"{p.prediction_label} score={p.threat_score:.1f} sev={p.severity}" for p in latest]
        elif page == "Threat Intelligence":
            ctx["ti_records"] = db.query(ThreatIntelligence).count()
            top = db.query(ThreatIntelligence).order_by(ThreatIntelligence.threat_score.desc()).limit(3).all()
            ctx["highlights"] = [f"{t.ip_address} score={t.threat_score}" for t in top]
        elif page == "Alerts":
            ctx["alerts_new"] = db.query(Alert).filter(Alert.status == "New").count()
            recent = db.query(Alert).order_by(Alert.alert_id.desc()).limit(5).all()
            ctx["highlights"] = [f"#{a.alert_id} {a.alert_type} ({a.priority})" for a in recent]
        elif page == "AI Models":
            models = db.query(AIModel).all()
            ctx["highlights"] = [f"{m.model_name} acc={m.accuracy*100:.1f}%" for m in models[:5]]
        elif page == "Incidents":
            incs = db.query(SocIncident).order_by(SocIncident.incident_id.desc()).limit(3).all()
            ctx["highlights"] = [f"#{i.incident_id} {i.title} ({i.severity})" for i in incs]
        elif page == "Assets":
            assets = db.query(Asset).order_by(Asset.risk_score.desc()).limit(5).all()
            ctx["highlights"] = [f"{a.ip_address} risk={a.risk_score}" for a in assets]
        elif page == "Blocked IPs":
            blocks = db.query(BlockedIP).filter(BlockedIP.status == "Active").limit(5).all()
            ctx["highlights"] = [b.ip_address for b in blocks]
        else:
            ctx["highlights"] = [
                f"Flows: {db.query(NetworkFlow).count()}",
                f"Alerts: {db.query(Alert).count()}",
                f"Predictions: {db.query(Prediction).count()}",
            ]
    finally:
        db.close()
    return ctx


def _wants_analyze(q: str) -> bool:
    return any(x in q for x in (
        "analyze", "analysis", "حلل", "حلّل", "اشرح", "explain", "ليش", "لماذا", "why",
    ))


def ask(question: str, page: str, focus: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    q = (question or "").strip()
    ql = q.lower()
    focus = focus or {}
    ctx = build_page_context(page)

    # Focused object from page selection
    if focus.get("type") == "alert" and focus.get("id"):
        if _wants_analyze(ql) or not q:
            return analyze_alert(int(focus["id"]))
    if focus.get("type") == "flow" and focus.get("id"):
        if _wants_analyze(ql) or not q:
            return analyze_flow(flow_id=int(focus["id"]))
    if focus.get("type") == "ip" and focus.get("value"):
        if _wants_analyze(ql) or "block" in ql or "حظر" in ql or not q:
            return analyze_ip(str(focus["value"]))

    # IP in question
    ip_m = _IP_RE.search(q)
    if ip_m and any(x in ql for x in ("ip", "block", "حظر", "explain", "اشرح", "شرح")):
        return analyze_ip(ip_m.group(0))

    # Threat score
    score_m = re.search(r"(\d+(?:\.\d+)?)\s*/?\s*10|score\s*(\d+(?:\.\d+)?)|threat score\s*(\d+(?:\.\d+)?)", ql)
    if score_m or "threat score" in ql or "نقاط" in ql:
        val = score_m.group(1) or score_m.group(2) or score_m.group(3) if score_m else "7"
        try:
            s = float(val)
        except Exception:
            s = 7.0
        return _fmt_response(
            summary=explain_threat_score(s),
            help_hint="On Live Monitoring, select a flow and ask 'why is this flow dangerous?'",
        )

    # Port scan
    if "port scan" in ql or "portscan" in ql or "مسح" in ql:
        fid = focus.get("id") if focus.get("type") == "flow" else None
        out = analyze_flow(flow_id=fid)
        out["why_detected"] = _port_scan_reason(
            SessionLocal().query(NetworkFlow).filter(NetworkFlow.flow_id == fid).first()
        ) if fid else out.get("why_detected", "")
        return out

    # Models
    if page == "AI Models" or "model" in ql or "xgboost" in ql or "lstm" in ql or "أي model" in ql:
        if "better" in ql or "أفضل" in ql or "compare" in ql or "lstm" in ql or "xgboost" in ql or not q:
            return compare_models()

    # Alert analyze by ID in text
    aid_m = re.search(r"alert\s*#?(\d+)|تنبيه\s*(\d+)", ql)
    if aid_m:
        aid = int(aid_m.group(1) or aid_m.group(2))
        return analyze_alert(aid)

    # Incident
    if "incident" in ql and focus.get("type") == "incident":
        return _fmt_response(summary=summarize_incident(int(focus["id"])))

    # Page-specific defaults
    if page == "Live Monitoring":
        return analyze_flow()
    if page == "Alerts" and ctx.get("highlights"):
        recent_id = int(str(ctx["highlights"][0]).split("#")[1].split()[0]) if ctx["highlights"] else None
        if recent_id:
            return analyze_alert(recent_id)
    if page == "Threat Intelligence" and ip_m:
        return analyze_ip(ip_m.group(0))

    # Generic help + context
    hints = {
        "Live Monitoring": "Try: 'Why is this flow dangerous?' or 'What does threat score 8.7 mean?'",
        "Threat Intelligence": "Try: 'Explain this IP' or 'Should I block 1.2.3.4?'",
        "AI Models": "Try: 'Which model is best?' or 'Why is XGBoost better than LSTM?'",
        "Alerts": "Enter an Alert ID in the page, then ask 'Analyze this'.",
    }
    hl = "; ".join(ctx.get("highlights") or [])[:400]
    return _fmt_response(
        summary=f"Context: **{page}**. {hl or 'No recent items.'}",
        help_hint=hints.get(page, "Ask about alerts, IPs, flows, models, or type 'analyze this'."),
        recommended_action="Investigate",
    )
