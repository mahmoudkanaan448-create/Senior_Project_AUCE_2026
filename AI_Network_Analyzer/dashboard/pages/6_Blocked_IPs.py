"""
Blocked IPs management page.

Shows active and removed blocks, and supports manual
block and unblock of IP addresses.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from database.database import SessionLocal, init_db
from database.models import BlockedIP
from database import queries
from dashboard.auth_gate import gate_page
from dashboard.i18n import t

st.set_page_config(page_title="Blocked IPs", page_icon="🔒", layout="wide")
gate_page("Blocked IPs")
st.title(f"🔒 {t('blocked.title')}")

init_db()
db = SessionLocal()
try:
    blocked = db.query(BlockedIP).order_by(BlockedIP.blocked_at.desc()).all()
    active = [b for b in blocked if b.status == "Active"]
    removed = [b for b in blocked if b.status != "Active"]

    c1, c2, c3 = st.columns(3)
    c1.metric(t("blocked.total"), len(blocked))
    c2.metric(t("blocked.active"), len(active))
    c3.metric(t("blocked.removed"), len(removed))

    st.markdown("---")

    st.subheader(t("blocked.block"))
    col1, col2 = st.columns(2)
    with col1:
        ip_to_block = st.text_input(t("blocked.ip"), placeholder="e.g. 192.168.1.100")
    with col2:
        reason = st.text_input(t("blocked.reason"), placeholder="e.g. DDoS attack")

    if st.button(t("blocked.btn")) and ip_to_block:
        queries.block_ip(db, ip_to_block, attack_type=reason, reason=reason)
        st.success(t("blocked.ok", ip=ip_to_block))
        st.rerun()

    st.markdown("---")

    st.subheader(t("blocked.active_list"))
    if active:
        data = [{
            "IP": b.ip_address, "Attack": b.attack_type or "",
            "Blocked At": str(b.blocked_at), "By": b.blocked_by,
            "Reason": b.reason or "",
        } for b in active]
        st.dataframe(pd.DataFrame(data), use_container_width=True)

        ip_to_unblock = st.text_input(t("blocked.unblock_ip"), placeholder="Enter IP to remove block")
        if st.button(t("blocked.unblock")) and ip_to_unblock:
            if queries.unblock_ip(db, ip_to_unblock):
                st.success(t("blocked.unblocked", ip=ip_to_unblock))
                st.rerun()
            else:
                st.error(t("blocked.not_found"))
    else:
        st.info(t("blocked.none"))
finally:
    db.close()
