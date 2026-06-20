import sys
import os

# Add the parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from app.core.google_sheet_reader import GoogleSheetReader

st.set_page_config(page_title="Google Sheets Test", layout="wide")

st.title("📊 Google Sheets Integration Test")

gsheet = GoogleSheetReader()

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### Connection Status")
    if st.button("🔌 Connect and Read Inventory", use_container_width=True, type="primary"):
        with st.spinner("Connecting to Google Sheets..."):
            if gsheet.authenticate():
                st.success("✅ Connected to Google Sheets!")
                st.session_state.connected = True
            else:
                st.error("❌ Connection failed. Check your credentials.")
                st.session_state.connected = False

with col2:
    if st.session_state.get("connected", False):
        st.markdown("### 📦 Inventory Data")
        
        # Get all worksheets
        sheets = gsheet.get_all_worksheets()
        st.write(f"**Worksheets found:** {', '.join(sheets)}")
        
        # Read stock listing
        stock = gsheet.get_stock_listing()
        st.write(f"**STOCK_LISTING:** {len(stock)} rows")
        if not stock.empty:
            st.dataframe(stock.head(10), use_container_width=True)
        else:
            st.warning("No data found in STOCK_LISTING")
        
        # Read current stock
        current = gsheet.get_current_stock()
        st.write(f"**CURRENT_STOCK:** {len(current)} rows")
        if not current.empty:
            st.dataframe(current.head(10), use_container_width=True)
        else:
            st.warning("No data found in CURRENT_STOCK")
        
        # Get inventory summary
        summary = gsheet.get_inventory_summary()
        st.write(f"**Inventory Summary:** {len(summary)} rows")
        if not summary.empty:
            st.dataframe(summary.head(10), use_container_width=True)
        
        # Get low stock items
        low = gsheet.get_low_stock_items()
        if not low.empty:
            st.warning(f"⚠️ {len(low)} items low in stock")
            st.dataframe(low, use_container_width=True)
        else:
            st.success("✅ All items have sufficient stock")
        
        # Get category summary
        categories = gsheet.get_category_summary()
        if not categories.empty:
            st.write("**Category Summary:**")
            st.dataframe(categories, use_container_width=True)
    else:
        st.info("Click the 'Connect and Read Inventory' button to start.")
