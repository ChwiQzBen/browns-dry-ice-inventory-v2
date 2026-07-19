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

CURRENT SCOPE: LPO Register, Sales, Customers, Commercial Reports.
Customer Analytics (RFM/CLV/churn/segments) is deliberately NOT here yet —
it needs customer_id-linked Sales/LPO history (both still use freetext
customer names) and the milk-cost-in-profitability fix first. Building it
against freetext-grouped, milk-cost-understated data now would mean
rebuilding it once those land.

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
from datetime import date, timedelta, datetime
from typing import Optional, Callable
import streamlit as st
import pandas as pd

from sales_service import dispatch_and_record_sale, available_stock_kg
from app.core.cheese_shared_state import ensure_cheese_state
from app.core.cheese_data_access import (
    save_lpo_line, get_lpo_lines, record_lpo_delivery, cancel_lpo_line,
    get_sales_history, save_customer, get_customers, delete_customer,
)

COMMERCIAL_TAB_NAMES = [
    "📄 LPO Register",
    "💰 Sales",
    "👥 Customers",
    "� Commercial Reports",
    # "📊 Customer Analytics",  # needs customer_id migration + milk-cost fix first
]


def render_commercial_mode(supabase_client=None,
                            has_permission: Optional[Callable[[str], bool]] = None) -> None:
    """Main entry point — call this from main.py inside the
    '💰 Commercial Mode' branch, the same way Manufacturing Mode is called."""

    def _allowed(permission: str) -> bool:
        return has_permission(permission) if has_permission else True

    ensure_cheese_state(supabase_client)
    book = st.session_state.cheese_recipe_book
    tracker = st.session_state.cheese_tracker

    visible = [name for name, perm in {
        "📄 LPO Register": "manage_lpo",
        "💰 Sales": "record_cheese_sale",
        "👥 Customers": "manage_customers",
        "📋 Commercial Reports": "view_commercial_reports",
    }.items() if _allowed(perm)]

    if not visible:
        st.warning("This section isn't available for your current role.")
        return

    tabs = st.tabs(visible)
    tab_lookup = dict(zip(visible, tabs))

    if "📄 LPO Register" in tab_lookup:
        with tab_lookup["📄 LPO Register"]:
            _render_lpo_register_tab(book, supabase_client)
    if "💰 Sales" in tab_lookup:
        with tab_lookup["💰 Sales"]:
            _render_sales_tab(book, tracker, supabase_client)
    if "👥 Customers" in tab_lookup:
        with tab_lookup["👥 Customers"]:
            _render_customers_tab(supabase_client)
    if "📋 Commercial Reports" in tab_lookup:
        with tab_lookup["📋 Commercial Reports"]:
            _render_commercial_reports_tab(supabase_client)


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

# ============================================================
# TAB: SALES  (moved from Manufacturing — routes through sales_service
# instead of importing FEFOInventory/BatchTracker business logic directly)
# ============================================================
def _render_sales_tab(book, tracker, supabase_client) -> None:
    st.markdown("### 💰 Record a Sale")
    st.caption(
        "Dispatches stock via FEFO (earliest-expiry batches consumed first) and "
        "saves the sale to history, so 🧀 Manufacturing → Production Planning's "
        "demand forecast has real data."
    )

    if not book.list_names():
        st.info("Add a recipe in 🧀 Manufacturing → Recipes first, then produce "
                 "and release some stock before recording sales.")
        return

    with st.form("record_sale_form"):
        col1, col2 = st.columns(2)
        with col1:
            sale_date = st.date_input("Sale Date", value=date.today())
            cheese_name = st.selectbox("Cheese", book.list_names(), key="sale_cheese")
        with col2:
            quantity_kg = st.number_input("Quantity Sold (kg)", min_value=0.0, value=1.0, step=0.5)
            price_per_kg = st.number_input("Price per kg (KSh)", min_value=0.0, value=0.0, step=10.0)
        customer = st.text_input("Customer (optional)")
        notes = st.text_input("Notes (optional)")

        available = available_stock_kg(tracker, cheese_name) if cheese_name else 0.0
        st.caption(f"Available stock: {available:,.1f} kg")

        if st.form_submit_button("💰 Record Sale", type="primary"):
            if quantity_kg <= 0:
                st.error("Enter a quantity greater than 0.")
            elif price_per_kg <= 0:
                st.error("Enter a price greater than 0.")
            elif quantity_kg > available:
                st.error(f"Only {available:,.1f}kg of {cheese_name} available — "
                         f"can't record a sale for {quantity_kg:,.1f}kg.")
            else:
                try:
                    result = dispatch_and_record_sale(
                        tracker, cheese_name, quantity_kg, price_per_kg, sale_date,
                        customer, notes, supabase_client,
                    )
                    st.success(f"✅ Sold {result.allocated_kg:,.1f}kg of {cheese_name} "
                               f"for KSh {result.revenue:,.0f}, drawn from "
                               f"{len(result.batch_lines)} batch(es).")
                    if result.shortfall_kg > 0:
                        st.warning(f"⚠️ {result.shortfall_kg:.1f}kg short — recorded what was "
                                   f"actually available. Stock may have changed since the page loaded.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Could not record sale: {e}")

    st.markdown("---")
    st.markdown("#### Recent Sales")
    start = date.today() - timedelta(days=30)
    sales = get_sales_history(start_date=start, supabase_client=supabase_client)
    if sales:
        df = pd.DataFrame(sales)
        st.dataframe(
            df[["id", "date", "cheese_name", "quantity_kg", "price_per_kg", "revenue", "customer", "notes"]],
            use_container_width=True, hide_index=True,
        )
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Sales CSV", csv,
                            file_name=f"cheese_sales_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
    else:
        st.info("No sales recorded in the last 30 days.")


# ============================================================
# TAB: CUSTOMERS  (registry only; Sales/LPO still use freetext customer
# names, see module docstring)
# ============================================================
def _render_customers_tab(supabase_client) -> None:
    st.markdown("### 👥 Customers")
    st.caption(
        "Customer registry. Sales and LPOs still use freetext customer names for "
        "now — linking them to this registry (and reconciling existing history) "
        "is a separate follow-up before Customer Analytics can trust the data."
    )

    customers = get_customers(supabase_client=supabase_client)

    if customers:
        df = pd.DataFrame(customers)
        cols = ["name", "contact_person", "phone", "email", "credit_terms_days"]
        st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True, hide_index=True)
    else:
        st.info("No customers yet — add your first one below.")

    with st.expander("➕ Add / Edit Customer", expanded=not customers):
        names = ["(new customer)"] + [c["name"] for c in customers]
        pick = st.selectbox("Customer", names, key="customer_picker")
        editing = next((c for c in customers if c["name"] == pick), None) if pick != "(new customer)" else None

        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name", value=editing["name"] if editing else "", key="customer_name")
            contact_person = st.text_input("Contact Person",
                                            value=editing.get("contact_person", "") if editing else "",
                                            key="customer_contact")
            phone = st.text_input("Phone", value=editing.get("phone", "") if editing else "",
                                   key="customer_phone")
        with col2:
            email = st.text_input("Email", value=editing.get("email", "") if editing else "",
                                   key="customer_email")
            credit_terms = st.number_input(
                "Credit Terms (days)", min_value=0,
                value=int(editing.get("credit_terms_days", 0)) if editing else 0,
                step=1, key="customer_credit_terms", help="0 = cash / COD",
            )
            address = st.text_input("Address", value=editing.get("address", "") if editing else "",
                                     key="customer_address")
        notes = st.text_input("Notes (optional)", value=editing.get("notes", "") if editing else "",
                               key="customer_notes")

        col_save, col_delete = st.columns(2)
        with col_save:
            if st.button("💾 Save Customer", type="primary", use_container_width=True, key="save_customer_btn"):
                if not name:
                    st.error("Name is required.")
                else:
                    try:
                        save_customer(
                            name=name, contact_person=contact_person, phone=phone, email=email,
                            address=address, credit_terms_days=int(credit_terms), notes=notes,
                            customer_id=editing["id"] if editing else None,
                            supabase_client=supabase_client,
                        )
                        st.success(f"✅ Saved '{name}'.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Could not save customer: {e}")
        with col_delete:
            if editing and st.button("🗑️ Delete Customer", use_container_width=True, key="delete_customer_btn"):
                delete_customer(editing["id"], supabase_client)
                st.success(f"Deleted '{editing['name']}'.")
                st.rerun()


# ============================================================
# TAB: COMMERCIAL REPORTS  (rollups over existing Sales/LPO data, no new
# schema needed)
# ============================================================
def _render_commercial_reports_tab(supabase_client) -> None:
    st.markdown("### 📋 Commercial Reports")
    st.caption(
        "Rollups over Sales and LPO data. Customer-level breakdowns use freetext "
        "customer names for now — expect some fragmentation (e.g. 'Java House' vs "
        "'java house') until Sales/LPO are linked to the Customers registry."
    )

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=date.today() - timedelta(days=30),
                                    key="comm_report_start")
    with col2:
        end_date = st.date_input("End Date", value=date.today(), key="comm_report_end")

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    sales = get_sales_history(start_date=start_date, end_date=end_date, supabase_client=supabase_client)
    all_lpo = get_lpo_lines(supabase_client=supabase_client)
    lpo_lines = [l for l in all_lpo
                 if start_date.isoformat() <= l["delivery_date"] <= end_date.isoformat()]

    if not sales and not lpo_lines:
        st.info("No sales or LPO activity in this date range.")
        return

    sales_df = pd.DataFrame(sales) if sales else pd.DataFrame(
        columns=["date", "cheese_name", "quantity_kg", "price_per_kg", "revenue", "customer"])

    total_revenue = sales_df["revenue"].sum() if not sales_df.empty else 0.0
    total_kg = sales_df["quantity_kg"].sum() if not sales_df.empty else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Revenue", f"KSh {total_revenue:,.0f}")
    c2.metric("Total Volume", f"{total_kg:,.1f} kg")
    c3.metric("Sales Transactions", len(sales_df))

    st.markdown("---")

    st.markdown("#### Revenue by Product")
    if not sales_df.empty:
        by_product = sales_df.groupby("cheese_name").agg(
            Revenue=("revenue", "sum"), Kg=("quantity_kg", "sum"), Sales=("revenue", "count"),
        ).reset_index().sort_values("Revenue", ascending=False)
        by_product["Revenue"] = by_product["Revenue"].map(lambda v: f"KSh {v:,.0f}")
        by_product["Kg"] = by_product["Kg"].map(lambda v: f"{v:,.1f}")
        st.dataframe(by_product.rename(columns={"cheese_name": "Cheese"}),
                     use_container_width=True, hide_index=True)
    else:
        st.caption("No sales in this range.")

    st.markdown("#### Revenue by Customer")
    if not sales_df.empty and sales_df["customer"].fillna("").str.strip().any():
        tagged = sales_df[sales_df["customer"].fillna("").str.strip() != ""]
        by_customer = tagged.groupby("customer").agg(
            Revenue=("revenue", "sum"), Kg=("quantity_kg", "sum"), Sales=("revenue", "count"),
        ).reset_index().sort_values("Revenue", ascending=False)
        by_customer["Revenue"] = by_customer["Revenue"].map(lambda v: f"KSh {v:,.0f}")
        by_customer["Kg"] = by_customer["Kg"].map(lambda v: f"{v:,.1f}")
        st.dataframe(by_customer.rename(columns={"customer": "Customer"}),
                     use_container_width=True, hide_index=True)
    else:
        st.caption("No customer-tagged sales in this range.")

    st.markdown("#### LPO Fulfillment")
    if lpo_lines:
        total_lpo_kg = sum(l["quantity_kg"] for l in lpo_lines)
        delivered = [l for l in lpo_lines if l["status"] in ("Delivered", "Partially Delivered")]
        delivered_kg = sum(l.get("quantity_delivered_kg") or 0 for l in delivered)
        fill_rate = (delivered_kg / total_lpo_kg * 100) if total_lpo_kg > 0 else 0.0
        cancelled = sum(1 for l in lpo_lines if l["status"] == "Cancelled")

        lc1, lc2, lc3 = st.columns(3)
        lc1.metric("LPO Volume", f"{total_lpo_kg:,.1f} kg")
        lc2.metric("Fill Rate", f"{fill_rate:.0f}%")
        lc3.metric("Cancelled", cancelled)

        status_counts = pd.DataFrame(lpo_lines)["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        st.dataframe(status_counts, use_container_width=True, hide_index=True)
    else:
        st.caption("No LPOs due in this range.")

    st.markdown("#### Sales vs LPO Volume")
    lpo_kg_total = sum(l["quantity_kg"] for l in lpo_lines)
    st.caption(
        f"Sold: {total_kg:,.1f} kg via {len(sales_df)} transaction(s)  •  "
        f"LPO-confirmed: {lpo_kg_total:,.1f} kg across {len(lpo_lines)} line(s) "
        f"due in this window."
    )           