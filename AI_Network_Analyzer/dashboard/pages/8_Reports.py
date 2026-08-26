"""
Reports and export page.

Exports detection CSVs, manages incident reports, and
downloads Predictions, Alerts, or Blocked IPs.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime
from database.database import SessionLocal, init_db
from database.models import Prediction, Alert, BlockedIP, IncidentReport
from database import queries
from dashboard.auth_gate import gate_page
from dashboard.i18n import t

st.set_page_config(page_title="Reports", page_icon="📊", layout="wide")
gate_page("Reports")
st.title(f"📊 {t('reports.title')}")

init_db()
db = SessionLocal()
try:
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        t("reports.tab.det"), t("reports.tab.inc"), t("reports.tab.export"),
        t("reports.tab.comp"), t("reports.tab.evidence"),
    ])

    with tab1:
        st.subheader(t("reports.summary"))
        preds = db.query(Prediction).order_by(Prediction.prediction_time.desc()).limit(500).all()
        if preds:
            data = [{
                "ID": p.prediction_id, "Flow": p.flow_id,
                "Model": p.model_name, "Label": p.prediction_label,
                "Confidence": p.confidence, "Threat Score": p.threat_score,
                "Severity": p.severity, "Time": str(p.prediction_time),
            } for p in preds]
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)

            st.download_button(
                t("reports.dl_csv"), df.to_csv(index=False),
                file_name=f"detection_report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.info(t("reports.none_det"))

    with tab2:
        st.subheader(t("reports.incidents"))
        incidents = db.query(IncidentReport).order_by(IncidentReport.created_at.desc()).all()
        if incidents:
            data = [{
                "ID": i.incident_id, "Summary": (i.summary or "")[:100],
                "Status": i.status, "Analyst": i.analyst or "",
                "Created": str(i.created_at),
            } for i in incidents]
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.info(t("reports.none_inc"))

        st.markdown("---")

        st.subheader(t("reports.create"))
        summary = st.text_area(t("reports.summary_field"))
        analyst = st.text_input(t("reports.analyst"))
        if st.button(t("reports.create_btn")) and summary:
            queries.create_incident(db, summary=summary, analyst=analyst)
            st.success(t("reports.created"))
            st.rerun()

    with tab3:
        st.subheader(t("reports.export"))
        export_map = {
            t("reports.type.preds"): "Predictions",
            t("reports.type.alerts"): "Alerts",
            t("reports.type.blocked"): "Blocked IPs",
            t("reports.type.inc"): "Incidents",
        }
        export_label = st.selectbox(t("reports.type"), list(export_map.keys()))
        export_type = export_map[export_label]
        if st.button(t("reports.gen")):
            if export_type == "Predictions":
                items = db.query(Prediction).all()
                data = [{"ID": i.prediction_id, "Label": i.prediction_label,
                         "Confidence": i.confidence, "Threat": i.threat_score,
                         "Severity": i.severity, "Time": str(i.prediction_time)}
                        for i in items]
            elif export_type == "Alerts":
                items = db.query(Alert).all()
                data = [{"ID": i.alert_id, "Type": i.alert_type,
                         "Priority": i.priority, "Status": i.status,
                         "Time": str(i.created_at)} for i in items]
            elif export_type == "Blocked IPs":
                items = db.query(BlockedIP).all()
                data = [{"IP": i.ip_address, "Attack": i.attack_type,
                         "Status": i.status, "Time": str(i.blocked_at)}
                        for i in items]
            else:
                from database.models import SocIncident
                items = db.query(SocIncident).all()
                data = [{"ID": i.incident_id, "Title": i.title, "Severity": i.severity,
                         "Status": i.status, "Chain": i.attack_chain, "Time": str(i.created_at)}
                        for i in items]

            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)
                st.download_button(
                    t("reports.dl_csv"), df.to_csv(index=False),
                    file_name=f"{export_type.lower()}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )
                st.download_button(
                    t("reports.dl_json"), df.to_json(orient="records", indent=2),
                    file_name=f"{export_type.lower()}_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                )
            else:
                st.info(t("reports.none_export", kind=export_label))

        if st.button(t("reports.digest")):
            from reports.report_generator import generate_daily_report
            path = generate_daily_report(db)
            st.success(path or "Failed")

    with tab4:
        st.subheader(t("reports.comp_title"))
        from reports.scheduler import compliance_summary
        snap = compliance_summary()
        st.json(snap)
        import json as _json
        st.download_button(
            t("reports.dl_json"),
            _json.dumps(snap, default=str, indent=2),
            file_name=f"compliance_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
        )
        st.caption(t("reports.comp_cap"))

    with tab5:
        st.subheader(t("reports.evidence_title"))
        st.caption(t("reports.evidence_cap"))
        if st.button(t("reports.evidence_snap"), type="primary"):
            from ops.session_evidence import write_evidence_report
            path = write_evidence_report()
            st.success(str(path))
            st.rerun()
        from config import REPORTS_DIR, MODELS_DIR
        import json as _json
        latest = REPORTS_DIR / "live_session_evidence.json"
        if latest.exists():
            snap = _json.loads(latest.read_text(encoding="utf-8"))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(t("reports.ev_flows"), snap.get("flows_total", 0))
            c2.metric(t("reports.ev_live"), snap.get("live_or_lan_flows", 0))
            c3.metric(t("reports.ev_sim"), snap.get("simulation_flows", 0))
            c4.metric(t("reports.ev_level"), str(snap.get("evidence_level", "")))
            st.json(snap)
            st.download_button(
                t("reports.dl_json"),
                _json.dumps(snap, indent=2),
                file_name="live_session_evidence.json",
                mime="application/json",
            )
        else:
            st.info(t("reports.evidence_none"))

        st.markdown("---")
        st.subheader(t("reports.eval_title"))
        eval_path = MODELS_DIR / "eval_metrics.json"
        if eval_path.exists():
            ev = _json.loads(eval_path.read_text(encoding="utf-8"))
            ds = ev.get("dataset") or {}
            st.caption(ds.get("disclaimer") or "")
            st.write(
                f"{ds.get('name')} · {ds.get('rows')} rows · {ds.get('features')} features"
            )
            rows = []
            for name in ("RandomForest", "XGBoost", "IsolationForest"):
                m = ev.get(name) or (ev.get("metrics") or {}).get(name) or {}
                if "accuracy" in m:
                    rows.append({
                        "Model": name,
                        "Accuracy": f"{m['accuracy']*100:.1f}%",
                        "Precision": f"{m.get('precision', 0)*100:.1f}%",
                        "Recall": f"{m.get('recall', 0)*100:.1f}%",
                        "F1": f"{m.get('f1', 0)*100:.1f}%",
                    })
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            per = (ev.get("RandomForest") or {}).get("per_class") or {}
            if per:
                st.caption(t("reports.eval_perclass"))
                st.dataframe(pd.DataFrame(per).T, use_container_width=True)
        else:
            st.caption(t("reports.eval_none"))
finally:
    db.close()
