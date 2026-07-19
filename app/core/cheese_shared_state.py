"""
app/core/cheese_shared_state.py
=================================
Session-state initialization shared between Cheese Production Mode
("🧀 Manufacturing") and Commercial Mode ("💰 Commercial") — both need the
SAME RecipeBook and BatchTracker instances so they're reading/writing one
in-memory object per session, not two independently-loaded copies that
could silently drift apart before the next Supabase persist.

Call ensure_cheese_state(supabase_client) at the top of EITHER mode's
render function, before touching st.session_state.cheese_recipe_book or
st.session_state.cheese_tracker. It's idempotent and order-independent —
safe to call from both modes on every rerun, whichever mode the user opens
first in a session.
"""
import streamlit as st

from app.core.cheese_data_access import init_cheese_storage, load_recipe_book, load_batch_tracker


def ensure_cheese_state(supabase_client) -> None:
    if "cheese_storage_initialized" not in st.session_state:
        init_cheese_storage(supabase_client)
        st.session_state.cheese_storage_initialized = True

    if "cheese_recipe_book" not in st.session_state:
        st.session_state.cheese_recipe_book = load_recipe_book(supabase_client)

    if "cheese_tracker" not in st.session_state:
        st.session_state.cheese_tracker = load_batch_tracker(supabase_client)

    if "cheese_demand_overrides" not in st.session_state:
        # {cheese_name: (mean_kg, std_kg)} — manual planning inputs until
        # cheese_sales_history has enough rows for the forecaster to take over
        st.session_state.cheese_demand_overrides = {}

    if "cheese_selling_prices" not in st.session_state:
        st.session_state.cheese_selling_prices = {}

    if "cheese_last_plan" not in st.session_state:
        st.session_state.cheese_last_plan = None