"""Floating AI Security Assistant widget for every dashboard page."""

from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from dashboard.i18n import t

_ASSISTANT_CSS = """
<style>
div[data-testid="stPopover"] button {
  background: linear-gradient(135deg, #1e3a5f 0%, #0c1a2e 100%) !important;
  border: 1px solid #d4af37 !important;
  color: #f8fafc !important;
  font-weight: 700 !important;
}
.aindr-ai-panel {
  background: #0c1a2e;
  border: 1px solid #1e3a5f;
  border-radius: 12px;
  padding: 8px 4px;
}
.aindr-ai-role {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 6px;
}
</style>
"""


def set_assistant_focus(
    focus_type: str,
    *,
    record_id: Optional[int] = None,
    value: Optional[str] = None,
    label: str = "",
) -> None:
    """Pages call this to pass the currently selected alert/flow/IP to the assistant."""
    st.session_state["ai_assistant_focus"] = {
        "type": focus_type,
        "id": record_id,
        "value": value,
        "label": label,
    }


def _render_answer(out: Dict[str, Any]) -> None:
    st.markdown(f"**{out.get('summary', '')}**")
    if out.get("threat_type"):
        c1, c2 = st.columns(2)
        c1.metric("Threat", out.get("threat_type", "—"))
        c2.metric("Severity", out.get("severity", "—"))
    if out.get("why_detected"):
        st.markdown(f"**{t('ai.why')}**")
        st.write(out["why_detected"])
    if out.get("evidence"):
        st.markdown(f"**{t('ai.evidence')}**")
        for line in out["evidence"]:
            st.markdown(f"- {line}")
    if out.get("mitre"):
        st.markdown(f"**MITRE ATT&CK:** `{out['mitre']}`")
    if out.get("recommended_action"):
        st.success(f"**{t('ai.recommended')}:** {out['recommended_action']}")
    if out.get("analyst_notes"):
        st.caption(out["analyst_notes"])
    if out.get("help_hint"):
        st.info(out["help_hint"])


def render_ai_assistant(page_title: str) -> None:
    """Fixed assistant control — call from gate_page on every authenticated page."""
    if not st.session_state.get("authenticated"):
        return

    st.markdown(_ASSISTANT_CSS, unsafe_allow_html=True)

    if "ai_assistant_chat" not in st.session_state:
        st.session_state.ai_assistant_chat = []

    focus = st.session_state.get("ai_assistant_focus") or {}
    focus_label = focus.get("label") or ""
    if focus.get("type") == "alert" and focus.get("id"):
        focus_label = focus_label or f"Alert #{focus['id']}"
    elif focus.get("type") == "flow" and focus.get("id"):
        focus_label = focus_label or f"Flow #{focus['id']}"
    elif focus.get("type") == "ip" and focus.get("value"):
        focus_label = focus_label or f"IP {focus['value']}"

    # Top-right popover on main area
    bar_l, bar_r = st.columns([8, 1])
    with bar_r:
        with st.popover(f"🤖 {t('ai.assistant')}", use_container_width=True):
            st.markdown(
                f"<div class='aindr-ai-role'>{t('ai.roles')}</div>",
                unsafe_allow_html=True,
            )
            st.caption(f"{t('ai.page')}: **{page_title}**")
            if focus_label:
                st.caption(f"{t('ai.focus')}: **{focus_label}**")

            from soc.assistant import build_page_context, ask

            ctx = build_page_context(page_title)
            if ctx.get("highlights"):
                with st.expander(t("ai.context"), expanded=False):
                    for h in ctx["highlights"][:6]:
                        st.caption(h)

            placeholders = {
                "Live Monitoring": "Why is this flow dangerous? What does threat score 8.7 mean?",
                "Threat Intelligence": "Explain this IP — should I block it?",
                "AI Models": "Which model is best? Why is XGBoost better than LSTM?",
                "Alerts": "Analyze this alert",
                "AI Detection": "Why was this classified as Port Scan?",
            }
            q = st.text_input(
                t("ai.ask"),
                placeholder=placeholders.get(page_title, "Analyze this / explain threat score"),
                key=f"ai_q_{page_title}",
                label_visibility="collapsed",
            )
            c1, c2 = st.columns(2)
            with c1:
                go = st.button(t("ai.ask"), type="primary", use_container_width=True, key=f"ai_go_{page_title}")
            with c2:
                quick = st.button(t("ai.analyze"), use_container_width=True, key=f"ai_quick_{page_title}")

            if go and q.strip():
                out = ask(q.strip(), page_title, focus)
                st.session_state.ai_assistant_chat.append({"q": q.strip(), "a": out})
            elif quick:
                out = ask("analyze this", page_title, focus)
                st.session_state.ai_assistant_chat.append({"q": "Analyze focus", "a": out})

            for turn in reversed(st.session_state.ai_assistant_chat[-5:]):
                st.markdown("---")
                st.markdown(f"**{t('ai.you')}:** {turn['q']}")
                _render_answer(turn["a"])

            if st.button(t("ai.clear_chat"), key=f"ai_clr_{page_title}"):
                st.session_state.ai_assistant_chat = []
                st.rerun()
