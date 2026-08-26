"""Login gate and shared sidebar for the Streamlit dashboard."""

from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

from config import APP_VERSION
from dashboard.i18n import (
    apply_language_css,
    get_lang,
    init_language,
    render_language_picker,
    render_translated_nav,
    t,
)

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "app_logo.png"

# AUCE-inspired palette: navy blue + white + gold
_CSS = """
<style>
.stApp {
  background: linear-gradient(180deg, #07111f 0%, #0c1a2e 45%, #102238 100%) !important;
  color: #f8fafc !important;
}
.block-container { padding-top: 1.1rem !important; }

.stApp, .stApp p, .stApp span, .stApp label, .stApp li,
.stMarkdown, .stMarkdown p, .stCaption, [data-testid="stMarkdownContainer"] {
  color: #f1f5f9 !important;
}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, h1, h2, h3 {
  color: #ffffff !important;
  font-weight: 700 !important;
}

[data-testid="stSidebar"] {
  background: #050d18 !important;
  border-right: 1px solid #1e3a5f !important;
}
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {
  color: #f8fafc !important;
}
[data-testid="stSidebarNav"] a, [data-testid="stSidebarNav"] span {
  color: #e2e8f0 !important;
  font-weight: 600 !important;
}
[data-testid="stSidebarNav"] a:hover { background: #12233d !important; }

.main-header {
  font-size: 28px !important;
  font-weight: 800 !important;
  color: #d4af37 !important;
  text-align: center;
  padding: 8px 0 4px 0;
}
.sub-header-line {
  text-align: center;
  color: #cbd5e1 !important;
  font-size: 14px !important;
  margin-bottom: 18px;
  font-weight: 500;
}
.section-title {
  color: #ffffff !important;
  font-size: 18px !important;
  font-weight: 700 !important;
  margin: 8px 0 12px 0;
  padding-bottom: 6px;
  border-bottom: 2px solid #d4af37;
}

div[data-testid="stMetric"] {
  background: #12233d !important;
  border: 1px solid #1e3a5f !important;
  border-radius: 12px;
  padding: 14px 16px !important;
}
div[data-testid="stMetric"] label {
  color: #cbd5e1 !important;
  font-weight: 600 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: #d4af37 !important;
  font-weight: 800 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
  color: #86efac !important;
}

.stTextInput label, .stSelectbox label, .stNumberInput label,
.stTextArea label, .stMultiSelect label, .stSlider label {
  color: #ffffff !important;
  font-weight: 700 !important;
  font-size: 14px !important;
}
.stTextInput input, .stNumberInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"] > div {
  background-color: #12233d !important;
  color: #ffffff !important;
  border: 1px solid #3b82a0 !important;
  border-radius: 8px !important;
}
.stTextInput input::placeholder { color: #94a3b8 !important; }

.stButton > button {
  font-weight: 700 !important;
  border-radius: 8px !important;
}
div[data-testid="stForm"] {
  background: #0c1a2e;
  border: 1px solid #1e3a5f;
  border-radius: 14px;
  padding: 18px 20px;
}

.stTabs [data-baseweb="tab"] { color: #e2e8f0 !important; font-weight: 650 !important; }
.stTabs [aria-selected="true"] { color: #d4af37 !important; }
.stAlert p, [data-testid="stAlert"] p { color: #0f172a !important; }

.status-online {
  display: inline-block;
  background: #14532d;
  color: #bbf7d0 !important;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}
hr { border-color: #1e3a5f !important; }

.login-title {
  text-align: center;
  color: #d4af37 !important;
  font-size: 26px;
  font-weight: 800;
  margin-top: 12px;
}
.login-sub {
  text-align: center;
  color: #e2e8f0 !important;
  font-size: 15px;
  font-weight: 500;
  margin-bottom: 18px;
}
.logo-wrap { text-align: center; margin-top: 24px; margin-bottom: 8px; }
</style>
"""

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(18,35,61,0.7)",
    font=dict(color="#f8fafc", size=13),
    title_font=dict(color="#ffffff", size=15),
    legend=dict(font=dict(color="#f1f5f9", size=12)),
    margin=dict(l=20, r=20, t=40, b=20),
    xaxis=dict(color="#e2e8f0", gridcolor="#1e3a5f", zerolinecolor="#334155"),
    yaxis=dict(color="#e2e8f0", gridcolor="#1e3a5f", zerolinecolor="#334155"),
)


def apply_theme():
    init_language()
    st.markdown(_CSS, unsafe_allow_html=True)
    apply_language_css()


def style_fig(fig):
    fig.update_layout(**PLOTLY_LAYOUT)
    return fig


def show_logo(width: int = 110):
    if LOGO_PATH.exists():
        c1, c2, c3 = st.columns([1.2, 1, 1.2])
        with c2:
            st.image(str(LOGO_PATH), width=width)


def _check_login(username: str, password: str):
    if not username or not password:
        return False, None, t("login.enter")
    try:
        from database.database import SessionLocal, init_db
        from database.queries import get_user_by_username
        from api.authentication import verify_password

        init_db()
        db = SessionLocal()
        try:
            user = get_user_by_username(db, username)
            if not user or not verify_password(password, user.password_hash):
                return False, None, t("login.invalid")
            status = (getattr(user, "status", "active") or "active").lower()
            if status not in ("active", "enabled", "1", "true"):
                return False, None, t("login.disabled")
            try:
                user.last_login = datetime.utcnow()
                db.commit()
            except Exception:
                db.rollback()
            try:
                from ops.audit import audit
                audit("login", f"user={user.username} role={user.role}", user_id=user.user_id)
            except Exception:
                pass
            return True, {
                "username": user.username,
                "role": getattr(user, "role", "Administrator"),
                "user_id": user.user_id,
            }, None
        finally:
            db.close()
    except Exception:
        if username == "admin" and password == "admin123":
            try:
                from ops.company import company_mode
                if company_mode():
                    return False, None, t("login.failed")
            except Exception:
                return False, None, t("login.failed")
            return True, {"username": "admin", "role": "Administrator", "user_id": 1}, None
        return False, None, t("login.failed")


def require_login() -> bool:
    if st.session_state.get("authenticated"):
        return True

    apply_theme()
    show_logo(120)
    st.markdown(
        f"<div class='login-title'>{t('app.name')}</div>"
        f"<div class='login-sub'>{t('app.login_sub', version=APP_VERSION)}</div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1, 1.15, 1])
    with c2:
        render_language_picker(key="login_lang_picker")
        with st.form("login_form"):
            username = st.text_input(t("login.username"))
            password = st.text_input(t("login.password"), type="password")
            submitted = st.form_submit_button(t("login.signin"), use_container_width=True, type="primary")
        if submitted:
            ok, info, err = _check_login(username.strip(), password)
            if ok:
                st.session_state.authenticated = True
                st.session_state.user = info
                st.rerun()
            st.error(err or t("login.invalid"))
        try:
            from ops.company import company_mode
            if not company_mode():
                st.caption(t("login.default"))
        except Exception:
            st.caption(t("login.default"))
    return False


def render_sidebar_brand():
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=96)
        st.markdown(f"## {t('app.name')}")
        st.markdown(f"**{t('app.platform', version=APP_VERSION)}**")
        st.markdown(f'<span class="status-online">{t("app.online")}</span>', unsafe_allow_html=True)
        st.markdown("---")
        render_language_picker(key="sidebar_lang_picker")
        st.markdown("---")
        render_translated_nav()
        st.markdown("---")
        try:
            @st.fragment(run_every=timedelta(seconds=1))
            def _clock():
                n = datetime.now()
                st.markdown(f"**{t('app.time')}:** `{n.strftime('%H:%M:%S')}`")
                st.markdown(f"**{t('app.date')}:** `{n.strftime('%Y-%m-%d')}`")

            _clock()
        except Exception:
            n = datetime.now()
            st.markdown(f"**{t('app.time')}:** `{n.strftime('%H:%M:%S')}`")
            st.markdown(f"**{t('app.date')}:** `{n.strftime('%Y-%m-%d')}`")
        st.markdown("---")
        user = st.session_state.get("user") or {}
        st.markdown(f"**{t('app.user')}:** `{user.get('username', '-')}`")
        st.markdown(f"**{t('app.role')}:** `{user.get('role', '-')}`")
        if st.button(t("app.logout"), use_container_width=True):
            lang = get_lang()
            st.session_state.clear()
            st.session_state.lang = lang
            st.rerun()
        st.markdown("---")
        st.markdown(f"**{t('app.student')}**")
        st.markdown(t("app.auce"))


def footer():
    st.markdown("---")
    st.markdown(
        f"<div style='text-align:center;color:#cbd5e1;font-size:13px;font-weight:500;'>"
        f"{t('app.footer', version=APP_VERSION)}"
        f"</div>",
        unsafe_allow_html=True,
    )


# Viewer = monitor/report. Analyst = investigate/respond. Admin = platform.
PAGE_ROLES = {
    "Settings": ["Administrator"],
    "AI Models": ["Administrator"],
    "Threat Simulation": ["Administrator", "Security Analyst"],
    "AI Detection": ["Administrator", "Security Analyst"],
    "Response": ["Administrator", "Security Analyst"],
    "SOC Ops": ["Administrator", "Security Analyst"],
    "Blocked IPs": ["Administrator", "Security Analyst"],
    "Copilot": ["Administrator", "Security Analyst"],
    "Incidents": ["Administrator", "Security Analyst"],
    "Threat Intelligence": ["Administrator", "Security Analyst"],
}


def _role_allowed(page_title: str, role: str) -> bool:
    allowed = PAGE_ROLES.get(page_title)
    if not allowed:
        return True
    return (role or "Viewer") in allowed


def gate_page(page_title: str = "AI Network Analyzer", page_icon: str = "shield"):
    apply_theme()
    if not require_login():
        st.stop()
    role = (st.session_state.get("user") or {}).get("role") or "Viewer"
    if not _role_allowed(page_title, role):
        st.error(t("rbac.denied"))
        st.stop()
    try:
        from database.database import init_db
        init_db()
    except Exception as exc:
        try:
            st.sidebar.warning(f"Database init: {exc}")
        except Exception:
            pass
    render_sidebar_brand()
    try:
        from dashboard.ai_assistant import render_ai_assistant
        render_ai_assistant(page_title)
    except Exception:
        pass
    # Live on-screen + sound notifications for new attacks
    try:
        import dashboard.attack_notify as attack_notify
        attack_notify.render_attack_notifier()
    except Exception as exc:
        # Surface notifier errors instead of swallowing (was hiding broken UI alerts)
        try:
            st.sidebar.error(f"Notifier: {exc}")
        except Exception:
            pass
