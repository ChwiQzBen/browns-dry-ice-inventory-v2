# core/google_sheet_reader.py
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

class GoogleSheetReader:
    def __init__(self):
        self.sheet_url = st.secrets.get("GOOGLE_SHEET_URL", "")
        self.client = None
        self.sheet = None
        self.authenticated = False
        
    def authenticate(self):
        """Authenticate with Google Sheets API"""
        try:
            # Read-only scope
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive.readonly'
            ]
            
            # Load credentials from secrets
            if 'google_credentials' in st.secrets:
                creds_dict = dict(st.secrets["google_credentials"])
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            else:
                creds = ServiceAccountCredentials.from_json_keyfile_name(
                    'google-credentials.json', scope
                )
            
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_url(self.sheet_url)
            self.authenticated = True
            return True
        except Exception as e:
            st.error(f"Authentication failed: {e}")
            return False
    
    def read_worksheet(self, worksheet_name):
        """Read any worksheet into a DataFrame"""
        if not self.authenticated:
            if not self.authenticate():
                return pd.DataFrame()
        
        try:
            worksheet = self.sheet.worksheet(worksheet_name)
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)
            df = df.dropna(how='all')
            return df
        except Exception as e:
            st.error(f"Error reading '{worksheet_name}': {e}")
            return pd.DataFrame()
    
    def get_all_worksheets(self):
        """Get list of all worksheets"""
        if not self.authenticated:
            self.authenticate()
        if self.sheet:
            return [ws.title for ws in self.sheet.worksheets()]
        return []
    
    def get_stock_listing(self):
        """Read STOCK_LISTING"""
        return self.read_worksheet("STOCK_LISTING")
    
    def get_current_stock(self):
        """Read CURRENT_STOCK"""
        return self.read_worksheet("CURRENT_STOCK")
    
    def get_check_in(self):
        """Read CHECK_IN"""
        return self.read_worksheet("CHECK_IN")
    
    def get_check_out(self):
        """Read CHECK_OUT"""
        return self.read_worksheet("CHECK_OUT")
    
    def get_unit_pricing(self):
        """Read UNIT PRICING"""
        return self.read_worksheet("UNIT PRICING")
    
    def get_inventory_summary(self):
        """Get combined inventory summary"""
        stock_df = self.get_stock_listing()
        current_stock_df = self.get_current_stock()
        pricing_df = self.get_unit_pricing()
        
        # Start with stock listing
        summary = stock_df.copy() if not stock_df.empty else pd.DataFrame()
        
        # Add current stock if available
        if not current_stock_df.empty and not summary.empty:
            # Try to find matching columns
            name_cols = ['Item Name', 'Product', 'Item', 'Name']
            found_col = None
            for col in name_cols:
                if col in summary.columns and col in current_stock_df.columns:
                    found_col = col
                    break
            
            if found_col:
                summary = summary.merge(
                    current_stock_df, 
                    on=found_col, 
                    how='left'
                )
        
        # Add pricing if available
        if not pricing_df.empty and not summary.empty:
            price_cols = ['Item', 'Product', 'Name']
            found_price = None
            for col in price_cols:
                if col in summary.columns and col in pricing_df.columns:
                    found_price = col
                    break
            
            if found_price:
                summary = summary.merge(
                    pricing_df,
                    on=found_price,
                    how='left'
                )
        
        return summary
    
    def get_low_stock_items(self, threshold=None):
        """Get items with low stock levels"""
        stock_df = self.get_current_stock()
        if stock_df.empty:
            return pd.DataFrame()
        
        # Find stock column
        stock_col = None
        for col in stock_df.columns:
            if 'stock' in col.lower():
                stock_col = col
                break
        
        if stock_col:
            if threshold is None:
                # Try to find reorder point column
                reorder_col = None
                for col in stock_df.columns:
                    if 'reorder' in col.lower():
                        reorder_col = col
                        break
                
                if reorder_col:
                    low_stock = stock_df[stock_df[stock_col] <= stock_df[reorder_col]]
                else:
                    # Use 10% of average as threshold
                    avg = stock_df[stock_col].mean()
                    low_stock = stock_df[stock_df[stock_col] <= avg * 0.1]
            else:
                low_stock = stock_df[stock_df[stock_col] <= threshold]
            
            return low_stock
        
        return pd.DataFrame()
    
    def get_category_summary(self):
        """Get summary by category"""
        stock_df = self.get_stock_listing()
        if stock_df.empty:
            return pd.DataFrame()
        
        # Find category column
        category_col = None
        for col in stock_df.columns:
            if 'category' in col.lower():
                category_col = col
                break
        
        if category_col:
            summary = stock_df.groupby(category_col).size().reset_index(name='Count')
            return summary
        
        return pd.DataFrame()