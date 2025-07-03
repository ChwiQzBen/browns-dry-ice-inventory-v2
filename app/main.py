from datetime import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm  # ADD THIS LINE
from pathlib import Path
import sys
import os
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.core.data_loader import DataLoader
from app.core.analyzer import DryIceAnalyzer
from app.core.report_generator import ReportGenerator
from app.core.mobile_interface import MobileInterface
from app.core.inventory_tracker import InventoryTracker
from app.core.smart_alerts import SmartAlerts
from app.core.predictive_maintenance import PredictiveMaintenance
from app.core.system_integrations import SystemIntegrations

# Initialize components
data_loader = DataLoader()
df = data_loader.load_orders('data/raw/historical_orders.csv')
analyzer = DryIceAnalyzer(data_loader)
kpis = analyzer.calculate_kpis()
eoq = analyzer.calculate_eoq()
safety_stock = analyzer.calculate_safety_stock()
forecast_data = analyzer.forecast_demand()
cost_savings = analyzer.calculate_cost_savings(eoq)

mobile_ui = MobileInterface()
print(f"Starting ReorderPoint: {eoq + safety_stock}")
# Initialize inventory tracker
inventory_tracker = InventoryTracker(
    initial_stock=2000,
    analyzer=analyzer,
)

# Initialize smart alerts
alerts_system = SmartAlerts(inventory_tracker)

# Initialize predictive maintenance
maintenance_system = PredictiveMaintenance()

# Initialize system integrations
integration_system = SystemIntegrations()


def create_enhanced_charts(manager, kpis, forecast_data):
    """Create enhanced visualizations"""
    
    # 1. Order Pattern Analysis
    fig_orders = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Order Quantities Over Time", "Order Size Distribution"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )
    
    # Time series
    fig_orders.add_trace(
        go.Scatter(x=df['Date'], y=df['Order_Quantity_kg'],
                  mode='markers+lines', name='Order Quantity',
                  line=dict(color='#1f77b4')), row=1, col=1
    )
    
    fig_orders.add_trace(
        go.Scatter(x=df['Date'], y=df['Effective_Quantity'],
                  mode='lines', name='Effective Quantity (Post-Sublimation)',
                  line=dict(color='#ff7f0e', dash='dash')), row=1, col=1
    )
    
    # Distribution
    fig_orders.add_trace(
        go.Histogram(x=df['Order_Quantity_kg'], name='Order Size Distribution',
                    nbinsx=20, opacity=0.7), row=2, col=1
    )
    
    fig_orders.update_layout(height=600, showlegend=True)
    
    # 2. Cost Analysis Chart
    cost_data = pd.DataFrame({
        'Date': df['Date'],
        'Transport_Cost': df['Transport_Cost'],
        'Product_Cost': df['Total_Cost'],
        'Total_Cost': df['Transport_Cost'] + df['Total_Cost']
    })
    
    fig_cost = px.area(cost_data, x='Date', y=['Transport_Cost', 'Product_Cost'],
                      title="Cost Breakdown Over Time",
                      color_discrete_map={
                          'Transport_Cost': '#ff6b6b',
                          'Product_Cost': '#4ecdc4'
                      })
    
    # 3. Forecast Chart
    fig_forecast = None
    if forecast_data is not None:
        fig_forecast = go.Figure()
        
        # Historical data
        fig_forecast.add_trace(go.Scatter(
            x=df['Date'], y=df['Order_Quantity_kg'],
            mode='markers+lines', name='Historical Orders',
            line=dict(color='#1f77b4')
        ))
        
        # Forecast
        future_data = forecast_data[forecast_data['ds'] > df['Date'].max()]
        fig_forecast.add_trace(go.Scatter(
            x=future_data['ds'], y=future_data['yhat'],
            mode='lines', name='Forecast',
            line=dict(color='#ff7f0e')
        ))
        
        # Confidence intervals
        fig_forecast.add_trace(go.Scatter(
            x=future_data['ds'], y=future_data['yhat_upper'],
            fill=None, mode='lines', line_color='rgba(0,0,0,0)',
            showlegend=False
        ))
        fig_forecast.add_trace(go.Scatter(
            x=future_data['ds'], y=future_data['yhat_lower'],
            fill='tonexty', mode='lines', line_color='rgba(0,0,0,0)',
            name='Confidence Interval', fillcolor='rgba(255,127,14,0.3)'
        ))
        
        # Safety stock line
        fig_forecast.add_hline(y=safety_stock, line_dash="dot", 
                              annotation_text=f"Safety Stock: {safety_stock:.1f} kg",
                              line_color="red")
        
        fig_forecast.update_layout(title="Demand Forecast (30 Days)")
    
    return fig_orders, fig_cost, fig_forecast

# Main Streamlit app
def main():
    st.set_page_config(
        layout="wide", 
        page_title="Browns Cheese Dry Ice Manager",
        page_icon="❄️",
        initial_sidebar_state="expanded"
    )
    
    # Apply mobile optimization
    mobile_ui.optimize_for_mobile()
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .alert-critical {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        padding: 10px;
        margin: 10px 0;
    }
    .alert-warning {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 10px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<div class="main-header">❄️ Browns Cheese - Dry Ice Inventory Optimizer</div>', 
                unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;font-size:1.2rem;margin-bottom:2rem;">Analysis Period: July 2024 - June 2025</div>', 
                unsafe_allow_html=True)
    
    # Real-time Inventory Tracking
    st.sidebar.header("📦 Real-time Inventory")
    current_stock = st.sidebar.number_input("Current Stock (kg)", min_value=0, value=inventory_tracker.current_stock, step=50)
    inventory_tracker.current_stock = current_stock
    stock_status = inventory_tracker.get_stock_status()
    print(stock_status)
    
    st.sidebar.markdown(f"**Status:** <span style='color:{stock_status['color']};font-weight:bold'>{stock_status['status']}</span>", 
                        unsafe_allow_html=True)
    st.sidebar.progress(min(1.0, current_stock / (eoq + safety_stock * 2)))
    
    # Update stock
    st.sidebar.subheader("Update Inventory")
    usage = st.sidebar.number_input("Quantity Used (kg)", min_value=0, value=150, step=10)
    if st.sidebar.button("Record Usage"):
        alert = inventory_tracker.update_stock(usage, "Daily Consumption")
        if alert:
            st.sidebar.error(alert["message"])
    
    # Receive new stock
    new_stock = st.sidebar.number_input("New Stock Received (kg)", min_value=0, value=0, step=50)
    if st.sidebar.button("Record Receipt"):
        inventory_tracker.current_stock += new_stock
        inventory_tracker._log_transaction(new_stock, "Stock Receipt")
        st.sidebar.success(f"Stock updated: {inventory_tracker.current_stock} kg")
    
    # KPI Dashboard
    st.markdown("### 📈 Key Performance Indicators")
    
    cols = st.columns(6)
    with cols[0]:
        st.metric("Total Orders", f"{kpis['total_orders']:,}", 
                 help="Total number of dry ice orders processed")
    with cols[1]:
        st.metric("Total Volume", f"{kpis['total_volume']:,.0f} kg", 
                 help="Total dry ice volume ordered")
    with cols[2]:
        st.metric("Safety Stock", f"{safety_stock:,.1f} kg", 
                 help="Recommended safety stock for 95% service level")
    with cols[3]:
        st.metric("Economic EOQ", f"{eoq:,.1f} kg", 
                 help="Optimal order quantity to minimize costs")
    with cols[4]:
        st.metric("Container Efficiency", f"{kpis['container_utilization']*100:.1f}%", 
                 help="Container space utilization rate")
    with cols[5]:
        st.metric("Monthly Savings", f"KSh {cost_savings['savings']:,.0f}", 
                 f"{cost_savings['percent_savings']:+.1f}%",
                 help="Potential monthly cost savings with EOQ optimization")
    
    # Display alerts
    alerts = alerts_system.check_conditions(
        current_demand=150,  # Would come from real-time data
        avg_demand=kpis['avg_order_size'],
        std_demand=kpis['std_order_size'],
        current_cost=analyzer.constants['TRANSPORT_COST'] * 1.15,
        avg_cost=analyzer.constants['TRANSPORT_COST']
    )
    
    if alerts:
        st.markdown("### ⚠️ Active Alerts")
        for alert in alerts_system.get_active_alerts():
            alert_class = "alert-critical" if "CRITICAL" in alert['message'] else "alert-warning"
            st.markdown(f"<div class='{alert_class}'>{alert['timestamp'].strftime('%H:%M')} - {alert['message']}</div>", 
                        unsafe_allow_html=True)

    fig_orders, fig_cost, fig_forecast = create_enhanced_charts(analyzer, kpis, forecast_data)

    # Main Dashboard Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Order Analysis", "🔮 Demand Forecast", "📦 Inventory Management", 
        "💰 Cost Optimization", "📋 Recommendations", "🛠️ Maintenance",
    ])
    
    with tab1:
        st.markdown("### Order Pattern Analysis")
        
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(fig_orders, use_container_width=True)
        with col2:
            st.plotly_chart(fig_cost, use_container_width=True)
        
        # Order statistics
        st.markdown("### Order Statistics")
        stat_cols = st.columns(4)
        with stat_cols[0]:
            st.metric("Average Order", f"{kpis['avg_order_size']:.1f} kg")
        with stat_cols[1]:
            st.metric("Order Std Dev", f"{kpis['std_order_size']:.1f} kg")
        with stat_cols[2]:
            st.metric("Monthly Orders", f"{kpis['order_frequency']:.1f}")
        with stat_cols[3]:
            st.metric("Avg Cost/Order", f"KSh {kpis['avg_cost_per_order']:,.0f}")
    
    with tab2:
        st.markdown("### 30-Day Demand Forecast")
        
        if fig_forecast:
            st.plotly_chart(fig_forecast, use_container_width=True)
            
            if forecast_data is not None:
                # Forecast summary
                future_forecast = forecast_data[forecast_data['ds'] > df['Date'].max()]
                avg_forecast = future_forecast['yhat'].mean()
                
                st.markdown("#### Forecast Summary")
                fore_cols = st.columns(3)
                with fore_cols[0]:
                    st.metric("Avg Daily Forecast", f"{avg_forecast:.1f} kg")
                with fore_cols[1]:
                    st.metric("Monthly Forecast", f"{avg_forecast * 30:.0f} kg")
                with fore_cols[2]:
                    st.metric("Forecast Confidence", "95%")
        else:
            st.warning("Unable to generate forecast. Please check data quality.")
    
    with tab3:
        st.markdown("### Inventory Optimization Formulas")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Economic Order Quantity (EOQ)")
            st.latex(r'''
                EOQ = \sqrt{\frac{2 \times D \times S}{H \times C}}
            ''')
            
            st.markdown("**Where:**")
            st.write(f"- D = Monthly Demand = {kpis['avg_monthly_demand']:.1f} kg")
            st.write(f"- S = Ordering Cost = KSh {analyzer.constants['TRANSPORT_COST']:,.2f}")
            st.write(f"- H = Holding Rate = {analyzer.constants['HOLDING_RATE']*100:.1f}%")
            st.write(f"- C = Unit Cost = KSh {analyzer.constants['PRICE_PER_KG']:.2f}/kg")
            
            st.markdown(f"**Result: EOQ = {eoq:.1f} kg**")
        
        with col2:
            st.markdown("#### Safety Stock")
            st.latex(r'''
                SS = Z \times \sigma_d \times \sqrt{LT}
            ''')
            
            st.markdown("**Where:**")
            st.write(f"- Z = Service Level Factor = {norm.ppf(analyzer.constants['SERVICE_LEVEL']):.2f}")
            st.write(f"- σd = Demand Std Dev = {kpis['std_order_size']:.2f} kg")
            st.write(f"- LT = Lead Time = {analyzer.constants['LEAD_TIME_DAYS']} days")
            
            st.markdown(f"**Result: Safety Stock = {safety_stock:.1f} kg**")
        
        # Reorder point calculation
        st.markdown("### Reorder Point")
        reorder_point = eoq + safety_stock
        st.markdown(f"""
        **Reorder Point = EOQ + Safety Stock = {eoq:.1f} + {safety_stock:.1f} = {reorder_point:.1f} kg**
        
        This means you should place a new order when inventory reaches {reorder_point:.1f} kg.
        """)
        
        # Inventory policy visualization
        st.markdown("### Recommended Inventory Policy")
        
        policy_data = pd.DataFrame({
            'Metric': ['Economic Order Quantity', 'Safety Stock', 'Reorder Point', 'Maximum Inventory'],
            'Value (kg)': [eoq, safety_stock, reorder_point, eoq + safety_stock],
            'Description': [
                'Optimal order size to minimize total costs',
                'Buffer stock for demand variability',
                'Inventory level to trigger new order',
                'Peak inventory after order arrives'
            ]
        })
        
        st.dataframe(policy_data, use_container_width=True)
    
    with tab4:
        st.markdown("### Cost Optimization Analysis")
        
        # Cost breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Current System Costs")
            current_ordering = (kpis['current_monthly_volume'] / kpis['avg_order_size']) * analyzer.constants['TRANSPORT_COST']
            current_holding = (analyzer.constants['HOLDING_RATE'] * analyzer.constants['PRICE_PER_KG'] * kpis['avg_order_size'] / 2)
            
            st.write(f"**Ordering Cost:** KSh {current_ordering:,.2f}")
            st.write(f"- Orders per month: {kpis['current_monthly_volume'] / kpis['avg_order_size']:.1f}")
            st.write(f"- Cost per order: KSh {analyzer.constants['TRANSPORT_COST']:,.2f}")
            
            st.write(f"**Holding Cost:** KSh {current_holding:,.2f}")
            st.write(f"- Average inventory: {kpis['avg_order_size']/2:.1f} kg")
            st.write(f"- Holding rate: {analyzer.constants['HOLDING_RATE']*100:.1f}%")
            
            st.write(f"**Total Monthly Cost:** KSh {cost_savings['current_cost']:,.2f}")
        
        with col2:
            st.markdown("#### EOQ Optimized Costs")
            eoq_ordering = (kpis['current_monthly_volume'] / eoq) * analyzer.constants['TRANSPORT_COST']
            eoq_holding = (analyzer.constants['HOLDING_RATE'] * analyzer.constants['PRICE_PER_KG'] * eoq / 2)
            
            st.write(f"**Ordering Cost:** KSh {eoq_ordering:,.2f}")
            st.write(f"- Orders per month: {kpis['current_monthly_volume'] / eoq:.1f}")
            st.write(f"- Cost per order: KSh {analyzer.constants['TRANSPORT_COST']:,.2f}")
            
            st.write(f"**Holding Cost:** KSh {eoq_holding:,.2f}")
            st.write(f"- Average inventory: {eoq/2:.1f} kg")
            st.write(f"- Holding rate: {analyzer.constants['HOLDING_RATE']*100:.1f}%")
            
            st.write(f"**Total Monthly Cost:** KSh {cost_savings['eoq_cost']:,.2f}")
        
        # Cost comparison chart
        st.markdown("### Cost Comparison")
        
        cost_comparison = pd.DataFrame({
            'Cost Type': ['Ordering', 'Holding', 'Total'],
            'Current System': [
                (kpis['current_monthly_volume'] / kpis['avg_order_size']) * analyzer.constants['TRANSPORT_COST'],
                (analyzer.constants['HOLDING_RATE'] * analyzer.constants['PRICE_PER_KG'] * kpis['avg_order_size'] / 2),
                cost_savings['current_cost']
            ],
            'EOQ System': [
                (kpis['current_monthly_volume'] / eoq) * analyzer.constants['TRANSPORT_COST'],
                (analyzer.constants['HOLDING_RATE'] * analyzer.constants['PRICE_PER_KG'] * eoq / 2),
                cost_savings['eoq_cost']
            ]
        })
        
        fig_cost_comp = px.bar(cost_comparison, x='Cost Type', y=['Current System', 'EOQ System'],
                              title="Monthly Cost Comparison",
                              barmode='group',
                              color_discrete_map={
                                  'Current System': '#ff6b6b',
                                  'EOQ System': '#4ecdc4'
                              })
        
        st.plotly_chart(fig_cost_comp, use_container_width=True)
        
        # Savings summary
        st.markdown("### 💰 Savings Summary")
        savings_cols = st.columns(3)
        with savings_cols[0]:
            st.metric("Monthly Savings", f"KSh {cost_savings['savings']:,.2f}")
        with savings_cols[1]:
            st.metric("Annual Savings", f"KSh {cost_savings['savings'] * 12:,.2f}")
        with savings_cols[2]:
            st.metric("Savings Percentage", f"{cost_savings['percent_savings']:.1f}%")
    
    with tab5:
        st.markdown("### 📋 Strategic Recommendations")
        
        # Immediate actions
        st.markdown("#### 🎯 Immediate Actions")
        
        recommendations = [
            f"**Implement EOQ-based ordering:** Order {eoq:.0f} kg per shipment instead of current average of {kpis['avg_order_size']:.0f} kg",
            f"**Establish safety stock:** Maintain minimum inventory of {safety_stock:.0f} kg",
            f"**Set reorder point:** Place new orders when inventory reaches {eoq + safety_stock:.0f} kg",
            f"**Optimize order frequency:** Reduce from {kpis['order_frequency']:.1f} to {kpis['current_monthly_volume'] / eoq:.1f} orders per month"
        ]
        
        for i, rec in enumerate(recommendations, 1):
            st.markdown(f"{i}. {rec}")
        
        # Medium-term improvements
        st.markdown("#### 🔄 Medium-term Improvements")
        
        medium_term = [
            "**Demand forecasting:** Implement automated forecasting for better demand planning",
            "**Supplier negotiations:** Leverage consistent ordering patterns for better transport rates",
            "**Container optimization:** Standardize orders to maximize container utilization",
            "**Inventory tracking:** Implement real-time inventory monitoring system"
        ]
        
        for i, rec in enumerate(medium_term, 1):
            st.markdown(f"{i}. {rec}")
        
        # Key metrics to monitor
        st.markdown("#### 📊 Key Metrics to Monitor")
        
        metrics_to_track = pd.DataFrame({
            'Metric': [
                'Service Level',
                'Inventory Turnover',
                'Stockout Frequency',
                'Order Frequency',
                'Container Utilization',
                'Total Inventory Cost'
            ],
            'Current Value': [
                f"{analyzer.constants['SERVICE_LEVEL']*100:.0f}%",
                f"{kpis['current_monthly_volume'] / (kpis['avg_order_size']/2):.1f}x/month",
                "Monitor",
                f"{kpis['order_frequency']:.1f}/month",
                f"{kpis['container_utilization']*100:.1f}%",
                f"KSh {cost_savings['current_cost']:,.0f}/month"
            ],
            'Target Value': [
                f"{analyzer.constants['SERVICE_LEVEL']*100:.0f}%",
                f"{kpis['current_monthly_volume'] / (eoq/2):.1f}x/month",
                "<5%",
                f"{kpis['current_monthly_volume'] / eoq:.1f}/month",
                ">85%",
                f"KSh {cost_savings['eoq_cost']:,.0f}/month"
            ]
        })
        
        st.dataframe(metrics_to_track, use_container_width=True)
        
        # Implementation timeline
        st.markdown("#### 📅 Implementation Timeline")
        
        timeline_data = pd.DataFrame({
            'Week': ['Week 1-2', 'Week 3-4', 'Month 2', 'Month 3', 'Ongoing'],
            'Activities': [
                'Calculate EOQ and safety stock, Set reorder points',
                'Implement new ordering policy, Train staff',
                'Monitor performance, Adjust parameters',
                'Evaluate results, Optimize further',
                'Regular review and adjustment'
            ],
            'Expected Outcome': [
                'Clear inventory targets established',
                'New system operational',
                'Initial cost savings realized',
                'Full optimization achieved',
                'Continuous improvement'
            ]
        })
        
        st.dataframe(timeline_data, use_container_width=True)

    # Predictive Maintenance Tab
    with tab6:
        st.markdown("### 🔧 Container Health & Maintenance")
        
        # Mock container data
        container_data = {
            'id': 'CTN-001',
            'insulation_efficiency': 75,
            'seal_integrity': 65,
            'structural_condition': 85,
            'usage_cycles': 42
        }
        
        # Predict container failure
        prediction = maintenance_system.predict_container_failure(container_data)
        
        st.markdown(f"#### Container {container_data['id']} Health Assessment")
        cols = st.columns(4)
        with cols[0]:
            st.metric("Insulation Efficiency", f"{container_data['insulation_efficiency']}%")
        with cols[1]:
            st.metric("Seal Integrity", f"{container_data['seal_integrity']}%")
        with cols[2]:
            st.metric("Structural Condition", f"{container_data['structural_condition']}%")
        with cols[3]:
            st.metric("Usage Cycles", container_data['usage_cycles'])
        
        # Show prediction results
        st.markdown("#### Predictive Maintenance Insights")
        st.metric("Failure Probability", f"{prediction['failure_probability']*100:.1f}%")
        st.metric("Estimated Life Remaining", f"{prediction['estimated_life_remaining']} days")
        
        st.markdown("#### Recommended Actions")
        for i, action in enumerate(prediction['maintenance_recommendations'], 1):
            st.markdown(f"{i}. {action}")
    
    # Sidebar - Report Generation and Settings
    st.sidebar.header("📄 Report Generation")
    
    if st.sidebar.button("Generate PDF Report", type="primary"):
        with st.spinner("Generating comprehensive report..."):
            try:
                report = ReportGenerator(analyzer)
                report_path = report.generate_pdf()
                
                with open(report_path, "rb") as f:
                    st.sidebar.download_button(
                        label="📥 Download Report",
                        data=f,
                        file_name=report_path,
                        mime="application/pdf",
                    )
                st.sidebar.success("Report generated successfully!")
            except Exception as e:
                st.sidebar.error(f"Error generating report: {str(e)}")
    
    # Sidebar - Key Parameters
    st.sidebar.header("🔧 System Parameters")
    
    with st.sidebar.expander("Inventory Parameters"):
        st.write(f"**Price per kg:** KSh {analyzer.constants['PRICE_PER_KG']:.2f}")
        st.write(f"**Container size:** {analyzer.constants['CONTAINER_SIZE']} kg")
        st.write(f"**Transport cost:** KSh {analyzer.constants['TRANSPORT_COST']:,.2f}")
        st.write(f"**Holding rate:** {analyzer.constants['HOLDING_RATE']*100:.1f}%")
        st.write(f"**Sublimation loss:** {analyzer.constants['SUB_LOSS_RANGE'][0]:.1f}-{analyzer.constants['SUB_LOSS_RANGE'][1]:.1f}%")
        st.write(f"**Lead time:** {analyzer.constants['LEAD_TIME_DAYS']} day(s)")
        st.write(f"**Service level:** {analyzer.constants['SERVICE_LEVEL']*100:.0f}%")
    
    # Data summary
    st.sidebar.header("📊 Data Summary")
    st.sidebar.write(f"**Analysis Period:** {df['Date'].min().strftime('%d-%m-%Y')} to {df['Date'].max().strftime('%d-%m-%Y')}")
    st.sidebar.write(f"**Total Orders:** {len(df):,}")
    st.sidebar.write(f"**Data Points:** {len(df):,}")
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Browns Cheese** 🧀")
    st.sidebar.markdown("Dry Ice Management System v3.0")
    st.sidebar.markdown("© 2025 - Gathura Chege")
    
    # Additional insights in main area
    st.markdown("---")
    st.markdown("### 🔍 Additional Insights")
    
    insights_cols = st.columns(3)
    
    with insights_cols[0]:
        st.markdown("#### Order Pattern Analysis")
        # Calculate order patterns
        order_counts = df['Order_Quantity_kg'].value_counts().sort_index()
        most_common_order = order_counts.idxmax()
        st.write(f"Most common order size: **{most_common_order:.0f} kg** ({order_counts[most_common_order]} orders)")
        
        # Calculate weekday patterns
        df['Weekday'] = df['Date'].dt.day_name()
        weekday_pattern = df.groupby('Weekday')['Order_Quantity_kg'].count().sort_values(ascending=False)
        st.write(f"Busiest day: **{weekday_pattern.index[0]}** ({weekday_pattern.iloc[0]} orders)")
    
    with insights_cols[1]:
        st.markdown("#### Efficiency Metrics")
        # Calculate efficiency metrics
        avg_containers_per_order = df['Containers_Used'].mean()
        container_efficiency = (df['Order_Quantity_kg'].sum() / 
                               (df['Containers_Used'].sum() * analyzer.constants['CONTAINER_SIZE'])) * 100
        
        st.write(f"Avg containers per order: **{avg_containers_per_order:.1f}**")
        st.write(f"Container fill rate: **{container_efficiency:.1f}%**")
        
        # Calculate cost per kg
        cost_per_kg = (cost_savings['current_cost'] / kpis['current_monthly_volume'])
        st.write(f"Current cost per kg: **KSh {cost_per_kg:.2f}**")
    
    with insights_cols[2]:
        st.markdown("#### Optimization Impact")
        # Calculate optimization metrics
        order_frequency_reduction = ((kpis['order_frequency'] - (kpis['current_monthly_volume'] / eoq)) / 
                                   kpis['order_frequency'] * 100)
        
        st.write(f"Order frequency reduction: **{order_frequency_reduction:.1f}%**")
        st.write(f"Inventory turns improvement: **{(kpis['current_monthly_volume'] / (eoq/2)) / (kpis['current_monthly_volume'] / (kpis['avg_order_size']/2)) - 1:.1f}x**")
        
        # ROI calculation
        annual_savings = cost_savings['savings'] * 12
        implementation_cost = 5000  # Estimated implementation cost
        roi = (annual_savings / implementation_cost) * 100 if implementation_cost > 0 else 0
        st.write(f"Estimated ROI: **{roi:.0f}%** annually")

if __name__ == "__main__":
    main()
