"""
app/core/dry_ice_ui.py
========================
Dry Ice Mode's tabs, extracted from main.py following the same shape as
cheese_production_ui.py: a single render_dry_ice_mode() entry point,
permission-filtered tabs, small _render_x_tab() functions per tab.

Takes has_permission as a callable (not the Permission enum) for the same
reason cheese_production_ui.py does — avoids a circular import, since
main.py is what imports THIS module. Permission is a (str, Enum), so its
members compare equal to their plain string values; passing plain strings
like "view_analytics" here works against main.py's ROLE_PERMISSIONS sets
without needing the enum at all.

STATUS: 📊 Order Analysis and 📜 Transaction History are fully ported.
The remaining five tabs are stubs — see the TODO checklist at the bottom
of this file before wiring this into main.py's mode branch.
"""
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime
import streamlit as st
import pandas as pd

from core.performance import paginate_dataframe, compress_dataframe
from core.error_handling import logger

DRY_ICE_TAB_REQUIREMENTS = {
    "📊 Order Analysis": "view_analytics",
    "🔮 Demand Forecast": "view_forecasts",
    "📦 Inventory Management": "view_stock",
    "💰 Cost Optimization": "view_cost_data",
    "📋 Recommendations": "view_strategy",
    "🛠️ Maintenance": "view_maintenance",
    "📜 Transaction History": "view_reports",
}


@dataclass
class DryIceContext:
    """Everything the tabs need, computed once in main() and passed in.
    Extend this as you port tabs 2–6 — e.g. fig_ensemble,
    ensemble_forecast_values, model_forecasts, backtest_accuracy for
    Demand Forecast; safety_stock, reorder_point for Inventory Management;
    decision, ai_insights if a tab ends up needing them."""
    df: pd.DataFrame
    kpis: dict
    constants: Any
    mobile_ui: Any
    inventory_tracker: Any
    fig_orders: Any
    fig_cost_overview: Any
    eoq: float
    monthly_savings: float


def render_dry_ice_mode(ctx: DryIceContext,
                         has_permission: Optional[Callable[[str], bool]] = None) -> None:
    def _allowed(permission: str) -> bool:
        return has_permission(permission) if has_permission else True

    visible = [name for name, perm in DRY_ICE_TAB_REQUIREMENTS.items() if _allowed(perm)]
    if not visible:
        st.warning("This section isn't available for your current role.")
        return

    tabs = st.tabs(visible)
    tab_lookup = dict(zip(visible, tabs))

    if "📊 Order Analysis" in tab_lookup:
        with tab_lookup["📊 Order Analysis"]:
            _render_order_analysis_tab(ctx)
    if "🔮 Demand Forecast" in tab_lookup:
        with tab_lookup["🔮 Demand Forecast"]:
            _render_demand_forecast_tab(ctx)
    if "📦 Inventory Management" in tab_lookup:
        with tab_lookup["📦 Inventory Management"]:
            _render_inventory_management_tab(ctx)
    if "💰 Cost Optimization" in tab_lookup:
        with tab_lookup["💰 Cost Optimization"]:
            _render_cost_optimization_tab(ctx)
    if "📋 Recommendations" in tab_lookup:
        with tab_lookup["📋 Recommendations"]:
            _render_recommendations_tab(ctx)
    if "🛠️ Maintenance" in tab_lookup:
        with tab_lookup["🛠️ Maintenance"]:
            _render_maintenance_tab(ctx)
    if "📜 Transaction History" in tab_lookup:
        with tab_lookup["📜 Transaction History"]:
            _render_transaction_history_tab(ctx)


# ============================================================
# FULLY PORTED
# ============================================================
def _render_order_analysis_tab(ctx: DryIceContext) -> None:
    df, kpis, constants, mobile_ui = ctx.df, ctx.kpis, ctx.constants, ctx.mobile_ui

    if not df.empty:
        st.markdown("""
        <h2 style='border-bottom: 1px solid #ddd; padding-bottom: 10px;'>
        Order Pattern & Cost Analysis
        </h2>
        """, unsafe_allow_html=True)
        with st.expander("Visual Analysis", expanded=not mobile_ui.should_collapse_advanced()):
            col1, col2 = st.columns(2)
            with col1:
                fig_orders = mobile_ui.optimize_chart_for_mobile(ctx.fig_orders)
                st.plotly_chart(fig_orders, use_container_width=True,
                    config=mobile_ui.get_mobile_chart_config())
            with col2:
                fig_cost_overview = mobile_ui.optimize_chart_for_mobile(ctx.fig_cost_overview)
                st.plotly_chart(fig_cost_overview, use_container_width=True,
                    config=mobile_ui.get_mobile_chart_config())

        st.markdown("""
        <h2 style='border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-top: 30px;'>
        Order Statistics
        </h2>
        """, unsafe_allow_html=True)

        stat_cols = st.columns(4)
        metric_style = """<style>.stMetric {border-left: 3px solid #4e79a7;padding: 10px 15px;border-radius: 5px;background-color: #f9f9f9;}</style>"""
        st.markdown(metric_style, unsafe_allow_html=True)

        metrics = [
            ("Average Order", f"{kpis.get('avg_order_size', 0):.1f} kg", "Average order quantity"),
            ("Order Std Dev", f"{kpis.get('std_order_size', 0):.1f} kg", "Variability in order sizes"),
            ("Monthly Orders", f"{kpis.get('order_frequency', 0):.1f}", "Total orders per month"),
            ("Avg Cost/Order", f"KSh {kpis.get('avg_cost_per_order', 0):,.0f}", "Average cost per order")
        ]

        for i, (label, value, help_text) in enumerate(metrics):
            with stat_cols[i]:
                st.metric(label, value, help=help_text)

        st.markdown("""
        <h2 style='border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-top: 30px;'>
        Additional Insights
        </h2>
        """, unsafe_allow_html=True)

        insights_cols = st.columns([1, 1, 1], gap="large")

        with insights_cols[0]:
            with st.container():
                st.markdown("#### 📊 Order Pattern Analysis")
                order_counts = df['Order_Quantity_kg'].value_counts().sort_index()
                most_common_order = order_counts.idxmax()
                st.metric("Most common order size", f"{most_common_order:.0f} kg", f"{order_counts.max()} orders")

                df['Weekday'] = df['Date'].dt.day_name()
                weekday_pattern = df.groupby('Weekday')['Order_Quantity_kg'].count().sort_values(ascending=False)
                st.metric("Busiest day", weekday_pattern.index[0], f"{weekday_pattern.iloc[0]} orders")

        with insights_cols[1]:
            with st.container():
                st.markdown("#### ⚙️ Efficiency Metrics")
                avg_containers_per_order = df['Containers_Used'].mean()
                container_efficiency = (df['Order_Quantity_kg'].sum() / (df['Containers_Used'].sum() * constants.CONTAINER_SIZE)) * 100
                st.metric("Avg containers per order", f"{avg_containers_per_order:.1f}")
                st.metric("Container fill rate", f"{container_efficiency:.1f}%")

                product_cost = constants.PRICE_PER_KG
                transport_cost = (kpis.get('order_frequency', 0) * constants.TRANSPORT_COST) / kpis.get('current_monthly_volume', 1)
                holding_cost = (kpis.get('avg_order_size', 0)/2) * constants.HOLDING_RATE * constants.PRICE_PER_KG / kpis.get('current_monthly_volume', 1)

                avg_sublimation_rate = sum(constants.SUB_LOSS_RANGE) / 2 / 100
                sublimation_cost_per_kg = constants.PRICE_PER_KG * avg_sublimation_rate

                current_cost_per_kg = product_cost + transport_cost + holding_cost + sublimation_cost_per_kg
                st.metric("Current cost per kg", f"KSh {current_cost_per_kg:.2f}", delta=None)

        with insights_cols[2]:
            with st.container():
                st.markdown("#### 📈 Optimization Impact")
                if ctx.eoq > 0:
                    order_frequency_reduction = ((kpis.get('order_frequency', 0) - (kpis.get('current_monthly_volume', 0) / ctx.eoq)) / kpis.get('order_frequency', 1) * 100)
                    st.metric("Order frequency reduction", f"{order_frequency_reduction:.1f}%")

                    current_turns = kpis.get('current_monthly_volume', 0) / (kpis.get('avg_order_size', 1)/2)
                    eoq_turns = 1.3
                    inventory_turns_improvement = eoq_turns - current_turns
                    st.metric("Inventory Turns Change", f"{inventory_turns_improvement:+.1f}x")

                annual_savings = ctx.monthly_savings * 12
                implementation_cost = st.session_state.get('implementation_cost', constants.IMPLEMENTATION_COST)
                roi = (annual_savings / implementation_cost) * 100 if implementation_cost > 0 else float('inf')
                st.metric("Estimated ROI", f"{roi:.0f}%", help="Return on investment from implementing optimizations")
    else:
        st.warning("📊 No order data exists for this analysis period.")
        st.info("Use the 'Record Receipt' button in the sidebar to add the first order for this period.")


def _render_transaction_history_tab(ctx: DryIceContext) -> None:
    mobile_ui, inventory_tracker = ctx.mobile_ui, ctx.inventory_tracker

    st.markdown("## 📜 Inventory Transaction History")

    if not st.session_state.transactions:
        st.info("No transactions recorded for this period yet. Use the sidebar to record usage or receipts.")
    else:
        trans_df = pd.DataFrame(st.session_state.transactions)
        trans_df['date'] = pd.to_datetime(trans_df['date'])
        trans_df = trans_df.sort_values('date', ascending=False)
        trans_df = compress_dataframe(trans_df)
        logger.info(f"Transactions loaded and compressed: {len(trans_df)} records")

        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            transaction_type = st.selectbox("Transaction Type", ["All", "usage", "receipt"], key="trans_type_filter")
        with filter_col2:
            date_min = trans_df['date'].min().date()
            date_max = trans_df['date'].max().date()
            selected_dates = st.date_input("Date Range", [date_min, date_max], min_value=date_min, max_value=date_max, key="date_range_filter")
        with filter_col3:
            show_limit = st.selectbox("Show Last", ["All", "10", "25", "50", "100"], key="show_limit_filter")

        filtered_df = trans_df.copy()
        if transaction_type != "All":
            filtered_df = filtered_df[filtered_df['type'] == transaction_type]
        if len(selected_dates) == 2:
            start_date, end_date = selected_dates
            filtered_df = filtered_df[(filtered_df['date'].dt.date >= start_date) & (filtered_df['date'].dt.date <= end_date)]
        if show_limit != "All":
            filtered_df = filtered_df.head(int(show_limit))

        with st.expander("📋 View Transaction Records", expanded=not mobile_ui.should_collapse_advanced()):
            if len(filtered_df) > 100:
                paginated_df, paginator = paginate_dataframe(
                    filtered_df, page_size=50, key_prefix="transactions",
                    show_controls=True, compact=False,
                )
                display_df = paginated_df
                show_pagination = True
            else:
                display_df = filtered_df
                show_pagination = False

            display_df_display = display_df.copy()
            display_df_display['Date'] = display_df_display['date'].dt.strftime('%Y-%m-%d %H:%M')
            display_df_display['Type'] = display_df_display['type'].str.title()
            display_df_display['Quantity (kg)'] = display_df_display['quantity'].apply(lambda x: f"{x:,.2f}")

            st.dataframe(
                display_df_display[['Date', 'Type', 'Quantity (kg)', 'description']],
                use_container_width=True, height=400, hide_index=True,
            )

            if show_pagination:
                st.caption(f"📊 Page {paginator.current_page} of {paginator.total_pages} | Showing {len(display_df):,} of {len(filtered_df):,} records")
            else:
                st.caption(f"📊 Showing {len(filtered_df):,} records")

        st.markdown("### 📈 Transaction Summary (Filtered Period)")
        total_used = filtered_df[filtered_df['type']=='usage']['quantity'].sum()
        total_received = filtered_df[filtered_df['type']=='receipt']['quantity'].sum()
        net_change = total_received - total_used

        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        stat_col1.metric("Total Used", f"{total_used:,.1f} kg")
        stat_col2.metric("Total Received", f"{total_received:,.1f} kg")
        stat_col3.metric("Net Change", f"{net_change:,.1f} kg", delta=f"{net_change:,.1f} kg")
        stat_col4.metric("Total Transactions", len(filtered_df))

        st.markdown("### 📥 Export Filtered Data")
        if not filtered_df.empty:
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV", data=csv,
                file_name=f"transaction_history_{st.session_state.selected_period.replace('/', '-')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv', use_container_width=True,
            )
        else:
            st.caption("No data in the current filter to export.")

    st.divider()
    st.markdown("### 📊 Current Status")
    st.metric("Current Stock Level", f"{inventory_tracker.current_stock:,.1f} kg")


# ============================================================
# TODO — port these from main.py, then delete the stub body
# ============================================================
def _render_demand_forecast_tab(ctx: DryIceContext) -> None:
    st.info("🚧 Not yet migrated — currently still rendered inline in main.py (tab2).")

def _render_inventory_management_tab(ctx: DryIceContext) -> None:
    st.info("🚧 Not yet migrated — currently still rendered inline in main.py (tab3).")

def _render_cost_optimization_tab(ctx: DryIceContext) -> None:
    st.info("🚧 Not yet migrated — currently still rendered inline in main.py (tab4).")

def _render_recommendations_tab(ctx: DryIceContext) -> None:
    st.info("🚧 Not yet migrated — currently still rendered inline in main.py (tab5).")

def _render_maintenance_tab(ctx: DryIceContext) -> None:
    st.info("🚧 Not yet migrated — currently still rendered inline in main.py (tab6).")