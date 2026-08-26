"""
AI Network Analyzer – Streamlit home dashboard.

Shows KPIs, traffic/attack charts, model performance, and recent
alerts, predictions, and blocked IPs.

Run: streamlit run dashboard/home.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from database.database import SessionLocal, init_db
from database import queries
from database.models import (
    NetworkFlow, Prediction, Alert, BlockedIP, ThreatIntelligence, AIModel,
)
from sqlalchemy import func
from dashboard.auth_gate import footer, gate_page
from dashboard.i18n import t


def style_fig(fig):
    """High-contrast dark Plotly layout (navy + gold theme)."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(18,35,61,0.7)",
        font=dict(color="#f8fafc", size=13),
        title_font=dict(color="#ffffff", size=15),
        legend=dict(font=dict(color="#f1f5f9", size=12)),
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(color="#e2e8f0", gridcolor="#1e3a5f", zerolinecolor="#334155"),
        yaxis=dict(color="#e2e8f0", gridcolor="#1e3a5f", zerolinecolor="#334155"),
    )
    return fig


st.set_page_config(
    page_title="AI Network Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

gate_page("AI Network Analyzer")

st.markdown(f'<div class="main-header">{t("app.full_title")}</div>',
            unsafe_allow_html=True)
st.markdown(f'<div class="sub-header-line">{t("app.subtitle")}</div>',
            unsafe_allow_html=True)

def get_db():
    """Initialise DB and return a new session."""
    init_db()
    return SessionLocal()


db = get_db()
try:
    total_flows = db.query(NetworkFlow).count()
    total_predictions = db.query(Prediction).count()
    total_alerts = db.query(Alert).count()
    active_alerts = db.query(Alert).filter(Alert.status == "New").count()
    blocked_count = db.query(BlockedIP).filter(BlockedIP.status == "Active").count()
    attack_count = db.query(Prediction).filter(Prediction.prediction_label != "Normal").count()
    normal_count = db.query(Prediction).filter(Prediction.prediction_label == "Normal").count()
    avg_threat = db.query(func.avg(Prediction.threat_score)).scalar() or 0
    avg_confidence = db.query(func.avg(Prediction.confidence)).scalar() or 0
    open_inc = asset_n = sensor_n = 0
    try:
        from database.orm import ensure_models
        _m = ensure_models()
        SocIncident, Asset, Sensor = _m.SocIncident, _m.Asset, _m.Sensor
        open_inc = db.query(SocIncident).filter(SocIncident.status.in_(["Open", "In Progress"])).count()
        asset_n = db.query(Asset).count()
        sensor_n = db.query(Sensor).count()
    except Exception:
        pass

    st.markdown(f'<div class="section-title">{t("home.overview")}</div>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
    col1.metric(t("home.metric.flows"), f"{total_flows:,}")
    col2.metric(t("home.metric.preds"), f"{total_predictions:,}")
    col3.metric(t("home.metric.attacks"), f"{attack_count:,}", delta=f"{normal_count} {t('home.normal').lower()}")
    col4.metric(t("home.metric.alerts"), active_alerts, delta="new" if active_alerts > 0 else None)
    col5.metric(t("home.metric.blocked"), blocked_count)
    col6.metric(t("home.metric.threat"), f"{avg_threat:.1f}/10")
    col7.metric(t("home.metric.incidents"), open_inc)
    col8.metric(t("home.metric.assets"), f"{asset_n}/{sensor_n}")

    st.markdown("---")
    st.markdown(f'<div class="section-title">{t("home.charts")}</div>', unsafe_allow_html=True)

    chart_col1, chart_col2, chart_col3 = st.columns(3)

    with chart_col1:
        st.subheader(t("home.traffic"))
        if total_predictions > 0:
            fig_pie = px.pie(
                values=[normal_count, attack_count],
                names=[t("home.normal"), t("home.attack")],
                color_discrete_sequence=["#22c55e", "#ef4444"],
                hole=0.4,
            )
            style_fig(fig_pie)
            fig_pie.update_layout(height=320, font_color="#f8fafc")
            fig_pie.update_traces(textfont_color="#ffffff", textinfo="label+percent")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info(t("home.no_preds"))

    with chart_col2:
        st.subheader(t("home.attack_types"))
        attack_types = (
            db.query(Prediction.attack_type, func.count(Prediction.prediction_id))
            .filter(Prediction.prediction_label != "Normal")
            .group_by(Prediction.attack_type)
            .all()
        )
        if attack_types:
            df_attacks = pd.DataFrame(attack_types, columns=["Attack", "Count"])
            fig_bar = px.bar(df_attacks, x="Attack", y="Count",
                             color="Count", color_continuous_scale="Reds")
            style_fig(fig_bar)
            fig_bar.update_layout(height=320)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info(t("home.no_attacks"))

    with chart_col3:
        st.subheader(t("home.severity"))
        severities = (
            db.query(Prediction.severity, func.count(Prediction.prediction_id))
            .group_by(Prediction.severity)
            .all()
        )
        if severities:
            df_sev = pd.DataFrame(severities, columns=["Severity", "Count"])
            color_map = {"Low": "#22c55e", "Medium": "#eab308", "High": "#f97316", "Critical": "#ef4444"}
            fig_sev = px.bar(df_sev, x="Severity", y="Count",
                             color="Severity", color_discrete_map=color_map)
            style_fig(fig_sev)
            fig_sev.update_layout(height=320)
            st.plotly_chart(fig_sev, use_container_width=True)
        else:
            st.info(t("home.no_sev"))

    st.markdown("---")
    st.markdown(f'<div class="section-title">{t("home.models")}</div>', unsafe_allow_html=True)
    models = db.query(AIModel).all()
    if models:
        model_data = []
        for m in models:
            model_data.append({
                "Model": m.model_name,
                "Accuracy": m.accuracy,
                "Precision": m.precision_score,
                "Recall": m.recall,
                "F1 Score": m.f1_score,
            })
        df_models = pd.DataFrame(model_data)

        fig_radar = go.Figure()
        for _, row in df_models.iterrows():
            fig_radar.add_trace(go.Scatterpolar(
                r=[row["Accuracy"], row["Precision"], row["Recall"], row["F1 Score"]],
                theta=["Accuracy", "Precision", "Recall", "F1 Score"],
                fill="toself",
                name=row["Model"],
            ))
        style_fig(fig_radar)
        fig_radar.update_layout(
            polar=dict(
                bgcolor="rgba(30,41,59,0.8)",
                radialaxis=dict(visible=True, range=[0, 1], gridcolor="#64748b", color="#f8fafc"),
                angularaxis=dict(color="#f8fafc", gridcolor="#475569"),
            ),
            height=420,
            legend=dict(font=dict(color="#f8fafc", size=12)),
        )
        st.plotly_chart(fig_radar, use_container_width=True)
        st.dataframe(df_models, use_container_width=True)
    else:
        st.info(t("home.no_models"))

    st.markdown("---")
    st.markdown(f'<div class="section-title">{t("home.quick")}</div>', unsafe_allow_html=True)
    q1, q2, q3, q4, q5, q6 = st.columns(6)
    with q1:
        st.markdown(f"**🎯 {t('nav.sim')}**")
        st.page_link("pages/3_Threat_Simulation.py", label=t("home.open_sim"), icon="🎯")
    with q2:
        st.markdown(f"**📡 {t('nav.live')}**")
        st.page_link("pages/1_Live_Monitoring.py", label=t("home.open_live"), icon="📡")
    with q3:
        st.markdown(f"**🗂️ {t('nav.incidents')}**")
        st.page_link("pages/11_Incidents.py", label=t("home.open_inc"), icon="🗂️")
    with q4:
        st.markdown(f"**🖥️ {t('nav.assets')}**")
        st.page_link("pages/12_Assets.py", label=t("home.open_assets"), icon="🖥️")
    with q5:
        st.markdown(f"**🔎 {t('nav.hunting')}**")
        st.page_link("pages/13_Hunting.py", label=t("home.open_hunt"), icon="🔎")
    with q6:
        st.markdown(f"**🧠 {t('nav.copilot')}**")
        st.page_link("pages/15_Copilot.py", label=t("home.open_copilot"), icon="🧠")
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.page_link("pages/14_Response.py", label=t("nav.response"), icon="🛡️")
    with r2:
        st.page_link("pages/10_SOC_Ops.py", label=t("nav.soc"), icon="🧭")
    with r3:
        st.page_link("pages/2_AI_Detection.py", label=t("nav.detection"), icon="🤖")
    with r4:
        st.page_link("pages/5_Alerts.py", label=t("nav.alerts"), icon="🚨")

    st.markdown("---")
    st.markdown(f'<div class="section-title">{t("home.recent_alerts")}</div>', unsafe_allow_html=True)
    recent_alerts = queries.get_alerts(db, limit=20)
    if recent_alerts:
        alert_data = []
        for a in recent_alerts:
            alert_data.append({
                "ID": a.alert_id,
                "Type": a.alert_type,
                "Priority": a.priority,
                "Status": a.status,
                "Message": a.message or "",
                "Time": str(a.created_at),
            })
        st.dataframe(pd.DataFrame(alert_data), use_container_width=True)
    else:
        st.info(t("home.no_alerts"))

    st.markdown(f'<div class="section-title">{t("home.recent_preds")}</div>', unsafe_allow_html=True)
    recent_preds = queries.get_recent_predictions(db, limit=20)
    if recent_preds:
        pred_data = []
        for p in recent_preds:
            pred_data.append({
                "ID": p.prediction_id,
                "Model": p.model_name,
                "Label": p.prediction_label,
                "Confidence": f"{p.confidence:.1f}%",
                "Threat": f"{p.threat_score:.1f}",
                "Severity": p.severity,
                "Time": str(p.prediction_time),
            })
        st.dataframe(pd.DataFrame(pred_data), use_container_width=True)
    else:
        st.info(t("home.no_preds"))

    st.markdown(f'<div class="section-title">{t("home.blocked")}</div>', unsafe_allow_html=True)
    blocked = queries.get_blocked_ips(db)
    if blocked:
        block_data = []
        for b in blocked:
            block_data.append({
                "IP": b.ip_address,
                "Attack": b.attack_type,
                "Blocked At": str(b.blocked_at),
                "By": b.blocked_by,
                "Reason": b.reason or "",
            })
        st.dataframe(pd.DataFrame(block_data), use_container_width=True)
    else:
        st.info(t("home.no_blocked"))

finally:
    db.close()

footer()
