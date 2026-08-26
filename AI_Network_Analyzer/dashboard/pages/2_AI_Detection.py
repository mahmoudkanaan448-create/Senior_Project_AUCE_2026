"""
AI detection page.

Runs batch predictions on unprocessed flows and displays
results with confidence, threat score, and severity charts.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
from database.database import SessionLocal, init_db
from database.models import Prediction, NetworkFlow
from database import queries
from sqlalchemy import func
from dashboard.auth_gate import gate_page
from dashboard.ai_assistant import set_assistant_focus
from dashboard.i18n import t

st.set_page_config(page_title="AI Detection", page_icon="🤖", layout="wide")
gate_page("AI Detection")
st.title(f"🤖 {t('det.title')}")

init_db()
db = SessionLocal()
try:
    total_preds = db.query(Prediction).count()
    attacks = db.query(Prediction).filter(Prediction.prediction_label != "Normal").count()
    normals = db.query(Prediction).filter(Prediction.prediction_label == "Normal").count()
    avg_conf = db.query(func.avg(Prediction.confidence)).scalar() or 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("det.total"), total_preds)
    c2.metric(t("det.attacks"), attacks)
    c3.metric(t("det.normal"), normals)
    c4.metric(t("det.conf"), f"{avg_conf:.1f}%")

    st.markdown("---")

    st.subheader(t("det.run"))
    if st.button(t("det.analyze")):
        from detection.attack_detector import load_models, predict_single
        from detection.decision_engine import fuse_decisions
        from config import MODELS_DIR

        try:
            models = load_models(str(MODELS_DIR))

            unprocessed = (
                db.query(NetworkFlow)
                .filter(~NetworkFlow.flow_id.in_(
                    db.query(Prediction.flow_id).filter(Prediction.flow_id.isnot(None))
                ))
                .limit(500)
                .all()
            )
            if not unprocessed:
                st.warning(t("det.no_unproc"))
            else:
                progress = st.progress(0)
                count = 0
                for i, flow in enumerate(unprocessed):
                    import json
                    features = {}
                    if flow.features_json:
                        try:
                            features = json.loads(flow.features_json)
                        except Exception:
                            pass
                    features.update({
                        "duration": flow.duration or 0,
                        "packet_count": flow.packets or 0,
                        "byte_count": flow.bytes_total or 0,
                        "packet_rate": (flow.packets or 0) / max(flow.duration or 0.001, 0.001),
                        "flow_rate": (flow.bytes_total or 0) / max(flow.duration or 0.001, 0.001),
                    })
                    raw = predict_single(features, models)
                    result = fuse_decisions(raw)
                    from explainable_ai.xai import explain_with_models, explanation_to_json
                    xai = explain_with_models(
                        features,
                        result["final_label"],
                        models,
                        model_name=str(result.get("best_model") or "random_forest"),
                        confidence_score=float(result.get("confidence") or 0),
                        threat_score=float(result.get("threat_score") or 0),
                    )
                    result["xai"] = xai
                    pred = queries.insert_prediction(
                        db, flow_id=flow.flow_id,
                        model_name=result.get("best_model", "Hybrid"),
                        prediction_label=result["final_label"],
                        confidence=result["confidence"],
                        threat_score=result["threat_score"],
                        severity=result["severity"],
                        attack_type=result["final_label"],
                        recommendation=xai.get("recommended_action") or result.get("recommendation", ""),
                        explanation_json=explanation_to_json(xai),
                    )
                    # Create alerts for Medium+ findings
                    try:
                        from alerts.alert_manager import process_alert
                        conf = result["confidence"]
                        process_alert(
                            {
                                "severity": result["severity"],
                                "source_ip": flow.source_ip or "unknown",
                                "destination_ip": flow.destination_ip or "",
                                "destination_port": flow.destination_port or 0,
                                "packet_rate": flow.packet_rate or 0,
                                "flow_rate": flow.flow_rate or 0,
                                "packet_count": flow.packets or 0,
                                "byte_count": flow.bytes_total or 0,
                                "dns_query": (features or {}).get("dns_query", ""),
                                "prediction_label": result["final_label"],
                                "confidence": conf / 100.0 if conf > 1 else conf,
                                "attack_type": result["final_label"],
                                "threat_score": result["threat_score"],
                                "recommendation": xai.get("recommended_action") or result.get("recommendation", ""),
                                "prediction_id": pred.prediction_id,
                                "xai": xai,
                                "explanation_json": explanation_to_json(xai),
                                "features": features if isinstance(features, dict) else {},
                                "mitre": result.get("mitre") or {},
                            },
                            db,
                            apply_os_firewall=False,
                            send_notifications=True,
                        )
                    except Exception:
                        pass
                    count += 1
                    progress.progress((i + 1) / len(unprocessed))

                st.success(t("det.analyzed", n=count))
                try:
                    from database.models import Alert
                    newest = (
                        db.query(Alert)
                        .filter(Alert.status == "New")
                        .order_by(Alert.created_at.desc())
                        .first()
                    )
                    if newest and newest.priority in ("High", "Critical", "Medium"):
                        st.session_state.pending_attack_sound = True
                        st.session_state.pending_attack_sound_times = 8
                        st.session_state.pending_attack_toast = {
                            "title": f"{newest.priority} Attack",
                            "message": f"{newest.alert_type} — {(newest.message or '')[:80]}",
                        }
                        # Allow fragment to treat as new after rerun
                        seen = st.session_state.get("attack_seen_ids") or set()
                        if newest.alert_id in seen:
                            st.session_state.attack_seen_ids = seen - {newest.alert_id}
                except Exception:
                    pass
                st.rerun()
        except Exception as e:
            st.error(t("det.err_train", e=e))

    st.markdown("---")

    st.subheader(t("nav.sim"))
    st.caption(t("sim.caption"))
    st.page_link("pages/3_Threat_Simulation.py", label=t("home.open_sim"), icon="🎯")

    st.markdown("---")

    st.subheader(t("det.results"))
    preds = db.query(Prediction).order_by(Prediction.prediction_time.desc()).limit(200).all()
    if preds:
        set_assistant_focus(
            "flow",
            record_id=int(preds[0].flow_id or 0) or None,
            label=f"{preds[0].prediction_label} (score {preds[0].threat_score:.1f})",
        )
        data = [{
            "ID": p.prediction_id, "Flow": p.flow_id,
            "Model": p.model_name, "Label": p.prediction_label,
            "Confidence": f"{p.confidence:.1f}%",
            "Threat Score": f"{p.threat_score:.1f}",
            "Severity": p.severity,
            "XAI": t("common.yes") if getattr(p, "explanation_json", None) else t("common.no"),
            "Time": str(p.prediction_time),
        } for p in preds]
        st.dataframe(pd.DataFrame(data), use_container_width=True, height=400)

        from explainable_ai.xai import explanation_from_json
        from dashboard.xai_panel import render_xai_panel
        ids = [p.prediction_id for p in preds]
        pick = st.selectbox(t("xai.pick_pred"), ids)
        chosen = next((p for p in preds if p.prediction_id == pick), None)
        if chosen:
            render_xai_panel(explanation_from_json(getattr(chosen, "explanation_json", None)))

        ch1, ch2 = st.columns(2)

        with ch1:
            labels = [p.prediction_label for p in preds]
            label_counts = pd.Series(labels).value_counts()
            fig = px.pie(values=label_counts.values, names=label_counts.index,
                         title=t("det.chart_pred"), hole=0.4,
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig, use_container_width=True)

        with ch2:
            sevs = [p.severity for p in preds]
            sev_counts = pd.Series(sevs).value_counts()
            color_map = {"Low": "#00cc44", "Medium": "#ffcc00", "High": "#ff8800", "Critical": "#ff4444"}
            fig2 = px.bar(x=sev_counts.index, y=sev_counts.values,
                          title=t("det.chart_sev"),
                          color=sev_counts.index, color_discrete_map=color_map)
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(t("det.none"))
finally:
    db.close()
