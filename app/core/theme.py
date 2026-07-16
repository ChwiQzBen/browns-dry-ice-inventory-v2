"""
app/core/theme.py
===================
Single source of truth for colors used across main.py and any UI module
that imports it (cheese_production_ui.py, and the new dry_ice_ui.py /
all_items_ui.py). Extracted from colors that were already in consistent
use throughout the app — not new branding, just one place to change it.
"""

THEME = {
    "primary": "#667eea",
    "primary_dark": "#764ba2",
    "primary_gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    "info": "#4fc3f7",
    "success": "#28a745",
    "warning": "#ffc107",
    "danger": "#dc3545",
    "purple": "#9c27b0",
    "cyan": "#00bcd4",
    "orange": "#ff9800",
    "orange_dark": "#ff6f00",
    "indigo": "#1a237e",
    "grey": "#90a4ae",
    "text_secondary": "#888",
    "card_bg": "rgba(255,255,255,0.06)",
    "card_radius": "10px",
}


def kpi_card(label, value, icon="", color=None, value_color="#333",
             subtext=None, action=None):
    """One KPI tile. Replaces the ~25-line hand-written HTML block that
    used to be repeated 8 times in main.py's KPI dashboard.

    subtext/action accept either plain text or a raw HTML fragment (e.g.
    a colored <span>) — the wrapping div's own color is inherited unless
    the fragment sets its own, which browsers apply on top regardless.
    """
    import streamlit as st

    color = color or THEME["primary"]
    subtext_html = f'<div style="font-size: 11px; color: #888;">{subtext}</div>' if subtext else ""
    action_html = (
        f'<div style="font-size:10px;color:{THEME["primary"]};font-weight:600;'
        f'margin-top:6px;padding-top:6px;border-top:1px dashed rgba(102,126,234,0.25);">{action}</div>'
        if action else ""
    )
    st.markdown(f"""
    <div style="
        background: {THEME['card_bg']};
        border-radius: {THEME['card_radius']};
        padding: 12px 8px;
        text-align: center;
        border-left: 3px solid {color};
    ">
        <div style="font-size: 10px; color: #888; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">
            {icon} {label}
        </div>
        <div style="font-size: 22px; font-weight: 700; color: {value_color}; margin: 4px 0;">
            {value}
        </div>
        {subtext_html}
        {action_html}
    </div>
    """, unsafe_allow_html=True)