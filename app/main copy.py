import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import sys
import os
import warnings
from datetime import datetime
warnings.filterwarnings('ignore')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.core.data_loader import DataLoader
from app.core.analyzer import DryIceAnalyzer
from app.core.report_generator import ReportGenerator
from app.core.inventory_tracker import InventoryTracker
from app.core.smart_alerts import SmartAlerts
from app.core.mobile_interface import MobileInterface
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

# Initialize inventory tracker
inventory_tracker = InventoryTracker(
    initial_stock=2000,
    safety_stock=safety_stock,
    reorder_point=eoq + safety_stock
)

# Initialize smart alerts
alerts_system = SmartAlerts(inventory_tracker)

# Initialize predictive maintenance
maintenance_system = PredictiveMaintenance()

# Initialize system integrations
integration_system = SystemIntegrations()

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
    
    # Main Dashboard Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Order Analysis", "🔮 Demand Forecast", "📦 Inventory Management", 
        "💰 Cost Optimization", "🛠️ Maintenance", "📋 Recommendations"
    ])
    
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
    
    # System Integration Panel
    with st.sidebar.expander("🔗 System Integrations"):
        st.markdown("**Connected Systems**")
        st.checkbox("ERP System (SAP)", value=True)
        st.checkbox("Accounting Software (QuickBooks)", value=True)
        st.checkbox("IoT Sensors", value=False)
        
        st.markdown("**Setup New Integration**")
        system_type = st.selectbox("System Type", ["ERP", "Accounting", "Supplier API"])
        if st.button("Connect System"):
            st.success("Integration setup initiated")

# Implementation Priority Matrix
PRIORITY_IMPROVEMENTS = {
    'HIGH_IMPACT_QUICK_WINS': [
        'Real-time inventory tracking',
        'Smart alerts system',
        'Mobile optimization'
    ],
    'HIGH_IMPACT_MEDIUM_EFFORT': [
        'Advanced forecasting',
        'Quality tracking',
        'Enhanced reporting'
    ],
    'MEDIUM_IMPACT_HIGH_VALUE': [
        'Supplier analytics',
        'Predictive maintenance',
        'System integrations'
    ],
    'LONG_TERM_STRATEGIC': [
        'AI/ML implementation',
        'IoT sensor integration',
        'Blockchain supply chain tracking'
    ]
}

if __name__ == "__main__":
    main()
