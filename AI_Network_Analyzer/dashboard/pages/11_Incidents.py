"""SOC incident management – correlated alerts, kill-chain, case notes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from dashboard.auth_gate import gate_page
from dashboard.i18n import t, fmt_opt
from database.database import init_db

init_db()

st.set_page_config(page_title="Incidents", page_icon="🗂️", layout="wide")
gate_page("Incidents")
st.title(f"🗂️ {t('inc.title')}")
st.caption(t("inc.caption"))

from detection.correlation import list_incidents, set_incident_status
from soc.copilot import summarize_incident, recommend_response

status = st.selectbox(t("inc.filter"), ["All", "Open", "In Progress", "Resolved"], format_func=fmt_opt)
rows = list_incidents(status=None if status == "All" else status, limit=200)

c1, c2, c3, c4 = st.columns(4)
c1.metric(t("inc.count"), len(rows))
c2.metric(t("inc.open"), sum(1 for r in rows if r["Status"] == "Open"))
c3.metric(t("inc.progress"), sum(1 for r in rows if r["Status"] == "In Progress"))
c4.metric(t("inc.critical"), sum(1 for r in rows if r["Severity"] == "Critical"))

if rows:
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=360)
else:
    st.info(t("inc.none"))

st.markdown("---")
st.subheader(t("inc.update"))
col_a, col_b, col_c = st.columns(3)
with col_a:
    iid = st.number_input(t("inc.id"), min_value=1, step=1)
with col_b:
    new_st = st.selectbox(t("inc.status"), ["Open", "In Progress", "Resolved"], format_func=fmt_opt)
with col_c:
    owner = st.text_input(t("inc.owner"), value=(st.session_state.get("user") or {}).get("username", "analyst"))
notes = st.text_area(t("inc.notes"))
if st.button(t("inc.save"), type="primary"):
    ok = set_incident_status(int(iid), new_st, owner=owner, notes=notes)
    st.success(t("inc.updated")) if ok else st.error(t("inc.not_found"))
    if ok:
        st.rerun()

if rows:
    pick = st.selectbox(t("inc.ai_summary"), [r["ID"] for r in rows])
    st.code(summarize_incident(int(pick)))
    row = next(r for r in rows if r["ID"] == pick)
    rec = recommend_response(row["Title"].split(" ")[0], row["Severity"], row["Source IP"])
    st.json(rec)
