"""
Threat Simulation – core SOC module for controlled attack generation.

Runs synthetic attack campaigns through the live Hybrid AI pipeline
(flows → detection → alerts → Telegram → local sound/balloon).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from dashboard.auth_gate import gate_page
from dashboard.i18n import t
from database.database import SessionLocal, init_db
from detection.attack_simulator import SCENARIOS, list_scenarios, run_simulation

st.set_page_config(page_title="Threat Simulation", page_icon="🎯", layout="wide")
gate_page("Threat Simulation")
st.title(f"🎯 {t('sim.title')}")
st.caption(t("sim.caption"))

init_db()

st.markdown(t("sim.pipeline"))

c1, c2 = st.columns([2, 1])
with c1:
    scenario = st.selectbox(
        t("sim.campaign"),
        options=list_scenarios(),
        index=list_scenarios().index("Mixed") if "Mixed" in list_scenarios() else 0,
    )
    if scenario in SCENARIOS:
        st.caption(SCENARIOS[scenario]["description"])
with c2:
    count = st.slider(t("sim.count"), min_value=1, max_value=20, value=5)

st.subheader(t("sim.response"))
o1, o2, o3, o4 = st.columns(4)
with o1:
    create_alerts = st.checkbox(t("sim.create_alerts"), value=True)
with o2:
    block_critical = st.checkbox(t("sim.block_crit"), value=True)
with o3:
    try:
        from ops.company import allow_forced_demo_labels
        _lab = allow_forced_demo_labels()
    except Exception:
        _lab = True
    ensure_labels = st.checkbox(t("sim.ensure"), value=_lab, disabled=not _lab)
    if not _lab:
        st.caption(t("sim.ensure_off"))
with o4:
    send_notifications = st.checkbox(t("sim.telegram"), value=True)

st.markdown("---")

run = st.button(f"▶ {t('sim.launch')}", type="primary", use_container_width=True)
if run:
    db = SessionLocal()
    try:
        with st.spinner(t("sim.spinner")):
            summary = run_simulation(
                db,
                scenario=scenario,
                count=count,
                create_alerts=create_alerts,
                block_critical=block_critical,
                force_demo_label=ensure_labels,
                send_notifications=send_notifications,
            )

        # Guarantee one Telegram summary from this page (fresh import)
        tg_ok = False
        tg_detail = ""
        if send_notifications and summary.get("attacks_detected", 0) > 0:
            try:
                import importlib
                import alerts.telegram_alert as tg
                importlib.reload(tg)
                msg = (
                    f"AI-NDR CAMPAIGN\n"
                    f"Scenario: {scenario}\n"
                    f"Attacks: {summary.get('attacks_detected', 0)}\n"
                    f"Alerts: {summary.get('alerts_created', 0)}\n"
                    f"Per-alert Telegram sent: {summary.get('telegram_sent', 0)}\n"
                    f"Failed: {summary.get('telegram_failed', 0)}"
                )
                tg_ok, tg_detail = tg.send_telegram_alert_detailed(msg, verify_bot=False)
                if tg_ok:
                    summary["telegram_sent"] = int(summary.get("telegram_sent") or 0) + 1
            except Exception as exc:
                tg_detail = str(exc)

        st.session_state["threat_sim_summary"] = summary

        # Cross-page queue: Home / any page will also show this
        try:
            import importlib
            import dashboard.attack_notify as attack_notify
            import alerts.local_notify as local_notify

            attack_notify = importlib.reload(attack_notify)
            local_notify = importlib.reload(local_notify)

            top = (summary.get("results") or [{}])[0]
            label = str(top.get("detected") or scenario)
            severity = str(top.get("severity") or "Critical")
            source_ip = str(top.get("source_ip") or "")

            if summary.get("attacks_detected", 0) > 0:
                msg = f"{label} from {source_ip}" if source_ip else label
                # Always set pending in session (works even if old module is cached)
                st.session_state["pending_global_notify"] = {
                    "title": f"{severity} Attack Detected",
                    "message": msg,
                    "severity": severity,
                    "source_ip": source_ip,
                }
                # Immediate UI + Windows sound on this page
                attack_notify.notify_attack_event(
                    label=label, severity=severity, source_ip=source_ip, play_sound=True
                )
                local_notify.notify_local_attack(
                    f"AI-NDR [{severity}] {label}",
                    f"Campaign {scenario}: {summary.get('attacks_detected', 0)} attacks",
                    play_sound=True,
                    show_balloon=True,
                    sound_seconds=5.0,
                )
                # Advance watermark so fragment doesn't spam; pending covers other pages
                try:
                    from database.models import Alert
                    max_id = db.query(Alert.alert_id).order_by(Alert.alert_id.desc()).limit(1).scalar() or 0
                    st.session_state.alert_watermark = int(max_id)
                except Exception:
                    pass
        except Exception as exc:
            st.warning(f"Notify issue: {exc}")
            # Last-resort Windows sound even if UI notify import failed
            try:
                from alerts.local_notify import notify_local_attack
                notify_local_attack(
                    "AI-NDR Attack",
                    f"Campaign {scenario} finished",
                    play_sound=True,
                    show_balloon=True,
                    sound_seconds=5.0,
                )
            except Exception:
                pass

        st.success(
            t("sim.done",
              flows=summary.get("flows_created"),
              attacks=summary.get("attacks_detected"),
              alerts=summary.get("alerts_created"),
              telegram=summary.get("telegram_sent", 0),
              blocked=summary.get("ips_blocked", 0))
        )
        if send_notifications:
            if tg_ok or summary.get("telegram_sent", 0):
                st.info(t("sim.tg_ok", detail=tg_detail or "OK"))
            else:
                st.error(t("sim.tg_fail", detail=tg_detail or "—"))

        st.warning(t("sim.open_home"))
    except Exception as exc:
        st.error(t("sim.failed", e=exc))
    finally:
        db.close()

summary = st.session_state.get("threat_sim_summary")
if summary:
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric(t("sim.flows"), summary.get("flows_created", 0))
    m2.metric(t("sim.preds"), summary.get("predictions", 0))
    m3.metric(t("sim.attacks"), summary.get("attacks_detected", 0))
    m4.metric(t("sim.alerts"), summary.get("alerts_created", 0))
    m5.metric(t("sim.tg_sent"), summary.get("telegram_sent", 0))

    rows = summary.get("results") or []
    if rows:
        st.subheader(t("sim.results"))
        df = pd.DataFrame(rows)
        show_cols = [c for c in [
            "flow_id", "intended", "detected", "severity", "threat_score",
            "source_ip", "alert_created", "telegram_sent", "ip_blocked",
        ] if c in df.columns]
        st.dataframe(df[show_cols], use_container_width=True, height=420)
else:
    st.subheader(t("sim.available"))
    for name, meta in SCENARIOS.items():
        st.markdown(f"- **{name}** — {meta['description']}")
