"""
Dashboard home surface: KPI grid, Decision Center, Insights & Scenarios
(AI Insights + What-If Simulator), and the System-Wide ROI Summary.

Rendered once per page load in main.py, between the sidebar and the
mode branch (All Items / BCPOS / Dry Ice). Mirrors the AllItemsContext /
DryIceContext + render_*_mode() pattern already used elsewhere in the app.
"""
from dataclasses import dataclass
from typing import Any, Optional

import math
import numpy as np
import pandas as pd
import streamlit as st

from app.core.theme import THEME, kpi_card
from app.core.decision_engine import InventorySnapshot, InventoryDecisionEngine, generate_ai_insights


@dataclass
class DashboardContext:
    # Forecast / inventory-policy pipeline outputs (computed earlier in main())
    kpis: dict
    eoq: float
    eoq_monthly_orders: float
    safety_stock: float
    reorder_point: float
    backtest_accuracy: float
    ensemble_forecast_values: np.ndarray
    monthly_demand_input: float
    demand_stddev_input: float
    sublimation_factor: float
    z_score: float
    annual_transport_savings: float
    annual_holding_cost: float
    total_annual_spending: float
    current_monthly_orders: float

    # Live objects / shared state
    inventory_tracker: Any
    constants: Any  # main.py's Constants instance (TRANSPORT_COST, PRICE_PER_KG, HOLDING_RATE, LEAD_TIME_DAYS, IMPLEMENTATION_COST, ALL_ITEMS_IMPLEMENTATION_COST, SYNERGY_DISCOUNT)
    decision: Optional[dict]
    stock_df: Optional[pd.DataFrame]


@st.cache_data(ttl=600)
def calculate_all_items_annual_savings(stock_df, order_cost, holding_rate):
    """
    Compute total EOQ-based annual savings across all priced inventory items.
    Cached and computed automatically once stock_df is loaded — no button click needed.
    Returns (total_annual_savings, items_analyzed).
    """
    if stock_df is None or stock_df.empty:
        return 0.0, 0

    cost_df = stock_df.copy()
    if 'QUANTITY' not in cost_df.columns or 'UNIT PRICE' not in cost_df.columns:
        return 0.0, 0

    cost_df['QUANTITY'] = pd.to_numeric(cost_df['QUANTITY'], errors='coerce')
    cost_df['UNIT PRICE'] = pd.to_numeric(cost_df['UNIT PRICE'], errors='coerce')
    cost_df = cost_df.dropna(subset=['QUANTITY', 'UNIT PRICE'])
    cost_df = cost_df[(cost_df['QUANTITY'] > 0) & (cost_df['UNIT PRICE'] > 0)]

    if cost_df.empty or holding_rate <= 0:
        return 0.0, 0

    cost_df['ANNUAL_DEMAND'] = cost_df['QUANTITY'] * 12
    total_savings = 0.0
    items_counted = 0

    for _, row in cost_df.iterrows():
        try:
            eoq = math.sqrt((2 * row['ANNUAL_DEMAND'] * order_cost) / (holding_rate * row['UNIT PRICE']))
            if eoq > 0 and row['QUANTITY'] > 0:
                current_cost = (row['ANNUAL_DEMAND'] / row['QUANTITY']) * order_cost + (row['QUANTITY'] / 2) * holding_rate * row['UNIT PRICE']
                optimal_cost = (row['ANNUAL_DEMAND'] / eoq) * order_cost + (eoq / 2) * holding_rate * row['UNIT PRICE']
                savings = max(0, current_cost - optimal_cost)
                total_savings += savings
                items_counted += 1
        except (ValueError, ZeroDivisionError):
            continue

    return total_savings, items_counted


def render_dashboard_home(ctx: DashboardContext) -> None:
    """Render the KPI grid, Decision Center, Insights & Scenarios, and ROI Summary."""

    kpis = ctx.kpis
    eoq = ctx.eoq
    eoq_monthly_orders = ctx.eoq_monthly_orders
    safety_stock = ctx.safety_stock
    reorder_point = ctx.reorder_point
    backtest_accuracy = ctx.backtest_accuracy
    ensemble_forecast_values = ctx.ensemble_forecast_values
    monthly_demand_input = ctx.monthly_demand_input
    demand_stddev_input = ctx.demand_stddev_input
    sublimation_factor = ctx.sublimation_factor
    z_score = ctx.z_score
    annual_transport_savings = ctx.annual_transport_savings
    monthly_savings=st.session_state.get('monthly_savings', 0),
    annual_holding_cost = ctx.annual_holding_cost
    total_annual_spending = ctx.total_annual_spending
    current_monthly_orders = ctx.current_monthly_orders
    inventory_tracker = ctx.inventory_tracker
    constants = ctx.constants
    decision = ctx.decision
    stock_df = ctx.stock_df

    # NOTE: stock_status used to be read from a sidebar-scoped variable of the
    # same name computed earlier in main(). That implicit reliance doesn't
    # survive extraction into a separate module, so it's computed explicitly
    # here instead (same call, same result — inventory_tracker.current_stock
    # hasn't changed between the sidebar render and this point).
    stock_status = inventory_tracker.get_stock_status()

    # ============================================================
    # 🎨 SINGLE KPI CARD - Like Sidebar Container Style
    # Calculate monthly savings and percentage
    monthly_savings = annual_transport_savings / 12
    monthly_transport_cost = (current_monthly_orders * constants.TRANSPORT_COST)
    percent_savings = (monthly_savings / monthly_transport_cost) * 100 if monthly_transport_cost > 0 else 0

    # ============================================================
    # SINGLE UNIFIED KPI CARD
    # ============================================================

    st.markdown("""
    <div style="
        border: 2px solid #667eea;
        border-radius: 16px;
        padding: 20px;
        margin: 20px 0;
        background: rgba(102, 126, 234, 0.04);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
    ">
        <!-- Card Header -->
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 2px solid rgba(102, 126, 234, 0.15);
        ">
            <div style="
                display: flex;
                align-items: center;
                gap: 12px;
            ">
                <span style="font-size: 28px;">📈</span>
                <span style="
                    font-size: 20px;
                    font-weight: 700;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                ">
                    Key Performance Indicators
                </span>
            </div>
            <div style="
                background: rgba(102, 126, 234, 0.1);
                padding: 4px 14px;
                border-radius: 20px;
                font-size: 11px;
                color: #667eea;
                font-weight: 600;
            ">
                Real-time
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ============================================================
    # KPI GRID - 4 Columns Inside Single Card
    # ============================================================
    container_eff = kpis.get('container_utilization', 0) * 100

    if stock_status['status'] in ['Critical', 'Low Stock']:
        action_stock = f"→ Order {eoq:,.0f} kg now"
    else:
        action_stock = "→ No action needed"

    if eoq_monthly_orders > 0:
        action_orders = f"→ Target {eoq_monthly_orders:.1f}/mo (EOQ-optimal)"
    else:
        action_orders = "→ —"

    if inventory_tracker.current_stock < safety_stock * 1.2:
        action_safety = "→ Near threshold — reorder soon"
    else:
        action_safety = "→ Buffer adequate"

    avg_order = kpis.get('avg_order_size', 0)
    if avg_order > 0 and eoq > 0 and abs(avg_order - eoq) / eoq > 0.25:
        action_eoq = f"→ Align orders closer to {eoq:,.0f} kg"
    else:
        action_eoq = "→ Order sizes aligned"

    action_spending = "→ See cost breakdown below"

    if annual_transport_savings > 0:
        action_transport = "→ Implement EOQ to realize this"
    else:
        action_transport = "→ Already optimized"

    if percent_savings > 0:
        action_monthly = "→ On track — maintain policy"
    else:
        action_monthly = "→ Review order frequency"

    if container_eff < 85:
        action_container = "→ Consolidate orders to improve fill"
    else:
        action_container = "→ Fill rate optimal"

    # Row 1: Main KPIs (4 columns)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        kpi_card("Current Stock", f"{inventory_tracker.current_stock:,.0f}", icon="📦",
                  color=stock_status['color'],
                  subtext=f"<span style='color:{stock_status['color']};font-weight:600;'>{stock_status['status']}</span>",
                  action=action_stock)
    with col2:
        kpi_card("Total Orders", f"{kpis.get('total_orders', 0):,}", icon="📋",
                  color=THEME["info"], subtext=f"{kpis.get('total_volume', 0):,.0f} kg total",
                  action=action_orders)
    with col3:
        kpi_card("Safety Stock", f"{safety_stock:,.1f}", icon="🛡️",
                  color=THEME["orange"], subtext=f"{kpis.get('order_frequency', 0):.1f} orders/mo",
                  action=action_safety)
    with col4:
        kpi_card("Economic EOQ", f"{eoq:,.1f}", icon="📦",
                  color=THEME["purple"], subtext="Optimal order size",
                  action=action_eoq)

    # Divider inside card
    st.markdown("""
    <div style="
        margin: 12px 0;
        border-top: 1px solid rgba(255,255,255,0.08);
    "></div>
    """, unsafe_allow_html=True)

    # Row 2: Financial KPIs (4 columns)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        kpi_card("Annual Spending", f"KSh {total_annual_spending:,.0f}", icon="💰",
                  color="#e74c3c", subtext="Total cost", action=action_spending)
    with col2:
        kpi_card("Annual Transport Savings", f"KSh {annual_transport_savings:,.0f}", icon="🚀",
                  color=THEME["success"], value_color=THEME["success"],
                  subtext="From EOQ optimization", action=action_transport)
    with col3:
        delta_color = THEME["success"] if percent_savings > 0 else THEME["danger"]
        delta_arrow = "▲" if percent_savings > 0 else "▼"
        kpi_card("Monthly Savings", f"KSh {monthly_savings:,.0f}", icon="📈",
                  color=THEME["orange_dark"],
                  subtext=f"<span style='color:{delta_color};font-weight:600;'>{delta_arrow} {percent_savings:+.1f}%</span>",
                  action=action_monthly)
    with col4:
        kpi_card("Container Efficiency", f"{container_eff:.1f}%", icon="📊",
                  color=THEME["cyan"], subtext="Fill rate", action=action_container)

    # Optional: Add a progress bar for stock level at the bottom
    if eoq > 0 and safety_stock > 0:
        max_stock = eoq + safety_stock
        current_pct = min(100, (inventory_tracker.current_stock / max_stock) * 100) if max_stock > 0 else 0

        # Determine color
        if current_pct < 30:
            gauge_color = "#dc3545"
            gauge_text = "Critical"
        elif current_pct < 50:
            gauge_color = "#ffc107"
            gauge_text = "Low"
        else:
            gauge_color = "#28a745"
            gauge_text = "Healthy"

        st.markdown(f"""
        <div style="
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid rgba(255,255,255,0.08);
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <div style="font-size: 11px; color: #888; font-weight: 500;">
                    📊 Stock Level Indicator
                </div>
                <div style="font-size: 12px; font-weight: 600; color: {gauge_color};">
                    {current_pct:.0f}% - {gauge_text}
                </div>
            </div>
            <div style="
                height: 6px;
                background: rgba(255,255,255,0.1);
                border-radius: 4px;
                overflow: hidden;
            ">
                <div style="
                    width: {current_pct:.1f}%;
                    height: 6px;
                    background: linear-gradient(90deg, {gauge_color}, {gauge_color});
                    border-radius: 4px;
                    transition: width 0.8s ease;
                "></div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 2px;">
                <span style="font-size: 8px; color: #999;">0%</span>
                <span style="font-size: 8px; color: #999;">EOQ + Safety Stock</span>
                <span style="font-size: 8px; color: #999;">100%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Close the card
    st.markdown("</div>", unsafe_allow_html=True)

    # 🎯 DECISION CENTER
    # ============================================================
    if decision:
        RISK_COLORS = {
            "Critical": "#dc3545",
            "High": "#ff9800",
            "Medium": "#ffc107",
            "Low": "#28a745",
        }
        decision_color = RISK_COLORS.get(decision["risk"]["level"], "#888888")
        inv = decision["inventory"]
        risk = decision["risk"]
        fin = decision["financial"]

        st.markdown(f"""
        <div style="
            border: 2px solid {decision_color};
            border-radius: 16px;
            padding: 20px;
            margin: 20px 0;
            background: {decision_color}0d;
        ">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <span style="font-size:18px; font-weight:700;">🎯 Decision Center</span>
                <span style="background:{decision_color}; color:white; padding:4px 14px; border-radius:20px; font-size:12px; font-weight:600;">
                    {risk['level']} Risk ({risk['score']}/100)
                </span>
            </div>
            <div style="font-size:20px; font-weight:700; color:{decision_color}; margin-bottom:6px;">
                {inv['action']}
            </div>
            <div style="font-size:14px; color:#555; margin-bottom:10px;">
                {inv['recommendation']}
            </div>
            <div style="display:flex; gap:24px; flex-wrap:wrap; font-size:13px; color:#888; margin-bottom:12px;">
                <span>📅 Days remaining: <strong>{inv['days_remaining']}</strong></span>
                <span>📦 Recommended qty: <strong>{inv['recommended_quantity']:,.0f} kg</strong></span>
                <span>🎯 Forecast confidence: <strong>{decision['forecast_accuracy']:.0f}%</strong></span>
                <span>💰 Potential savings: <strong>KSh {fin['potential_monthly_savings']:,.0f}/mo</strong></span>
            </div>
            <div style="border-top: 1px solid rgba(0,0,0,0.08); padding-top: 10px;">
                <div style="font-size:12px; font-weight:600; color:#666; margin-bottom:4px;">Why?</div>
                {''.join(f'<div style="font-size:13px; color:#555; margin-bottom:2px;">• {reason}</div>' for reason in decision['explanation'])}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ============================================================
    # 🔎 INSIGHTS & SCENARIOS (AI Insights + What-If, merged into tabs
    # inside one expander so they read as a single surface, not two
    # separately-floating blocks)
    # ============================================================
    avg_daily_forecast_val = float(np.mean(ensemble_forecast_values)) if len(ensemble_forecast_values) > 0 else 0
    historical_avg_daily_val = kpis.get('current_monthly_volume', 0) / 30

    ai_insights = generate_ai_insights(
        current_stock=inventory_tracker.current_stock,
        safety_stock=safety_stock,
        reorder_point=reorder_point,
        eoq=eoq,
        avg_daily_forecast=avg_daily_forecast_val,
        historical_avg_daily=historical_avg_daily_val,
        forecast_accuracy=backtest_accuracy * 100,
        container_efficiency=kpis.get('container_utilization', 0) * 100,
    )

    with st.expander("🔎 Insights & Scenarios", expanded=False):
        insights_tab, whatif_tab = st.tabs(["🤖 AI Insights", "🔮 What-If Simulator"])

        with insights_tab:
            if ai_insights:
                insight_lines = "".join(
                    f'<div style="font-size:13px; color:#444; margin-bottom:6px;">{i["icon"]} {i["text"]}</div>'
                    for i in ai_insights
                )
                st.markdown(f"""
                <div style="padding: 4px 0 0 0;">
                    {insight_lines}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.caption("No notable insights right now.")

        with whatif_tab:
            if not decision:
                st.info("🔮 What-If Simulator will be available after the next page refresh — the Decision Center needs one full run first.")
            else:
                st.caption("Adjust assumptions below to see how they'd affect inventory recommendations. This does not change your live data.")
                with st.form("whatif_form"):
                    sim_col1, sim_col2 = st.columns(2)
                    with sim_col1:
                        demand_change_pct = st.slider(
                            "Demand change (%)", min_value=-50, max_value=100, value=0, step=5,
                            help="Simulate a demand increase or decrease vs. current forecast",
                            key="sim_demand_change"
                        )
                    with sim_col2:
                        lead_time_delta = st.slider(
                            "Additional supplier lead time (days)", min_value=0, max_value=10, value=0, step=1,
                            help="Simulate a supplier delay",
                            key="sim_lead_time_delta"
                        )
                    run_sim = st.form_submit_button("Apply scenario")

                if run_sim and (demand_change_pct != 0 or lead_time_delta != 0):
                    sim_monthly_demand = monthly_demand_input * (1 + demand_change_pct / 100)
                    sim_adjusted_demand = sim_monthly_demand * sublimation_factor
                    sim_lead_time_days = constants.LEAD_TIME_DAYS + lead_time_delta

                    sim_eoq = math.sqrt(
                        (2 * sim_adjusted_demand * constants.TRANSPORT_COST) / (constants.HOLDING_RATE * constants.PRICE_PER_KG)
                    ) if (constants.HOLDING_RATE * constants.PRICE_PER_KG) > 0 else 0

                    sim_safety_stock = z_score * demand_stddev_input * math.sqrt(sim_lead_time_days) * sublimation_factor
                    sim_reorder_point = (sim_adjusted_demand / 30 * sim_lead_time_days) + sim_safety_stock
                    sim_forecast_values = ensemble_forecast_values * (1 + demand_change_pct / 100)

                    sim_snapshot = InventorySnapshot(
                        current_stock=inventory_tracker.current_stock,
                        eoq=sim_eoq,
                        safety_stock=sim_safety_stock,
                        reorder_point=sim_reorder_point,
                        forecast_values=sim_forecast_values,
                        forecast_accuracy=backtest_accuracy * 100,
                        lead_time_days=sim_lead_time_days,
                        transport_cost=constants.TRANSPORT_COST,
                        avg_order_size=kpis.get('avg_order_size', 300),
                        monthly_holding_cost=annual_holding_cost / 12,
                    )
                    sim_decision = InventoryDecisionEngine(sim_snapshot).executive_summary()

                    st.markdown("---")
                    compare_col1, compare_col2 = st.columns(2)
                    with compare_col1:
                        st.markdown("**📍 Current (Baseline)**")
                        st.metric("Days Remaining", f"{decision['inventory']['days_remaining']}")
                        st.metric("Action", decision['inventory']['action'])
                        st.metric("Recommended Qty", f"{decision['inventory']['recommended_quantity']:,.0f} kg")
                    with compare_col2:
                        st.markdown("**🔮 Simulated Scenario**")
                        delta_days = sim_decision['inventory']['days_remaining'] - decision['inventory']['days_remaining']
                        st.metric("Days Remaining", f"{sim_decision['inventory']['days_remaining']}", delta=f"{delta_days:+d} days")
                        st.metric("Action", sim_decision['inventory']['action'])
                        st.metric("Recommended Qty", f"{sim_decision['inventory']['recommended_quantity']:,.0f} kg")

                    st.info(f"**{sim_decision['inventory']['recommendation']}**")

                    if sim_decision['risk']['level'] in ('Critical', 'High') and decision['risk']['level'] not in ('Critical', 'High'):
                        st.warning(f"⚠️ This scenario would raise your risk level from {decision['risk']['level']} to {sim_decision['risk']['level']}.")
                else:
                    st.caption("Move a slider above to see the simulated impact.")

    # ============================================================
    # 🏢 SYSTEM-WIDE ROI SUMMARY (Tier 3 — Combined, auto-recomputed)
    # ============================================================
    dry_ice_implementation_cost = st.session_state.get('implementation_cost', constants.IMPLEMENTATION_COST)
    all_items_implementation_cost = st.session_state.get('all_items_implementation_cost', constants.ALL_ITEMS_IMPLEMENTATION_COST)
    combined_implementation_cost = (dry_ice_implementation_cost + all_items_implementation_cost) * (1 - constants.SYNERGY_DISCOUNT)

    all_items_annual_savings, items_analyzed = calculate_all_items_annual_savings(
        stock_df if stock_df is not None else pd.DataFrame(),
        constants.TRANSPORT_COST,
        constants.HOLDING_RATE
    )

    combined_annual_savings = annual_transport_savings + all_items_annual_savings
    combined_monthly_savings = combined_annual_savings / 12
    combined_payback_months = (
        combined_implementation_cost / combined_monthly_savings
        if combined_monthly_savings > 0 else 0
    )
    combined_roi = (
        (combined_annual_savings / combined_implementation_cost) * 100
        if combined_implementation_cost > 0 else 0
    )

    with st.expander("🏢 System-Wide ROI Summary (Dry Ice + All Items Combined)", expanded=False):
        st.caption(
            f"Analyzed {items_analyzed} priced items across all categories, plus Dry Ice EOQ optimization. "
            f"Costs below are estimates — adjust in Sidebar → System Parameters → Inventory Parameters."
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**❄️ Dry Ice Tier**")
            st.metric("Implementation Cost", f"KSh {dry_ice_implementation_cost:,.0f}")
            st.metric("Annual Savings", f"KSh {annual_transport_savings:,.0f}")
            dry_ice_roi = (annual_transport_savings / dry_ice_implementation_cost * 100
                           if dry_ice_implementation_cost > 0 else 0)
            st.metric("ROI", f"{dry_ice_roi:.0f}%")

        with col2:
            st.markdown("**📦 All Items Tier**")
            st.metric("Implementation Cost", f"KSh {all_items_implementation_cost:,.0f}")
            st.metric("Annual Savings", f"KSh {all_items_annual_savings:,.0f}")
            all_items_roi = (all_items_annual_savings / all_items_implementation_cost * 100
                              if all_items_implementation_cost > 0 else 0)
            st.metric("ROI", f"{all_items_roi:.0f}%")

        with col3:
            st.markdown("**🎯 Combined System**")
            st.metric("Implementation Cost", f"KSh {combined_implementation_cost:,.0f}",
                       help=f"Auto-computed: (Dry Ice + All Items) × {1 - constants.SYNERGY_DISCOUNT:.2f} — reflects shared training/supervision overhead when rolled out together")
            st.metric("Annual Savings", f"KSh {combined_annual_savings:,.0f}")
            st.metric("ROI", f"{combined_roi:.0f}%")

        st.markdown("---")
        st.metric("📅 Combined Payback Period", f"{combined_payback_months:.1f} months")