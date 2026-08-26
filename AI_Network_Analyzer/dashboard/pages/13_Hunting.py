"""Threat hunting, forensics PCAP, protocol / DNS / TLS investigation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from dashboard.auth_gate import gate_page
from dashboard.i18n import t
from database.database import init_db

init_db()

st.set_page_config(page_title="Hunting", page_icon="🔎", layout="wide")
gate_page("Hunting")
st.title(f"🔎 {t('hunt.title')}")
st.caption(t("hunt.caption"))

from soc.hunting import hunt
from monitoring.pcap_store import list_evidence
from monitoring.dpi import WELL_KNOWN, tls_cert_flags
from threat_intelligence.domain_intel import score_domain, lookup_hash

tab1, tab2, tab3 = st.tabs([t("hunt.tab.hunt"), t("hunt.tab.pcap"), t("hunt.tab.proto")])

with tab1:
    c1, c2, c3 = st.columns(3)
    ip = c1.text_input(t("hunt.ip"))
    attack = c2.text_input(t("hunt.attack"))
    proto = c3.text_input(t("hunt.proto"))
    if st.button(t("hunt.run"), type="primary") or ip or attack:
        result = hunt(ip=ip.strip(), attack=attack.strip(), protocol=proto.strip(), limit=200)
        st.metric(t("sim.flows"), len(result["flows"]))
        st.dataframe(pd.DataFrame(result["flows"]), use_container_width=True, height=260)
        st.metric(t("sim.alerts"), len(result["alerts"]))
        st.dataframe(pd.DataFrame(result["alerts"]), use_container_width=True, height=220)
        st.dataframe(pd.DataFrame(result["predictions"]), use_container_width=True, height=180)

with tab2:
    ev = list_evidence(80)
    if ev:
        st.dataframe(pd.DataFrame(ev), use_container_width=True, height=360)
        st.caption(t("hunt.pcap_cap"))
    else:
        st.info(t("hunt.no_pcap"))

with tab3:
    st.subheader(t("hunt.services"))
    st.dataframe(pd.DataFrame([{"Port": p, "Service": s} for p, s in WELL_KNOWN.items()]), height=220)
    d = st.text_input(t("hunt.domain"))
    if d:
        st.json(score_domain(d))
    sni = st.text_input(t("hunt.sni"))
    issuer = st.text_input(t("hunt.issuer"))
    if sni or issuer:
        st.json(tls_cert_flags(issuer=issuer, sni=sni))
    h = st.text_input(t("hunt.hash"))
    if h:
        st.json(lookup_hash(h))
