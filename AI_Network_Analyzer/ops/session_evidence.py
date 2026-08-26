"""
Live-session evidence snapshot.

Separates lab/simulation TEST-NET IPs from RFC1918 LAN and other hosts,
counts real captured flows/PCAPs, and writes a dated report for defense.
"""
from __future__ import annotations

import json
from datetime import datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Dict, List

from config import CAPTURED_DATA_DIR, REPORTS_DIR


def _ip_kind(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "unknown"
    if text.startswith("203.0.113.") or text.startswith("198.51.100.") or text.startswith("192.0.2."):
        return "simulation"
    try:
        ip = ip_address(text.split("%")[0])
    except Exception:
        return "unknown"
    if ip.is_loopback:
        return "loopback"
    if ip.is_private:
        return "lan"
    if ip.is_multicast or ip.is_reserved or ip.is_link_local:
        return "special"
    return "public"


def collect_evidence() -> Dict[str, Any]:
    from database.database import SessionLocal, init_db
    from database.models import Alert, NetworkFlow, PcapEvidence, Prediction

    init_db()
    db = SessionLocal()
    try:
        flows = db.query(NetworkFlow).all()
        preds = db.query(Prediction).all()
        alerts = db.query(Alert).all()
        pcaps_db = []
        try:
            pcaps_db = db.query(PcapEvidence).all()
        except Exception:
            pcaps_db = []
    finally:
        db.close()

    kinds = {"simulation": 0, "lan": 0, "public": 0, "loopback": 0, "special": 0, "unknown": 0}
    unique_src: Dict[str, str] = {}
    times: List[datetime] = []
    for flow in flows:
        kind = _ip_kind(str(flow.source_ip or ""))
        kinds[kind] = kinds.get(kind, 0) + 1
        unique_src[str(flow.source_ip or "")] = kind
        if flow.timestamp:
            times.append(flow.timestamp)

    pcap_files = []
    if CAPTURED_DATA_DIR.exists():
        for path in CAPTURED_DATA_DIR.rglob("*"):
            if path.suffix.lower() in {".pcap", ".pcapng", ".cap"}:
                pcap_files.append({"path": str(path), "bytes": path.stat().st_size})

    live_flows = kinds.get("lan", 0) + kinds.get("public", 0)
    sim_flows = kinds.get("simulation", 0)
    span_min = 0.0
    if len(times) >= 2:
        span_min = (max(times) - min(times)).total_seconds() / 60.0

    attack_preds = [p for p in preds if str(p.prediction_label or "") not in ("Normal", "", "None")]
    explained = [p for p in preds if getattr(p, "explanation_json", None)]

    snapshot = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "flows_total": len(flows),
        "unique_source_ips": len([k for k in unique_src if k]),
        "flow_kinds": kinds,
        "live_or_lan_flows": live_flows,
        "simulation_flows": sim_flows,
        "loopback_flows": kinds.get("loopback", 0),
        "capture_span_minutes": round(span_min, 2),
        "predictions": len(preds),
        "attack_predictions": len(attack_preds),
        "predictions_with_xai": len(explained),
        "alerts": len(alerts),
        "pcap_files": pcap_files,
        "pcap_db_rows": len(pcaps_db),
        "realism_notes": [
            "Simulation uses RFC 5737 TEST-NET addresses (203.0.113.0/24, 198.51.100.0/24).",
            "LAN/private RFC1918 and public IPs come from live capture or real hosts.",
            "XAI is stored per prediction when detection has been run.",
        ],
    }
    if live_flows == 0 and sim_flows > 0:
        snapshot["evidence_level"] = "simulation_only"
    elif live_flows > 0 and sim_flows > 0:
        snapshot["evidence_level"] = "mixed_live_and_simulation"
    elif live_flows > 0:
        snapshot["evidence_level"] = "live_capture"
    else:
        snapshot["evidence_level"] = "insufficient"
    return snapshot


def write_evidence_report(snapshot: Dict[str, Any] | None = None) -> Path:
    snap = snapshot or collect_evidence()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_path = REPORTS_DIR / f"live_session_evidence_{stamp}.json"
    md_path = REPORTS_DIR / f"live_session_evidence_{stamp}.md"
    latest_json = REPORTS_DIR / "live_session_evidence.json"
    latest_md = REPORTS_DIR / "live_session_evidence.md"

    json_path.write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")
    latest_json.write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")

    md = [
        "# Live session evidence",
        "",
        f"Generated: {snap.get('generated_at')}",
        f"Evidence level: **{snap.get('evidence_level')}**",
        "",
        f"- Total flows: {snap.get('flows_total')}",
        f"- Unique source IPs: {snap.get('unique_source_ips')}",
        f"- Live/LAN flows: {snap.get('live_or_lan_flows')}",
        f"- Simulation (TEST-NET) flows: {snap.get('simulation_flows')}",
        f"- Capture span (minutes): {snap.get('capture_span_minutes')}",
        f"- Predictions: {snap.get('predictions')} (attacks: {snap.get('attack_predictions')})",
        f"- Predictions with XAI: {snap.get('predictions_with_xai')}",
        f"- Alerts: {snap.get('alerts')}",
        f"- PCAP files: {len(snap.get('pcap_files') or [])}",
        "",
        "## Flow kinds",
        "",
        "```json",
        json.dumps(snap.get("flow_kinds") or {}, indent=2),
        "```",
        "",
        "## Notes",
        "",
    ]
    for note in snap.get("realism_notes") or []:
        md.append(f"- {note}")
    md.append("")
    text = "\n".join(md)
    md_path.write_text(text, encoding="utf-8")
    latest_md.write_text(text, encoding="utf-8")
    return latest_json


if __name__ == "__main__":
    path = write_evidence_report()
    print(path)
