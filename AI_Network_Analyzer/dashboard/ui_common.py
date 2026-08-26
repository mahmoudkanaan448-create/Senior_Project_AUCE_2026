"""Compatibility shim – prefer dashboard.auth_gate."""
from dashboard.auth_gate import (  # noqa: F401
    APP_VERSION,
    apply_theme,
    footer,
    gate_page,
    render_sidebar_brand,
    require_login,
    style_fig,
)
