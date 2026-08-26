"""Asset inventory, risk scores, host profiles, network topology."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.auth_gate import gate_page, style_fig
from dashboard.i18n import t
from database.database import init_db

init_db()

st.set_page_config(page_title="Assets", page_icon="🖥️", layout="wide")
gate_page("Assets")
st.title(f"🖥️ {t('assets.title')}")
st.caption(t("assets.caption"))

from assets.inventory import list_assets, set_critical, topology_edges, recompute_risk
from detection.baselines import list_drifted
from identity.monitor import auth_anomalies

assets = list_assets(300)
c1, c2, c3 = st.columns(3)
c1.metric(t("assets.count"), len(assets))
c2.metric(t("assets.critical"), sum(1 for a in assets if a["Criticality"] == "Critical"))
c3.metric(t("assets.high_risk"), sum(1 for a in assets if float(a["Risk"] or 0) >= 60))

tab1, tab2, tab3, tab4 = st.tabs([
    t("assets.tab.inv"), t("assets.tab.topo"), t("assets.tab.profile"), t("assets.tab.ident"),
])

with tab1:
    if assets:
        st.dataframe(pd.DataFrame(assets), use_container_width=True, height=420)
    else:
        st.info(t("assets.none"))
    ip = st.text_input(t("assets.tag_ip"))
    colx, coly = st.columns(2)
    with colx:
        if st.button(t("assets.mark_crit")):
            st.success(t("common.tagged")) if set_critical(ip, True) else st.error(t("common.not_found"))
    with coly:
        if st.button(t("assets.mark_norm")):
            st.success(t("common.tagged")) if set_critical(ip, False) else st.error(t("common.not_found"))

with tab2:
    edges = topology_edges(100)
    if not edges:
        st.info(t("assets.need_flows"))
    else:
        nodes = sorted({e["from"] for e in edges} | {e["to"] for e in edges})
        idx = {n: i for i, n in enumerate(nodes)}
        fig = go.Figure(data=[go.Sankey(
            node=dict(label=nodes, pad=12, thickness=14),
            link=dict(
                source=[idx[e["from"]] for e in edges],
                target=[idx[e["to"]] for e in edges],
                value=[1] * len(edges),
            ),
        )])
        style_fig(fig)
        fig.update_layout(height=480, title=t("assets.topo_title"))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(pd.DataFrame(edges), use_container_width=True, height=240)

with tab3:
    hip = st.text_input(t("assets.host_ip"), key="host_profile_ip")
    if hip:
        recompute_risk(hip)
        row = next((a for a in list_assets(500) if a["IP"] == hip), None)
        if row:
            st.json(row)
        from soc.hunting import hunt
        h = hunt(ip=hip, limit=40)
        st.subheader(t("assets.recent_alerts"))
        st.dataframe(pd.DataFrame(h["alerts"]), use_container_width=True)
        st.subheader(t("assets.recent_flows"))
        st.dataframe(pd.DataFrame(h["flows"]), use_container_width=True)

with tab4:
    st.subheader(t("assets.auth"))
    findings = auth_anomalies()
    if findings:
        st.dataframe(pd.DataFrame(findings), use_container_width=True)
    else:
        st.info(t("assets.no_auth"))
    st.subheader(t("assets.drift"))
    drifted = list_drifted()
    if drifted:
        st.dataframe(pd.DataFrame(drifted), use_container_width=True)
    else:
        st.caption(t("assets.drift_cap"))
