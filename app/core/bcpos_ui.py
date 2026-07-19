"""
app/core/bcpos_ui.py
======================
Top-level entry point for "🧀 BCPOS Mode" — dispatches between
🏭 Manufacturing (cheese_production_ui.py) and 💰 Commercial (commercial_ui.py).

BCPOS is ONE product with two operational sides, not two separate app
modes — this keeps a single top-level radio entry in main.py's sidebar
(alongside All Items Mode / Dry Ice Mode), with Manufacturing/Commercial
as an internal choice, rather than treating Commercial as a sibling to
those genuinely separate businesses.

Deliberately a thin dispatcher, not merged into cheese_production_ui.py:
keeps that file's job to "render Manufacturing tabs" only, so it doesn't
need to import commercial_ui.py (or vice versa) — avoids a circular-import
risk and mirrors the existing all_items_ui.py / dry_ice_ui.py split, where
each *_ui.py module owns exactly one tab set.

Entry point:
    from app.core.bcpos_ui import render_bcpos_mode
    render_bcpos_mode(supabase_client=init_supabase(), has_permission=has_permission,
                       milk_cost_per_liter=..., raw_milk_price_per_liter=...)
"""
import streamlit as st
from typing import Optional, Callable

from app.core.cheese_shared_state import ensure_cheese_state
from app.core.cheese_production_ui import render_cheese_production_mode
from app.core.commercial_ui import render_commercial_mode


def render_bcpos_mode(supabase_client=None,
                       has_permission: Optional[Callable[[str], bool]] = None,
                       milk_cost_per_liter: float = 45.0,
                       raw_milk_price_per_liter: float = 35.0) -> None:
    # Called unconditionally, before the sub-mode radio, so correctness
    # doesn't depend on Manufacturing happening to run first — belt and
    # suspenders alongside the idempotent init inside each sub-mode.
    ensure_cheese_state(supabase_client)

    sub_mode = st.radio(
        "BCPOS section:", ["🏭 Manufacturing", "💰 Commercial"],
        horizontal=True, key="bcpos_sub_mode",
    )
    st.markdown("---")

    if sub_mode == "🏭 Manufacturing":
        render_cheese_production_mode(
            supabase_client=supabase_client, has_permission=has_permission,
            milk_cost_per_liter=milk_cost_per_liter,
            raw_milk_price_per_liter=raw_milk_price_per_liter,
        )
    else:  # "💰 Commercial"
        render_commercial_mode(supabase_client=supabase_client, has_permission=has_permission)