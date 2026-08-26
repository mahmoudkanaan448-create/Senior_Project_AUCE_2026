"""
AI models performance page.

Displays accuracy/precision/recall/F1 charts and provides
a UI to upload a dataset and train all models.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from database.database import SessionLocal, init_db
from database.models import AIModel, ModelHistory
from dashboard.auth_gate import gate_page
from dashboard.i18n import t

st.set_page_config(page_title="AI Models", page_icon="🧠", layout="wide")
gate_page("AI Models")
st.title(f"🧠 {t('models.title')}")

init_db()
db = SessionLocal()
try:
    models = db.query(AIModel).all()

    if models:
        data = [{
            "Model": m.model_name, "Version": m.version,
            "Accuracy": f"{m.accuracy * 100:.1f}%",
            "Precision": f"{m.precision_score * 100:.1f}%",
            "Recall": f"{m.recall * 100:.1f}%",
            "F1 Score": f"{m.f1_score * 100:.1f}%",
            "Status": m.status,
            "Trained": str(m.training_date),
        } for m in models]
        st.dataframe(pd.DataFrame(data), use_container_width=True)

        st.markdown("---")

        st.subheader(t("models.radar"))
        fig = go.Figure()
        colors = ["#00d4ff", "#ff4444", "#00cc44", "#ffcc00", "#ff8800"]
        for i, m in enumerate(models):
            fig.add_trace(go.Scatterpolar(
                r=[m.accuracy, m.precision_score, m.recall, m.f1_score],
                theta=["Accuracy", "Precision", "Recall", "F1 Score"],
                fill="toself",
                name=m.model_name,
                line_color=colors[i % len(colors)],
            ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            height=500,
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader(t("models.acc"))
        names = [m.model_name for m in models]
        accs = [m.accuracy * 100 for m in models]
        fig2 = px.bar(x=names, y=accs, title=t("models.acc_title"),
                      color=accs, color_continuous_scale="Viridis")
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(t("models.none"))

    st.markdown("---")

    st.subheader(t("models.train"))
    st.markdown(t("models.upload"))
    uploaded = st.file_uploader(t("models.csv"), type=["csv"])
    if uploaded and st.button(t("models.start")):
        import tempfile, os
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        try:
            from training.train_all import train_all_models
            with st.spinner(t("models.spinner")):
                results = train_all_models(tmp_path)
            st.success(t("models.done"))
            st.json(results)
            st.rerun()
        except Exception as e:
            st.error(t("models.fail", e=e))
        finally:
            os.unlink(tmp_path)
    st.markdown("---")
    st.subheader(t("models.online"))
    st.caption(t("models.online_cap"))
    try:
        from training.online_learning import get_online_status, maybe_incremental_train
        ol = get_online_status()
        oc1, oc2 = st.columns(2)
        oc1.metric(t("models.buffer"), ol.get("buffer", {}).get("count", 0))
        oc2.metric(t("models.ready"), t("common.yes") if ol.get("model_exists") else t("common.no"))
        if st.button(t("models.train_online")):
            st.json(maybe_incremental_train(force=True))
    except Exception as exc:
        st.caption(t("models.online_unavail", e=exc))

finally:
    db.close()
