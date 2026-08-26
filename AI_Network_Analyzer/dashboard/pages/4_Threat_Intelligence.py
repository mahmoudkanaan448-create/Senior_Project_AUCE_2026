"""
Threat intelligence page.

Looks up IP reputation and geo-location, and lists stored
ThreatIntelligence records with a top-countries chart.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard.auth_gate import gate_page
from dashboard.ai_assistant import set_assistant_focus
from dashboard.i18n import t

st.set_page_config(page_title="Threat Intelligence", page_icon="🌐", layout="wide")
gate_page("Threat Intelligence")
st.title(f"🌐 {t('ti.title')}")

st.subheader(t("ti.lookup"))
ip_input = st.text_input(t("ti.enter"), placeholder="e.g. 185.220.101.1")
if ip_input.strip():
    set_assistant_focus("ip", value=ip_input.strip(), label=f"IP {ip_input.strip()}")

if st.button(t("ti.lookup_btn")) and ip_input:
    try:
        from threat_intelligence.ip_lookup import lookup_ip
        from threat_intelligence.geo_location import get_location

        with st.spinner(t("ti.spinner")):
            result = lookup_ip(ip_input)
            geo = get_location(ip_input)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"### {t('ti.rep')}")
            st.json(result)

        with col2:
            st.markdown(f"### {t('ti.geo')}")
            st.json(geo)

            if geo.get("lat") and geo.get("lon"):
                map_data = pd.DataFrame({
                    "lat": [geo["lat"]],
                    "lon": [geo["lon"]],
                })
                st.map(map_data, zoom=4)

        threat_score = result.get("threat_score", 0)
        if threat_score >= 8:
            st.error(t("ti.crit", score=threat_score))
        elif threat_score >= 6:
            st.warning(t("ti.high", score=threat_score))
        elif threat_score >= 4:
            st.info(t("ti.med", score=threat_score))
        else:
            st.success(t("ti.low", score=threat_score))

    except Exception as e:
        st.error(t("ti.fail", e=e))

st.markdown("---")

st.subheader(t("ti.stored"))
from database.database import SessionLocal, init_db
from database.models import ThreatIntelligence

init_db()
db = SessionLocal()
try:
    records = db.query(ThreatIntelligence).order_by(ThreatIntelligence.last_seen.desc()).limit(100).all()
    if records:
        data = [{
            "IP": r.ip_address, "Country": r.country, "City": r.city,
            "ISP": r.isp, "ASN": r.asn, "Reputation": r.reputation,
            "Threat Score": r.threat_score, "Reports": r.reports,
            "Blacklisted": t("common.yes") if r.blacklisted else t("common.no"),
        } for r in records]
        st.dataframe(pd.DataFrame(data), use_container_width=True)

        countries = [r.country for r in records if r.country]
        if countries:
            country_counts = pd.Series(countries).value_counts().head(10)
            import plotly.express as px
            fig = px.bar(x=country_counts.index, y=country_counts.values,
                         title=t("ti.chart_countries"),
                         color=country_counts.values, color_continuous_scale="Reds")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig, use_container_width=True)
            try:
                df_geo = pd.DataFrame(country_counts.reset_index())
                df_geo.columns = ["country", "count"]
                fig_map = px.choropleth(
                    df_geo, locations="country", locationmode="country names",
                    color="count", color_continuous_scale="Reds",
                    title=t("ti.chart_map"),
                )
                fig_map.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white", height=420)
                st.plotly_chart(fig_map, use_container_width=True)
            except Exception:
                pass
    else:
        st.info(t("ti.none"))
finally:
    db.close()
