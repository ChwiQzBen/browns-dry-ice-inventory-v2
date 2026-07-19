from __future__ import annotations
"""
app/core/commercial_ui.py
===========================
Streamlit tab bodies for "💰 Commercial Mode" — customer-facing operations,
split out from "🧀 Manufacturing Mode" (recipes, milk, batches, aging,
production planning — see cheese_production_ui.py).

Shares session state with Manufacturing Mode via
app.core.cheese_shared_state.ensure_cheese_state() — both modes read/write
the SAME RecipeBook and BatchTracker instances within a session, not
independent copies.

Entry point:

    from app.core.commercial_ui import render_commercial_mode
    render_commercial_mode(supabase_client=init_supabase(), has_permission=has_permission)

CURRENT SCOPE: LPO Register only. Sales, Customers, Customer Analytics, and
Commercial Reports are later slices — see chat history for the full
Commercial roadmap and build order.

Deliberate cuts in THIS slice (documented so they're a choice, not an
oversight):
- No separate "Confirmed" status step — an LPO counts toward
  get_confirmed_demand_for_date() the moment it's saved (status defaults
  to "Pending", which the floor logic already treats as confirmed).
- customer_name is freetext, matching the existing Sales tab. Switch this
  to a customer_id select once the Customers tab exists — freetext here
  will need the same one-time reconciliation pass as cheese_sales.history.
- No dedicated "Tomorrow's Deliveries" sub-view — the Pending LPOs list is
  sorted by delivery_date, so tomorrow's (and any overdue) LPOs surface at
  the top on their own; a headline metric above it gives the number
  Production Planning will floor against.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from datetime import date, timedelta
from typing import Optional, Callable
import streamlit as st
import pandas as pd

from app.core.cheese_shared_state import ensure_cheese_state
from app.core.cheese_data_access import (
    save_lpo_line, get_lpo_lines, record_lpo_delivery, cancel_lpo_line,
)

COMMERCIAL_TAB_NAMES = [
    "📄 LPO Register",
    # "💰 Sales",             # moves here from Manufacturing in a later slice
    # "👥 Customers",
    # "📊 Customer Analytics",
    # "📋 Commercial Reports",
]


def render_commercial_mode(supabase_client=None,
                            has_permission: Optional[Callable[[str], bool]] = None) -> None:
    """Main entry point — call this from main.py inside the
    '💰 Commercial Mode' branch, the same way Manufacturing Mode is called."""

    def _allowed(permission: str) -> bool:
        return has_permission(permission) if has_permission else True

    ensure_cheese_state(supabase_client)
    book = st.session_state.cheese_recipe_book

    visible = [name for name, perm in {
        "📄 LPO Register": "manage_lpo",
    }.items() if _allowed(perm)]

    if not visible:
        st.warning("This section isn't available for your current role.")
        return

    tabs = st.tabs(visible)
    tab_lookup = dict(zip(visible, tabs))

    if "📄 LPO Register" in tab_lookup:
        with tab_lookup["📄 LPO Register"]:
            _render_lpo_register_tab(book, supabase_client)


# ============================================================
# TAB: LPO REGISTER
# ============================================================
def _render_lpo_register_tab(book, supabase_client) -> None:
    st.markdown("### 📄 LPO Register")
    st.caption(
        "Confirmed customer orders. Open quantities here floor tomorrow's "
        "production plan in 🧀 Manufacturing → 📋 Production Planning."
    )

    if not book.list_names():
        st.info("Add a recipe in 🧀 Manufacturing → Recipes before receiving LPOs.")
        return

    tomorrow = date.today() + timedelta(days=1)
    tomorrow_lines = get_lpo_lines(delivery_date=tomorrow, supabase_client=supabase_client)
    tomorrow_open = [l for l in tomorrow_lines if l["status"] not in ("Cancelled", "Delivered")]
    if tomorrow_open:
        total_kg = sum(l["quantity_kg"] for l in tomorrow_open)
        st.metric(
            f"Confirmed for {tomorrow.strftime('%b %d')} (tomorrow)",
            f"{total_kg:,.1f} kg",
            help="This is what Production Planning will floor tomorrow's plan against.",
        )
    else:
        st.caption(f"No open LPOs due {tomorrow.strftime('%b %d')} (tomorrow) yet.")

    # ---- Receive LPO ----
    with st.expander("➕ Receive LPO", expanded=not tomorrow_open):
        with st.form("receive_lpo_form"):
            col1, col2 = st.columns(2)
            with col1:
                lpo_number = st.text_input("LPO Number")
                customer_name = st.text_input("Customer")
                cheese_name = st.selectbox("Cheese", book.list_names(), key="lpo_cheese")
            with col2:
                delivery_date = st.date_input("Delivery Date", value=tomorrow, min_value=date.today())
                quantity_kg = st.number_input("Quantity (kg)", min_value=0.0, value=10.0, step=1.0)
                price_per_kg = st.number_input("Price per kg (KSh, optional)", min_value=0.0,
                                                value=0.0, step=10.0)
            notes = st.text_input("Notes (optional)")

            if st.form_submit_button("📥 Record LPO", type="primary"):
                if not lpo_number or not customer_name:
                    st.error("LPO number and customer are required.")
                elif quantity_kg <= 0:
                    st.error("Enter a quantity greater than 0.")
                else:
                    try:
                        new_id = save_lpo_line(
                            lpo_number=lpo_number, customer_name=customer_name,
                            delivery_date=delivery_date, cheese_name=cheese_name,
                            quantity_kg=quantity_kg, price_per_kg=price_per_kg,
                            notes=notes, supabase_client=supabase_client,
                        )
                        st.success(f"✅ Recorded LPO {lpo_number} — {quantity_kg:.1f}kg of "
                                   f"{cheese_name} due {delivery_date.strftime('%b %d')} (line #{new_id}).")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Could not record LPO: {e}")

    # ---- Pending LPOs (sorted by delivery date — soonest/overdue first) ----
    st.markdown("---")
    st.markdown("#### Pending LPOs")
    all_lines = get_lpo_lines(supabase_client=supabase_client)
    pending = [l for l in all_lines if l["status"] in ("Pending", "Confirmed")]
    pending.sort(key=lambda l: l["delivery_date"])

    if not pending:
        st.info("No open LPOs.")
    else:
        today_str = date.today().isoformat()
        for line in pending:
            overdue = line["delivery_date"] < today_str
            with st.container():
                st.markdown(
                    f"{'⚠️ OVERDUE — ' if overdue else ''}**{line['lpo_number']}** — "
                    f"{line['customer_name']} — {line['cheese_name']} — "
                    f"{line['quantity_kg']:.1f}kg — due {line['delivery_date']} — *{line['status']}*"
                )
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    delivered_kg = st.number_input(
                        "Deliver (kg)", min_value=0.0, value=float(line["quantity_kg"]),
                        step=1.0, key=f"deliver_kg_{line['id']}", label_visibility="collapsed",
                    )
                with c2:
                    if st.button("✅ Mark Delivered", key=f"deliver_{line['id']}"):
                        record_lpo_delivery(line["id"], delivered_kg, supabase_client)
                        st.success(f"Recorded delivery for {line['lpo_number']}.")
                        st.rerun()
                with c3:
                    if st.button("🚫 Cancel", key=f"cancel_{line['id']}"):
                        cancel_lpo_line(line["id"], supabase_client)
                        st.warning(f"Cancelled {line['lpo_number']}.")
                        st.rerun()
                st.markdown("---")

    # ---- History ----
    with st.expander("📜 LPO History (delivered / cancelled)", expanded=False):
        history = [l for l in all_lines if l["status"] in ("Delivered", "Partially Delivered", "Cancelled")]
        if history:
            df = pd.DataFrame(history)
            cols = ["lpo_number", "customer_name", "cheese_name", "delivery_date",
                    "quantity_kg", "quantity_delivered_kg", "status"]
            st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download LPO History CSV", csv,
                                file_name=f"lpo_history_{date.today().strftime('%Y%m%d')}.csv",
                                mime="text/csv")
        else:
            st.caption("Nothing delivered or cancelled yet.")