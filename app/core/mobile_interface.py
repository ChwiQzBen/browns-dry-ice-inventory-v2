import streamlit as st

class MobileInterface:
    def __init__(self):
        self.mobile_features = {
            'quick_order_entry': True,
            'stock_level_alerts': True,
            'photo_documentation': True,
            'gps_tracking': True
        }
    
    def create_mobile_dashboard(self):
        """Mobile-optimized dashboard"""
        return {
            'layout': 'responsive_grid',
            'key_metrics': ['current_stock', 'next_delivery', 'alerts'],
            'quick_actions': ['place_order', 'update_stock', 'view_forecast'],
            'offline_capability': True
        }
    
    def optimize_for_mobile(self):
        """Apply mobile-friendly styles and layouts"""
        st.markdown("""
        <style>
        /* Mobile-responsive design */
        @media (max-width: 768px) {
            .main-header { font-size: 1.8rem; }
            .metric-card { padding: 0.5rem; }
            .stButton > button { width: 100%; }
            .stDataFrame { font-size: 0.8rem; }
            .stPlotlyChart { height: 300px; }
        }
        .mobile-view {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .mobile-card {
            background: white;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        </style>
        """, unsafe_allow_html=True)
    
    def quick_order_entry(self):
        """Mobile-optimized order form"""
        with st.expander("➕ Quick Order Entry"):
            with st.form("quick_order"):
                product = st.selectbox("Product", ["Dry Ice Pellets", "Dry Ice Blocks"])
                quantity = st.number_input("Quantity (kg)", min_value=1, value=150)
                delivery_date = st.date_input("Delivery Date")
                
                if st.form_submit_button("Place Order"):
                    return {"product": product, "quantity": quantity, "delivery_date": delivery_date}
        return None
