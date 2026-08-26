"""
Live traffic monitoring – continuous live connection feed.

Connects to the system network stack and refreshes automatically.
No CSV upload: Start Live Capture then watch flows appear in real time.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st
from sqlalchemy import func

from dashboard.auth_gate import APP_VERSION, gate_page
from dashboard.ai_assistant import set_assistant_focus
from dashboard.i18n import t
from database.database import SessionLocal, init_db
from database.models import NetworkFlow
from monitoring.flow_builder import build_flows
from monitoring.live_capture import capture_live, list_interfaces, protocol_name

st.set_page_config(page_title="Live Monitoring", page_icon="📡", layout="wide")
gate_page("Live Monitoring")

st.title(f"📡 {t('live.title')}")
st.caption(t("live.caption", version=APP_VERSION))

if "live_capturing" not in st.session_state:
    st.session_state.live_capturing = False
if "live_mode" not in st.session_state:
    st.session_state.live_mode = "—"
if "live_last_count" not in st.session_state:
    st.session_state.live_last_count = 0
if "live_packets_seen" not in st.session_state:
    st.session_state.live_packets_seen = 0

interfaces = list_interfaces()
iface_labels = [
    f"{i['name']}" + (f" — {i['description']}" if i["description"] != i["name"] else "")
    for i in interfaces
]
# Prefer Wi-Fi / Ethernet-looking names
default_idx = 0
for idx, label in enumerate(iface_labels):
    low = label.lower()
    if "wi-fi" in low or "wifi" in low or "ethernet" in low:
        default_idx = idx
        break

col_a, col_b, col_c = st.columns([2, 1, 1])
with col_a:
    selected_label = st.selectbox(t("live.iface"), iface_labels, index=default_idx)
    selected_iface = interfaces[iface_labels.index(selected_label)]["name"]
with col_b:
    if st.button(f"▶ {t('live.start')}", type="primary", use_container_width=True):
        st.session_state.live_capturing = True
        st.rerun()
with col_c:
    if st.button(f"⏹ {t('live.stop')}", use_container_width=True):
        st.session_state.live_capturing = False
        st.rerun()

status = t("live.connected") if st.session_state.live_capturing else t("live.idle")
color = "#00cc44" if st.session_state.live_capturing else "#888888"
st.markdown(
    f"**{t('live.status')}:** <span style='color:{color}; font-weight:bold;'>{status}</span> "
    f"&nbsp;|&nbsp; {t('live.mode')}: `{st.session_state.live_mode}` "
    f"&nbsp;|&nbsp; {t('live.last_batch')}: `{st.session_state.live_last_count}` "
    f"&nbsp;|&nbsp; {t('live.seen')}: `{st.session_state.live_packets_seen}`",
    unsafe_allow_html=True,
)

try:
    from ops.retention import capture_health
    from monitoring.sensors import heartbeat
    ch = capture_health()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("live.sensors"), ch.get("sensors", 0))
    m2.metric(t("live.pps"), f"{ch.get('packets_sec', 0):.1f}")
    m3.metric(t("live.dropped"), ch.get("dropped_packets", 0))
    m4.metric(t("live.stored"), ch.get("flows_stored", 0))
    if st.session_state.live_capturing:
        heartbeat("local", packets_sec=float(st.session_state.live_last_count or 0), interfaces=selected_iface)
except Exception:
    pass

st.info(t("live.info"))

if st.button(t("live.evidence")):
    from ops.session_evidence import write_evidence_report
    path = write_evidence_report()
    st.success(t("live.evidence_ok", path=str(path)))


def _save_flows(flows: list[dict]) -> int:
    """Persist new flows to the database; skip exact duplicates from the last minute."""
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
            # Update counters if same flow seen again recently; else insert
            if exists and exists.timestamp and (datetime.utcnow() - exists.timestamp).total_seconds() < 30:
                exists.packets = int(flow.get("packet_count", exists.packets or 1))
                exists.bytes_total = int(flow.get("byte_count", exists.bytes_total or 0))
                exists.packet_rate = float(flow.get("packet_rate", 0) or 0)
                exists.flow_rate = float(flow.get("flow_rate", 0) or 0)
                exists.duration = float(flow.get("duration", 0) or 0)
                exists.timestamp = datetime.utcnow()
            else:
                row = NetworkFlow(
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
                )
                db.add(row)
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


@st.fragment(run_every=timedelta(seconds=2) if st.session_state.live_capturing else None)
def live_feed():
    """Auto-refreshing live capture panel."""
    live_rows = []
    if st.session_state.live_capturing:
        packets, mode = capture_live(interface=selected_iface, timeout=1.5)
        st.session_state.live_mode = mode
        st.session_state.live_last_count = len(packets)
        st.session_state.live_packets_seen += len(packets)

        flows = build_flows(packets) if packets else []
        if flows:
            _save_flows(flows)

        for p in packets:
            live_rows.append(
                {
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Source IP": p.get("src_ip"),
                    "Dest IP": p.get("dst_ip"),
                    "Src Port": p.get("src_port"),
                    "Dst Port": p.get("dst_port"),
                    "Protocol": protocol_name(p.get("protocol", 0)),
                    "App": p.get("app_protocol", ""),
                    "Status": p.get("status", "CAPTURED"),
                }
            )

    m1, m2, m3, m4 = st.columns(4)
    init_db()
    db = SessionLocal()
    try:
        total = db.query(NetworkFlow).count()
        protocols = db.query(NetworkFlow.protocol, func.count()).group_by(NetworkFlow.protocol).all()
        total_bytes = db.query(func.sum(NetworkFlow.bytes_total)).scalar() or 0
        m1.metric(t("live.stored"), f"{total:,}")
        m2.metric(t("live.batch"), st.session_state.live_last_count)
        m3.metric(t("live.protocols"), len(protocols))
        m4.metric(
            t("live.bytes"),
            f"{total_bytes / 1_000_000:.1f} MB" if total_bytes > 1_000_000 else f"{total_bytes:,}",
        )

        st.subheader(t("live.active"))
        if live_rows:
            st.dataframe(pd.DataFrame(live_rows), use_container_width=True, height=320)
        elif st.session_state.live_capturing:
            st.warning(t("live.wait"))
        else:
            st.info(t("live.press"))

        st.subheader(t("live.recent"))
        flows = db.query(NetworkFlow).order_by(NetworkFlow.timestamp.desc()).limit(100).all()
        if flows:
            set_assistant_focus("flow", record_id=int(flows[0].flow_id), label=f"Latest flow #{flows[0].flow_id}")
            data = [
                {
                    "Time": str(f.timestamp),
                    "Source IP": f.source_ip,
                    "Dest IP": f.destination_ip,
                    "Src Port": f.source_port,
                    "Dst Port": f.destination_port,
                    "Protocol": f.protocol,
                    "Duration": f"{(f.duration or 0):.3f}",
                    "Packets": f.packets,
                    "Bytes": f.bytes_total,
                }
                for f in flows
            ]
            st.dataframe(pd.DataFrame(data), use_container_width=True, height=360)
        else:
            st.info(t("live.none"))
    finally:
        db.close()


live_feed()
