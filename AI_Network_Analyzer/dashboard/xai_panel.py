"""Shared Streamlit panel for per-alert / per-prediction XAI."""
from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from dashboard.i18n import t


def render_xai_panel(explanation: Optional[Dict[str, Any]], *, expanded: bool = True) -> None:
    if not explanation:
        st.caption(t("xai.none"))
        return
    with st.expander(t("xai.title"), expanded=expanded):
        st.write(explanation.get("decision_explanation") or "")
        action = explanation.get("recommended_action")
        if action:
            st.success(f"{t('xai.action')}: {action}")
        local = explanation.get("local_evidence") or []
        if local:
            st.caption(t("xai.local"))
            st.dataframe(pd.DataFrame(local), use_container_width=True, hide_index=True)
        feats = explanation.get("important_features") or []
        if feats:
            st.caption(t("xai.model_features"))
            st.dataframe(pd.DataFrame(feats), use_container_width=True, hide_index=True)
        model_used = explanation.get("model_used")
        if model_used:
            st.caption(f"{t('xai.model')}: {model_used}")
