"""
Alerts management page.

Lists alerts with status filters and lets analysts update
status (New / Investigating / Closed).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from database.database import SessionLocal, init_db
from database.models import Alert
from database import queries
from dashboard.auth_gate import gate_page
from dashboard.ai_assistant import set_assistant_focus
from dashboard.i18n import t, fmt_opt

st.set_page_config(page_title="Alerts", page_icon="🚨", layout="wide")
gate_page("Alerts")
st.title(f"🚨 {t('alerts.title')}")

init_db()
db = SessionLocal()
try:
    total = db.query(Alert).count()
    new_alerts = db.query(Alert).filter(Alert.status == "New").count()
    investigating = db.query(Alert).filter(Alert.status == "Investigating").count()
    closed = db.query(Alert).filter(Alert.status == "Closed").count()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("alerts.total"), total)
    c2.metric(t("alerts.new"), new_alerts)
    c3.metric(t("alerts.inv"), investigating)
    c4.metric(t("alerts.closed"), closed)

    st.markdown("---")

    filter_status = st.selectbox(
        t("alerts.filter"),
        ["All", "New", "Investigating", "Closed"],
        format_func=fmt_opt,
    )
    status_val = None if filter_status == "All" else filter_status

    alerts = queries.get_alerts(db, status=status_val, limit=200)
    if alerts:
        data = [{
            "ID": a.alert_id,
            "Type": a.alert_type,
            "Priority": a.priority,
            "Status": a.status,
            "MITRE": "",
            "Message": (a.message or "")[:100],
            "Time": str(a.created_at),
        } for a in alerts]
        try:
            from threat_intelligence.mitre_map import format_mitre_short
            for row in data:
                row["MITRE"] = format_mitre_short(row["Type"])
        except Exception:
            pass
        st.dataframe(pd.DataFrame(data), use_container_width=True, height=400)

        st.markdown("---")
        st.subheader(t("xai.title"))
        explain_id = st.number_input(t("alerts.id"), min_value=1, step=1, key="xai_alert")
        if explain_id:
            from database.models import Prediction
            from explainable_ai.xai import explanation_from_json
            from dashboard.xai_panel import render_xai_panel
            picked = db.query(Alert).filter(Alert.alert_id == int(explain_id)).first()
            if picked and picked.prediction_id:
                pred_row = db.query(Prediction).filter(Prediction.prediction_id == picked.prediction_id).first()
                xai = explanation_from_json(getattr(pred_row, "explanation_json", None) if pred_row else None)
                if not xai and pred_row:
                    from explainable_ai.xai import explain_features_only
                    xai = explain_features_only(
                        {},
                        pred_row.prediction_label or picked.alert_type or "Unknown",
                        confidence_score=float(pred_row.confidence or 0),
                        threat_score=float(pred_row.threat_score or 0),
                    )
                render_xai_panel(xai)
            elif picked:
                st.caption(t("xai.none"))

        st.markdown("---")

        st.subheader(t("alerts.update"))
        alert_id = st.number_input(t("alerts.id"), min_value=1, step=1)
        set_assistant_focus("alert", record_id=int(alert_id), label=f"Alert #{int(alert_id)}")
        new_status = st.selectbox(t("alerts.new_status"), ["New", "Investigating", "Closed"], format_func=fmt_opt)
        if st.button(t("alerts.update_btn")):
            alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
            if alert:
                alert.status = new_status
                db.commit()
                st.success(t("alerts.updated", id=alert_id, status=fmt_opt(new_status)))
                st.rerun()
            else:
                st.error(t("alerts.not_found"))

        st.markdown("---")
        st.subheader(t("alerts.feedback"))
        st.caption(t("alerts.feedback_cap"))
        fid = st.number_input(t("alerts.fb_id"), min_value=1, step=1, key="fb_alert")
        comment = st.text_input(t("alerts.comment"))
        b1, b2, b3 = st.columns(3)
        analyst = (st.session_state.get("user") or {}).get("username", "analyst")
        from soc.feedback import record_feedback, list_feedback, fp_rate
        with b1:
            if st.button(f"👍 {t('alerts.tp')}"):
                st.json(record_feedback(int(fid), "true_positive", analyst=analyst, comment=comment))
                st.rerun()
        with b2:
            if st.button(f"👎 {t('alerts.fp')}"):
                st.json(record_feedback(int(fid), "false_positive", analyst=analyst, comment=comment))
                st.rerun()
        with b3:
            st.json(fp_rate())
        fb = list_feedback(40)
        if fb:
            st.dataframe(pd.DataFrame(fb), use_container_width=True, height=220)
    else:
        st.info(t("alerts.none"))
finally:
    db.close()
