"""AI Security Copilot – NL hunt, incident summary, recommended response."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from dashboard.auth_gate import gate_page
from dashboard.i18n import t, fmt_opt
from database.database import init_db

init_db()

st.set_page_config(page_title="Copilot", page_icon="🧠", layout="wide")
gate_page("Copilot")
st.title(f"🧠 {t('copilot.title')}")
st.caption(t("copilot.caption"))

from soc.copilot import nl_query, summarize_incident, recommend_response, explain_attack, explain_alert
from detection.correlation import list_incidents

q = st.text_input(t("copilot.ask"), placeholder=t("copilot.ph"))
if st.button(t("copilot.go"), type="primary") or q:
    out = nl_query(q)
    st.info(out.get("answer", ""))
    rows = out.get("rows") or []
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

st.markdown("---")
c1, c2 = st.columns(2)
with c1:
    st.subheader(t("copilot.summary"))
    incs = list_incidents(limit=50)
    if incs:
        iid = st.selectbox(t("copilot.incident"), [r["ID"] for r in incs])
        st.code(summarize_incident(int(iid)))
    else:
        st.caption(t("copilot.none"))
with c2:
    st.subheader(t("copilot.rec"))
    atk = st.text_input(t("copilot.atk"), value="Exfiltration")
    sev = st.selectbox(t("copilot.sev"), ["Low", "Medium", "High", "Critical"], index=2, format_func=fmt_opt)
    sip = st.text_input(t("copilot.src"), value="10.0.0.12")
    if st.button(t("copilot.recommend")):
        rec = recommend_response(atk, sev, sip)
        st.json(rec)
        st.caption(t("copilot.rec_cap"))

st.markdown("---")
st.subheader(t("copilot.why"))
aid = st.number_input(t("copilot.alert_id"), min_value=0, step=1, value=0)
label = st.text_input(t("copilot.label"), value="LateralMovement")
evidence = st.text_input(t("copilot.evidence"), value="Internal 10.0.0.8 → 10.0.0.5:445")
if st.button(t("copilot.explain")):
    if aid:
        st.code(explain_alert(int(aid)))
    else:
        st.code(explain_attack(label, evidence))
