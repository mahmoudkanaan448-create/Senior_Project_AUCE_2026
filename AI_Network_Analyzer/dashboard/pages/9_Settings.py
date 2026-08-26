"""
System settings page.

General settings, account credentials, Telegram alerts, and AI thresholds.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from database.database import SessionLocal, init_db
from database import queries
from dashboard.auth_gate import gate_page
from dashboard.i18n import t, fmt_opt
from config import APP_VERSION

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
gate_page("Settings")
st.title(f"⚙️ {t('settings.title')}")

init_db()
db = SessionLocal()
try:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        t("settings.tab.general"),
        t("settings.tab.telegram"),
        t("settings.tab.ai"),
        t("settings.tab.ndr"),
        t("settings.tab.clear"),
        t("settings.tab.company"),
    ])

    with tab1:
        st.markdown(f'<div class="section-title">{t("settings.general")}</div>', unsafe_allow_html=True)
        refresh = st.number_input(
            t("settings.refresh"),
            min_value=1, max_value=60,
            value=int(queries.get_setting(db, "refresh_rate") or 5),
        )
        sound_default = (queries.get_setting(db, "attack_sound_enabled") or "1") not in ("0", "false", "False")
        attack_sound = st.checkbox(
            t("settings.sound"),
            value=sound_default,
            help=t("settings.sound_help"),
        )
        if st.button(t("settings.save_general"), key="save_general"):
            queries.set_setting(db, "refresh_rate", str(refresh))
            queries.set_setting(db, "attack_sound_enabled", "1" if attack_sound else "0")
            st.session_state.attack_sound_enabled = attack_sound
            st.success(t("settings.saved"))

        st.markdown("---")
        st.markdown(f'<div class="section-title">{t("settings.account")}</div>', unsafe_allow_html=True)
        st.caption(t("settings.account_cap"))

        current_user = (st.session_state.get("user") or {}).get("username", "admin")
        st.text_input(t("settings.current_user"), value=current_user, disabled=True)

        with st.form("change_account_form"):
            new_username = st.text_input(t("settings.new_user"), value=current_user)
            current_password = st.text_input(t("settings.current_pw"), type="password")
            new_password = st.text_input(t("settings.new_pw"), type="password")
            confirm_password = st.text_input(t("settings.confirm_pw"), type="password")
            submitted = st.form_submit_button(t("settings.update_account"), use_container_width=True, type="primary")

        if submitted:
            from api.authentication import hash_password, verify_password

            user = queries.get_user_by_username(db, current_user)
            if user is None:
                st.error(t("settings.user_not_found"))
            elif not current_password:
                st.error(t("settings.enter_current_pw"))
            elif not verify_password(current_password, user.password_hash):
                st.error(t("settings.bad_current_pw"))
            elif new_password and new_password != confirm_password:
                st.error(t("settings.pw_mismatch"))
            else:
                try:
                    from ops.company import min_password_len
                    need = min_password_len()
                except Exception:
                    need = 6
                if new_password and len(new_password) < need:
                    st.error(t("settings.pw_short"))
                else:
                    pwd_hash = hash_password(new_password) if new_password else None
                    uname = new_username.strip() if new_username.strip() != current_user else None
                    if not uname and not pwd_hash:
                        st.warning(t("settings.nothing_update"))
                    else:
                        ok, msg = queries.update_user_credentials(
                            db,
                            current_username=current_user,
                            new_username=new_username.strip() if new_username.strip() else None,
                            new_password_hash=pwd_hash,
                        )
                        if ok:
                            if new_username.strip() and new_username.strip() != current_user:
                                st.session_state.user = {
                                    **(st.session_state.get("user") or {}),
                                    "username": new_username.strip(),
                                }
                            st.success(msg + " " + t("settings.remember_creds"))
                            st.rerun()
                        else:
                            st.error(msg)

    with tab2:
        st.subheader(t("tg.title"))
        st.caption(t("tg.help"))
        saved_token = (queries.get_setting(db, "telegram_token") or "").strip()
        saved_chat = (queries.get_setting(db, "telegram_chat_id") or "").strip()
        bot_token = st.text_input(t("tg.token"), value=saved_token)
        chat_id = st.text_input(t("tg.chat"), value=saved_chat)

        t1, t2, t3 = st.columns(3)
        with t1:
            if st.button(t("tg.save"), use_container_width=True):
                token_to_save = bot_token.strip() or saved_token
                chat_to_save = chat_id.strip() or saved_chat
                if not token_to_save or not chat_to_save:
                    st.error(t("tg.required"))
                else:
                    queries.set_setting(db, "telegram_token", token_to_save)
                    queries.set_setting(db, "telegram_chat_id", chat_to_save)
                    st.success(t("tg.saved"))
        with t2:
            if st.button(t("tg.test"), use_container_width=True, type="primary"):
                # Never overwrite good DB values with empty form fields
                token_to_use = bot_token.strip() or saved_token
                chat_to_use = chat_id.strip() or saved_chat
                if token_to_use:
                    queries.set_setting(db, "telegram_token", token_to_use)
                if chat_to_use:
                    queries.set_setting(db, "telegram_chat_id", chat_to_use)
                try:
                    import importlib
                    import alerts.telegram_alert as tg
                    importlib.reload(tg)
                    from alerts.runtime_config import telegram_configured
                    if not telegram_configured():
                        st.error(t("tg.required"))
                    else:
                        ok, detail = tg.send_telegram_alert_detailed(
                            "AI Network Analyzer\nTelegram test OK – alerts channel is connected.",
                            verify_bot=True,
                        )
                        if ok:
                            st.success(detail)
                        else:
                            st.error(detail)
                except Exception as e:
                    st.error(t("tg.error", e=e))
        with t3:
            if st.button(t("tg.detect"), use_container_width=True):
                token_to_use = bot_token.strip() or saved_token
                if token_to_use:
                    queries.set_setting(db, "telegram_token", token_to_use)
                try:
                    import importlib
                    import alerts.telegram_alert as tg
                    importlib.reload(tg)
                    info = tg.fetch_recent_chat_ids()
                    chats = info.get("chats") or []
                    if chats:
                        st.success(t("tg.found"))
                        for c in chats:
                            st.code(str(c.get("id")))
                            st.caption(
                                f"{c.get('type')} · {c.get('first_name') or c.get('title') or ''} "
                                f"@{c.get('username') or '-'}"
                            )
                    else:
                        st.warning(t("tg.no_chats"))
                        if info.get("error") or info.get("raw_error"):
                            st.caption(str(info.get("error") or info.get("raw_error")))
                except Exception as e:
                    st.error(t("tg.detect_fail", e=e))

        from alerts.runtime_config import telegram_configured
        st.markdown(
            f"**{t('common.status')}:** {'✅ ' + t('tg.status_ok') if telegram_configured() else '❌ ' + t('tg.status_no')}"
        )
        st.info(t("tg.auto"))

    with tab3:
        st.subheader(t("settings.tab.ai"))
        confidence_threshold = st.slider(
            t("ai.conf"),
            0,
            100,
            value=int(queries.get_setting(db, "confidence_threshold") or 50),
        )
        threat_block_threshold = st.slider(
            t("ai.block_th"),
            0,
            10,
            value=int(queries.get_setting(db, "threat_block_threshold") or 7),
        )
        if st.button(t("ai.save")):
            queries.set_setting(db, "confidence_threshold", str(confidence_threshold))
            queries.set_setting(db, "threat_block_threshold", str(threat_block_threshold))
            st.success(t("ai.saved"))

    with tab4:
        st.subheader(t("ndr.policy"))
        mode = st.selectbox(
            t("ndr.mode"),
            ["automatic", "ask"],
            index=0 if (queries.get_setting(db, "response_mode") or "automatic") == "automatic" else 1,
            format_func=fmt_opt,
            help="ask = human approval before block",
        )
        retention = st.selectbox(
            t("ndr.retention"),
            [7, 30, 90],
            index={7: 0, 30: 1, 90: 2}.get(int(queries.get_setting(db, "retention_days") or 30), 1),
        )
        cadence = st.selectbox(
            t("ndr.cadence"),
            ["off", "daily", "weekly", "monthly"],
            index=["off", "daily", "weekly", "monthly"].index(queries.get_setting(db, "report_cadence") or "off"),
        )
        syslog_host = st.text_input(t("ndr.syslog"), value=queries.get_setting(db, "syslog_host") or "")
        if st.button(t("ndr.save"), type="primary"):
            queries.set_setting(db, "response_mode", mode)
            queries.set_setting(db, "retention_days", str(retention))
            queries.set_setting(db, "report_cadence", cadence)
            queries.set_setting(db, "syslog_host", syslog_host.strip())
            st.success(t("ndr.saved"))

        st.markdown("---")
        st.subheader(t("ndr.audit"))
        try:
            from ops.audit import list_audit
            logs = list_audit(50)
            if logs:
                import pandas as pd
                st.dataframe(pd.DataFrame(logs), use_container_width=True, height=240)
        except Exception as exc:
            st.caption(str(exc))

        st.markdown("---")
        if st.button(t("ndr.purge")):
            from ops.retention import purge_old
            st.json(purge_old())

    with tab5:
        st.subheader(t("clear.title"))
        st.caption(t("clear.help"))
        st.info(t("clear.also"))

        from ops.data_clear import CLEAR_TARGETS, preview_counts, clear_selected

        counts = preview_counts()
        st.markdown(f"**{t('clear.counts')}**")
        count_cols = st.columns(4)
        for i, (key, n) in enumerate(counts.items()):
            count_cols[i % 4].metric(t(f"tgt.{key}"), n)

        options = ["all"] + list(CLEAR_TARGETS.keys())
        with st.form("clear_data_form"):
            selected = st.multiselect(
                t("clear.select"),
                options,
                format_func=lambda k: t("tgt.all") if k == "all" else t(f"tgt.{k}"),
            )
            confirm_user = st.text_input(t("clear.username"))
            confirm_pw = st.text_input(t("clear.password"), type="password")
            ack = st.checkbox(t("clear.ack"))
            do_clear = st.form_submit_button(t("clear.button"), type="primary", use_container_width=True)

        if do_clear:
            from api.authentication import verify_password

            logged = (st.session_state.get("user") or {}).get("username", "")
            if not selected:
                st.error(t("clear.need_select"))
            elif not ack:
                st.error(t("clear.need_ack"))
            elif not confirm_user.strip() or not confirm_pw:
                st.error(t("clear.need_creds"))
            elif confirm_user.strip() != logged:
                st.error(t("clear.bad_user"))
            else:
                user = queries.get_user_by_username(db, logged)
                if user is None or not verify_password(confirm_pw, user.password_hash):
                    st.error(t("clear.bad_pw"))
                else:
                    try:
                        result = clear_selected(selected, username=logged)
                        st.success(t("clear.ok"))
                        st.json(result)
                    except Exception as exc:
                        st.error(f"{t('common.error')}: {exc}")

    with tab6:
        st.subheader(t("company.title"))
        st.caption(t("company.cap"))
        from ops.company import company_mode, readiness, secret_is_default
        enabled = st.checkbox(t("company.enable"), value=company_mode())
        if st.button(t("company.save"), type="primary"):
            queries.set_setting(db, "company_mode", "1" if enabled else "0")
            from ops.audit import audit
            audit("company_mode", "on" if enabled else "off",
                  user_id=(st.session_state.get("user") or {}).get("user_id"))
            st.success(t("company.saved"))
            st.rerun()
        if secret_is_default():
            st.warning(t("company.secret_warn"))
        snap = readiness()
        st.metric(t("company.score"), snap.get("ready_score"))
        import pandas as pd
        st.dataframe(pd.DataFrame(snap.get("checks") or []), use_container_width=True, hide_index=True)
        st.caption(snap.get("note") or "")

        st.markdown("---")
        st.subheader(t("company.users"))
        users = queries.list_users(db)
        if users:
            st.dataframe(pd.DataFrame([{
                "ID": u.user_id, "User": u.username, "Role": u.role,
                "Status": u.status, "Last login": str(u.last_login or ""),
            } for u in users]), use_container_width=True, hide_index=True)
        with st.form("add_company_user"):
            fu = st.text_input(t("company.full"))
            un = st.text_input(t("company.username"))
            em = st.text_input(t("company.email"))
            pw = st.text_input(t("company.password"), type="password")
            role = st.selectbox(t("company.role"), ["Viewer", "Security Analyst", "Administrator"])
            add_u = st.form_submit_button(t("company.add_user"))
        if add_u:
            from api.authentication import hash_password
            from ops.company import min_password_len
            if not un or not pw or not em:
                st.error(t("company.need_fields"))
            elif len(pw) < min_password_len():
                st.error(t("settings.pw_short"))
            elif queries.get_user_by_username(db, un.strip()):
                st.error(t("company.exists"))
            else:
                queries.create_user(
                    db, full_name=fu or un, username=un.strip(), email=em.strip(),
                    password_hash=hash_password(pw), role=role,
                )
                st.success(t("company.user_added"))
                st.rerun()

        st.markdown("---")
        st.subheader(t("company.backup"))
        if st.button(t("company.backup_now")):
            from ops.backup import backup_now
            st.json(backup_now())
        from ops.backup import list_backups
        bks = list_backups()
        if bks:
            st.dataframe(pd.DataFrame(bks), use_container_width=True, hide_index=True)
        st.caption(t("company.capture_hint"))

    st.markdown("---")
    st.subheader(t("settings.sysinfo"))
    st.json({
        "Version": APP_VERSION,
        "Student": "Mahmoud Talal Kanaan",
        "ID": "2240004",
        "University": "AUCE",
        "Project": "AI-Powered Network Traffic Analyzer & Anomaly Detector",
    })
finally:
    db.close()
