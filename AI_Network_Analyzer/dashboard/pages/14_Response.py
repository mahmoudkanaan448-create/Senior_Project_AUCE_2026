"""Response control: IOC, allowlist, blacklist, approvals, rollback, webhooks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from dashboard.auth_gate import gate_page
from dashboard.i18n import t, fmt_opt
from database.database import init_db, SessionLocal
from database import queries

init_db()

st.set_page_config(page_title="Response", page_icon="🛡️", layout="wide")
gate_page("Response")
st.title(f"🛡️ {t('resp.title')}")
st.caption(t("resp.caption"))

from response.policy import (
    add_allow, list_allow, list_pending, decide_pending, rollback_block,
    expire_temp_blocks, response_mode, queue_or_block,
)
from threat_intelligence.ioc_manager import add_ioc, list_iocs, deactivate
from alerts.webhooks import add_webhook, list_webhooks
from monitoring.sensors import register_sensor, list_sensors

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [t("resp.tab.ioc"), t("resp.tab.allow"), t("resp.tab.approvals"), t("resp.tab.webhooks"), t("resp.tab.sensors")]
)

with tab1:
    st.subheader(t("resp.iocs"))
    iocs = list_iocs(active_only=False)
    if iocs:
        st.dataframe(pd.DataFrame(iocs), use_container_width=True, height=280)
    c1, c2, c3 = st.columns(3)
    ioc_type = c1.selectbox(t("resp.type"), ["ip", "domain", "hash"])
    value = c2.text_input(t("resp.value"))
    sev = c3.selectbox(t("resp.sev"), ["High", "Critical", "Medium", "Low"], format_func=fmt_opt)
    desc = st.text_input(t("resp.desc"))
    if st.button(t("resp.add_ioc"), type="primary") and value:
        add_ioc(ioc_type, value, source="manual", severity=sev, description=desc)
        st.success(t("resp.ioc_added"))
        st.rerun()
    did = st.number_input(t("resp.deact_id"), min_value=0, step=1)
    if st.button(t("resp.deact")) and did:
        deactivate(int(did))
        st.rerun()

with tab2:
    st.subheader(t("resp.allow"))
    al = list_allow()
    if al:
        st.dataframe(pd.DataFrame(al), use_container_width=True)
    av = st.text_input(t("resp.trusted"))
    if st.button(t("resp.add_allow")) and av:
        add_allow(av.strip())
        st.success(t("resp.trusted_ok"))
        st.rerun()

    st.markdown("---")
    st.subheader(t("resp.manual"))
    bip = st.text_input(t("resp.ip_block"))
    dur = st.selectbox(t("resp.duration"), ["5m", "1h", "24h", "permanent"])
    reason = st.text_input(t("resp.reason"), value="manual SOC action")
    if st.button(t("resp.queue")):
        st.json(queue_or_block(bip.strip(), reason=reason, duration=dur, blocked_by="analyst"))
    uip = st.text_input(t("resp.unblock_ip"))
    if st.button(t("resp.rollback")) and uip:
        st.success(t("resp.unblocked")) if rollback_block(uip.strip()) else st.error(t("resp.not_active"))
    n = expire_temp_blocks()
    st.caption(t("resp.expired", n=n, mode=response_mode()))

    db = SessionLocal()
    try:
        blocked = queries.get_blocked_ips(db)
        if blocked:
            st.dataframe(pd.DataFrame([{
                "IP": b.ip_address, "Duration": b.duration, "Status": b.status,
                "Reason": b.reason or "", "At": str(b.blocked_at),
            } for b in blocked]), use_container_width=True)
    finally:
        db.close()

with tab3:
    st.subheader(t("resp.approval"))
    pending = list_pending()
    if pending:
        st.dataframe(pd.DataFrame(pending), use_container_width=True)
        aid = st.number_input(t("resp.action_id"), min_value=1, step=1)
        a1, a2 = st.columns(2)
        with a1:
            if st.button(t("resp.approve"), type="primary"):
                decide_pending(int(aid), True, actor=(st.session_state.get("user") or {}).get("username", "admin"))
                st.rerun()
        with a2:
            if st.button(t("resp.reject")):
                decide_pending(int(aid), False)
                st.rerun()
    else:
        st.info(t("resp.no_pending"))

with tab4:
    st.subheader(t("resp.webhooks"))
    wh = list_webhooks()
    if wh:
        st.dataframe(pd.DataFrame(wh), use_container_width=True)
    name = st.text_input(t("resp.name"), value="soc-webhook")
    url = st.text_input(t("resp.url"))
    ev = st.selectbox(t("resp.event"), ["alert", "incident", "all"])
    if st.button(t("resp.add_wh")) and url:
        add_webhook(name, url, ev)
        st.success(t("resp.wh_saved"))
        st.rerun()

with tab5:
    st.subheader(t("resp.sensors"))
    sensors = list_sensors()
    if sensors:
        st.dataframe(pd.DataFrame(sensors), use_container_width=True)
    sname = st.text_input(t("resp.sname"), value="branch-1")
    site = st.text_input(t("resp.site"), value="branch")
    ifaces = st.text_input(t("resp.ifaces"), value="eth0")
    if st.button(t("resp.reg")):
        rec = register_sensor(sname, site, ifaces)
        st.success(t("resp.keep_key"))
        st.json(rec)
        st.caption(t("resp.post"))
