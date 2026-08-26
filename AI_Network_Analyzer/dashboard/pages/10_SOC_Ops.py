"""
SOC Operations – MITRE ATT&CK, SOAR Playbooks, Online Learning, Server Health.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from dashboard.auth_gate import gate_page
from dashboard.i18n import t

st.set_page_config(page_title="SOC Ops", page_icon="🧭", layout="wide")
gate_page("SOC Ops")
st.title(f"🧭 {t('soc.title')}")
st.caption(t("soc.caption"))

tab_mitre, tab_soar, tab_online, tab_health, tab_ml = st.tabs(
    [t("soc.tab.mitre"), t("soc.tab.soar"), t("soc.tab.online"), t("soc.tab.health"), t("soc.tab.ml")]
)

with tab_mitre:
    st.subheader(t("soc.mitre_map"))
    try:
        from threat_intelligence.mitre_map import list_all_mappings, map_attack_to_mitre
        rows = list_all_mappings()
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=420)
        pick = st.selectbox(t("soc.inspect"), [r["Attack Label"] for r in rows])
        detail = map_attack_to_mitre(pick)
        st.json(detail)
    except Exception as exc:
        st.error(t("soc.mitre_err", e=exc))

with tab_soar:
    st.subheader(t("soc.playbooks"))
    try:
        from soar.playbooks import list_playbooks
        pb = list_playbooks()
        st.dataframe(pd.DataFrame(pb), use_container_width=True, height=480)
        st.info(t("soc.playbooks_info"))
    except Exception as exc:
        st.error(t("soc.soar_err", e=exc))

with tab_online:
    st.subheader(t("soc.online_title"))
    st.markdown(t("soc.online_md"))
    try:
        from training.online_learning import get_online_status, maybe_incremental_train
        status = get_online_status()
        c1, c2, c3 = st.columns(3)
        c1.metric(t("soc.buffer"), status.get("buffer", {}).get("count", 0))
        c2.metric(t("soc.min"), status.get("min_samples", 40))
        c3.metric(t("soc.online_model"), t("common.yes") if status.get("model_exists") else t("common.no"))
        if status.get("buffer", {}).get("labels"):
            st.write(t("soc.labels"))
            st.json(status["buffer"]["labels"])
        if status.get("meta"):
            st.write(t("soc.meta"))
            st.json(status["meta"])
        if st.button(t("soc.force_train"), type="primary"):
            result = maybe_incremental_train(force=True)
            st.success(result if result.get("trained") else result)
            st.rerun()
    except Exception as exc:
        st.error(t("soc.online_err", e=exc))

with tab_health:
    st.subheader(t("soc.health_title"))
    st.markdown(t("soc.health_md"))
    try:
        from ops.health import collect_health, try_auto_heal
        health = collect_health()
        st.metric(t("soc.overall"), health.get("status", "?"))
        st.json(health)
        if st.button(t("soc.heal")):
            st.json(try_auto_heal())
            st.rerun()
        try:
            from ops.retention import capture_health
            from monitoring.sensors import list_sensors
            st.subheader(t("soc.capture"))
            st.json(capture_health())
            sens = list_sensors()
            if sens:
                st.dataframe(pd.DataFrame(sens), use_container_width=True)
        except Exception as exc:
            st.caption(str(exc))
        if st.button(t("soc.bench")):
            from ops.benchmarks import detection_latency, load_flows_per_sec, false_positive_benchmark
            st.json({
                "latency": detection_latency(12),
                "load": load_flows_per_sec(),
                "fp": false_positive_benchmark(),
            })
    except Exception as exc:
        st.error(t("soc.health_err", e=exc))

with tab_ml:
    st.subheader(t("soc.registry"))
    try:
        from database.database import SessionLocal
        from database.models import AIModel, ModelHistory
        db = SessionLocal()
        try:
            models = db.query(AIModel).all()
            hist = db.query(ModelHistory).order_by(ModelHistory.history_id.desc()).limit(40).all()
            if models:
                st.dataframe(pd.DataFrame([{
                    "Model": m.model_name, "Version": m.version, "Accuracy": m.accuracy,
                    "Precision": m.precision_score, "Recall": m.recall, "F1": m.f1_score,
                    "Status": m.status, "Trained": str(m.training_date),
                } for m in models]), use_container_width=True)
            if hist:
                st.caption(t("soc.history"))
                st.dataframe(pd.DataFrame([{
                    "Model": h.model_name, "Dataset": h.dataset, "Acc": h.accuracy,
                    "F1": h.f1_score, "When": str(h.trained_at),
                } for h in hist]), use_container_width=True)
        finally:
            db.close()
        from training.dataset_registry import list_datasets, scan_local, register_dataset
        st.write(t("soc.datasets"))
        st.json(list_datasets())
        local = scan_local()
        pick = st.selectbox(t("soc.register_file"), ["-"] + local)
        if st.button(t("soc.register")) and pick != "-":
            st.json(register_dataset(pick, note="dashboard"))
        from detection.baselines import list_drifted
        st.subheader(t("soc.drift"))
        drifted = list_drifted()
        if drifted:
            st.dataframe(pd.DataFrame(drifted), use_container_width=True)
        else:
            st.caption(t("soc.no_drift"))
    except Exception as exc:
        st.error(str(exc))
