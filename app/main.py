from datetime import datetime
import streamlit as st
import traceback
import gc
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import sys
import os
from pathlib import Path
import sqlite3
import math
from scipy import stats
from statsmodels.tsa.arima.model import ARIMA
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_percentage_error
from core.analyzer import DryIceAnalyzer
from core.inventory_tracker import InventoryTracker
from core.mobile_interface import MobileInterface
from core.smart_alerts import SmartAlerts
from core.predictive_maintenance import PredictiveMaintenance
from core.system_integrations import SystemIntegrations
from core.report_generator import ReportGenerator
from app.core.google_sheet_reader import GoogleSheetReader
import warnings
from supabase import create_client, Client
USE_SUPABASE = True
DATABASE_FILE = 'dry_ice.db'
BAD_DATE = '2_024-09-26'
GOOD_DATE = '2024-09-26'
@st.cache_resource
def init_supabase():
    """Initialize Supabase client using Streamlit secrets"""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Failed to connect to Supabase: {e}")
        st.info("Please add SUPABASE_URL and SUPABASE_KEY to your Streamlit secrets")
        return None

def fix_order_date():
    """Finds and fixes the incorrect date in both Supabase and SQLite."""
    
    # Fix in Supabase first
    if USE_SUPABASE:
        supabase = init_supabase()
        if supabase:
            try:
                result = supabase.table('historical_orders')\
                    .select('id')\
                    .eq('date', BAD_DATE)\
                    .execute()
                
                if result.data:
                    for row in result.data:
                        supabase.table('historical_orders')\
                            .update({'date': GOOD_DATE})\
                            .eq('id', row['id'])\
                            .execute()
                    print(f"Supabase: Fixed {len(result.data)} row(s) from '{BAD_DATE}' to '{GOOD_DATE}'.")
                else:
                    print(f"Supabase: No bad date found. Already clean.")
            except Exception as e:
                print(f"Supabase fix_order_date error: {e}")

    # Fix in SQLite as well
    if not os.path.exists(DATABASE_FILE):
        return

    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()

    try:
        c.execute("SELECT id FROM historical_orders WHERE date = ?", (BAD_DATE,))
        record = c.fetchone()

        if not record:
            print(f"SQLite: No bad date found. Already clean.")
            conn.close()
            return

        c.execute("UPDATE historical_orders SET date = ? WHERE date = ?", (GOOD_DATE, BAD_DATE))
        conn.commit()
        print(f"SQLite: Fixed {c.rowcount} row(s) from '{BAD_DATE}' to '{GOOD_DATE}'.")

    except sqlite3.Error as e:
        print(f"SQLite fix_order_date error: {e}")
        conn.rollback()
    finally:
        conn.close()


st.set_page_config(
    page_title="Browns Food Co - Dry Ice Inventory Optimizer",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded"
)
# ENHANCED CSS WITH LIQUID GLASS DESIGN
st.markdown("""
    <style>
        /* ===== LIQUID GLASS DESIGN SYSTEM (Inspired by Zoho) ===== */
        
        /* Main glass effect for cards */
        .glass-card {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 16px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.15);
            transition: all 0.3s ease;
        }
        
        .glass-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 40px 0 rgba(31, 38, 135, 0.25);
            background: rgba(255, 255, 255, 0.25);
        }
        
        /* Glass metric cards */
        .glass-metric {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        }
        
        .glass-metric:hover {
            transform: scale(1.02);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
            background: rgba(255, 255, 255, 0.2);
        }
        
        /* Floating Quick Action Button (like Zoho's + menu) */
        .quick-action-fab {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 30px;
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
            cursor: pointer;
            z-index: 999;
            transition: all 0.3s ease;
            border: none;
        }
        
        .quick-action-fab:hover {
            transform: scale(1.1) rotate(90deg);
            box-shadow: 0 6px 30px rgba(102, 126, 234, 0.6);
        }
        
        /* Status cards with glass effect */
        .status-card {
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(6px);
            -webkit-backdrop-filter: blur(6px);
            border-radius: 12px;
            padding: 12px 16px;
            margin: 6px 0;
            border-left: 4px solid;
            transition: all 0.3s ease;
        }
        
        .status-card:hover {
            background: rgba(255, 255, 255, 0.15);
            transform: translateX(4px);
        }
        
        .status-critical {
            border-left-color: #dc3545;
            background: rgba(220, 53, 69, 0.08);
        }
        
        .status-warning {
            border-left-color: #ffc107;
            background: rgba(255, 193, 7, 0.08);
        }
        
        .status-success {
            border-left-color: #28a745;
            background: rgba(40, 167, 69, 0.08);
        }
        
        .status-info {
            border-left-color: #17a2b8;
            background: rgba(23, 162, 184, 0.08);
        }
        
        /* Modern sidebar with glass effect */
        .css-1d391kg {
            background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(10px) !important;
            -webkit-backdrop-filter: blur(10px) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
        }
        
        /* Enhanced metric styling */
        .stMetric {
            background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(4px) !important;
            -webkit-backdrop-filter: blur(4px) !important;
            border-radius: 12px !important;
            padding: 12px 16px !important;
            margin: 8px 0 !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            transition: all 0.3s ease !important;
        }
        
        .stMetric:hover {
            background: rgba(255, 255, 255, 0.1) !important;
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.05);
        }
        
        .stMetric label {
            font-size: 13px !important;
            line-height: 1.4 !important;
            margin-bottom: 6px !important;
            font-weight: 500 !important;
            color: #444 !important;
            white-space: normal !important;
            word-wrap: break-word !important;
        }
        
        .stMetric .stMetricValue {
            font-size: 24px !important;
            line-height: 1.3 !important;
            font-weight: 600 !important;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-top: 2px !important;
        }
        
        .stMetric .stMetricDelta {
            font-size: 13px !important;
            margin-top: 2px !important;
        }
        
        /* Enhanced button styling */
        .stButton button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 8px 20px !important;
            font-weight: 500 !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2) !important;
        }
        
        .stButton button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 25px rgba(102, 126, 234, 0.3) !important;
        }
        
        .stButton button:active {
            transform: scale(0.98) !important;
        }
        
        /* Enhanced tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(4px);
            border-radius: 12px;
            padding: 8px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        
        .stTabs [data-baseweb="tab"] {
            background: transparent !important;
            border-radius: 8px !important;
            padding: 8px 16px !important;
            transition: all 0.3s ease !important;
            color: #666 !important;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            background: rgba(102, 126, 234, 0.08) !important;
            color: #667eea !important;
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3) !important;
        }
        
        /* Enhanced expander */
        .streamlit-expanderHeader {
            background: rgba(255, 255, 255, 0.05) !important;
            border-radius: 8px !important;
            font-weight: 500 !important;
            transition: all 0.3s ease !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
        }
        
        .streamlit-expanderHeader:hover {
            background: rgba(255, 255, 255, 0.1) !important;
            transform: translateX(4px);
        }
        
        /* Enhanced sidebar */
        .css-1d391kg .stSelectbox {
            background: rgba(255, 255, 255, 0.03) !important;
            border-radius: 8px !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
        }
        
        /* Smooth scrolling */
        .main {
            scroll-behavior: smooth;
        }
        
        /* Loading animation */
        @keyframes shimmer {
            0% { background-position: -200% center; }
            100% { background-position: 200% center; }
        }
        
        .shimmer-loading {
            background: linear-gradient(90deg, 
                rgba(255,255,255,0.05) 25%, 
                rgba(255,255,255,0.1) 50%, 
                rgba(255,255,255,0.05) 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 8px;
            padding: 20px;
        }
        
        /* Notification toast */
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 24px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.2);
            z-index: 1000;
            animation: slideInRight 0.5s ease;
        }
        
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        /* Enhanced data table */
        .stDataFrame {
            background: rgba(255, 255, 255, 0.03) !important;
            border-radius: 12px !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            overflow: hidden !important;
        }
        
        .stDataFrame table {
            border-collapse: separate !important;
            border-spacing: 0 !important;
        }
        
        .stDataFrame thead tr th {
            background: rgba(102, 126, 234, 0.08) !important;
            font-weight: 600 !important;
            padding: 10px 12px !important;
            border-bottom: 2px solid rgba(102, 126, 234, 0.2) !important;
        }
        
        .stDataFrame tbody tr:hover {
            background: rgba(102, 126, 234, 0.05) !important;
            transition: background 0.3s ease;
        }
        
        /* ===== YOUR ORIGINAL CSS KEPT BELOW ===== */
        
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
        
        /* Fix tab content spacing */
        .stTabs [role="tabpanel"] {
            padding-top: 30px !important;
            padding-bottom: 20px !important;
        }
        
        /* Fix all column spacing */
        .stColumns {
            gap: 15px !important;
            margin-top: 10px !important;
            margin-bottom: 10px !important;
        }
        
        /* Fix markdown spacing */
        .stMarkdown {
            margin-bottom: 15px !important;
        }
        
        /* Fix heading spacing */
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
            margin-top: 20px !important;
            margin-bottom: 15px !important;
        }
        
        /* Fix plotly chart spacing */
        .stPlotlyChart {
            margin-top: 15px !important;
            margin-bottom: 25px !important;
        }
        
        /* Fix container padding */
        .stContainer {
            padding: 5px 0 !important;
        }
        
        /* Fix horizontal rule spacing */
        hr {
            margin: 30px 0 !important;
        }
        
        /* Fix expander spacing */
        .streamlit-expanderHeader {
            font-weight: 500 !important;
            padding: 10px 0 !important;
        }
        
        /* Fix dataframes - prevent overflow */
        .stDataFrame {
            overflow: auto !important;
            min-height: 100px !important;
            transition: none !important;
            animation: none !important;
        }
        
        .stDataFrame table {
            table-layout: fixed !important;
            width: 100% !important;
        }
        
        .stDataFrame iframe {
            min-height: 200px !important;
            transition: none !important;
            animation: none !important;
        }
        
        [data-testid="stDataFrame"] > div {
            transition: none !important;
            animation: none !important;
        }
        
        /* ===== MOBILE RESPONSIVENESS ===== */
        @media (max-width: 768px) {
            .glass-card {
                padding: 12px !important;
                margin: 6px 0 !important;
            }
            
            .stColumns {
                gap: 5px !important;
                flex-wrap: wrap !important;
            }
            
            .stMetric {
                padding: 8px 3px !important;
                min-height: 60px !important;
            }
            
            .stMetric label {
                font-size: 11px !important;
            }
            
            .stMetric .stMetricValue {
                font-size: 18px !important;
            }
            
            .stTabs [role="tabpanel"] {
                padding-top: 15px !important;
            }
            
            [data-testid="stMetricValue"] {
                font-size: 16px !important;
            }
            
            [data-testid="stDataFrame"] iframe {
                min-height: 150px !important;
            }
            
            .quick-action-fab {
                width: 50px;
                height: 50px;
                font-size: 24px;
                bottom: 20px;
                right: 20px;
            }
            
            .stButton button {
                padding: 6px 12px !important;
                font-size: 13px !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)

class Constants:
    PRICE_PER_KG = 146.55
    CONTAINER_SIZE = 150
    TRANSPORT_COST = 1741.94
    HOLDING_RATE = 0.03
    SUB_LOSS_RANGE = (1.51, 3.03)
    LEAD_TIME_DAYS = 1
    SERVICE_LEVEL = 0.95
    IMPLEMENTATION_COST = 50000

constants = Constants()

# SQLite Database Setup
def init_db():
    """Initialize database (Supabase or SQLite)"""
    if USE_SUPABASE and init_supabase():
        # Supabase tables are created manually in the Supabase dashboard
        # Or you can run a one-time setup script
        st.toast("☁️ Connected to cloud database", icon="✅")
        return
    
    # Fallback to SQLite
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  type TEXT NOT NULL,
                  quantity REAL NOT NULL,
                  item TEXT NOT NULL,
                  description TEXT,
                  notes TEXT,
                  analysis_period TEXT)''')
    
    c.execute("PRAGMA table_info(transactions)")
    if 'analysis_period' not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE transactions ADD COLUMN analysis_period TEXT")

    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  stock_level REAL NOT NULL,
                  transaction_id INTEGER,
                  FOREIGN KEY(transaction_id) REFERENCES transactions(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS historical_orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  order_quantity REAL NOT NULL,
                  analysis_period TEXT)''')
    
    c.execute("PRAGMA table_info(historical_orders)")
    if 'analysis_period' not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE historical_orders ADD COLUMN analysis_period TEXT")

    conn.commit()
    conn.close()

def clear_transactions_from_db():
        """
        Permanently delete all records from the transactions, inventory,
        AND historical_orders tables to perform a full reset.
        """
        conn = sqlite3.connect('dry_ice.db')
        c = conn.cursor()

        try:
            # Use DELETE to empty the tables. This is a permanent action.
            c.execute('DELETE FROM transactions')
            c.execute('DELETE FROM inventory')
            c.execute('DELETE FROM historical_orders') # --- ADD THIS LINE ---

            # Good practice: Reset the auto-increment counter for the primary keys
            c.execute('DELETE FROM sqlite_sequence WHERE name="transactions"')
            c.execute('DELETE FROM sqlite_sequence WHERE name="inventory"')
            c.execute('DELETE FROM sqlite_sequence WHERE name="historical_orders"') # --- AND THIS LINE ---

            conn.commit()
            # The success message is now part of the button logic, so it's okay to remove it here

        except sqlite3.Error as e:
            st.error(f"Database error while clearing transactions: {e}")
        finally:
            conn.close()

def add_transaction_to_db(transaction_type, quantity, description, date, period):
    """Add transaction to Supabase or SQLite database"""
    
    # Try Supabase first if enabled
    if USE_SUPABASE:
        supabase = init_supabase()
        if supabase:
            try:
                # Get current stock from Supabase
                current_stock_response = supabase.table('inventory')\
                    .select('stock_level')\
                    .order('date', desc=True)\
                    .limit(1)\
                    .execute()
                
                current_stock = current_stock_response.data[0]['stock_level'] if current_stock_response.data else 0
                
                # Calculate new stock
                if transaction_type == 'usage':
                    new_stock = current_stock - quantity
                else:  # receipt
                    new_stock = current_stock + quantity
                
                # Insert transaction
                transaction_data = {
                    'date': date.isoformat(),
                    'type': transaction_type,
                    'quantity': quantity,
                    'item': 'Dry Ice',
                    'description': description,
                    'notes': f"{description} - {quantity} kg",
                    'analysis_period': period
                }
                
                transaction_result = supabase.table('transactions').insert(transaction_data).execute()
                transaction_id = transaction_result.data[0]['id']
                
                # Insert inventory record
                inventory_data = {
                    'date': date.isoformat(),
                    'stock_level': new_stock,
                    'transaction_id': transaction_id
                }
                supabase.table('inventory').insert(inventory_data).execute()
                
                # If receipt, add to historical orders
                if transaction_type == 'receipt':
                    order_data = {
                        'date': date.isoformat(),
                        'order_quantity': quantity,
                        'analysis_period': period
                    }
                    supabase.table('historical_orders').insert(order_data).execute()
                
                return transaction_id
                
            except Exception as e:
                st.error(f"Supabase error: {e}. Falling back to SQLite.")
                # Fall through to SQLite
    
    # Fallback to SQLite
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    transaction = {
        'date': date.isoformat(),
        'type': transaction_type,
        'quantity': quantity,
        'item': 'Dry Ice',
        'description': description,
        'notes': f"{description} - {quantity} kg",
        'analysis_period': period
    }

    c.execute('''INSERT INTO transactions
                 (date, type, quantity, item, description, notes, analysis_period)
                 VALUES (:date, :type, :quantity, :item, :description, :notes, :analysis_period)''',
              transaction)

    transaction_id = c.lastrowid

    if transaction_type == 'usage':
        c.execute('''INSERT INTO inventory (date, stock_level, transaction_id)
                     VALUES (?, (SELECT stock_level FROM inventory ORDER BY date DESC LIMIT 1) - ?, ?)''',
                  (date.isoformat(), quantity, transaction_id))
    elif transaction_type == 'receipt':
        c.execute('''INSERT INTO inventory (date, stock_level, transaction_id)
                     VALUES (?, (SELECT stock_level FROM inventory ORDER BY date DESC LIMIT 1) + ?, ?)''',
                  (date.isoformat(), quantity, transaction_id))

        c.execute('''INSERT INTO historical_orders (date, order_quantity, analysis_period)
                     VALUES (?, ?, ?)''',
                  (date.isoformat(), quantity, period))

    conn.commit()
    conn.close()
    return transaction_id

@st.cache_data(ttl=300)
def get_transactions_from_db(period):
    """Retrieve transactions from Supabase or SQLite"""
    
    # Try Supabase first
    if USE_SUPABASE:
        supabase = init_supabase()
        if supabase:
            try:
                response = supabase.table('transactions')\
                    .select('date, type, quantity, item, description, notes')\
                    .eq('analysis_period', period)\
                    .order('date', desc=True)\
                    .execute()
                
                transaction_list = []
                for t in response.data:
                    transaction_list.append({
                        'date': datetime.fromisoformat(t['date']),
                        'type': t['type'],
                        'quantity': t['quantity'],
                        'item': t['item'],
                        'description': t['description'],
                        'notes': t['notes']
                    })
                return transaction_list
            except Exception as e:
                st.error(f"Supabase error: {e}. Falling back to SQLite.")
    
    # Fallback to SQLite
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    c.execute('''SELECT date, type, quantity, item, description, notes
                 FROM transactions WHERE analysis_period = ? ORDER BY date DESC''', (period,))
    transactions = c.fetchall()

    conn.close()

    transaction_list = []
    for t in transactions:
        transaction_list.append({
            'date': datetime.fromisoformat(t[0]),
            'type': t[1], 'quantity': t[2], 'item': t[3],
            'description': t[4], 'notes': t[5]
        })

    return transaction_list

def get_current_stock_from_db():
    """Get current stock from Supabase or SQLite"""
    
    # Try Supabase first
    if USE_SUPABASE:
        supabase = init_supabase()
        if supabase:
            try:
                response = supabase.table('inventory')\
                    .select('stock_level')\
                    .order('date', desc=True)\
                    .limit(1)\
                    .execute()
                
                return response.data[0]['stock_level'] if response.data else 0
            except Exception as e:
                st.error(f"Supabase error: {e}. Falling back to SQLite.")
    
    # Fallback to SQLite
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    c.execute('''SELECT stock_level FROM inventory ORDER BY date DESC LIMIT 1''')
    result = c.fetchone()

    conn.close()

    return result[0] if result else 0
def update_current_stock_in_db(new_stock, date):
    """Update the current stock level in the database (Supabase or SQLite)"""
    
    # Try Supabase first if enabled
    if USE_SUPABASE:
        supabase = init_supabase()
        if supabase:
            try:
                # Handle date formatting
                if hasattr(date, 'isoformat'):
                    date_str = date.isoformat()
                else:
                    date_str = str(date)
                
                # Insert new inventory record
                inventory_data = {
                    'date': date_str,
                    'stock_level': float(new_stock),
                    'transaction_id': None  # Direct update, no associated transaction
                }
                supabase.table('inventory').insert(inventory_data).execute()
                print(f"Stock updated in Supabase: {new_stock} kg on {date_str}")
                return
            except Exception as e:
                print(f"Supabase error updating stock: {e}. Falling back to SQLite.")
                # Fall through to SQLite
    
    # Fallback to SQLite
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()
    
    # Handle date formatting for SQLite
    if hasattr(date, 'isoformat'):
        date_str = date.isoformat()
    else:
        date_str = str(date)

    c.execute('''INSERT INTO inventory (date, stock_level)
                 VALUES (?, ?)''',
              (date_str, float(new_stock)))

    conn.commit()
    conn.close()
    print(f"Stock updated in SQLite: {new_stock} kg on {date_str}")

def seed_historical_data():
    """
    Seed the database with historical order data if empty, and run a one-time
    update to tag any existing untagged records.
    """
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()
    
    # Check if the historical_orders table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_orders'")
    table_exists = c.fetchone()
    
    if not table_exists:
        print("historical_orders table doesn't exist yet. Creating it...")
        # Create the table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS historical_orders
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT NOT NULL,
                      order_quantity REAL NOT NULL,
                      analysis_period TEXT)''')
        conn.commit()
        conn.close()
        return

    # --- Part 1: Seed data only if the table is completely empty ---
    c.execute('''SELECT COUNT(*) FROM historical_orders''')
    count = c.fetchone()[0]

    if count == 0:
        print("Database is empty. Seeding historical data for 2024/2025...")
        # This historical data is based on the list you provided, containing 151 orders.
        base_historical_data = [
            ('2025-06-30', 450.00), ('2025-06-27', 300.00), ('2025-06-26', 150.00),
            ('2025-06-26', 300.00), ('2025-06-23', 450.00), ('2025-06-20', 300.00),
            ('2025-06-18', 300.00), ('2025-06-16', 450.00), ('2025-06-12', 150.00),
            ('2025-06-12', 300.00), ('2025-06-09', 450.00), ('2025-06-05', 300.00),
            ('2025-06-05', 150.00), ('2025-06-03', 450.00), ('2025-05-30', 150.00),
            ('2025-05-26', 450.00), ('2025-05-23', 450.00), ('2025-05-28', 300.00),
            ('2025-05-21', 300.00), ('2025-05-19', 450.00), ('2025-05-07', 300.00),
            ('2025-05-09', 300.00), ('2025-05-14', 300.00), ('2025-05-12', 450.00),
            ('2025-04-28', 300.00), ('2025-05-16', 150.00), ('2025-05-02', 300.00),
            ('2025-05-05', 450.00), ('2025-04-30', 150.00), ('2025-04-30', 300.00),
            ('2025-04-17', 150.00), ('2025-04-14', 450.00), ('2025-04-25', 300.00),
            ('2025-04-24', 450.00), ('2025-04-22', 450.00), ('2025-04-11', 150.00),
            ('2025-04-07', 150.00), ('2025-04-04', 450.00), ('2025-04-09', 300.00),
            ('2025-04-07', 300.00), ('2025-04-02', 300.00), ('2025-04-01', 450.00),
            ('2025-03-28', 150.00), ('2025-03-26', 300.00), ('2025-03-21', 150.00),
            ('2025-03-24', 450.00), ('2025-03-19', 300.00), ('2025-03-17', 450.00),
            ('2025-03-14', 150.00), ('2025-03-12', 300.00), ('2025-03-07', 150.00),
            ('2025-03-07', 150.00), ('2025-03-05', 300.00), ('2025-03-10', 450.00),
            ('2025-03-03', 450.00), ('2025-02-28', 150.00), ('2025-02-26', 300.00),
            ('2025-02-24', 450.00), ('2025-02-21', 150.00), ('2025-02-17', 150.00),
            ('2025-02-17', 300.00), ('2025-02-19', 450.00), ('2025-02-14', 150.00),
            ('2025-02-12', 450.00), ('2025-02-10', 450.00), ('2025-02-05', 450.00),
            ('2025-02-03', 450.00), ('2025-01-27', 450.00), ('2025-01-29', 450.00),
            ('2025-01-22', 450.00), ('2025-01-16', 300.00), ('2025-01-20', 450.00),
            ('2025-01-10', 300.00), ('2025-01-13', 450.00), ('2025-01-08', 300.00),
            ('2025-01-06', 450.00), ('2025-01-02', 300.00), ('2024-12-31', 450.00),
            ('2024-12-31', 150.00), ('2024-12-31', 300.00), ('2024-12-23', 450.00),
            ('2024-12-20', 300.00), ('2024-12-18', 300.00), ('2024-12-16', 450.00),
            ('2024-12-13', 300.00), ('2024-12-01', 450.00), ('2024-12-11', 300.00),
            ('2024-12-09', 450.00), ('2024-12-05', 450.00), ('2024-12-06', 300.00),
            ('2024-12-02', 450.01), ('2024-11-28', 300.00), ('2024-11-25', 450.00),
            ('2024-11-22', 300.00), ('2024-11-18', 450.00), ('2024-11-21', 600.00),
            ('2024-11-14', 450.01), ('2024-11-14', 300.00), ('2024-11-11', 450.01),
            ('2024-11-07', 300.00), ('2024-10-31', 450.00), ('2024-10-28', 450.01),
            ('2024-10-22', 450.00), ('2024-10-24', 300.00), ('2024-10-01', 450.00),
            ('2024-10-01', 60.00), ('2024-10-01', 450.00), ('2024-10-04', 150.00),
            ('2024-10-11', 450.00), ('2024-10-14', 450.00), ('2024-10-17', 450.00),
            ('2024-10-03', 300.00), ('2024-09-23', 450.00), ('2024-09-26', 300.00),
            ('2024-09-13', 150.00), ('2024-09-19', 300.00), ('2024-09-16', 450.00),
            ('2024-09-12', 300.00), ('2024-09-09', 450.01), ('2024-09-05', 300.00),
            ('2024-08-29', 450.00), ('2024-09-02', 450.00), ('2024-08-26', 450.00),
            ('2024-08-22', 300.00), ('2024-08-19', 450.00), ('2024-08-15', 300.00),
            ('2024-08-13', 450.00), ('2024-08-08', 300.00), ('2024-08-05', 450.00),
            ('2024-08-02', 150.00), ('2024-08-01', 300.00), ('2024-07-31', 150.00),
            ('2024-07-30', 300.00), ('2024-07-26', 150.00), ('2024-07-25', 300.00),
            ('2024-07-22', 450.00), ('2024-07-18', 300.00), ('2024-07-15', 450.00),
            ('2024-07-11', 300.00), ('2024-07-08', 450.00), ('2024-07-04', 300.00),
            ('2024-07-01', 450.00)
        ]

        historical_data_with_period = [
            (date, qty, '2024/2025') for date, qty in base_historical_data
        ]

        c.executemany('''INSERT INTO historical_orders (date, order_quantity, analysis_period)
                         VALUES (?, ?, ?)''', historical_data_with_period)

        conn.commit()

    # --- Part 2: Find and fix any old records that don't have a period tag ---
    c.execute("SELECT COUNT(*) FROM historical_orders WHERE analysis_period IS NULL")
    untagged_count = c.fetchone()[0]

    if untagged_count > 0:
        print(f"Found {untagged_count} untagged historical records. Updating them to the '2024/2025' period...")
        # This SQL command updates all rows where the 'analysis_period' column is empty
        c.execute("""
            UPDATE historical_orders
            SET analysis_period = '2024/2025'
            WHERE analysis_period IS NULL
        """)
        conn.commit()
        print("Database update complete.")

    conn.close()

def get_period_from_date(order_date):
    """
    Determines the correct financial period string (e.g., '2025/2026')
    based on a given date, assuming a fiscal year starts in July.

    Args:
        order_date (datetime.date or datetime.datetime): The date of the transaction.

    Returns:
        str: The corresponding analysis period string.
    """
    if order_date.month >= 7:
        # If it's July or later, the financial year starts in the current year.
        start_year = order_date.year
    else:
        # If it's June or earlier, the financial year started in the previous year.
        start_year = order_date.year - 1

    return f"{start_year}/{start_year + 1}"   
def import_csv_to_supabase():
    """Import transaction CSV data to Supabase (one-time migration)"""
    if not USE_SUPABASE:
        st.warning("Supabase is not enabled")
        return False
    
    supabase = init_supabase()
    if not supabase:
        return False
    
    csv_file = 'transactions_export.csv'
    if not os.path.exists(csv_file):
        st.error(f"CSV file '{csv_file}' not found. Run export_to_csv.py first.")
        return False
    
    try:
        df = pd.read_csv(csv_file)
        df['date'] = pd.to_datetime(df['date']).dt.date
        
        inserted = 0
        for _, row in df.iterrows():
            # Check if exists
            existing = supabase.table('transactions')\
                .select('id')\
                .eq('date', row['date'].isoformat())\
                .eq('quantity', float(row['quantity']))\
                .eq('type', row['type'])\
                .execute()
            
            if not existing.data:
                transaction_data = {
                    'date': row['date'].isoformat(),
                    'type': row['type'],
                    'quantity': float(row['quantity']),
                    'item': row['item'],
                    'description': row['description'],
                    'notes': row['notes'],
                    'analysis_period': '2025/2026'
                }
                supabase.table('transactions').insert(transaction_data).execute()
                inserted += 1
        
        st.success(f"✅ Imported {inserted} transactions to Supabase!")
        return True
    except Exception as e:
        st.error(f"Import failed: {e}")
        return False 

@st.cache_data(ttl=300)
def get_historical_orders_from_db(period):
    """Retrieve historical orders from Supabase or SQLite"""
    
    # Try Supabase first
    if USE_SUPABASE:
        supabase = init_supabase()
        if supabase:
            try:
                response = supabase.table('historical_orders')\
                    .select('date, order_quantity, analysis_period')\
                    .eq('analysis_period', period)\
                    .order('date')\
                    .execute()
                
                if response.data:
                    # FIX: Convert list of dicts to DataFrame correctly
                    df = pd.DataFrame(response.data)
                    df = df.rename(columns={
                        'date': 'Date',
                        'order_quantity': 'Order_Quantity_kg'
                    })
                    
                    # Convert date strings to datetime
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                    
                    # Check for invalid dates
                    invalid_rows_mask = df['Date'].isnull()
                    if invalid_rows_mask.any():
                        bad_data_df = df[invalid_rows_mask].copy()
                        st.warning(
                            f"⚠️ Found and ignored {len(bad_data_df)} row(s) with an invalid date format.",
                            icon="❗"
                        )
                        with st.expander("Click here to see the problematic row(s)"):
                            st.dataframe(bad_data_df, use_container_width=True)
                        
                        df = df[~invalid_rows_mask].copy()
                    
                    return df
            except Exception as e:
                st.error(f"Supabase error: {e}. Falling back to SQLite.")
    
    # Fallback to SQLite (your existing code)
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    c.execute('''SELECT date, order_quantity, analysis_period FROM historical_orders
                 WHERE analysis_period = ? ORDER BY date''', (period,))
    orders = c.fetchall()

    conn.close()

    if orders:
        df = pd.DataFrame(orders, columns=['Date', 'Order_Quantity_kg', 'analysis_period'])
        original_dates = df['Date'].copy()
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        invalid_rows_mask = df['Date'].isnull()
        
        if invalid_rows_mask.any():
            bad_data_df = pd.DataFrame({
                'Problematic_Date_String': original_dates[invalid_rows_mask],
                'Order_Quantity_kg': df.loc[invalid_rows_mask, 'Order_Quantity_kg'],
                'Analysis_Period': df.loc[invalid_rows_mask, 'analysis_period']
            })
            
            st.warning(
                f"⚠️ Found and ignored {len(bad_data_df)} row(s) with an invalid date format.",
                icon="❗"
            )
            with st.expander("Click here to see the problematic row(s)"):
                st.dataframe(bad_data_df, use_container_width=True)
            
            df.dropna(subset=['Date'], inplace=True)
        
        return df
    else:
        return pd.DataFrame(columns=['Date', 'Order_Quantity_kg', 'analysis_period'])

def add_transaction_to_history(transaction_type, quantity, description, date, period):
    """Add transaction to session state and to database for a specific period"""
    transaction = {
        'date': datetime.combine(date, datetime.min.time()) if isinstance(date, type(datetime.today().date())) else date,
        'type': transaction_type,
        'quantity': quantity,
        'item': 'Dry Ice',
        'description': description,
        'notes': f"{description} - {quantity} kg"
    }

    # Add to database with the specified period
    add_transaction_to_db(transaction_type, quantity, description, date, period)

    # Update session state
    if 'transactions' not in st.session_state:
        st.session_state.transactions = []

    st.session_state.transactions.append(transaction)

# ============================================================
# 🎨 NEW UI HELPER FUNCTIONS (Glass Design System)
# ============================================================

def apply_glass_metric(label, value, delta=None, help_text=None):
    """
    Apply glass design to metrics - inspired by Zoho's Liquid Glass design
    Usage: apply_glass_metric("Total Orders", "1,234", "+12%", "Monthly total")
    """
    # Handle delta formatting
    delta_html = ""
    if delta:
        delta_color = "#28a745" if "+" in str(delta) or (isinstance(delta, (int, float)) and delta > 0) else "#dc3545"
        delta_html = f'<div style="font-size:13px;color:{delta_color};">{delta}</div>'
    
    # Handle help text
    help_html = f'<div style="font-size:11px;color:#999;margin-top:4px;">{help_text}</div>' if help_text else ""
    
    st.markdown(f"""
    <div class="glass-metric" style="
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        min-height: 80px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    ">
        <div style="font-size:13px;color:#666;font-weight:500;margin-bottom:4px;">{label}</div>
        <div style="font-size:28px;font-weight:600;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin:4px 0;">{value}</div>
        {delta_html}
        {help_html}
    </div>
    """, unsafe_allow_html=True)

def create_glass_container(content, height=None, padding="20px"):
    """
    Create a glass container for content
    Usage: create_glass_container("Your content here", height=200)
    """
    height_style = f"height:{height}px;" if height else ""
    padding_style = f"padding:{padding};" if padding else "padding:20px;"
    
    st.markdown(f"""
    <div class="glass-card" style="
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 16px;
        {padding_style}
        margin: 10px 0;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.08);
        transition: all 0.3s ease;
        {height_style}
        overflow: auto;
    ">
        {content}
    </div>
    """, unsafe_allow_html=True)

def status_badge(status, message):
    """
    Create status badge with glass effect
    Usage: status_badge('success', '✅ Stock levels are optimal')
    """
    status_colors = {
        'success': {'border': '#28a745', 'bg': 'rgba(40, 167, 69, 0.08)'},
        'warning': {'border': '#ffc107', 'bg': 'rgba(255, 193, 7, 0.08)'},
        'critical': {'border': '#dc3545', 'bg': 'rgba(220, 53, 69, 0.08)'},
        'info': {'border': '#17a2b8', 'bg': 'rgba(23, 162, 184, 0.08)'}
    }
    
    color = status_colors.get(status, status_colors['info'])
    
    st.markdown(f"""
    <div class="status-card" style="
        background: {color['bg']};
        backdrop-filter: blur(4px);
        -webkit-backdrop-filter: blur(4px);
        border-radius: 12px;
        padding: 12px 16px;
        margin: 6px 0;
        border-left: 4px solid {color['border']};
        transition: all 0.3s ease;
    ">
        {message}
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# 🎨 VISUAL INVENTORY GRID (inFlow Style)
def visual_inventory_grid(items, columns=3):
    """
    Display inventory items in a visual grid like inFlow's pictorial view
    """
    if not items:
        st.info("No inventory items to display")
        return
    
    # Create columns for the grid
    cols = st.columns(columns)
    
    for idx, (item, details) in enumerate(items.items()):
        with cols[idx % columns]:
            # Determine status colors
            is_low_stock = details.get('stock', 0) < details.get('reorder', 0)
            stock_color = '#dc3545' if is_low_stock else '#28a745'
            bg_color = '#fff5f5' if is_low_stock else '#f8f9fa'
            
            # Calculate stock percentage for progress bar
            stock_pct = min(100, (details.get('stock', 0) / details.get('max', 1)) * 100)
            
            # Category badge color
            category_colors = {
                'Dry Ice': '#4fc3f7',
                'Chemicals': '#ff8a65',
                'Packaging': '#81c784',
                'Equipment': '#ffd54f',
                'Default': '#90a4ae'
            }
            cat_color = category_colors.get(details.get('category', 'Default'), '#90a4ae')
            
            html_content = f"""
            <div style="
                border: 1px solid {'#ffcdd2' if is_low_stock else '#e0e0e0'};
                border-radius: 12px;
                padding: 15px 12px;
                text-align: center;
                background: {bg_color};
                box-shadow: 0 2px 8px rgba(0,0,0,0.06);
                margin-bottom: 12px;
                position: relative;
                min-height: 200px;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            ">
                <!-- Category Badge -->
                <div style="
                    position: absolute;
                    top: 8px;
                    right: 8px;
                    background: {cat_color};
                    color: white;
                    font-size: 9px;
                    padding: 2px 10px;
                    border-radius: 12px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">
                    {details.get('category', 'General')}
                </div>
                
                <!-- Icon -->
                <div style="font-size: 32px; margin-bottom: 4px;">
                    {details.get('icon', '📦')}
                </div>
                
                <!-- Item Name -->
                <div style="
                    font-weight: 600;
                    font-size: 13px;
                    color: #333;
                    margin: 4px 0;
                    line-height: 1.2;
                    min-height: 32px;
                ">
                    {item[:30]}{'...' if len(item) > 30 else ''}
                </div>
                
                <!-- Stock Level -->
                <div style="
                    font-size: 22px;
                    font-weight: 700;
                    color: {stock_color};
                    margin: 2px 0;
                ">
                    {details.get('stock', 0):,.0f} <span style="font-size: 11px; color: #999;">{details.get('unit', 'kg')}</span>
                </div>
                
                <!-- Reorder Level -->
                <div style="
                    font-size: 11px;
                    color: #888;
                    margin-bottom: 6px;
                ">
                    Reorder: {details.get('reorder', 0):,.0f} {details.get('unit', 'kg')}
                </div>
                
                <!-- Progress Bar -->
                <div style="
                    margin: 6px 0 4px 0;
                    height: 5px;
                    background: #e9ecef;
                    border-radius: 3px;
                    overflow: hidden;
                ">
                    <div style="
                        width: {stock_pct:.1f}%;
                        height: 5px;
                        background: {stock_color};
                        border-radius: 3px;
                        transition: width 0.6s ease;
                    "></div>
                </div>
                
                <!-- Status Badge -->
                <div style="
                    display: inline-block;
                    margin-top: 4px;
                    padding: 2px 10px;
                    border-radius: 10px;
                    font-size: 9px;
                    font-weight: 600;
                    background: {'#ffe6e6' if is_low_stock else '#e6f4ea'};
                    color: {'#dc3545' if is_low_stock else '#1e7e34'};
                ">
                    {'⚠️ LOW STOCK' if is_low_stock else '✅ In Stock'}
                </div>
            </div>
            """
            
            # Try multiple rendering methods
            try:
                if hasattr(st, 'html'):
                    st.html(html_content)
                else:
                    st.markdown(html_content, unsafe_allow_html=True)
            except Exception as e:
                # Fallback to st.markdown
                st.markdown(html_content, unsafe_allow_html=True) 

def get_sample_inventory_data():
    """
    Get sample inventory data for testing the visual grid
    """
    return {
        "Dry Ice Block (10kg)": {
            "icon": "🧊",
            "stock": 450,
            "reorder": 200,
            "max": 600,
            "unit": "kg",
            "category": "Dry Ice",
            "location": "Warehouse A",
            "price": 146.55
        },
        "Dry Ice Pellets (5kg)": {
            "icon": "❄️",
            "stock": 320,
            "reorder": 150,
            "max": 500,
            "unit": "kg",
            "category": "Dry Ice",
            "location": "Warehouse A"
        },
        "Dry Ice Slices (2kg)": {
            "icon": "💎",
            "stock": 180,
            "reorder": 100,
            "max": 300,
            "unit": "kg",
            "category": "Dry Ice",
            "location": "Warehouse B"
        },
        "Insulated Containers": {
            "icon": "📦",
            "stock": 45,
            "reorder": 20,
            "max": 60,
            "unit": "units",
            "category": "Packaging",
            "location": "Warehouse B"
        },
        "CO2 Gas Cylinders": {
            "icon": "🛢️",
            "stock": 12,
            "reorder": 5,
            "max": 20,
            "unit": "units",
            "category": "Equipment",
            "location": "Storage Unit #1"
        },
        "Dry Ice Bags (25kg)": {
            "icon": "🎒",
            "stock": 85,
            "reorder": 40,
            "max": 150,
            "unit": "kg",
            "category": "Dry Ice",
            "location": "Warehouse A"
        },
        "Safety Gloves": {
            "icon": "🧤",
            "stock": 28,
            "reorder": 15,
            "max": 50,
            "unit": "pairs",
            "category": "Safety",
            "location": "Storage Unit #2"
        }
    }            
              
def inventory_stats_summary(items):
    """
    Display quick summary statistics for inventory
    """
    total_items = len(items)
    total_stock = sum(details.get('stock', 0) for details in items.values())
    low_stock_items = sum(1 for details in items.values() if details.get('stock', 0) < details.get('reorder', 0))
    categories = set(details.get('category', 'Uncategorized') for details in items.values())
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        html = f"""
        <div style="
            background: rgba(255,255,255,0.06);
            backdrop-filter: blur(8px);
            border-radius: 12px;
            padding: 12px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <div style="font-size: 24px;">📦</div>
            <div style="font-size: 20px; font-weight: 700;">{total_items}</div>
            <div style="font-size: 12px; color: #888;">Total Items</div>
        </div>
        """
        try:
            if hasattr(st, 'html'):
                st.html(html)
            else:
                st.markdown(html, unsafe_allow_html=True)
        except:
            st.markdown(html, unsafe_allow_html=True)
    
    with col2:
        html = f"""
        <div style="
            background: rgba(255,255,255,0.06);
            backdrop-filter: blur(8px);
            border-radius: 12px;
            padding: 12px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <div style="font-size: 24px;">📊</div>
            <div style="font-size: 20px; font-weight: 700;">{total_stock:,.0f}</div>
            <div style="font-size: 12px; color: #888;">Total Stock (kg)</div>
        </div>
        """
        try:
            if hasattr(st, 'html'):
                st.html(html)
            else:
                st.markdown(html, unsafe_allow_html=True)
        except:
            st.markdown(html, unsafe_allow_html=True)
    
    with col3:
        color = '#dc3545' if low_stock_items > 0 else '#28a745'
        html = f"""
        <div style="
            background: rgba(255,255,255,0.06);
            backdrop-filter: blur(8px);
            border-radius: 12px;
            padding: 12px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <div style="font-size: 24px;">⚠️</div>
            <div style="font-size: 20px; font-weight: 700; color: {color};">{low_stock_items}</div>
            <div style="font-size: 12px; color: #888;">Low Stock Items</div>
        </div>
        """
        try:
            if hasattr(st, 'html'):
                st.html(html)
            else:
                st.markdown(html, unsafe_allow_html=True)
        except:
            st.markdown(html, unsafe_allow_html=True)
    
    with col4:
        html = f"""
        <div style="
            background: rgba(255,255,255,0.06);
            backdrop-filter: blur(8px);
            border-radius: 12px;
            padding: 12px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <div style="font-size: 24px;">📂</div>
            <div style="font-size: 20px; font-weight: 700;">{len(categories)}</div>
            <div style="font-size: 12px; color: #888;">Categories</div>
        </div>
        """
        try:
            if hasattr(st, 'html'):
                st.html(html)
            else:
                st.markdown(html, unsafe_allow_html=True)
        except:
            st.markdown(html, unsafe_allow_html=True)

def inventory_filters(items):
    """
    Add filter controls for the inventory grid
    """
    # Get unique categories
    categories = ['All'] + sorted(set(
        details.get('category', 'Uncategorized') 
        for details in items.values()
    ))
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        search = st.text_input(
            "🔍 Search Items",
            placeholder="Type item name...",
            key="inventory_search"
        )
    
    with col2:
        category_filter = st.selectbox(
            "📂 Category",
            categories,
            key="inventory_category_filter"
        )
    
    with col3:
        show_low_stock = st.checkbox(
            "⚠️ Low Stock Only",
            key="inventory_low_stock_filter"
        )
    
    return search, category_filter, show_low_stock

# ============================================================
# 🎨 INVENTORY HEAT MAP
# ============================================================

def inventory_heatmap(inventory_items, title="Inventory Heat Map", columns=6):
    """
    Display an inventory heat map showing stock levels with color coding
    
    Args:
        inventory_items: Dictionary with item names as keys and details as values
        title: Title for the heat map
        columns: Number of columns in the grid (default: 6)
    """
    if not inventory_items:
        st.info("No inventory items to display in heat map")
        return
    
    # Convert inventory_items dict to heatmap data
    heatmap_data = []
    for item_name, details in inventory_items.items():
        stock = details.get('stock', 0)
        reorder = details.get('reorder', 0)
        eoq = details.get('eoq', details.get('max', stock * 2))
        
        # Determine status
        if stock <= 0:
            status = 'Critical'
            color = '#dc3545'  # Red
        elif stock < reorder:
            status = 'Low'
            color = '#ff9800'  # Orange
        elif stock >= reorder and stock < eoq:
            status = 'Good'
            color = '#4caf50'  # Green
        else:
            status = 'Overstocked'
            color = '#2196f3'  # Blue
        
        heatmap_data.append({
            'Item': item_name[:20] + ('...' if len(item_name) > 20 else ''),
            'Item_Full': item_name,
            'Stock': stock,
            'Reorder': reorder,
            'EOQ': eoq,
            'Status': status,
            'Color': color,
            'Unit': details.get('unit', 'kg'),
            'Category': details.get('category', 'Uncategorized'),
            'Stock_Percentage': min(100, (stock / eoq) * 100) if eoq > 0 else 0
        })
    
    # Sort items: Critical first, then Low, then Good, then Overstocked
    status_order = {'Critical': 0, 'Low': 1, 'Good': 2, 'Overstocked': 3}
    heatmap_data.sort(key=lambda x: status_order.get(x['Status'], 4))
    
    # Display title
    st.markdown(f"""
    <div style="
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 15px 20px;
        margin-bottom: 15px;
        border: 1px solid rgba(255,255,255,0.08);
    ">
        <div style="
            font-size: 1.2rem;
            font-weight: 600;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        ">
            🔥 {title}
        </div>
        <div style="color: #888; font-size: 13px; margin-top: 4px;">
            Color legend: 🔴 Critical | 🟠 Low Stock | 🟢 Good | 🔵 Overstocked
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Create columns for the grid
    cols = st.columns(columns)
    
    for idx, item in enumerate(heatmap_data):
        with cols[idx % columns]:
            # Get status icon
            status_icons = {
                'Critical': '🔴',
                'Low': '🟠',
                'Good': '🟢',
                'Overstocked': '🔵'
            }
            status_icon = status_icons.get(item['Status'], '⚪')
            
            stock_pct = item['Stock_Percentage']
            
            # Create the heat map card
            html = f"""
            <div style="
                background: {item['Color']};
                color: white;
                padding: 12px 8px;
                border-radius: 10px;
                text-align: center;
                margin: 4px 0;
                min-height: 80px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            "
            onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 4px 15px rgba(0,0,0,0.2)';"
            onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)';"
            title="{item['Item_Full']} - Stock: {item['Stock']} {item['Unit']} | Reorder: {item['Reorder']} {item['Unit']}"
            >
                <!-- Status Indicator -->
                <div style="
                    position: absolute;
                    top: 4px;
                    left: 8px;
                    font-size: 12px;
                ">
                    {status_icon}
                </div>
                
                <!-- Item Name -->
                <div style="
                    font-size: 11px;
                    font-weight: 500;
                    opacity: 0.9;
                    margin-bottom: 4px;
                    line-height: 1.2;
                    min-height: 24px;
                ">
                    {item['Item']}
                </div>
                
                <!-- Stock Level -->
                <div style="
                    font-size: 20px;
                    font-weight: 700;
                    line-height: 1.2;
                ">
                    {item['Stock']:,.0f}
                </div>
                
                <!-- Unit -->
                <div style="
                    font-size: 9px;
                    opacity: 0.7;
                    margin-top: 1px;
                ">
                    {item['Unit']}
                </div>
                
                <!-- Progress Bar (Stock Level Indicator) -->
                <div style="
                    margin-top: 4px;
                    height: 3px;
                    background: rgba(255,255,255,0.3);
                    border-radius: 2px;
                    overflow: hidden;
                ">
                    <div style="
                        width: {stock_pct:.1f}%;
                        height: 3px;
                        background: rgba(255,255,255,0.8);
                        border-radius: 2px;
                        transition: width 0.6s ease;
                    "></div>
                </div>
            </div>
            """
            
            # Render with fallback
            try:
                if hasattr(st, 'html'):
                    st.html(html)
                else:
                    st.markdown(html, unsafe_allow_html=True)
            except:
                st.markdown(html, unsafe_allow_html=True)
    
    # Display summary statistics
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_items = len(heatmap_data)
    critical_items = sum(1 for item in heatmap_data if item['Status'] == 'Critical')
    low_items = sum(1 for item in heatmap_data if item['Status'] == 'Low')
    good_items = sum(1 for item in heatmap_data if item['Status'] == 'Good')
    overstocked_items = sum(1 for item in heatmap_data if item['Status'] == 'Overstocked')
    
    with col1:
        st.metric("📦 Total Items", total_items)
    with col2:
        st.metric("🔴 Critical", critical_items, delta=f"-{critical_items}" if critical_items > 0 else None)
    with col3:
        st.metric("🟠 Low Stock", low_items, delta=f"-{low_items}" if low_items > 0 else None)
    with col4:
        st.metric("🟢 Good", good_items)
    with col5:
        st.metric("🔵 Overstocked", overstocked_items)

def inventory_heatmap_filters(heatmap_data):
    """
    Add filter controls for the inventory heat map
    """
    # Get unique statuses and categories
    statuses = ['All'] + sorted(set(item['Status'] for item in heatmap_data))
    categories = ['All'] + sorted(set(item['Category'] for item in heatmap_data))
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        search = st.text_input(
            "🔍 Search Items",
            placeholder="Type item name...",
            key="heatmap_search"
        )
    
    with col2:
        status_filter = st.selectbox(
            "📊 Status",
            statuses,
            key="heatmap_status_filter"
        )
    
    with col3:
        category_filter = st.selectbox(
            "📂 Category",
            categories,
            key="heatmap_category_filter"
        )
    
    return search, status_filter, category_filter 

# ============================================================
# 🎨 SMART REPLENISHMENT RECOMMENDATIONS (Katana Style)
# ============================================================
@st.cache_data(ttl=300)
def get_replenishment_recommendations(inventory_items, daily_usage_rate=None):
    """
    Generate replenishment recommendations based on current stock levels
    
    Args:
        inventory_items: Dictionary with item names as keys and details as values
        daily_usage_rate: Optional daily usage rate (if not provided, will be estimated)
    
    Returns:
        DataFrame with replenishment recommendations
    """
    if not inventory_items:
        return pd.DataFrame()
    
    recommendations = []
    
    for item_name, details in inventory_items.items():
        current_stock = details.get('stock', 0)
        reorder_point = details.get('reorder', 0)
        eoq = details.get('eoq', details.get('max', current_stock * 2))
        max_stock = details.get('max', current_stock * 2)
        
        # Estimate daily usage if not provided
        if daily_usage_rate:
            daily_usage = daily_usage_rate
        else:
            # Estimate based on reorder point and assumed lead time
            # If reorder point is 0, use 10% of current stock as daily usage
            if reorder_point > 0:
                daily_usage = reorder_point / 7  # Assume 7 days lead time
            else:
                daily_usage = max(1, current_stock * 0.05)  # 5% of current stock per day
        
        # Check if reorder is needed
        needs_reorder = current_stock < reorder_point
        
        if needs_reorder:
            # Calculate days until stockout (estimated)
            stock_deficit = reorder_point - current_stock
            days_to_reorder = max(1, int(stock_deficit / daily_usage)) if daily_usage > 0 else 1
            
            # Calculate suggested quantity (EOQ or minimum)
            suggested_qty = max(eoq, reorder_point * 1.2)  # Order enough to cover reorder point + buffer
            
            # Determine urgency
            if days_to_reorder <= 3:
                urgency = 'High'
                urgency_color = '#dc3545'  # Red
                action = '⚠️ Order Immediately'
            elif days_to_reorder <= 7:
                urgency = 'Medium'
                urgency_color = '#ffc107'  # Yellow
                action = '📋 Schedule Order'
            else:
                urgency = 'Low'
                urgency_color = '#28a745'  # Green
                action = '📝 Plan Order'
            
            # Determine priority score (higher = more urgent)
            priority_score = 100 - (days_to_reorder * 10)  # Lower days = higher priority
            priority_score = max(0, min(100, priority_score))
            
            recommendations.append({
                'Item': item_name,
                'Current Stock': f"{current_stock:,.0f} {details.get('unit', 'kg')}",
                'Reorder Point': f"{reorder_point:,.0f} {details.get('unit', 'kg')}",
                'Suggested Order': f"{suggested_qty:,.0f} {details.get('unit', 'kg')}",
                'Days Until Stockout': days_to_reorder,
                'Urgency': urgency,
                'Action': action,
                'Priority Score': priority_score,
                'Category': details.get('category', 'Uncategorized')
            })
    
    # Sort by priority (most urgent first)
    recommendations.sort(key=lambda x: x['Priority Score'], reverse=True)
    
    return pd.DataFrame(recommendations)

def show_replenishment_suggestions(recommendations_df, title="🛒 Replenishment Suggestions"):
    """
    Display replenishment recommendations in a styled table
    
    Args:
        recommendations_df: DataFrame from get_replenishment_recommendations()
        title: Title for the section
    """
    if recommendations_df.empty:
        st.info("✅ All items are well-stocked. No replenishment needed at this time.")
        return
    
    # Display header with count
    urgent_count = len(recommendations_df[recommendations_df['Urgency'] == 'High'])
    medium_count = len(recommendations_df[recommendations_df['Urgency'] == 'Medium'])
    
    st.markdown(f"""
    <div style="
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 15px 20px;
        margin-bottom: 15px;
        border: 1px solid rgba(255,255,255,0.08);
    ">
        <div style="
            font-size: 1.2rem;
            font-weight: 600;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        ">
            {title}
        </div>
        <div style="color: #888; font-size: 13px; margin-top: 4px;">
            {len(recommendations_df)} items need attention · 
            <span style="color: #dc3545;">🔴 {urgent_count} Urgent</span> · 
            <span style="color: #ffc107;">🟡 {medium_count} Medium</span> · 
            <span style="color: #28a745;">🟢 {len(recommendations_df) - urgent_count - medium_count} Low</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Display as styled dataframe with urgency highlighting
    display_df = recommendations_df.copy()
    
    # Color coding function for urgency
    def color_urgency(val):
        if val == 'High':
            return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
        elif val == 'Medium':
            return 'background-color: #fff3cd; color: #856404; font-weight: bold;'
        else:
            return 'background-color: #d4edda; color: #155724;'
    
    # Color coding for action
    def color_action(val):
        if 'Immediately' in val:
            return 'background-color: #f8d7da;'
        elif 'Schedule' in val:
            return 'background-color: #fff3cd;'
        else:
            return 'background-color: #d4edda;'
    
    # Apply styling
    styled_df = display_df.style.applymap(
        color_urgency, subset=['Urgency']
    ).applymap(
        color_action, subset=['Action']
    )
    
    # Hide index and display
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=400,
        hide_index=True,
        column_config={
            'Item': st.column_config.TextColumn('Item', width='medium'),
            'Current Stock': st.column_config.TextColumn('Current Stock', width='small'),
            'Reorder Point': st.column_config.TextColumn('Reorder Point', width='small'),
            'Suggested Order': st.column_config.TextColumn('Suggested Order', width='medium'),
            'Days Until Stockout': st.column_config.NumberColumn('Days Until Stockout', width='small'),
            'Urgency': st.column_config.TextColumn('Urgency', width='small'),
            'Action': st.column_config.TextColumn('Action', width='medium'),
            'Priority Score': st.column_config.NumberColumn('Priority', width='small'),
            'Category': st.column_config.TextColumn('Category', width='small')
        }
    )
    
    # Quick action buttons for urgent items
    if urgent_count > 0:
        st.markdown("---")
        st.markdown("#### ⚡ Quick Actions for Urgent Items")
        
        urgent_items = recommendations_df[recommendations_df['Urgency'] == 'High']
        
        cols = st.columns(min(3, len(urgent_items)))
        for idx, (_, item) in enumerate(urgent_items.head(3).iterrows()):
            with cols[idx % 3]:
                st.markdown(f"""
                <div style="
                    border: 1px solid #dc3545;
                    border-radius: 8px;
                    padding: 12px;
                    margin: 4px 0;
                    background: rgba(220, 53, 69, 0.05);
                ">
                    <div style="font-weight: 600; font-size: 13px; color: #721c24;">
                        {item['Item']}
                    </div>
                    <div style="font-size: 12px; color: #666;">
                        Suggested: {item['Suggested Order']}
                    </div>
                    <div style="font-size: 12px; color: #666;">
                        Days until stockout: {item['Days Until Stockout']}
                    </div>
                    <div style="margin-top: 6px;">
                        <span style="
                            background: #dc3545;
                            color: white;
                            padding: 2px 10px;
                            border-radius: 12px;
                            font-size: 10px;
                            font-weight: 600;
                        ">
                            {item['Action']}
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

def get_replenishment_summary(recommendations_df):
    """
    Get summary statistics for replenishment recommendations
    
    Args:
        recommendations_df: DataFrame from get_replenishment_recommendations()
    
    Returns:
        Dictionary with summary statistics
    """
    if recommendations_df.empty:
        return {
            'total_items': 0,
            'urgent_count': 0,
            'medium_count': 0,
            'low_count': 0,
            'average_days': 0,
            'total_suggested_qty': 0
        }
    
    return {
        'total_items': len(recommendations_df),
        'urgent_count': len(recommendations_df[recommendations_df['Urgency'] == 'High']),
        'medium_count': len(recommendations_df[recommendations_df['Urgency'] == 'Medium']),
        'low_count': len(recommendations_df[recommendations_df['Urgency'] == 'Low']),
        'average_days': recommendations_df['Days Until Stockout'].mean(),
        'total_suggested_qty': sum(float(str(qty).replace(' kg', '').replace(' units', '').replace(' pairs', '').replace(' ltrs', '').replace(',', '')) for qty in recommendations_df['Suggested Order'].values)
    }
def show_replenishment_summary_cards(summary):
    """
    Display replenishment summary as metric cards
    """
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "📋 Items Needing Action",
            summary['total_items']
        )
    with col2:
        st.metric(
            "🔴 Urgent",
            summary['urgent_count'],
            delta=f"-{summary['urgent_count']}" if summary['urgent_count'] > 0 else None
        )
    with col3:
        st.metric(
            "🟡 Medium",
            summary['medium_count']
        )
    with col4:
        st.metric(
            "🟢 Low",
            summary['low_count']
        )
    with col5:
        st.metric(
            "📦 Suggested Order Volume",
            f"{summary['total_suggested_qty']:,.0f} kg"
        )

# ===========================================================
# 🎨 QUICK CREATE MENU (Zoho Style)
def quick_create_menu(inventory_tracker):
    """
    Zoho-style Quick Create Menu with floating action button
    """
    # Check if we need to show modals
    if 'show_quick_receipt' not in st.session_state:
        st.session_state.show_quick_receipt = False
    if 'show_quick_usage' not in st.session_state:
        st.session_state.show_quick_usage = False
    
    # CSS for the FAB and modal
    st.markdown("""
    <style>
    /* Floating Action Button */
    .fab-container {
        position: fixed;
        bottom: 30px;
        right: 30px;
        z-index: 1000;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 10px;
    }
    
    .fab-main {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        font-size: 28px;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
        cursor: pointer;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
    }
    
    .fab-main:hover {
        transform: scale(1.1) rotate(90deg);
        box-shadow: 0 6px 30px rgba(102, 126, 234, 0.6);
    }
    
    .fab-main.active {
        transform: rotate(45deg);
    }
    
    /* Quick Action Menu Items */
    .fab-menu {
        display: none;
        flex-direction: column;
        align-items: flex-end;
        gap: 10px;
        margin-bottom: 10px;
    }
    
    .fab-menu.show {
        display: flex;
    }
    
    .fab-item {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 12px;
        padding: 10px 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
        cursor: pointer;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 14px;
        color: #333;
        min-width: 150px;
    }
    
    .fab-item:hover {
        transform: translateX(-5px);
        box-shadow: 0 6px 30px rgba(0, 0, 0, 0.15);
        background: white;
    }
    
    .fab-item .icon {
        font-size: 20px;
    }
    
    .fab-item .shortcut {
        font-size: 11px;
        color: #999;
        margin-left: auto;
    }
    
    /* Quick Modal Overlay */
    .quick-modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.4);
        backdrop-filter: blur(4px);
        z-index: 2000;
        display: none;
        align-items: center;
        justify-content: center;
    }
    
    .quick-modal-overlay.show {
        display: flex;
    }
    
    .quick-modal {
        background: white;
        border-radius: 20px;
        padding: 30px;
        max-width: 450px;
        width: 90%;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        animation: modalSlideUp 0.3s ease;
    }
    
    @keyframes modalSlideUp {
        from {
            opacity: 0;
            transform: translateY(20px) scale(0.95);
        }
        to {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
    }
    
    .quick-modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    
    .quick-modal-header h3 {
        margin: 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .quick-modal-close {
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: #999;
        transition: all 0.3s ease;
    }
    
    .quick-modal-close:hover {
        color: #333;
        transform: rotate(90deg);
    }
    
    .quick-modal .stButton button {
        width: 100%;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .fab-main {
            width: 50px;
            height: 50px;
            font-size: 24px;
        }
        .fab-item {
            font-size: 13px;
            padding: 8px 16px;
            min-width: 130px;
        }
        .quick-modal {
            padding: 20px;
            max-width: 95%;
        }
    }
    </style>
    
    <!-- FAB Container -->
    <div class="fab-container" id="fabContainer">
        <div class="fab-menu" id="fabMenu">
            <div class="fab-item" onclick="document.getElementById('quickReceiptBtn').click();">
                <span class="icon">📥</span>
                Quick Receipt
                <span class="shortcut">⌘R</span>
            </div>
            <div class="fab-item" onclick="document.getElementById('quickUsageBtn').click();">
                <span class="icon">📤</span>
                Quick Usage
                <span class="shortcut">⌘U</span>
            </div>
            <div class="fab-item" onclick="document.getElementById('quickReportBtn').click();">
                <span class="icon">📊</span>
                Generate Report
                <span class="shortcut">⌘P</span>
            </div>
        </div>
        <button class="fab-main" id="fabToggle" onclick="toggleFabMenu()">
            <span id="fabIcon">+</span>
        </button>
    </div>
    
    <script>
        function toggleFabMenu() {
            const menu = document.getElementById('fabMenu');
            const icon = document.getElementById('fabIcon');
            const btn = document.getElementById('fabToggle');
            
            menu.classList.toggle('show');
            btn.classList.toggle('active');
            
            if (menu.classList.contains('show')) {
                icon.textContent = '✕';
            } else {
                icon.textContent = '+';
            }
        }
        
        // Close menu when clicking outside
        document.addEventListener('click', function(event) {
            const container = document.getElementById('fabContainer');
            if (!container.contains(event.target)) {
                const menu = document.getElementById('fabMenu');
                const icon = document.getElementById('fabIcon');
                const btn = document.getElementById('fabToggle');
                menu.classList.remove('show');
                btn.classList.remove('active');
                icon.textContent = '+';
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(event) {
            // Cmd/Ctrl + R for Receipt
            if ((event.metaKey || event.ctrlKey) && event.key === 'r') {
                event.preventDefault();
                document.getElementById('quickReceiptBtn').click();
            }
            // Cmd/Ctrl + U for Usage
            if ((event.metaKey || event.ctrlKey) && event.key === 'u') {
                event.preventDefault();
                document.getElementById('quickUsageBtn').click();
            }
        });
    </script>
    """, unsafe_allow_html=True)
    
    # Hidden buttons to trigger modals from JavaScript
    if st.button("📥 Quick Receipt", key="quickReceiptBtn", type="primary"):
        st.session_state.show_quick_receipt = True
        st.session_state.show_quick_usage = False
        st.rerun()
    
    if st.button("📤 Quick Usage", key="quickUsageBtn", type="primary"):
        st.session_state.show_quick_usage = True
        st.session_state.show_quick_receipt = False
        st.rerun()
    
    if st.button("📊 Generate Report", key="quickReportBtn", type="primary"):
        # Trigger report generation
        st.session_state.generate_report = True
        st.rerun()
    
    # Show Quick Receipt Modal
    if st.session_state.get('show_quick_receipt', False):
        show_quick_receipt_modal(inventory_tracker)
    
    # Show Quick Usage Modal
    if st.session_state.get('show_quick_usage', False):
        show_quick_usage_modal(inventory_tracker) 

def show_quick_receipt_modal(inventory_tracker):
    """
    Display Quick Receipt Modal (inline in sidebar)
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px;
        border-radius: 12px;
        color: white;
        margin-bottom: 15px;
    ">
        <div style="font-size: 18px; font-weight: 600;">📥 Quick Receipt</div>
        <div style="font-size: 13px; opacity: 0.8;">Record a new stock receipt</div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar.container():
        col1, col2 = st.columns(2)
        with col1:
            qty = st.number_input(
                "Quantity (kg)",
                min_value=0.0,
                value=300.0,
                step=50.0,
                key="quick_receipt_qty"
            )
        with col2:
            receipt_date = st.date_input(
                "Date",
                value=datetime.today(),
                key="quick_receipt_date"
            )
        
        notes = st.text_input(
            "Notes (optional)",
            placeholder="e.g., Supplier: XYZ, Order #123",
            key="quick_receipt_notes"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Save Receipt", type="primary", use_container_width=True):
                # Process the receipt
                correct_period = get_period_from_date(receipt_date)
                
                # Update inventory
                inventory_tracker.current_stock += qty
                update_current_stock_in_db(inventory_tracker.current_stock, receipt_date)
                
                # Add to transaction history
                add_transaction_to_history(
                    transaction_type="receipt",
                    quantity=qty,
                    description=f"Quick Receipt: {notes if notes else 'No notes'}",
                    date=receipt_date,
                    period=correct_period
                )
                
                # Show success and close modal
                st.session_state.quick_receipt_success = True
                st.session_state.show_quick_receipt = False
                st.rerun()
        
        with col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.show_quick_receipt = False
                st.rerun()
        
        # Show success message
        if st.session_state.get('quick_receipt_success', False):
            st.success(f"✅ Receipt of {qty:.0f} kg recorded successfully!")
            st.session_state.quick_receipt_success = False

def show_quick_usage_modal(inventory_tracker):
    """
    Display Quick Usage Modal (inline in sidebar)
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style="
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 15px;
        border-radius: 12px;
        color: white;
        margin-bottom: 15px;
    ">
        <div style="font-size: 18px; font-weight: 600;">📤 Quick Usage</div>
        <div style="font-size: 13px; opacity: 0.8;">Record stock usage/consumption</div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar.container():
        col1, col2 = st.columns(2)
        with col1:
            qty = st.number_input(
                "Quantity Used (kg)",
                min_value=0.0,
                value=150.0,
                step=25.0,
                key="quick_usage_qty"
            )
        with col2:
            usage_date = st.date_input(
                "Date",
                value=datetime.today(),
                key="quick_usage_date"
            )
        
        # Check if stock is sufficient
        current_stock = inventory_tracker.current_stock
        if qty > current_stock:
            st.warning(f"⚠️ Insufficient stock! Current stock: {current_stock:.0f} kg")
        
        notes = st.text_input(
            "Notes (optional)",
            placeholder="e.g., Production, Packaging, etc.",
            key="quick_usage_notes"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Save Usage", type="primary", use_container_width=True):
                if qty <= current_stock:
                    # Process the usage
                    alert = inventory_tracker.update_stock(qty, f"Quick Usage: {notes if notes else 'No notes'}", usage_date)
                    add_transaction_to_history(
                        transaction_type="usage",
                        quantity=qty,
                        description=f"Quick Usage: {notes if notes else 'No notes'}",
                        date=usage_date,
                        period=st.session_state.selected_period
                    )
                    
                    if alert is not None:
                        st.error(alert["message"])
                    else:
                        st.session_state.quick_usage_success = True
                        st.session_state.show_quick_usage = False
                        st.rerun()
                else:
                    st.error(f"❌ Insufficient stock! Available: {current_stock:.0f} kg")
        
        with col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.show_quick_usage = False
                st.rerun()
        
        # Show success message
        if st.session_state.get('quick_usage_success', False):
            st.success(f"✅ Usage of {qty:.0f} kg recorded successfully!")
            st.session_state.quick_usage_success = False

# END OF QUICK CREATE MENU

def responsive_metric_grid(metrics, columns=4):
    """
    Display metrics in a responsive grid with glass design
    Usage: 
    metrics = [
        ('Total Orders', '1,234', '+12%'),
        ('Revenue', 'KSh 45,678', '+8%'),
    ]
    responsive_metric_grid(metrics, columns=4)
    """
    cols = st.columns(columns)
    for idx, (label, value, delta) in enumerate(metrics):
        with cols[idx % columns]:
            apply_glass_metric(label, value, delta)

def glass_table(dataframe, title=None, height=300):
    """
    Display a dataframe with glass design styling
    Usage: glass_table(df, title="Transaction History", height=400)
    """
    if title:
        st.markdown(f"""
        <div style="font-size:18px;font-weight:600;margin:20px 0 10px 0;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
            {title}
        </div>
        """, unsafe_allow_html=True)
    
    st.dataframe(
        dataframe,
        use_container_width=True,
        height=height,
        hide_index=True
    )

    # ============================================================
    # END OF UI HELPER FUNCTIONS
    # ============================================================
@st.cache_data(ttl=1800, show_spinner=False)
def create_ensemble_forecast(df, forecast_days=30):
    """
    Create ensemble forecast combining Prophet, LSTM, ARIMA and Monte Carlo.
    This version includes robust error handling and non-negative constraints.
    """
    # Import required libraries with error handling
    try:
        from sklearn.preprocessing import MinMaxScaler
        sklearn_available = True
    except ImportError:
        print("Warning: scikit-learn not available, LSTM forecast will be skipped")
        sklearn_available = False
    
    try:
        import torch
        import torch.nn as nn
        pytorch_available = True
    except ImportError:
        print("Warning: PyTorch not available, LSTM forecast will be skipped")
        pytorch_available = False

    try:
        from statsmodels.tsa.arima.model import ARIMA
        statsmodels_available = True
    except ImportError:
        print("Warning: statsmodels not available, ARIMA forecast will be skipped")
        statsmodels_available = False
        
    try:
        from prophet import Prophet
        prophet_available = True
    except ImportError:
        print("Warning: Prophet not available, it will be skipped")
        prophet_available = False

    # 1. Prepare data with validation
    dates = pd.to_datetime(df['Date'])
    values = df['Order_Quantity_kg'].values.astype(float)
    mape = 0.0

    # CRITICAL FIX: Data validation and fallback
    if len(values) == 0:
        st.warning("No historical data available for forecasting. Using default conservative estimates.")
        conservative_forecast = np.full(forecast_days, 300.0)  # Default 300kg/day
        return None, conservative_forecast, {'Conservative': 300.0}, 0.0
    
    if len(values) < 5:
        st.warning(f"⚠️ Limited historical data ({len(values)} points). Forecast reliability may be reduced.")
        # Use simple average for limited data
        avg_demand = np.mean(values) if len(values) > 0 else 300.0
        conservative_forecast = np.full(forecast_days, max(0, avg_demand))
        
        # Create a simple visualization
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=values, name='Actual Demand', 
                                line=dict(color='blue', width=2)))
        future_dates = pd.date_range(dates.max(), periods=forecast_days + 1)[1:]
        fig.add_trace(go.Scatter(x=future_dates, y=conservative_forecast, 
                                name='Conservative Forecast', 
                                line=dict(color='orange', width=3)))
        fig.update_layout(title='Conservative Forecast (Limited Historical Data)', 
                         xaxis_title='Date', yaxis_title='Demand (kg)')
        
        return fig, conservative_forecast, {'Conservative': avg_demand}, 0.0

    # Define the smart Prophet model configuration
    def get_prophet_model():
        model = Prophet(
            seasonality_mode='multiplicative',
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.8  # Adjust confidence intervals
        )
        model.add_country_holidays(country_name='KE')
        return model

    # --- A. Backtesting Section (to calculate MAPE) ---
    test_size = min(30, len(values) // 3)  # Use 1/3 of data for testing, max 30 points
    
    if prophet_available and len(values) > test_size * 2:
        try:
            # Split data into training and testing sets for backtesting
            train_df = df.iloc[:-test_size]
            test_df = df.iloc[-test_size:]

            # Rename for Prophet
            prophet_train_df = train_df.rename(columns={'Date': 'ds', 'Order_Quantity_kg': 'y'})

            # Train the smart model on the training data
            backtest_model = get_prophet_model()
            
            # Suppress Prophet warnings during fitting
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                backtest_model.fit(prophet_train_df)

            # Create a future dataframe for the test period
            future_backtest = backtest_model.make_future_dataframe(periods=test_size)
            
            # Generate the forecast for the test period
            backtest_forecast_df = backtest_model.predict(future_backtest)
            
            # Extract the forecasted values that correspond to the test period
            backtest_predictions = backtest_forecast_df['yhat'].values[-test_size:]
            
            # CRITICAL FIX: Ensure non-negative predictions
            backtest_predictions = np.maximum(backtest_predictions, 0)
            
            # Get the actual values from the test set
            test_actuals = test_df['Order_Quantity_kg'].values

            # Filter out days where actual sales were zero to avoid division-by-zero errors
            non_zero_mask = test_actuals > 0
            test_actuals_safe = test_actuals[non_zero_mask]
            backtest_predictions_safe = backtest_predictions[non_zero_mask]

            # Calculate MAPE only on the non-zero days
            if len(test_actuals_safe) > 0:
                mape = mean_absolute_percentage_error(test_actuals_safe, backtest_predictions_safe)
            else:
                mape = 0.0

        except Exception as e:
            print(f"Prophet backtesting failed: {e}. Using default accuracy.")
            mape = 0.2  # Default 20% error rate
    
    # --- B. Main Forecasting Section (for the chart) ---
    
    # 2. Prophet forecast (on full dataset)
    if prophet_available and len(values) >= 2:
        try:
            prophet_df = df.rename(columns={'Date': 'ds', 'Order_Quantity_kg': 'y'})
            main_model = get_prophet_model()
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                main_model.fit(prophet_df)
                
            future = main_model.make_future_dataframe(periods=forecast_days)
            prophet_forecast_df = main_model.predict(future)
            prophet_values = prophet_forecast_df['yhat'].values[-forecast_days:]
            
            # CRITICAL FIX: Ensure non-negative values
            prophet_values = np.maximum(prophet_values, 0)
            
        except Exception as e:
            print(f"Prophet forecast failed: {e}. Using fallback.")
            prophet_values = np.full(forecast_days, max(0, np.mean(values)))
    else:
        prophet_values = np.full(forecast_days, max(0, np.mean(values)) if len(values) > 0 else 0)

    # 3. ARIMA forecast (on full dataset)
    if statsmodels_available and len(values) > 10:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                arima_model = ARIMA(values, order=(2,1,1))  # Simpler model
                arima_fit = arima_model.fit()
                arima_forecast = arima_fit.forecast(steps=forecast_days)
                
            # CRITICAL FIX: Ensure non-negative values
            arima_forecast = np.maximum(arima_forecast, 0)
            
        except Exception as e:
            print(f"ARIMA forecast failed: {e}. Using average.")
            arima_forecast = np.full(forecast_days, max(0, np.mean(values)))
    else:
        arima_forecast = np.full(forecast_days, max(0, np.mean(values)) if len(values) > 0 else 0)

    # 4. LSTM forecast (simplified for stability)
    lstm_forecast = np.full(forecast_days, max(0, np.mean(values)) if len(values) > 0 else 0)

    # 5. Monte Carlo forecast
    def discrete_event_monte_carlo(df_mc, n_simulations=200, days_to_forecast=30):
        df_mc = df_mc[df_mc['Order_Quantity_kg'] > 0].sort_values('Date').reset_index(drop=True)
        if len(df_mc) < 2: 
            return np.full(days_to_forecast, max(0, np.mean(values)) if len(values) > 0 else 0)
            
        inter_arrival_times = df_mc['Date'].diff().dt.days.dropna()
        if len(inter_arrival_times) < 2:
            return np.full(days_to_forecast, max(0, np.mean(values)) if len(values) > 0 else 0)

        mean_time, std_time = inter_arrival_times.mean(), inter_arrival_times.std()
        mean_size, std_size = df_mc['Order_Quantity_kg'].mean(), df_mc['Order_Quantity_kg'].std()

        # Add safety checks
        if pd.isna(std_time) or std_time <= 0:
            std_time = max(1, mean_time * 0.1)
        if pd.isna(std_size) or std_size <= 0:
            std_size = max(1, mean_size * 0.1)

        all_simulations = []
        for _ in range(n_simulations):
            daily_demand = [0] * days_to_forecast
            current_day = 0
            while current_day < days_to_forecast:
                time_to_next_raw = np.random.normal(mean_time, std_time)
                time_to_next = max(1, round(time_to_next_raw))
                order_day = current_day + int(time_to_next)

                if order_day < days_to_forecast:
                    order_quantity_raw = np.random.normal(mean_size, std_size)
                    order_quantity = max(0, order_quantity_raw)  # Ensure non-negative
                    daily_demand[order_day] += order_quantity
                current_day = order_day
            all_simulations.append(daily_demand)
        
        mc_result = np.median(all_simulations, axis=0)
        return np.maximum(mc_result, 0)  # Final safety check

    mc_forecast = discrete_event_monte_carlo(df, days_to_forecast=forecast_days)

    # 6. Create weighted ensemble with non-negative constraint
    models = [prophet_values, arima_forecast, lstm_forecast, mc_forecast]
    weights = [0.5, 0.2, 0.15, 0.15]  # Prophet gets 50%
    ensemble_forecast = np.average(models, axis=0, weights=weights)
    
    # CRITICAL FIX: Final non-negative constraint
    ensemble_forecast = np.maximum(ensemble_forecast, 0)

    # 7. Create visualization
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=values, name='Actual Demand', 
                            line=dict(color='blue', width=2)))
    future_dates = pd.date_range(dates.max(), periods=forecast_days + 1)[1:]
    
    # Add individual model traces
    fig.add_trace(go.Scatter(x=future_dates, y=prophet_values, name='Prophet', 
                            line=dict(dash='dot', color='green')))
    fig.add_trace(go.Scatter(x=future_dates, y=arima_forecast, name='ARIMA', 
                            line=dict(dash='dot', color='red')))
    fig.add_trace(go.Scatter(x=future_dates, y=lstm_forecast, name='LSTM', 
                            line=dict(dash='dot', color='purple')))
    fig.add_trace(go.Scatter(x=future_dates, y=mc_forecast, name='Monte Carlo', 
                            line=dict(dash='dot', color='orange')))
    fig.add_trace(go.Scatter(x=future_dates, y=ensemble_forecast, name='Ensemble Forecast', 
                            line=dict(color='black', width=3)))
    
    fig.update_layout(
        title='30-Day Demand Forecast with Ensemble Methods', 
        xaxis_title='Date', 
        yaxis_title='Demand (kg)', 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    model_forecasts = {
        'Prophet': np.mean(prophet_values),
        'ARIMA': np.mean(arima_forecast),
        'LSTM': np.mean(lstm_forecast),
        'Monte Carlo': np.mean(mc_forecast)
    }

    return fig, ensemble_forecast, model_forecasts, mape

def create_enhanced_charts(df, analyzer, kpis, forecast_data, safety_stock):
    """Create enhanced visualizations with all required parameters"""
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

    # Distribution
    fig_orders.add_trace(
        go.Histogram(x=df['Order_Quantity_kg'], name='Order Size Distribution',
                    nbinsx=20, opacity=0.7), row=2, col=1
    )

    fig_orders.update_layout(height=600, showlegend=True)

    # 2. Cost Analysis Chart - Calculate costs if columns don't exist
    if 'Transport_Cost' not in df.columns:
        df['Transport_Cost'] = constants.TRANSPORT_COST  # Assuming fixed cost per order

    if 'Total_Cost' not in df.columns:
        df['Total_Cost'] = df['Order_Quantity_kg'] * constants.PRICE_PER_KG

    cost_data = pd.DataFrame({
        'Date': df['Date'],
        'Transport_Cost': df['Transport_Cost'],
        'Product_Cost': df['Total_Cost'],
        'Total_Cost': df['Transport_Cost'] + df['Total_Cost']
    })

    fig_cost_overview = px.area(cost_data, x='Date', y=['Transport_Cost', 'Product_Cost'],
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

    return fig_orders, fig_cost_overview, fig_forecast

def main():
    # Initialize database
    init_db()
    fix_order_date()

    seed_historical_data()
    # ADD THIS ONE LINE - clears cached data so it loads fresh
    get_historical_orders_from_db.clear()
    
    st.sidebar.header("🗓️ Analysis Period")
    analysis_periods = ['2024/2025', '2025/2026', '2026/2027', '2027/2028']

    if 'selected_period' not in st.session_state:
        st.session_state.selected_period = '2024/2025'

    selected_period = st.sidebar.selectbox(
        "Choose a period to analyze or update:",
        analysis_periods,
        index=analysis_periods.index(st.session_state.selected_period)
    )
    st.session_state.selected_period = selected_period

    # Get today's date once
    today = datetime.today()
    try:
        start_year = int(selected_period.split('/')[0])
    except (ValueError, IndexError):
        st.error("Invalid analysis period format. Using current year as fallback.")
        start_year = today.year

    # 1. Parse the start year from the selected period string (e.g., '2025/2026' -> 2025)
    try:
        start_year = int(selected_period.split('/')[0])
    except (ValueError, IndexError):
        st.error("Invalid analysis period format. Check the 'analysis_periods' list.")
        st.stop()

    # 2. Define the fixed start date and the potential (full year) end date
    display_start_date = datetime(start_year, 7, 1)
    display_end_date = datetime(start_year + 1, 6, 30)

    # 3. Determine the final end_date using your logic: the earlier of the potential end date or today
    # --- SET 2: DATES FOR FILTERING THE DATA (Cannot go past today) ---
    filter_start_date = display_start_date
    filter_end_date = min(display_end_date, today) # The end date for analysis is the earlier of the two

    alert = None
    # Initialize components

    # THIS LINE IS MODIFIED to use the selected period from the dropdown
    df = get_historical_orders_from_db(st.session_state.selected_period)

    # ADD THIS BLOCK to handle cases where a new period has no data yet
    if df.empty:
        st.info(f"No order data found for the {st.session_state.selected_period} period. Record a receipt in the sidebar to begin the analysis.")
        # Create an empty df with correct columns to prevent errors downstream
        df = pd.DataFrame(columns=['Date', 'Order_Quantity_kg', 'Containers_Used', 'Transport_Cost', 'Total_Cost'])

    # The rest of your analysis code will now work on the period-specific 'df'
    analyzer = DryIceAnalyzer(df)
    kpis = analyzer.calculate_kpis(period=st.session_state.selected_period)

    # Initialize other components
    mobile_ui = MobileInterface()
    #alerts_system = SmartAlerts(inventory_tracker)
    maintenance_system = PredictiveMaintenance()
    integration_system = SystemIntegrations()

    # Initialize session state for transactions
    if 'last_loaded_period' not in st.session_state or st.session_state.last_loaded_period != st.session_state.selected_period:
        print(f"Period changed. Loading transactions for {st.session_state.selected_period}...")
        st.session_state.transactions = get_transactions_from_db(st.session_state.selected_period)
        st.session_state.last_loaded_period = st.session_state.selected_period # Update the tracker
    
    
    # --- 1. Generate Forecast (Logic from former Tab 2) ---
    if not df.empty:
        with st.spinner("🔄 Generating forecast... This may take a moment."):
            daily_df = df.set_index('Date').resample('D')['Order_Quantity_kg'].sum().reset_index()
            daily_df = daily_df.rename(columns={'Date': 'Date', 'Order_Quantity_kg': 'Order_Quantity_kg'})
            fig_ensemble, ensemble_forecast_values, model_forecasts, backtest_accuracy = create_ensemble_forecast(daily_df, forecast_days=30)
            total_forecasted_demand = np.sum(ensemble_forecast_values)
            forecast_std_dev = np.std(ensemble_forecast_values)
    else:
        # Provide default values if no data exists
        fig_ensemble, ensemble_forecast_values, model_forecasts, backtest_accuracy = None, np.array([0]), {}, 0
        total_forecasted_demand = 0
        forecast_std_dev = 0

    
    if total_forecasted_demand <= 0:
        st.warning("⚠️ Forecast resulted in zero/negative demand. Using intelligent fallback.")
        # Use historical KPIs as fallback
        fallback_monthly_demand = max(
            kpis.get('current_monthly_volume', 0),
            kpis.get('avg_order_size', 300) * 4,  # Assume 4 orders per month minimum
            1200  # Absolute minimum of 1200kg/month
        )
        total_forecasted_demand = fallback_monthly_demand
        forecast_std_dev = total_forecasted_demand * 0.25  # 25% coefficient of variation
        st.info(f"Using fallback monthly demand: {total_forecasted_demand:,.0f} kg")

    # --- 2. Calculate Inventory Policy (Logic from former Tab 3) ---
    # Use forecast demand if available, otherwise fallback to historical KPIs
    monthly_demand_input = total_forecasted_demand if total_forecasted_demand > 0 else kpis.get('current_monthly_volume', 0)
    demand_stddev_input = forecast_std_dev * np.sqrt(30) if forecast_std_dev > 0 else kpis.get('std_order_size', 0) * math.sqrt(4) #Approx 4 weeks in month

    # Calculate policy parameters
    avg_sublimation = sum(constants.SUB_LOSS_RANGE) / 2 / 100
    sublimation_factor = 1 + avg_sublimation
    adjusted_demand = monthly_demand_input * sublimation_factor
    
    z_score = stats.norm.ppf(constants.SERVICE_LEVEL)
    eoq = math.sqrt((2 * adjusted_demand * constants.TRANSPORT_COST) / (constants.HOLDING_RATE * constants.PRICE_PER_KG)) if (constants.HOLDING_RATE * constants.PRICE_PER_KG) > 0 else 0
    safety_stock = z_score * demand_stddev_input * math.sqrt(constants.LEAD_TIME_DAYS) * sublimation_factor
    reorder_point = (adjusted_demand / 30 * constants.LEAD_TIME_DAYS) + safety_stock

    # --- 3. Calculate the Definitive Annual Transport Savings ---
    current_monthly_orders = kpis.get('order_frequency', 0)
    eoq_monthly_orders = adjusted_demand / eoq if eoq > 0 else 0
    annual_transport_savings = (current_monthly_orders - eoq_monthly_orders) * 12 * constants.TRANSPORT_COST

    # Ensure savings cannot be negative
    annual_transport_savings = max(0, annual_transport_savings)

    # --- 4. Recalculate Total Annual Spending & Other Costs ---
    annual_volume = kpis.get('total_volume', 0)
    annual_product_cost = annual_volume * constants.PRICE_PER_KG
    annual_transport_cost = kpis.get('total_orders', 0) * constants.TRANSPORT_COST
    annual_sublimation_loss = annual_volume * constants.PRICE_PER_KG * avg_sublimation

    # Corrected holding cost calculation
    average_inventory_level = (kpis.get('avg_order_size', 0) / 2) + safety_stock
    annual_holding_cost = average_inventory_level * constants.PRICE_PER_KG * constants.HOLDING_RATE
    
    total_annual_spending = annual_product_cost + annual_transport_cost + annual_holding_cost + annual_sublimation_loss

    # --- 5. Generate Other Charts and Visualizations ---
    # The original Prophet forecast_data object for chart in Tab 1
    forecast_data = analyzer.forecast_demand()
    fig_orders, fig_cost_overview, fig_forecast = create_enhanced_charts(
        df=df, analyzer=analyzer, kpis=kpis, forecast_data=forecast_data, safety_stock=safety_stock
    )
    
    # Get current stock from the database
    current_stock = get_current_stock_from_db()

    # If the database is empty, seed it with the smart, dynamically calculated value
    if current_stock == 0:
        target_days_coverage = 45
        # average_daily_demand is now calculated based on forecast values if available
        avg_daily_forecast = np.mean(ensemble_forecast_values) if total_forecasted_demand > 0 else (kpis.get('avg_order_size', 0) / 7)

        # Use the final, forecast-driven eoq and safety_stock values
        initial_stock = max(
            eoq * 2,                                    # Ensure at least 2 order cycles
            safety_stock * 4,                           # Ensure adequate safety buffer
            avg_daily_forecast * target_days_coverage   # Meet strategic coverage goals
        )
        # Ensure initial stock is not zero if all calculations result in zero (e.g., no data)
        if initial_stock <= 0:
            initial_stock = 1000 # Fallback to a default value

        current_stock = initial_stock
        update_current_stock_in_db(current_stock, datetime.now())
        print(f"Database was empty. Seeded initial stock with: {current_stock:.2f} kg")

    # Initialize the inventory tracker with the definitive current_stock value
    inventory_tracker = InventoryTracker(
        initial_stock=current_stock,
        analyzer=analyzer
    )
   
    # Initialize SmartAlerts after inventory_tracker is created
    alerts_system = SmartAlerts(inventory_tracker)
    mobile_ui.optimize_for_mobile()
    mobile_ui.show_mobile_welcome()

    # Header
    start_date_str = display_start_date.strftime('%B %d, %Y')
    end_date_str = display_end_date.strftime('%B %d, %Y')

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div class="glass-header">
            <img src="../assets/browns_logo.jpg" style="width: 200px; margin-bottom: 10px;">
            <h3>DRY ICE INVENTORY OPTIMIZER</h3>
            <div class="period-pill">📅 {start_date_str} - {end_date_str}</div>
        </div>
        """, unsafe_allow_html=True)

    st.sidebar.header("📦 Real-time Inventory")

    current_stock_input = st.sidebar.number_input(
        "Current Stock (kg)",
        min_value=0.0,
        value=float(inventory_tracker.current_stock),
        step=50.0,
        help="Enter the current stock level in kilograms"
    )

    # Update tracker only if value changed
    if current_stock_input != inventory_tracker.current_stock:
        inventory_tracker.current_stock = current_stock_input
        update_current_stock_in_db(current_stock_input, datetime.now())

    # Display status (LOW/CRITICAL/OK)
    status = inventory_tracker.get_stock_status()
    st.sidebar.markdown(
        f"**Status:** <span style='color:{status['color']};font-weight:bold'>"
        f"{status['status']}</span>",
        unsafe_allow_html=True
    )
    st.sidebar.subheader("Update Inventory")

    # Record Usage
    usage_date = st.sidebar.date_input("Usage Date", value=datetime.today())
    usage = st.sidebar.number_input("Quantity Used (kg)", min_value=0, value=150, step=10)

    if st.sidebar.button("Record Usage"):
        alert = inventory_tracker.update_stock(usage, "Daily Consumption", usage_date) or None
        add_transaction_to_history("usage", usage, "Daily Consumption", usage_date, st.session_state.selected_period)
        if alert is not None:
            st.sidebar.error(alert["message"])
        else:
            st.sidebar.success(f"Usage of {usage} kg recorded on {usage_date.strftime('%Y-%m-%d')}.")
        st.rerun()

    # Record Receipt
    receipt_date = st.sidebar.date_input("Receipt Date", value=datetime.today(), key="receipt_date")
    new_stock = st.sidebar.number_input("New Stock Received (kg)", min_value=0, value=0, step=50)

    if st.sidebar.button("Record Receipt"):
        
        correct_period = get_period_from_date(receipt_date)

        inventory_tracker.current_stock += new_stock
        update_current_stock_in_db(inventory_tracker.current_stock, receipt_date)
        add_transaction_to_history(
            transaction_type="receipt",
            quantity=new_stock,
            description="Stock Receipt",
            date=receipt_date,
            period=correct_period  # Use the derived period, not the one from the sidebar
        )
        # 3. Provide clear feedback to the user about what happened.
        st.sidebar.success(
            f"Order for {new_stock} kg on {receipt_date.strftime('%Y-%m-%d')} recorded. "
            f"It has been automatically assigned to the {correct_period} period."
        )

        # 4. (Optional but highly recommended UX improvement)
        # If the order belongs to a different period, switch the dashboard view to that period.
        if st.session_state.selected_period != correct_period:
            st.session_state.selected_period = correct_period
            st.sidebar.info(f"Dashboard view switched to {correct_period} to show your new entry.")
        st.rerun()
        
    # Mobile Quick Order Entry (only show on mobile devices)
    if mobile_ui.is_mobile_device():
        st.sidebar.markdown("---")
        quick_order = mobile_ui.quick_order_entry()
        
        if quick_order:
            # Process the quick order
            with st.spinner("Processing your order..."):
                # Add to database as a receipt
                correct_period = get_period_from_date(quick_order['delivery_date'])
                
                # Update inventory
                inventory_tracker.current_stock += quick_order['quantity']
                update_current_stock_in_db(inventory_tracker.current_stock, quick_order['delivery_date'])
                
                # Add to transaction history
                add_transaction_to_history(
                    transaction_type="receipt",
                    quantity=quick_order['quantity'],
                    description=f"Quick Order: {quick_order['product']} - {quick_order['notes'] if quick_order['notes'] else 'No notes'}",
                    date=quick_order['delivery_date'],
                    period=correct_period
                )
                
                # Show success message
                st.sidebar.success(f"""
                ✅ **Order Placed Successfully!**
                
                Product: {quick_order['product']}
                Quantity: {quick_order['quantity']} kg
                Delivery: {quick_order['delivery_date'].strftime('%Y-%m-%d')}
                """)
                
                # Optional: Add to session state for tracking
                if 'quick_orders' not in st.session_state:
                    st.session_state.quick_orders = []
                st.session_state.quick_orders.append(quick_order)
                
                # Rerun to refresh the UI
                st.rerun()
            
    # Enhanced Stock Status Display
    stock_status = inventory_tracker.get_stock_status()
    st.sidebar.markdown(
        f"**Status:** <span style='color:{stock_status['color']};font-weight:bold'>"
        f"{stock_status['status']}</span>",
        unsafe_allow_html=True
    )

    max_stock = eoq + safety_stock * 2
    current_stock_val = inventory_tracker.current_stock
    progress_value = min(1.0, current_stock_val / max_stock) if max_stock > 0 else 0
    st.sidebar.progress(progress_value)
    st.sidebar.caption(f"Stock Level: {current_stock_val:.1f}/{max_stock:.1f} kg ({progress_value:.1%})")

    if stock_status['status'] in ['Low Stock', 'Critical']:
        st.sidebar.warning(f"⚠️ Consider reordering. Recommended order: {eoq:.1f} kg")    

    # Sidebar - Report Generator (Always Visible)
    st.sidebar.header("📄 Report Generation")
    if st.sidebar.button("Generate PDF Report", type="primary"):
        with st.spinner("Generating comprehensive report..."):
            try:
                if df is None or df.empty:
                    st.sidebar.error("No data available. Please upload data first.")
                else:
                    report = ReportGenerator(analyzer=analyzer, df=df)
                    report_path = report.generate_pdf()

                    with open(report_path, "rb") as f:
                        st.sidebar.download_button(
                            label="📥 Download Report",
                            data=f,
                            file_name=f"dry_ice_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                        )
                    st.sidebar.success("Report generated successfully!")
            except Exception as e:
                st.sidebar.error(f"Error generating report: {str(e)}")

    # Sidebar - System Parameters (Always Visible)
    st.sidebar.header("⚙️ System Parameters")
    with st.sidebar.expander("Inventory Parameters"):
        st.write(f"**Price per kg:** KSh {constants.PRICE_PER_KG:.2f}")
        st.write(f"**Container size:** {constants.CONTAINER_SIZE} kg")
        st.write(f"**Transport cost:** KSh {constants.TRANSPORT_COST:,.2f}")
        st.write(f"**Holding rate:** {constants.HOLDING_RATE*100:.1f}%")
        st.write(f"**Sublimation loss:** {constants.SUB_LOSS_RANGE[0]:.1f}-{constants.SUB_LOSS_RANGE[1]:.1f}%")
        st.write(f"**Lead time:** {constants.LEAD_TIME_DAYS} day(s)")
        st.write(f"**Service level:** {constants.SERVICE_LEVEL*100:.0f}%")

    # Sidebar - Data Summary (Always Visible)
    st.sidebar.header("📊 Data Summary")
    sidebar_start_str = display_start_date.strftime('%d/%m/%Y')
    sidebar_end_str = display_end_date.strftime('%d/%m/%Y')

    st.sidebar.write(f"**Analysis Period:** {sidebar_start_str} to {sidebar_end_str}")
    st.sidebar.write(f"**Total Orders:** {len(df):,}")
    st.sidebar.write(f"**Data Points:** {df.shape[0]:,}")

    # Sidebar - Footer (Always Visible)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Browns Cheese** 🧀")
    st.sidebar.markdown("Dry Ice Management System")
    st.sidebar.markdown("© 2025 - Gathura Chege")    

    monthly_savings = annual_transport_savings / 12
    monthly_transport_cost = (current_monthly_orders * constants.TRANSPORT_COST)
    percent_savings = (monthly_savings / monthly_transport_cost) * 100 if monthly_transport_cost > 0 else 0

    # ============================================================
    # 🎨 ENHANCED KPI DASHBOARD WITH GLASS DESIGN
    # ============================================================

    st.markdown("""
    <div style="
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 20px;
        margin: 20px 0;
        border: 1px solid rgba(255, 255, 255, 0.08);
    ">
        <div style="
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        ">
            📈 Key Performance Indicators
        </div>
    """, unsafe_allow_html=True)

    # Create metrics in a responsive grid with glass design
    metrics_list = [
        ("Total Orders", f"{kpis.get('total_orders', 0):,}", None),
        ("Total Volume", f"{kpis.get('total_volume', 0):,.0f} kg", None),
        ("Annual Spending", f"KSh {total_annual_spending:,.0f}", None),
        ("Annual Transport Savings", f"KSh {annual_transport_savings:,.0f}", None),
        ("Safety Stock", f"{safety_stock:,.1f} kg", None),
        ("Economic EOQ", f"{eoq:,.1f} kg", None),
        ("Container Efficiency", f"{kpis.get('container_utilization', 0.0)*100:.1f}%", None),
        ("Monthly Savings", f"KSh {monthly_savings:,.0f}", f"{percent_savings:+.1f}%"),
    ]

    # Display metrics in a 4-column grid with glass design
    cols = st.columns(4)
    for idx, (label, value, delta) in enumerate(metrics_list):
        with cols[idx % 4]:
            # Glass metric card
            delta_html = ""
            if delta:
                delta_color = "#28a745" if "+" in str(delta) or (isinstance(delta, (int, float)) and delta > 0) else "#dc3545"
                delta_html = f'<div style="font-size:12px;color:{delta_color};margin-top:4px;">{delta}</div>'
            
            st.markdown(f"""
            <div style="
                background: rgba(255, 255, 255, 0.06);
                backdrop-filter: blur(6px);
                -webkit-backdrop-filter: blur(6px);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
                padding: 14px 12px;
                text-align: center;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
                min-height: 80px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                margin: 4px 0;
                cursor: default;
            ">
                <div style="
                    font-size: 11px;
                    color: #888;
                    font-weight: 500;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 4px;
                ">{label}</div>
                <div style="
                    font-size: 22px;
                    font-weight: 700;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    margin: 2px 0;
                ">{value}</div>
                {delta_html}
            </div>
            """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ============================================================
    # 🎨 ENHANCED STOCK ALERTS WITH GLASS DESIGN
    # ============================================================

    st.markdown("""
    <div style="margin-top: 20px;">
    """, unsafe_allow_html=True)

    # Display stock alerts with glass design
    stock_status = inventory_tracker.get_stock_status()

    # Create glass alert cards
    if stock_status['status'] in ['Low Stock', 'Critical']:
        alert_color = "#dc3545" if stock_status['status'] == 'Critical' else "#ffc107"
        alert_icon = "🔴" if stock_status['status'] == 'Critical' else "🟡"
        
        st.markdown(f"""
        <div style="
            background: rgba(220, 53, 69, 0.06);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border: 1px solid rgba(220, 53, 69, 0.15);
            border-radius: 12px;
            padding: 16px 20px;
            margin: 10px 0;
            display: flex;
            align-items: center;
            gap: 15px;
        ">
            <div style="font-size: 28px;">{alert_icon}</div>
            <div style="flex: 1;">
                <div style="font-weight: 600; color: #333;">{stock_status['status'].upper()}</div>
                <div style="font-size: 14px; color: #666;">
                    Current stock: {inventory_tracker.current_stock:.0f} kg | 
                    Reorder point: {reorder_point:.0f} kg | 
                    Safety stock: {safety_stock:.0f} kg
                </div>
            </div>
            <div style="
                background: rgba(255,255,255,0.05);
                border-radius: 20px;
                padding: 6px 16px;
                font-size: 13px;
                border: 1px solid rgba(255,255,255,0.05);
            ">
                📦 {eoq:.0f} kg recommended
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="
            background: rgba(40, 167, 69, 0.06);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border: 1px solid rgba(40, 167, 69, 0.15);
            border-radius: 12px;
            padding: 16px 20px;
            margin: 10px 0;
            display: flex;
            align-items: center;
            gap: 15px;
        ">
            <div style="font-size: 28px;">✅</div>
            <div style="flex: 1;">
                <div style="font-weight: 600; color: #333;">STOCK LEVEL HEALTHY</div>
                <div style="font-size: 14px; color: #666;">
                    Current stock: {inventory_tracker.current_stock:.0f} kg | 
                    Reorder point: {reorder_point:.0f} kg
                </div>
            </div>
            <div style="
                background: rgba(255,255,255,0.05);
                border-radius: 20px;
                padding: 6px 16px;
                font-size: 13px;
                border: 1px solid rgba(255,255,255,0.05);
            ">
                📊 {((inventory_tracker.current_stock / (eoq + safety_stock)) * 100):.0f}% capacity
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ============================================================
    # 🎨 ACTIVE ALERTS WITH GLASS DESIGN
    # ============================================================

    alerts = alerts_system.check_conditions(
        current_demand=usage,
        avg_demand=kpis.get('avg_order_size', 0),
        std_demand=kpis.get('std_order_size', 0),
        current_cost=analyzer.constants['transport_cost'],
        avg_cost=analyzer.constants['transport_cost']
    )

    if alerts or alerts_system.get_active_alerts():
        st.markdown("""
        <div style="
            background: rgba(255, 193, 7, 0.04);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 193, 7, 0.10);
            border-radius: 12px;
            padding: 16px 20px;
            margin: 15px 0;
        ">
            <div style="
                font-size: 1.1rem;
                font-weight: 600;
                margin-bottom: 10px;
                color: #856404;
            ">
                ⚠️ Active Alerts
            </div>
        """, unsafe_allow_html=True)
        
        for alert in alerts_system.get_active_alerts():
            is_critical = "CRITICAL" in alert['message']
            alert_color = "#dc3545" if is_critical else "#ffc107"
            bg_color = "rgba(220, 53, 69, 0.04)" if is_critical else "rgba(255, 193, 7, 0.04)"
            
            st.markdown(f"""
            <div style="
                background: {bg_color};
                backdrop-filter: blur(4px);
                -webkit-backdrop-filter: blur(4px);
                border-left: 4px solid {alert_color};
                border-radius: 8px;
                padding: 12px 16px;
                margin: 8px 0;
                display: flex;
                align-items: center;
                gap: 12px;
            ">
                <div style="font-size: 20px;">{'🔴' if is_critical else '🟡'}</div>
                <div style="flex: 1;">
                    <div style="font-size: 13px; color: #666;">
                        {alert['timestamp'].strftime('%H:%M')}
                    </div>
                    <div style="font-size: 14px; color: #333;">
                        {alert['message']}
                    </div>
                </div>
                <div style="
                    background: rgba(255,255,255,0.05);
                    border-radius: 12px;
                    padding: 2px 10px;
                    font-size: 11px;
                    border: 1px solid rgba(255,255,255,0.05);
                    color: #888;
                ">
                    {'CRITICAL' if is_critical else 'WARNING'}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ============================================================
    # END OF ENHANCED KPI DASHBOARD
    # ============================================================
    tab_inventory, tab_movements,tab_analytics,tab_inventory_visual,tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📦 Inventory",
        "📊 Stock Movements",
        "📈 All Items Analytics",
        "🖼️ Visual Inventory",
        "📊 Order Analysis",
        "🔮 Demand Forecast",
        "📦 Inventory Management",
        "💰 Cost Optimization",
        "📋 Recommendations",
        "🛠️ Maintenance",
        "📜 Transaction History"
    ])

    with tab_inventory:
        st.markdown("## 📦 Company Inventory (Google Sheets)")

        # --- HIDE SEARCH ONLY IN THIS TAB ---
        st.markdown("""
        <style>
        .stDataFrame [data-testid="stDataFrameSearch"] {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Refresh button
        col1, col2 = st.columns([1, 4])

        with col1:
            if st.button("🔄 Refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        with col2:
            st.caption(
                f"Data source: Google Sheets | Updated: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

        st.divider()

        @st.cache_data(ttl=300)
        def load_inventory_data():
            try:
                gsheet = GoogleSheetReader()

                if gsheet.authenticate():
                    stock = gsheet.get_stock_with_pricing()
                    current = gsheet.get_current_stock()
                    low = gsheet.get_low_stock_items()

                    # Count categories
                    category_count = (
                        stock['ITEM_CATEGORY'].nunique()
                        if 'ITEM_CATEGORY' in stock.columns
                        else 0
                    )

                    return stock, current, low, category_count

            except Exception as e:
                st.error(f"Inventory loading error: {e}")

            # Fallback if authentication fails
            return (
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
                0
            )

        with st.spinner("Loading inventory data..."):
            stock_df, current_df, low_df, category_count = load_inventory_data()

        # Everything below stays INSIDE tab_inventory
        if not stock_df.empty:

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("📦 Total Items", len(stock_df))

            with col2:
                st.metric("📂 Categories", category_count)

            with col3:
                st.metric(
                    "📊 Current Stock",
                    len(current_df) if not current_df.empty else 0
                )

            with col4:
                low_count = len(low_df) if not low_df.empty else 0
                st.metric(
                    "⚠️ Low Stock",
                    low_count,
                    delta=f"-{low_count}" if low_count > 0 else None
                )

            # Price stats
            if 'UNIT PRICE' in stock_df.columns:
                price_count = stock_df['UNIT PRICE'].notna().sum()

                if price_count > 0:
                    st.caption(
                        f"💰 Prices available for "
                        f"{price_count} out of {len(stock_df)} items"
                    )

            # --- ABC ANALYSIS (Fixed) ---
            if 'UNIT PRICE' in stock_df.columns and 'QUANTITY' in stock_df.columns:
                st.divider()
                st.markdown("### 📊 ABC Analysis (Pareto Analysis)")
                
                # Create a copy for ABC analysis
                abc_df = stock_df.copy()
                
                # Convert to numeric, coercing errors to NaN
                abc_df['QUANTITY'] = pd.to_numeric(abc_df['QUANTITY'], errors='coerce')
                abc_df['UNIT PRICE'] = pd.to_numeric(abc_df['UNIT PRICE'], errors='coerce')
                
                # Drop rows with missing values
                abc_df = abc_df.dropna(subset=['QUANTITY', 'UNIT PRICE'])
                
                if not abc_df.empty and len(abc_df) > 0:
                    # Calculate annual value
                    abc_df['ANNUAL_VALUE'] = abc_df['QUANTITY'] * abc_df['UNIT PRICE']
                    
                    # Sort by value and calculate cumulative percentage
                    abc_df = abc_df.sort_values('ANNUAL_VALUE', ascending=False)
                    total_value = abc_df['ANNUAL_VALUE'].sum()
                    
                    if total_value > 0:
                        abc_df['CUM_PERCENT'] = abc_df['ANNUAL_VALUE'].cumsum() / total_value
                        
                        # Classify items
                        def get_abc_class(row):
                            if row['CUM_PERCENT'] <= 0.70:
                                return '🔴 A (70% value)'
                            elif row['CUM_PERCENT'] <= 0.90:
                                return '🟡 B (20% value)'
                            else:
                                return '🟢 C (10% value)'
                        
                        abc_df['ABC_CLASS'] = abc_df.apply(get_abc_class, axis=1)
                        
                        # Show ABC breakdown
                        abc_counts = abc_df['ABC_CLASS'].value_counts()
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("🔴 A Items (70% Value)", abc_counts.get('🔴 A (70% value)', 0))
                        with col2:
                            st.metric("🟡 B Items (20% Value)", abc_counts.get('🟡 B (20% value)', 0))
                        with col3:
                            st.metric("🟢 C Items (10% Value)", abc_counts.get('🟢 C (10% value)', 0))
                        with col4:
                            st.metric("💰 Total Inventory Value", f"KSh {total_value:,.2f}")
                        
                        # Show ABC summary table
                        abc_summary = abc_df.groupby('ABC_CLASS').agg({
                            'ITEM_NAME': 'count',
                            'ANNUAL_VALUE': 'sum'
                        }).reset_index()
                        abc_summary.columns = ['Class', 'Item Count', 'Total Value']
                        st.dataframe(abc_summary, use_container_width=True, hide_index=True)
                        
                        # Show top A items
                        with st.expander("🔍 View Top A Items (70% Value)"):
                            top_a = abc_df[abc_df['ABC_CLASS'] == '🔴 A (70% value)'].head(20)
                            st.dataframe(
                                top_a[['ITEM_NAME', 'ITEM_CATEGORY', 'QUANTITY', 'UNIT PRICE', 'ANNUAL_VALUE']],
                                use_container_width=True,
                                hide_index=True
                            )
                    else:
                        st.info("Total inventory value is zero. Cannot perform ABC analysis.")
                else:
                    st.info("No valid items with both quantity and price data found for ABC analysis.")


                # --- CATEGORY-LEVEL INVENTORY SUMMARY ---
            if 'ITEM_CATEGORY' in stock_df.columns and 'QUANTITY' in stock_df.columns and 'UNIT PRICE' in stock_df.columns:
                st.divider()
                st.markdown("### 📊 Category-Level Inventory Summary")
                
                # Convert to numeric
                cat_df = stock_df.copy()
                cat_df['QUANTITY'] = pd.to_numeric(cat_df['QUANTITY'], errors='coerce')
                cat_df['UNIT PRICE'] = pd.to_numeric(cat_df['UNIT PRICE'], errors='coerce')
                
                # Drop rows with missing values
                cat_df = cat_df.dropna(subset=['QUANTITY', 'UNIT PRICE'])
                
                if not cat_df.empty:
                    # Calculate annual value first
                    cat_df['ANNUAL_VALUE'] = cat_df['QUANTITY'] * cat_df['UNIT PRICE']
                    
                    # Group by category with all aggregations at once
                    category_summary = cat_df.groupby('ITEM_CATEGORY').agg({
                        'ITEM_NAME': 'count',
                        'QUANTITY': 'sum',
                        'UNIT PRICE': 'mean',
                        'ANNUAL_VALUE': 'sum'
                    }).reset_index()
                    
                    # Rename columns
                    category_summary.columns = ['Category', 'Items', 'Total Quantity', 'Avg Unit Price', 'Total Value']
                    
                    # Format currency columns (keep as numbers for chart, format for display)
                    display_summary = category_summary.copy()
                    display_summary['Avg Unit Price'] = display_summary['Avg Unit Price'].apply(lambda x: f"KSh {x:,.2f}")
                    display_summary['Total Value'] = display_summary['Total Value'].apply(lambda x: f"KSh {x:,.2f}")
                    
                    # Show summary table
                    st.dataframe(display_summary, use_container_width=True, hide_index=True)
                    
                    # Chart: Category breakdown (use numeric values)
                    fig_category = px.bar(
                        category_summary,
                        x='Category',
                        y='Total Value',
                        title='Inventory Value by Category',
                        color='Category',
                        height=400,
                        labels={'Total Value': 'Total Value (KSh)'}
                    )
                    fig_category.update_layout(showlegend=False)
                    st.plotly_chart(fig_category, use_container_width=True)
                    
                    # Show total value
                    total_inventory_value = cat_df['ANNUAL_VALUE'].sum()
                    st.metric("💰 Total Inventory Value Across All Categories", f"KSh {total_inventory_value:,.2f}")
                else:
                    st.info("No valid data available for category summary.")
                    
            # Search + Filter
            col1, col2 = st.columns(2)

            with col1:
                search = st.text_input(
                    "🔍 Search Items",
                    placeholder="Type item name..."
                )

            with col2:
                if 'ITEM_CATEGORY' in stock_df.columns:
                    categories = (
                        ['All'] +
                        sorted(
                            stock_df['ITEM_CATEGORY']
                            .dropna()
                            .unique()
                            .tolist()
                        )
                    )

                    category_filter = st.selectbox(
                        "📂 Category",
                        categories
                    )
                else:
                    category_filter = "All"

            # Apply filters
            filtered_df = stock_df.copy()

            if search:
                mask = False

                for col in ['ITEM_NAME', 'ITEM_SERIAL']:
                    if col in filtered_df.columns:
                        mask = (
                            mask |
                            filtered_df[col]
                            .astype(str)
                            .str.contains(
                                search,
                                case=False,
                                na=False
                            )
                        )

                filtered_df = filtered_df[mask]

            if (
                category_filter != "All"
                and 'ITEM_CATEGORY' in filtered_df.columns
            ):
                filtered_df = filtered_df[
                    filtered_df['ITEM_CATEGORY']
                    == category_filter
                ]

            # Display table
            st.markdown(
                f"### 📋 Stock Listing ({len(filtered_df)} items)"
            )

            display_cols = [
                'ITEM_SERIAL',
                'ITEM_CATEGORY',
                'ITEM_NAME',
                'UNIT_OF_MEASURE',
                'QUANTITY',
                'UNIT PRICE',
                'REORDER LEVEL'
            ]

            display_cols = [
                col for col in display_cols
                if col in filtered_df.columns
            ]

            st.dataframe(
                filtered_df[display_cols],
                use_container_width=True,
                height=400,
                hide_index=True
            )

            # Low stock section
            if not low_df.empty:
                st.divider()

                st.warning(
                    f"⚠️ {len(low_df)} items are low in stock and need reordering!"
                )

                with st.expander("📋 View Low Stock Items"):
                    st.dataframe(
                        low_df,
                        use_container_width=True,
                        height=300
                    )

            # CSV export
            if not filtered_df.empty:
                csv = (
                    filtered_df
                    .to_csv(index=False)
                    .encode('utf-8')
                )

                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"inventory_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

        else:
            st.info(
            "📊 No inventory data found. "
            "Please check your Google Sheets connection."
        )
            
    with tab_movements:
        st.markdown("## 📊 Stock Movements (Google Sheets)")
    
        # Refresh button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 Refresh Movements", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        with col2:
            st.caption(f"Data source: Google Sheets | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        st.divider()
        
        @st.cache_data(ttl=300)
        def load_movement_data():
            gsheet = GoogleSheetReader()
            if gsheet.authenticate():
                check_in = gsheet.get_check_in()
                check_out = gsheet.get_check_out()
                current_stock = gsheet.get_current_stock()
                return check_in, check_out, current_stock
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        with st.spinner("Loading stock movement data..."):
            check_in_df, check_out_df, current_stock_df = load_movement_data()
        
        # Show summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📥 Check-Ins", len(check_in_df) if not check_in_df.empty else 0)
        with col2:
            st.metric("📤 Check-Outs", len(check_out_df) if not check_out_df.empty else 0)
        with col3:
            st.metric("📊 Current Stock Records", len(current_stock_df) if not current_stock_df.empty else 0)
        
        st.divider()
        
        # Create tabs for each movement type
        movement_tab1, movement_tab2, movement_tab3 = st.tabs([
            "📥 Check-Ins",
            "📤 Check-Outs",
            "📊 Current Stock"
        ])
        
        with movement_tab1:
            st.markdown("### 📥 Check-In Records")
            if not check_in_df.empty:
                st.dataframe(check_in_df, use_container_width=True, height=400)
                
                # Export
                csv = check_in_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Check-Ins CSV",
                    data=csv,
                    file_name=f"check_ins_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime='text/csv'
                )
            else:
                st.info("No check-in records found.")
        
        with movement_tab2:
            st.markdown("### 📤 Check-Out Records")
            if not check_out_df.empty:
                st.dataframe(check_out_df, use_container_width=True, height=400)
                
                # Export
                csv = check_out_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Check-Outs CSV",
                    data=csv,
                    file_name=f"check_outs_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime='text/csv'
                )
            else:
                st.info("No check-out records found.")
        
        with movement_tab3:
            st.markdown("### 📊 Current Stock Levels")
            if not current_stock_df.empty:
                st.dataframe(current_stock_df, use_container_width=True, height=400)
                
                # Export
                csv = current_stock_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Current Stock CSV",
                    data=csv,
                    file_name=f"current_stock_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime='text/csv'
                )
            else:
                st.info("No current stock records found.")

    with tab_analytics:
        st.markdown("## 📈 All Items Analytics")
        st.markdown("Comprehensive analysis for all inventory items using Google Sheets data")
        
        # Load data with caching
        @st.cache_data(ttl=600)
        def load_analytics_data():
            try:
                gsheet = GoogleSheetReader()
                if gsheet.authenticate():
                    stock = gsheet.get_stock_with_pricing()
                    check_in = gsheet.get_check_in()
                    check_out = gsheet.get_check_out()
                    current_stock = gsheet.get_current_stock()
                    return stock, check_in, check_out, current_stock
            except Exception as e:
                st.error(f"Error loading data: {e}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        with st.spinner("Loading analytics data..."):
            stock_df, check_in_df, check_out_df, current_stock_df = load_analytics_data()
        
        if not stock_df.empty:
            # --- SECTION 1: ORDER ANALYSIS FOR ALL ITEMS ---
            st.divider()
            st.markdown("### 📊 Order Analysis for All Items")
            
            # Show summary metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("📦 Total Items", len(stock_df))
            with col2:
                st.metric("📥 Check-Ins", len(check_in_df) if not check_in_df.empty else 0)
            with col3:
                st.metric("📤 Check-Outs", len(check_out_df) if not check_out_df.empty else 0)
            with col4:
                st.metric("📊 Current Stock", len(current_stock_df) if not current_stock_df.empty else 0)
            with col5:
                if not check_in_df.empty and not check_out_df.empty:
                    net_movement = len(check_in_df) - len(check_out_df)
                    st.metric("📈 Net Movement", net_movement, delta=f"{net_movement:+d}")
            
            # Define parse_date_safe function once
            def parse_date_safe(date_str):
                if pd.isna(date_str) or date_str == '' or date_str == 'nan' or date_str == 'None' or date_str == 'NaT':
                    return None
                try:
                    return pd.to_datetime(date_str, format='%Y-%m-%d', errors='coerce')
                except:
                    try:
                        return pd.to_datetime(date_str, format='%Y-%m-%d %H:%M:%S', errors='coerce')
                    except:
                        try:
                            return pd.to_datetime(date_str, format='mixed', errors='coerce')
                        except:
                            return None
            
            # --- CHECK-IN ANALYSIS ---
            if not check_in_df.empty:
                st.markdown("#### 📥 Check-In Analysis")
                
                # Print column names to console for debugging (hidden from UI)
                print("Check-In Columns:", list(check_in_df.columns))
                
                # Find date column - try multiple approaches
                date_col_in = None
                for col in check_in_df.columns:
                    if 'date' in col.lower():
                        date_col_in = col
                        break
                
                # Find item column
                item_col_in = None
                for col in check_in_df.columns:
                    if 'item' in col.lower() or 'product' in col.lower() or 'name' in col.lower():
                        item_col_in = col
                        break
                
                # If still not found, try the first column (often it's the item column)
                if item_col_in is None and len(check_in_df.columns) > 0:
                    # Check if first column looks like item names (contains text)
                    first_col = check_in_df.columns[0]
                    if check_in_df[first_col].dtype == 'object':
                        item_col_in = first_col
                
                # Debug output in UI
                #with st.expander("🔍 Debug: Check-In Data Info"):
                #    st.write(f"**Columns found:** {list(check_in_df.columns)}")
                #    st.write(f"**Date column used:** {date_col_in}")
                #    st.write(f"**Item column used:** {item_col_in}")
                #    st.write(f"**Total rows:** {len(check_in_df)}")
                #    st.write("**Sample data (first 3 rows):**")
                #    st.dataframe(check_in_df.head(3))
                
                if date_col_in:
                    try:
                        # Parse dates for check-in
                        check_in_df['DATE_STR'] = check_in_df[date_col_in].astype(str).str.strip()
                        check_in_df['DATE'] = check_in_df['DATE_STR'].apply(parse_date_safe)
                        check_in_df = check_in_df.dropna(subset=['DATE'])
                        
                        if not check_in_df.empty:
                            check_in_df['MONTH'] = check_in_df['DATE'].dt.to_period('M')
                            
                            # Monthly check-ins
                            monthly_checkins = check_in_df.groupby('MONTH').size().reset_index(name='Check-In Count')
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown("##### 📈 Monthly Check-In Trends")
                                if not monthly_checkins.empty:
                                    monthly_checkins['MONTH_STR'] = monthly_checkins['MONTH'].astype(str)
                                    fig_checkin = px.line(
                                        monthly_checkins,
                                        x='MONTH_STR',
                                        y='Check-In Count',
                                        title='Monthly Check-Ins (Receipts/Incoming)',
                                        markers=True
                                    )
                                    st.plotly_chart(fig_checkin, use_container_width=True)
                                else:
                                    st.info("No monthly check-in data")
                            
                            with col2:
                                st.markdown("##### 🏆 Top Received Items")
                                if item_col_in:
                                    # Get value counts and clean data
                                    top_checkins = check_in_df[item_col_in].value_counts().head(10)
                                    top_checkins = top_checkins[top_checkins.index.notna()]
                                    top_checkins = top_checkins[top_checkins.index != '']
                                    top_checkins = top_checkins[top_checkins.index != 'nan']
                                    
                                #    st.write(f"**Debug: Found {len(top_checkins)} unique items in check-in data**")
                                    
                                    if not top_checkins.empty:
                                        fig_top_in = px.bar(
                                            x=top_checkins.values,
                                            y=top_checkins.index,
                                            title='Top 10 Most Received Items',
                                            labels={'x': 'Receipt Count', 'y': 'Item Name'},
                                            orientation='h'
                                        )
                                        fig_top_in.update_layout(height=400)
                                        st.plotly_chart(fig_top_in, use_container_width=True)
                                    else:
                                        st.info("No item data available for check-ins")
                                else:
                                    st.warning("No item column found. Available columns: " + ", ".join(list(check_in_df.columns)))
                    except Exception as e:
                        st.warning(f"Could not process check-in data: {e}")
                else:
                    st.warning("No date column found in check-in data")
            
            # --- CHECK-OUT ANALYSIS ---
            if not check_out_df.empty:
                st.markdown("#### 📤 Check-Out Analysis")
                
                # Find date and item columns for check-out
                date_col_out = None
                for col in check_out_df.columns:
                    if 'date' in col.lower():
                        date_col_out = col
                        break
                
                item_col_out = None
                for col in check_out_df.columns:
                    if 'item' in col.lower() or 'product' in col.lower() or 'name' in col.lower():
                        item_col_out = col
                        break
                
                if item_col_out is None and len(check_out_df.columns) > 0:
                    first_col = check_out_df.columns[0]
                    if check_out_df[first_col].dtype == 'object':
                        item_col_out = first_col
                
                if date_col_out:
                    try:
                        # Parse dates for check-out
                        check_out_df['DATE_STR'] = check_out_df[date_col_out].astype(str).str.strip()
                        check_out_df['DATE'] = check_out_df['DATE_STR'].apply(parse_date_safe)
                        check_out_df = check_out_df.dropna(subset=['DATE'])
                        
                        if not check_out_df.empty:
                            check_out_df['MONTH'] = check_out_df['DATE'].dt.to_period('M')
                            check_out_df['WEEKDAY'] = check_out_df['DATE'].dt.day_name()
                            
                            # Monthly check-outs
                            monthly_checkouts = check_out_df.groupby('MONTH').size().reset_index(name='Check-Out Count')
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown("##### 📈 Monthly Check-Out Trends")
                                if not monthly_checkouts.empty:
                                    monthly_checkouts['MONTH_STR'] = monthly_checkouts['MONTH'].astype(str)
                                    fig_checkout = px.line(
                                        monthly_checkouts,
                                        x='MONTH_STR',
                                        y='Check-Out Count',
                                        title='Monthly Check-Outs (Issues/Usage)',
                                        markers=True
                                    )
                                    st.plotly_chart(fig_checkout, use_container_width=True)
                                else:
                                    st.info("No monthly check-out data")
                            
                            with col2:
                                st.markdown("##### 🏆 Top Used Items")
                                if item_col_out:
                                    top_checkouts = check_out_df[item_col_out].value_counts().head(10)
                                    top_checkouts = top_checkouts[top_checkouts.index.notna()]
                                    top_checkouts = top_checkouts[top_checkouts.index != '']
                                    top_checkouts = top_checkouts[top_checkouts.index != 'nan']
                                    
                                    if not top_checkouts.empty:
                                        fig_top_out = px.bar(
                                            x=top_checkouts.values,
                                            y=top_checkouts.index,
                                            title='Top 10 Most Used Items',
                                            labels={'x': 'Usage Count', 'y': 'Item Name'},
                                            orientation='h'
                                        )
                                        fig_top_out.update_layout(height=400)
                                        st.plotly_chart(fig_top_out, use_container_width=True)
                                    else:
                                        st.info("No item data available for check-outs")
                                else:
                                    st.warning("No item column found in check-out data")
                    except Exception as e:
                        st.warning(f"Could not process check-out data: {e}")
                else:
                    st.warning("No date column found in check-out data")
            
            # --- COMPARISON: CHECK-IN vs CHECK-OUT ---
            if not check_in_df.empty and not check_out_df.empty and 'MONTH' in check_in_df.columns and 'MONTH' in check_out_df.columns:
                st.markdown("#### 📊 Check-In vs Check-Out Comparison")
                
                try:
                    checkin_monthly = check_in_df.groupby('MONTH').size().reset_index(name='Check-Ins')
                    checkout_monthly = check_out_df.groupby('MONTH').size().reset_index(name='Check-Outs')
                    
                    comparison = pd.merge(checkin_monthly, checkout_monthly, on='MONTH', how='outer').fillna(0)
                    comparison['MONTH_STR'] = comparison['MONTH'].astype(str)
                    comparison['Net'] = comparison['Check-Ins'] - comparison['Check-Outs']
                    
                    fig_comparison = go.Figure()
                    fig_comparison.add_trace(go.Bar(
                        x=comparison['MONTH_STR'],
                        y=comparison['Check-Ins'],
                        name='Check-Ins',
                        marker_color='#2ecc71'
                    ))
                    fig_comparison.add_trace(go.Bar(
                        x=comparison['MONTH_STR'],
                        y=comparison['Check-Outs'],
                        name='Check-Outs',
                        marker_color='#e74c3c'
                    ))
                    fig_comparison.update_layout(
                        title='Monthly Check-Ins vs Check-Outs',
                        xaxis_title='Month',
                        yaxis_title='Count',
                        barmode='group',
                        height=400
                    )
                    st.plotly_chart(fig_comparison, use_container_width=True)
                    
                    total_net = comparison['Net'].sum()
                    st.metric(
                        "📊 Net Total Movement",
                        f"{total_net:+.0f}",
                        delta=f"{total_net:+.0f}"
                    )
                except Exception as e:
                    st.warning(f"Could not create comparison chart: {e}")
            
            # --- SECTION 2: DEMAND FORECAST FOR ALL ITEMS ---
            st.divider()
            st.markdown("### 🔮 Demand Forecast for All Items")
            
            if not check_out_df.empty and 'DATE' in check_out_df.columns:
                # Find item column
                item_col = None
                for col in check_out_df.columns:
                    if 'item' in col.lower() or 'product' in col.lower() or 'name' in col.lower():
                        item_col = col
                        break
                
                # Find quantity column
                qty_col = None
                for col in check_out_df.columns:
                    if 'quantity' in col.lower() or 'qty' in col.lower():
                        qty_col = col
                        break
                
                if item_col and qty_col:
                    items_with_history = check_out_df[item_col].dropna().unique().tolist()
                    items_with_history = [x for x in items_with_history if x != '' and x != 'nan']
                    
                    if items_with_history:
                        selected_item = st.selectbox(
                            "Select Item for Demand Forecast",
                            sorted(items_with_history),
                            key="forecast_item"
                        )
                        
                        if selected_item:
                            item_history = check_out_df[check_out_df[item_col] == selected_item].copy()
                            
                            if not item_history.empty and 'DATE' in item_history.columns and qty_col:
                                try:
                                    item_history[qty_col] = pd.to_numeric(item_history[qty_col], errors='coerce')
                                    item_history = item_history.dropna(subset=[qty_col])
                                    
                                    if not item_history.empty:
                                        daily_demand = item_history.groupby('DATE')[qty_col].sum().reset_index()
                                        daily_demand.columns = ['Date', 'Order_Quantity_kg']
                                        
                                        daily_demand['Order_Quantity_kg'] = pd.to_numeric(daily_demand['Order_Quantity_kg'], errors='coerce')
                                        daily_demand = daily_demand.dropna()
                                        
                                        if len(daily_demand) >= 5 and daily_demand['Order_Quantity_kg'].sum() > 0:
                                            with st.spinner(f"Generating forecast for {selected_item}..."):
                                                fig_forecast, forecast_values, model_forecasts, accuracy = create_ensemble_forecast(
                                                    daily_demand,
                                                    forecast_days=30
                                                )
                                                
                                                if fig_forecast:
                                                    st.plotly_chart(fig_forecast, use_container_width=True)
                                                    
                                                    col1, col2, col3 = st.columns(3)
                                                    with col1:
                                                        total_forecast = np.sum(forecast_values) if len(forecast_values) > 0 else 0
                                                        st.metric("📊 Total Forecasted Demand (30 days)", f"{total_forecast:,.0f}")
                                                    with col2:
                                                        avg_daily = np.mean(forecast_values) if len(forecast_values) > 0 else 0
                                                        st.metric("📈 Average Daily Demand", f"{avg_daily:.1f}")
                                                    with col3:
                                                        st.metric("🎯 Forecast Accuracy", f"{100-accuracy*100:.1f}%")
                                                    
                                                    with st.expander("🔬 View Model Performance"):
                                                        for model_name, daily_avg in model_forecasts.items():
                                                            st.metric(model_name, f"{daily_avg:.1f} units/day")
                                                else:
                                                    st.warning("Could not generate forecast for this item.")
                                        else:
                                            st.warning(f"Not enough data for {selected_item}. Need at least 5 positive values.")
                                    else:
                                        st.warning("No valid quantity data after cleaning")
                                except Exception as e:
                                    st.warning(f"Error processing data: {e}")
                            else:
                                st.warning("No quantity data available for this item.")
                    else:
                        st.info("No items with check-out history found.")
                else:
                    st.info(f"Missing required columns. Item column: {item_col}, Quantity column: {qty_col}")
            else:
                st.info("No check-out data available for forecasting.")
            
            # --- SECTION 3: COST OPTIMIZATION FOR ALL ITEMS ---
            st.divider()
            st.markdown("### 💰 Cost Optimization for All Items")
            
            if 'UNIT PRICE' in stock_df.columns and 'QUANTITY' in stock_df.columns:
                cost_df = stock_df.copy()
                cost_df['QUANTITY'] = pd.to_numeric(cost_df['QUANTITY'], errors='coerce')
                cost_df['UNIT PRICE'] = pd.to_numeric(cost_df['UNIT PRICE'], errors='coerce')
                cost_df = cost_df.dropna(subset=['QUANTITY', 'UNIT PRICE'])
                
                if not cost_df.empty:
                    cost_df['TOTAL_VALUE'] = cost_df['QUANTITY'] * cost_df['UNIT PRICE']
                    cost_df['ANNUAL_DEMAND'] = cost_df['QUANTITY'] * 12
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        order_cost = st.number_input(
                            "Ordering Cost (KSh)", 
                            value=float(constants.TRANSPORT_COST), 
                            step=100.0,
                            key="cost_analysis_order_cost"
                        )
                    with col2:
                        holding_rate = st.number_input(
                            "Holding Rate (%)", 
                            value=float(constants.HOLDING_RATE * 100), 
                            step=0.5,
                            key="cost_analysis_holding_rate"
                        ) / 100
                    
                    if st.button("📊 Run Cost Analysis", key="run_cost_analysis"):
                        cost_results = []
                        for _, row in cost_df.iterrows():
                            try:
                                if row['UNIT PRICE'] > 0 and row['QUANTITY'] > 0 and row['ANNUAL_DEMAND'] > 0:
                                    eoq = math.sqrt((2 * row['ANNUAL_DEMAND'] * order_cost) / (holding_rate * row['UNIT PRICE']))
                                    
                                    if row['QUANTITY'] > 0 and eoq > 0:
                                        current_total_cost = (row['ANNUAL_DEMAND'] / row['QUANTITY']) * order_cost + (row['QUANTITY'] / 2) * holding_rate * row['UNIT PRICE']
                                        optimal_total_cost = (row['ANNUAL_DEMAND'] / eoq) * order_cost + (eoq / 2) * holding_rate * row['UNIT PRICE']
                                        
                                        cost_results.append({
                                            'Item': row.get('ITEM_NAME', 'Unknown'),
                                            'Category': row.get('ITEM_CATEGORY', 'Uncategorized'),
                                            'Current Stock': row['QUANTITY'],
                                            'Unit Price': row['UNIT PRICE'],
                                            'Annual Demand': row['ANNUAL_DEMAND'],
                                            'EOQ': eoq,
                                            'Current Cost': current_total_cost,
                                            'Optimal Cost': optimal_total_cost,
                                            'Potential Savings': current_total_cost - optimal_total_cost if current_total_cost > optimal_total_cost else 0
                                        })
                            except:
                                pass
                        
                        if cost_results:
                            cost_df_results = pd.DataFrame(cost_results)
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("📦 Items Analyzed", len(cost_df_results))
                            with col2:
                                total_savings = cost_df_results['Potential Savings'].sum()
                                st.metric("💰 Total Potential Savings", f"KSh {total_savings:,.0f}")
                            with col3:
                                avg_savings = cost_df_results['Potential Savings'].mean()
                                st.metric("📊 Avg Savings per Item", f"KSh {avg_savings:,.0f}")
                            with col4:
                                items_with_savings = len(cost_df_results[cost_df_results['Potential Savings'] > 0])
                                st.metric("✅ Items with Savings", items_with_savings)
                            
                            st.dataframe(cost_df_results, use_container_width=True, hide_index=True)
                            
                            csv = cost_df_results.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download Cost Analysis Results",
                                data=csv,
                                file_name=f"cost_analysis_all_items_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime='text/csv'
                            )
                            
                            st.divider()
                            st.markdown("#### 🏆 Top 10 Items with Highest Potential Savings")
                            top_savings = cost_df_results.sort_values('Potential Savings', ascending=False).head(10)
                            if not top_savings.empty:
                                st.dataframe(
                                    top_savings[['Item', 'Category', 'Current Cost', 'Optimal Cost', 'Potential Savings']],
                                    use_container_width=True,
                                    hide_index=True
                                )
                            
                            st.divider()
                            st.markdown("#### 📊 Cost Savings by Category")
                            category_cost_summary = cost_df_results.groupby('Category').agg({
                                'Item': 'count',
                                'Potential Savings': 'sum'
                            }).reset_index()
                            category_cost_summary.columns = ['Category', 'Items', 'Total Savings']
                            st.dataframe(category_cost_summary, use_container_width=True, hide_index=True)
                            
                            fig_savings = px.bar(
                                category_cost_summary,
                                x='Category',
                                y='Total Savings',
                                title='Potential Savings by Category',
                                color='Category',
                                height=400,
                                labels={'Total Savings': 'Savings (KSh)'}
                            )
                            fig_savings.update_layout(showlegend=False)
                            st.plotly_chart(fig_savings, use_container_width=True)
                        else:
                            st.warning("No valid cost results generated. Please check your data.")
                else:
                    st.warning("No valid data with both quantity and price found.")
            else:
                st.warning("Required columns (UNIT PRICE, QUANTITY) not found in stock data.")
        else:
            st.warning("No stock data found.")

    with tab_inventory_visual:  
        st.markdown("### 📦 Visual Inventory Dashboard")
        
        # Try to load from Google Sheets first
        inventory_items = {}
        try:
            gsheet = GoogleSheetReader()
            if gsheet.authenticate():
                stock_df = gsheet.get_stock_with_pricing()
                if not stock_df.empty:
                    for _, row in stock_df.iterrows():
                        try:
                            item_name = row.get('ITEM_NAME', 'Unknown')
                            if not item_name or str(item_name).strip() == '':
                                continue
                            
                            # Safe conversion for stock
                            stock_val = row.get('QUANTITY', 0)
                            if pd.isna(stock_val) or str(stock_val).strip() == '':
                                stock = 0
                            else:
                                try:
                                    stock = float(stock_val)
                                except (ValueError, TypeError):
                                    stock = 0
                            
                            # Safe conversion for reorder
                            reorder_val = row.get('REORDER LEVEL', 0)
                            if pd.isna(reorder_val) or str(reorder_val).strip() == '':
                                reorder = stock * 0.5
                            else:
                                try:
                                    reorder = float(reorder_val)
                                except (ValueError, TypeError):
                                    reorder = stock * 0.5
                            
                            # Safe conversion for price
                            price_val = row.get('UNIT PRICE', 0)
                            if pd.isna(price_val) or str(price_val).strip() == '':
                                price = 0
                            else:
                                try:
                                    price = float(price_val)
                                except (ValueError, TypeError):
                                    price = 0
                            
                            # Skip items with zero or negative stock
                            if stock <= 0:
                                continue
                            
                            # Map icons based on category
                            icon_map = {
                                'Dry Ice': '🧊',
                                'Chemicals': '🧪',
                                'Packaging': '📦',
                                'Equipment': '⚙️',
                                'Safety': '🛡️',
                                'Default': '📦'
                            }
                            category = row.get('ITEM_CATEGORY', 'Default')
                            if pd.isna(category) or str(category).strip() == '':
                                category = 'Default'
                            icon = icon_map.get(category, icon_map['Default'])
                            
                            inventory_items[item_name] = {
                                'icon': icon,
                                'stock': stock,
                                'reorder': reorder,
                                'max': max(stock * 2, reorder * 3, 100),
                                'unit': row.get('UNIT_OF_MEASURE', 'kg') if not pd.isna(row.get('UNIT_OF_MEASURE', 'kg')) else 'kg',
                                'category': category if category else 'Uncategorized',
                                'location': 'Warehouse',
                                'price': price
                            }
                        except Exception as e:
                            # Skip problematic rows
                            continue
                    
                    # If no valid items were loaded, use sample data
                    if not inventory_items:
                        st.info("No valid inventory items found in Google Sheets. Using sample data.")
                        inventory_items = get_sample_inventory_data()
                else:
                    inventory_items = get_sample_inventory_data()
            else:
                inventory_items = get_sample_inventory_data()
        except Exception as e:
            st.warning(f"Could not load from Google Sheets: {e}. Using sample data.")
            inventory_items = get_sample_inventory_data()
        
        # If inventory_items is still empty (shouldn't happen), use sample data
        if not inventory_items:
            inventory_items = get_sample_inventory_data()
        
        # Add filters
        search, category_filter, show_low_stock = inventory_filters(inventory_items)
        
        # Apply filters
        filtered_items = {}
        for item, details in inventory_items.items():
            # Search filter
            if search and search.lower() not in item.lower():
                continue
            
            # Category filter
            if category_filter != 'All' and details.get('category', 'Uncategorized') != category_filter:
                continue
            
            # Low stock filter
            if show_low_stock and details.get('stock', 0) >= details.get('reorder', 0):
                continue
            
            filtered_items[item] = details
        
        # Show stats
        inventory_stats_summary(filtered_items)
        
        st.markdown("---")
        
        # Show the grid
        if filtered_items:
            visual_inventory_grid(filtered_items, columns=3)
        else:
            st.info("No items match your filters")
        
        # ============================================================
        # 🎨 HEAT MAP EXPANDER
        # ============================================================
        st.markdown("---")
        
        with st.expander("🔥 View Inventory Heat Map", expanded=False):
            st.markdown("""
            <div style="
                background: rgba(255,255,255,0.05);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 15px;
                margin-bottom: 15px;
                border: 1px solid rgba(255,255,255,0.08);
            ">
                <div style="color: #888; font-size: 13px;">
                    Color-coded overview of inventory stock levels. 
                    <span style="color: #dc3545;">🔴 Critical</span> | 
                    <span style="color: #ff9800;">🟠 Low Stock</span> | 
                    <span style="color: #4caf50;">🟢 Good</span> | 
                    <span style="color: #2196f3;">🔵 Overstocked</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Use the filtered_items from the visual inventory
            if filtered_items:
                # Create heatmap data from filtered items
                heatmap_data = []
                for item_name, details in filtered_items.items():
                    stock = details.get('stock', 0)
                    reorder = details.get('reorder', 0)
                    eoq = details.get('max', stock * 2)
                    
                    if stock <= 0:
                        status = 'Critical'
                    elif stock < reorder:
                        status = 'Low'
                    elif stock >= reorder and stock < eoq:
                        status = 'Good'
                    else:
                        status = 'Overstocked'
                    
                    heatmap_data.append({
                        'Item': item_name,
                        'Stock': stock,
                        'Reorder': reorder,
                        'EOQ': eoq,
                        'Status': status,
                        'Category': details.get('category', 'Uncategorized'),
                        'Unit': details.get('unit', 'kg')
                    })
                
                # Add heat map specific filters
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    heatmap_search = st.text_input(
                        "🔍 Search Items",
                        placeholder="Type item name...",
                        key="heatmap_search"
                    )
                with col2:
                    # Get unique statuses for filter
                    status_options = ['All'] + sorted(set(item['Status'] for item in heatmap_data))
                    heatmap_status = st.selectbox(
                        "📊 Status",
                        status_options,
                        key="heatmap_status_filter"
                    )
                with col3:
                    # Get unique categories for filter
                    cat_options = ['All'] + sorted(set(item['Category'] for item in heatmap_data))
                    heatmap_category = st.selectbox(
                        "📂 Category",
                        cat_options,
                        key="heatmap_category_filter"
                    )
                
                # Apply heat map filters
                filtered_heatmap = []
                for item in heatmap_data:
                    if heatmap_search and heatmap_search.lower() not in item['Item'].lower():
                        continue
                    if heatmap_status != 'All' and item['Status'] != heatmap_status:
                        continue
                    if heatmap_category != 'All' and item['Category'] != heatmap_category:
                        continue
                    filtered_heatmap.append(item)
                
                # Convert back to dict
                heatmap_items = {}
                for item in filtered_heatmap:
                    heatmap_items[item['Item']] = {
                        'stock': item['Stock'],
                        'reorder': item['Reorder'],
                        'max': item['EOQ'],
                        'unit': item['Unit'],
                        'category': item['Category']
                    }
                
                if heatmap_items:
                    inventory_heatmap(heatmap_items, title="Inventory Stock Levels", columns=6)
                else:
                    st.info("No items match your heat map filters")
            else:
                st.info("No inventory items to display in heat map")
        
        # ============================================================
        # 🎨 REPLENISHMENT RECOMMENDATIONS EXPANDER (ADD THIS)
        # ============================================================
        st.markdown("---")
        
        with st.expander("🛒 View Replenishment Recommendations", expanded=False):
            st.markdown("""
            <div style="
                background: rgba(255,255,255,0.05);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 15px;
                margin-bottom: 15px;
                border: 1px solid rgba(255,255,255,0.08);
            ">
                <div style="color: #888; font-size: 13px;">
                    Smart replenishment suggestions based on current stock levels.
                    <span style="color: #dc3545;">🔴 Urgent (≤3 days)</span> | 
                    <span style="color: #ffc107;">🟡 Medium (4-7 days)</span> | 
                    <span style="color: #28a745;">🟢 Low (>7 days)</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Use the filtered_items from the visual inventory
            if filtered_items:
                # Generate recommendations
                recommendations_df = get_replenishment_recommendations(filtered_items)
                
                # Show summary and recommendations
                if not recommendations_df.empty:
                    summary = get_replenishment_summary(recommendations_df)
                    show_replenishment_summary_cards(summary)
                    st.markdown("---")
                    show_replenishment_suggestions(recommendations_df)
                    
                    # Export button
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        csv = recommendations_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Recommendations",
                            data=csv,
                            file_name=f"replenishment_recommendations_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime='text/csv'
                        )
                    with col2:
                        st.caption("Download recommendations as CSV for offline review or sharing")
                else:
                    st.success("✅ All items are well-stocked. No replenishment needed at this time.")
            else:
                st.info("No inventory items to analyze for replenishment")      

    with tab1:
        if not df.empty:
            st.markdown("""
            <h2 style='border-bottom: 1px solid #ddd; padding-bottom: 10px;'>
            Order Pattern & Cost Analysis
            </h2>
            """, unsafe_allow_html=True)
            with st.expander("Visual Analysis", expanded=not mobile_ui.should_collapse_advanced()):
                col1, col2 = st.columns(2)
                with col1:
                    fig_orders = mobile_ui.optimize_chart_for_mobile(fig_orders)
                    st.plotly_chart(fig_orders, use_container_width=True,
                        config=mobile_ui.get_mobile_chart_config())
                with col2:
                    fig_cost_overview = mobile_ui.optimize_chart_for_mobile(fig_cost_overview)
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
                    if eoq > 0:
                        order_frequency_reduction = ((kpis.get('order_frequency', 0) - (kpis.get('current_monthly_volume', 0) / eoq)) / kpis.get('order_frequency', 1) * 100)
                        st.metric("Order frequency reduction", f"{order_frequency_reduction:.1f}%")

                        current_turns = kpis.get('current_monthly_volume', 0) / (kpis.get('avg_order_size', 1)/2)
                        eoq_turns = 1.3
                        inventory_turns_improvement = eoq_turns - current_turns
                        st.metric("Inventory Turns Change", f"{inventory_turns_improvement:+.1f}x")

                    annual_savings = monthly_savings * 12
                    implementation_cost = 5000
                    roi = (annual_savings / implementation_cost) * 100 if implementation_cost > 0 else float('inf')
                    st.metric("Estimated ROI", f"{roi:.0f}%", help="Return on investment from implementing optimizations")
        else:
            st.warning("📊 No order data exists for this analysis period.")
            st.info("Use the 'Record Receipt' button in the sidebar to add the first order for this period.")

    with tab2:
        if not df.empty:
            st.markdown("### 🔮 30-Day Demand Forecast")

            # The forecast figure is now generated in the main block. We just display it here.
            if not fig_ensemble:
                st.warning("Unable to generate forecast. Please check data quality or model configurations.")
            else:
                fig_ensemble = mobile_ui.optimize_chart_for_mobile(fig_ensemble)
                st.plotly_chart(fig_ensemble, use_container_width=True,
                    config=mobile_ui.get_mobile_chart_config())
            # --- SPACING ---
            st.markdown("<br>", unsafe_allow_html=True)  # Add vertical space

            # --- Core Forecast Metrics ---
            adjusted_total_demand = total_forecasted_demand * sublimation_factor
            avg_daily_forecast = np.mean(ensemble_forecast_values)

            st.markdown("---")  # <- ADD THIS DIVIDER
            st.markdown("#### 📈 Forecast Summary (Next 30 Days)")
            summary_cols = st.columns(4)
            with summary_cols[0]:
                st.metric(
                    label="Total Forecasted Demand",
                    value=f"{total_forecasted_demand:,.0f} kg",
                    help="The total expected demand based on the ensemble model."
                )
            with summary_cols[1]:
                st.metric(
                    label="Required Purchase Volume",
                    value=f"{adjusted_total_demand:,.0f} kg",
                    delta=f"+{total_forecasted_demand * avg_sublimation:,.0f} kg",
                    help=f"The volume you need to buy to compensate for a {avg_sublimation:.1%} sublimation loss."
                )
            with summary_cols[2]:
                st.metric(
                    label="Average Daily Demand",
                    value=f"{avg_daily_forecast:,.1f} kg/day",
                    help="The average demand expected per day over the next 30 days."
                )
            with summary_cols[3]:
                st.metric(
                    label="Forecast Accuracy",
                    value=f"{100-backtest_accuracy*100:.1f}%",
                    help="Model accuracy (1-MAPE) based on backtesting on historical data."
                )

            # --- SPACING ---
            st.markdown("<br>", unsafe_allow_html=True)

            # --- Probabilistic Forecast for Risk Management ---
            st.markdown("---")
            st.markdown("#### 📊 Risk-Based Demand Scenarios")
            st.markdown("Instead of a single number, it's better to plan for a range of possibilities. This shows a likely scenario versus a high-demand (worst-case) scenario.")

            p50_total_demand = total_forecasted_demand
            p90_total_demand = total_forecasted_demand + (1.282 * forecast_std_dev * np.sqrt(30))

            risk_cols = st.columns(2)
            with risk_cols[0]:
                with st.container():
                    st.markdown("""
                    <div style='background-color:#d1ecf1; padding:15px; border-radius:8px; min-height:160px;'>
                    <strong>📊 Likely Scenario (50th Percentile)</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    st.metric(
                        label="Likely Monthly Demand",
                        value=f"~{p50_total_demand:,.0f} kg"
                    )
                    st.caption("There is a 50% chance demand will be at or below this level.")
            with risk_cols[1]:
                with st.container():
                    st.markdown("""
                    <div style='background-color:#fff3cd; padding:15px; border-radius:8px; min-height:160px;'>
                    <strong>⚠️ High-Demand Scenario (90th Percentile)</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    st.metric(
                        label="Worst-Case Monthly Demand",
                        value=f"~{p90_total_demand:,.0f} kg"
                    )
                    st.caption("There is a 10% chance demand will exceed this level. Use this for setting safety stock and risk buffers.")

            # --- SPACING ---
            st.markdown("<br>", unsafe_allow_html=True)

            # --- Individual Model Breakdown ---
            with st.expander("🔬 View Individual Model Performance", expanded=not mobile_ui.should_collapse_advanced()):
                st.markdown("The final forecast is a weighted average of these underlying models.")
                model_cols = st.columns(len(model_forecasts))
                for i, (model_name, daily_avg) in enumerate(model_forecasts.items()):
                    with model_cols[i]:
                        st.metric(
                            label=model_name,
                            value=f"{daily_avg:.1f} kg/day",
                            help=f"The average daily forecast from the {model_name} model."
                        )
        else:
            st.warning("🔮 Cannot generate a forecast without historical data for this period.")
            st.info("Please record some receipts to build up an order history.")

    with tab3:
        if not df.empty:
            st.markdown("### 📦 Proactive Inventory Policy")
            st.success("✅ Inventory policy is dynamically calculated using the live forecast data from Tab 2.")
            
            #st.markdown("### ❄️ Inventory Optimization Formulas")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### Economic Order Quantity (EOQ)")
            #    st.latex(r'\text{EOQ} = \sqrt{\frac{2 \times D \times S}{H \times C}}')
            #    st.latex(r'D_{\text{adj}} = %.1f \times %.4f = %.1f' % (monthly_demand_input, sublimation_factor, adjusted_demand))
            #    st.latex(r'\text{EOQ} = \sqrt{\frac{2 \times %.1f \times %.2f}{%.2f \times %.2f}} = %.1f \text{ kg}' % (adjusted_demand, constants.TRANSPORT_COST, constants.HOLDING_RATE, constants.PRICE_PER_KG, eoq))

                st.markdown("**Where:**")
                st.markdown(f"<span style='color:green;'>- D = Forecasted Monthly Demand = {monthly_demand_input:,.1f} kg</span>", unsafe_allow_html=True)
                st.write(f"- S = Ordering Cost = KSh {constants.TRANSPORT_COST:,.2f}")
                st.write(f"- H = Holding Rate = {constants.HOLDING_RATE*100:.1f}%")
                st.write(f"- C = Unit Cost = KSh {constants.PRICE_PER_KG:.2f}/kg")
                st.markdown(f"<p style='color:green; font-weight:bold;'>Result: EOQ = {eoq:.1f} kg</p>", unsafe_allow_html=True)

            with col2:
                st.markdown("#### Safety Stock")
            #    st.latex(r'\text{SS} = z \cdot \sigma_{\text{demand}} \cdot \sqrt{LT} \cdot (1 + \text{sublimation})')
            #    st.latex(r'= %.2f \times %.1f \times \sqrt{%d} \times %.4f = %.1f \text{ kg}' % (z_score, demand_stddev_input, constants.LEAD_TIME_DAYS, sublimation_factor, safety_stock))

                st.markdown("**Where:**")
                st.write(f"- z = Z-score ({constants.SERVICE_LEVEL*100:.0f}%) = {z_score:.2f}")
                st.markdown(f"<span style='color:green;'>- σ = Forecast Demand Std Dev = {demand_stddev_input:,.1f} kg</span>", unsafe_allow_html=True)
                st.write(f"- LT = Lead Time = {constants.LEAD_TIME_DAYS} days")
                st.write(f"- Sublimation Rate = {avg_sublimation:.2%}")
                st.markdown(f"<p style='color:green; font-weight:bold;'>Result: Safety Stock = {safety_stock:.1f} kg</p>", unsafe_allow_html=True)

            st.markdown("### 🔄 Reorder Point")
            st.markdown(f"**Reorder Point = ({adjusted_demand:.1f}/30 × {constants.LEAD_TIME_DAYS}) + {safety_stock:.1f} = {reorder_point:.1f} kg**")
            st.caption("*This policy is now dynamically updated based on the 30-day demand forecast.*")

            st.markdown("### 📊 Recommended Inventory Policy")
            policy_data = pd.DataFrame({'Metric': ['Economic Order Quantity', 'Safety Stock', 'Reorder Point', 'Maximum Inventory'], 'Value (kg)': [eoq, safety_stock, reorder_point, eoq + safety_stock]})
            st.dataframe(policy_data, use_container_width=True, height=180)

            st.markdown("### 🎯 EOQ Implementation Impact")
            # The savings are now calculated in the main block. We just display them here.
            annual_savings_percentage = (annual_transport_savings / annual_transport_cost) * 100 if annual_transport_cost > 0 else 0

            impact_cols = st.columns(4)
            with impact_cols[0]:
                order_freq_delta_percent = ((eoq_monthly_orders - current_monthly_orders) / current_monthly_orders) * 100 if current_monthly_orders > 0 else 0
                st.metric("Order Frequency Change", f"{eoq_monthly_orders:.1f} orders/month", f"{order_freq_delta_percent:.1f}%")
            with impact_cols[1]:
                # THIS VALUE IS NOW CONSISTENT
                st.metric("Annual Transport Savings", f"KSh {annual_transport_savings:,.0f}", f"{annual_savings_percentage:.1f}% of total")

            implementation_cost = constants.IMPLEMENTATION_COST
            payback_period = implementation_cost / (annual_transport_savings / 12) if annual_transport_savings > 0 else 0
            roi_percentage = (annual_transport_savings / implementation_cost) * 100 if implementation_cost > 0 else 0
            with impact_cols[2]:
                st.metric("Payback Period", f"{payback_period:.1f} months")
            with impact_cols[3]:
                st.metric("Implementation ROI", f"{roi_percentage:.0f}%")

            st.markdown("### 🔄 Current vs. Forecast-Driven System Comparison")
            comparison_data = {
                'Metric': ['Orders per Month', 'Avg. Order Size (kg)', 'Monthly Transport Cost (KSh)', 'Annual Transport Cost (KSh)'],
                'Current System (Historical)': [
                    f"{current_monthly_orders:.1f}", f"{kpis.get('avg_order_size', 0):.0f}",
                    f"{current_monthly_orders * constants.TRANSPORT_COST:,.0f}", f"{annual_transport_cost:,.0f}"
                ],
                'EOQ System (Forecast-Driven)': [
                    f"{eoq_monthly_orders:.1f}", f"{eoq:.0f}",
                    f"{eoq_monthly_orders * constants.TRANSPORT_COST:,.0f}", f"{eoq_monthly_orders * 12 * constants.TRANSPORT_COST:,.0f}"
                ]
            }
            st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, height=185, hide_index=True)

            st.markdown("#### 📈 5-Year Cumulative Savings Projection")
            years = list(range(1, 6))
            cumulative_savings = [annual_transport_savings * year for year in years]
            fig_savings = go.Figure()
            fig_savings.add_trace(go.Scatter(x=years, y=cumulative_savings, name="Cumulative Savings", line=dict(color='#3498db', width=3), mode='lines+markers'))
            fig_savings.add_hline(y=implementation_cost, line_dash="dot", annotation_text="Implementation Cost", line_color="red")
            fig_savings.update_layout(title="Projected Savings from Adopting Forecast-Driven EOQ", xaxis_title="Year", yaxis_title="Cumulative Savings (KSh)", height=mobile_ui.get_chart_height())
            fig_savings = mobile_ui.optimize_chart_for_mobile(fig_savings)
            st.plotly_chart(fig_savings, use_container_width=True,
                config=mobile_ui.get_mobile_chart_config())
                        # --- ITEM-LEVEL OPTIMIZATION FOR ALL INVENTORY ---
            st.divider()
            st.markdown("### 📦 Item-Level Optimization for All Inventory")
            
            with st.expander("🔧 Calculate EOQ for Selected Items", expanded=False):
                # Get stock data with pricing
                try:
                    gsheet = GoogleSheetReader()
                    if gsheet.authenticate():
                        stock_df = gsheet.get_stock_with_pricing()
                        
                        if not stock_df.empty and 'ITEM_NAME' in stock_df.columns and 'UNIT PRICE' in stock_df.columns and 'QUANTITY' in stock_df.columns:
                            # Convert to numeric
                            stock_df['QUANTITY'] = pd.to_numeric(stock_df['QUANTITY'], errors='coerce')
                            stock_df['UNIT PRICE'] = pd.to_numeric(stock_df['UNIT PRICE'], errors='coerce')
                            
                            # Drop rows with missing values
                            stock_df = stock_df.dropna(subset=['QUANTITY', 'UNIT PRICE'])
                            
                            if not stock_df.empty:
                                # Let user select a category or item
                                cat_options = ['All Categories'] + sorted(stock_df['ITEM_CATEGORY'].dropna().unique().tolist())
                                selected_cat = st.selectbox("Select Category", cat_options, key="eoq_category")
                                
                                # Filter items
                                if selected_cat != 'All Categories':
                                    items_df = stock_df[stock_df['ITEM_CATEGORY'] == selected_cat]
                                else:
                                    items_df = stock_df
                                
                                # Show items with EOQ calculation
                                st.markdown("#### EOQ for Selected Items")
                                
                                # Let user set ordering cost and holding rate
                                col1, col2 = st.columns(2)
                                with col1:
                                    order_cost = st.number_input(
                                        "Ordering Cost (KSh)", 
                                        value=float(constants.TRANSPORT_COST), 
                                        step=100.0, 
                                        key="eoq_order_cost"
                                    )
                                with col2:
                                    holding_rate = st.number_input(
                                        "Holding Rate (%)", 
                                        value=float(constants.HOLDING_RATE * 100), 
                                        step=0.5, 
                                        key="eoq_holding_rate"
                                    ) / 100
                                
                                # Calculate EOQ for items
                                if st.button("Calculate EOQ for Items", key="calc_eoq"):
                                    eoq_results = []
                                    for _, row in items_df.iterrows():
                                        if pd.notna(row['UNIT PRICE']) and pd.notna(row['QUANTITY']) and row['QUANTITY'] > 0:
                                            # Estimate annual demand (assuming current stock is monthly demand)
                                            annual_demand = row['QUANTITY'] * 12
                                            unit_price = row['UNIT PRICE']
                                            
                                            if unit_price > 0 and holding_rate > 0:
                                                try:
                                                    eoq = math.sqrt((2 * annual_demand * order_cost) / (holding_rate * unit_price))
                                                    eoq_results.append({
                                                        'Item': row['ITEM_NAME'],
                                                        'Category': row['ITEM_CATEGORY'],
                                                        'Annual Demand': annual_demand,
                                                        'Unit Price': unit_price,
                                                        'EOQ': eoq,
                                                        'Orders/Year': annual_demand / eoq if eoq > 0 else 0
                                                    })
                                                except:
                                                    pass
                                    
                                    if eoq_results:
                                        eoq_df = pd.DataFrame(eoq_results)
                                        st.dataframe(eoq_df, use_container_width=True, hide_index=True)
                                        
                                        # Download EOQ results
                                        csv = eoq_df.to_csv(index=False).encode('utf-8')
                                        st.download_button(
                                            label="📥 Download EOQ Results",
                                            data=csv,
                                            file_name=f"eoq_results_{datetime.now().strftime('%Y%m%d')}.csv",
                                            mime='text/csv'
                                        )
                                        
                                        # Show summary stats
                                        st.markdown("#### EOQ Summary")
                                        col1, col2, col3 = st.columns(3)
                                        with col1:
                                            st.metric("Total Items", len(eoq_df))
                                        with col2:
                                            avg_eoq = eoq_df['EOQ'].mean()
                                            st.metric("Avg EOQ", f"{avg_eoq:.0f}")
                                        with col3:
                                            avg_orders = eoq_df['Orders/Year'].mean()
                                            st.metric("Avg Orders/Year", f"{avg_orders:.1f}")
                                    else:
                                        st.warning("No items with valid price and quantity data found.")
                            else:
                                st.warning("No valid inventory data found. Please check Google Sheets connection.")
                        else:
                            st.warning("Inventory data missing required columns (ITEM_NAME, UNIT PRICE, QUANTITY).")
                except Exception as e:
                                        st.error(f"Error loading inventory data for EOQ calculation: {e}")
            
            # --- BULK EOQ CALCULATION FOR ALL ITEMS ---
            st.divider()
            st.markdown("### 📊 Bulk EOQ Calculation for All Items")
            
            with st.expander("📊 Calculate EOQ for All Inventory Items", expanded=False):
                try:
                    gsheet = GoogleSheetReader()
                    if gsheet.authenticate():
                        stock_df = gsheet.get_stock_with_pricing()
                        
                        if not stock_df.empty and 'ITEM_NAME' in stock_df.columns and 'UNIT PRICE' in stock_df.columns and 'QUANTITY' in stock_df.columns:
                            # Convert to numeric
                            stock_df['QUANTITY'] = pd.to_numeric(stock_df['QUANTITY'], errors='coerce')
                            stock_df['UNIT PRICE'] = pd.to_numeric(stock_df['UNIT PRICE'], errors='coerce')
                            stock_df = stock_df.dropna(subset=['QUANTITY', 'UNIT PRICE'])
                            
                            if not stock_df.empty:
                                # Parameters
                                col1, col2 = st.columns(2)
                                with col1:
                                    order_cost = st.number_input(
                                        "Ordering Cost (KSh)", 
                                        value=float(constants.TRANSPORT_COST), 
                                        step=100.0, 
                                        key="bulk_order_cost"
                                    )
                                with col2:
                                    holding_rate = st.number_input(
                                        "Holding Rate (%)", 
                                        value=float(constants.HOLDING_RATE * 100), 
                                        step=0.5, 
                                        key="bulk_holding_rate"
                                    ) / 100
                                
                                # Category filter
                                cat_options = ['All Categories'] + sorted(stock_df['ITEM_CATEGORY'].dropna().unique().tolist())
                                selected_cat = st.selectbox("Filter by Category", cat_options, key="bulk_category")
                                
                                # Filter items
                                if selected_cat != 'All Categories':
                                    items_df = stock_df[stock_df['ITEM_CATEGORY'] == selected_cat]
                                else:
                                    items_df = stock_df
                                
                                st.caption(f"📊 Calculating EOQ for {len(items_df)} items")
                                
                                if st.button("🚀 Calculate EOQ for All Items", key="bulk_calc_eoq"):
                                    results = []
                                    for _, row in items_df.iterrows():
                                        if row['QUANTITY'] > 0 and row['UNIT PRICE'] > 0 and holding_rate > 0:
                                            annual_demand = row['QUANTITY'] * 12
                                            eoq = math.sqrt((2 * annual_demand * order_cost) / (holding_rate * row['UNIT PRICE']))
                                            current_orders = annual_demand / row['QUANTITY'] if row['QUANTITY'] > 0 else 0
                                            optimal_orders = annual_demand / eoq if eoq > 0 else 0
                                            
                                            results.append({
                                                'Item': row['ITEM_NAME'],
                                                'Category': row['ITEM_CATEGORY'],
                                                'Current Stock': row['QUANTITY'],
                                                'Unit Price': row['UNIT PRICE'],
                                                'Annual Demand': annual_demand,
                                                'EOQ': eoq,
                                                'Current Orders/Year': current_orders,
                                                'Optimal Orders/Year': optimal_orders,
                                                'Potential Savings': (current_orders - optimal_orders) * order_cost if eoq > 0 else 0
                                            })
                                    
                                    if results:
                                        eoq_df = pd.DataFrame(results)
                                        
                                        # Summary metrics
                                        st.divider()
                                        st.markdown("#### 📊 EOQ Summary")
                                        col1, col2, col3, col4 = st.columns(4)
                                        with col1:
                                            st.metric("📦 Total Items", len(eoq_df))
                                        with col2:
                                            total_savings = eoq_df['Potential Savings'].sum()
                                            st.metric("💰 Total Potential Savings", f"KSh {total_savings:,.0f}")
                                        with col3:
                                            avg_eoq = eoq_df['EOQ'].mean()
                                            st.metric("📊 Average EOQ", f"{avg_eoq:.0f}")
                                        with col4:
                                            items_below = len(eoq_df[eoq_df['Current Stock'] < eoq_df['EOQ']])
                                            st.metric("⚠️ Items Below EOQ", items_below)
                                        
                                        # Show full table
                                        st.markdown("#### 📋 Detailed EOQ Results")
                                        st.dataframe(eoq_df, use_container_width=True, hide_index=True)
                                        
                                        # Download button
                                        csv = eoq_df.to_csv(index=False).encode('utf-8')
                                        st.download_button(
                                            label="📥 Download EOQ Results CSV",
                                            data=csv,
                                            file_name=f"bulk_eoq_results_{datetime.now().strftime('%Y%m%d')}.csv",
                                            mime='text/csv'
                                        )
                                        
                                        # Recommendations
                                        st.divider()
                                        st.markdown("#### 📋 Recommendations")
                                        
                                        if items_below > 0:
                                            st.warning(f"⚠️ {items_below} items have stock below EOQ level")
                                            
                                            # Show top 10 items needing attention
                                            low_items = eoq_df[eoq_df['Current Stock'] < eoq_df['EOQ']].sort_values('Potential Savings', ascending=False).head(10)
                                            st.markdown("**Top 10 Items Needing Reorder:**")
                                            st.dataframe(
                                                low_items[['Item', 'Category', 'Current Stock', 'EOQ', 'Potential Savings']],
                                                use_container_width=True,
                                                hide_index=True
                                            )
                                        else:
                                            st.success("✅ All items have stock above EOQ level")
                                            
                                        # Category breakdown
                                        st.divider()
                                        st.markdown("#### 📊 Category Breakdown")
                                        category_summary = eoq_df.groupby('Category').agg({
                                            'Item': 'count',
                                            'Potential Savings': 'sum'
                                        }).reset_index()
                                        category_summary.columns = ['Category', 'Items', 'Total Savings']
                                        st.dataframe(category_summary, use_container_width=True, hide_index=True)
                                    else:
                                        st.warning("No items with valid price and quantity data found.")
                            else:
                                st.warning("No valid inventory data found.")
                        else:
                            st.warning("Inventory data missing required columns.")
                except Exception as e:
                    st.error(f"Error loading inventory data for bulk EOQ calculation: {e}")
                    
        else:
            st.warning("📦 Cannot calculate inventory policy without historical data for this period.")
            st.info("Please record some receipts to build up an order history for inventory optimization.")

    with tab4:
        if not df.empty:
            st.markdown("### 🧮 Detailed Annual Cost Breakdown")
            
            # 1. Core Cost Components Table
            st.markdown("#### 📋 Annual Cost Component Details")
            avg_inventory_for_display = (kpis.get('avg_order_size', 0) / 2) + safety_stock
            cost_components_data = {
                'Component': ['Product Purchase', 'Transport', 'Holding', 'Sublimation Loss', 'Total'],
                'Calculation': [
                    f"{annual_volume:,.0f} kg × KSh {constants.PRICE_PER_KG:.2f}",
                    f"{kpis.get('total_orders', 0):,} orders × KSh {constants.TRANSPORT_COST:,.0f}",
                    f"({avg_inventory_for_display:,.1f} kg avg inv) × KSh {constants.PRICE_PER_KG:.2f} × {constants.HOLDING_RATE * 100:.1f}%",
                    f"{annual_volume:,.0f} kg × {sum(constants.SUB_LOSS_RANGE) / 2:.2f}% loss × KSh {constants.PRICE_PER_KG:.2f}",
                    "Sum of all components"
                ],
                'Annual Cost (KSh)': [
                    annual_product_cost, annual_transport_cost, annual_holding_cost,
                    annual_sublimation_loss, total_annual_spending
                ],
                '% of Total': [
                    (annual_product_cost / total_annual_spending) * 100 if total_annual_spending > 0 else 0,
                    (annual_transport_cost / total_annual_spending) * 100 if total_annual_spending > 0 else 0,
                    (annual_holding_cost / total_annual_spending) * 100 if total_annual_spending > 0 else 0,
                    (annual_sublimation_loss / total_annual_spending) * 100 if total_annual_spending > 0 else 0,
                    100
                ]
            }
            cost_components = pd.DataFrame(cost_components_data)
            st.dataframe(
                    cost_components.style
                    .format({'Annual Cost (KSh)': '{:,.0f}', '% of Total': '{:.1f}%'})
                    .applymap(lambda x: 'font-weight: bold', subset=['Component'])
                    .bar(subset=['Annual Cost (KSh)'], color='#5fba7d'),
                    use_container_width=True,
                    height=220,
                     hide_index=True
                    )

            st.markdown("---")
            st.markdown("#### 📊 Cost Structure Visualization")
            fig_cost_breakdown = make_subplots(
                rows=1, cols=2,
                specs=[[{"type": "pie"}, {"type": "bar"}]],
                subplot_titles=("Cost Distribution", "Cost per kg Analysis"),
                column_widths=[0.5, 0.5]       
            )

            # Trace 1: Pie Chart with labels and percentages
            fig_cost_breakdown.add_trace(go.Pie(
                labels=cost_components['Component'][:-1],
                values=cost_components['Annual Cost (KSh)'][:-1],
                marker_colors=['#3498db','#e74c3c','#f39c12','#2ecc71'],
                textinfo='label+percent',  # Show both label and percentage
                textposition='inside',    # Place text inside slices
                insidetextorientation='radial',  # Curve the text
                textfont=dict(size=12),   # Adjust font size
                hoverinfo='label+percent+value',  # Show details on hover
                domain={'x': [0, 0.45]}
            ), row=1, col=1)

            # Trace 2: Bar Chart (Cost per kg)
            cost_per_kg_data = {
                'Metric': ['Product Cost', 'Transport Cost', 'Holding Cost', 'Sublimation'],
                'Cost per kg (KSh)': [
                    constants.PRICE_PER_KG,
                    annual_transport_cost / annual_volume if annual_volume > 0 else 0,
                    annual_holding_cost / annual_volume if annual_volume > 0 else 0,
                    annual_sublimation_loss / annual_volume if annual_volume > 0 else 0
                ]
            }
            cost_per_kg = pd.DataFrame(cost_per_kg_data)
            fig_cost_breakdown.add_trace(go.Bar(
                x=cost_per_kg['Metric'],
                y=cost_per_kg['Cost per kg (KSh)'],
                marker_color=['#3498db','#e74c3c','#f39c12','#2ecc71'],
                text=cost_per_kg['Cost per kg (KSh)'].round(2),
                textposition='auto'
            ), row=1, col=2)

            fig_cost_breakdown.update_layout(height=400, showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
            fig_cost_breakdown = mobile_ui.optimize_chart_for_mobile(fig_cost_breakdown)
            st.plotly_chart(fig_cost_breakdown, use_container_width=True,
                config=mobile_ui.get_mobile_chart_config())


            st.markdown("---")
            st.markdown("#### 📈 Monthly Cost Trends (KSh)")
            
            df_monthly = df.copy()
            df_monthly['Date'] = pd.to_datetime(df_monthly['Date'])
            df_monthly['Month'] = df_monthly['Date'].dt.to_period('M').dt.strftime('%Y-%b')

            monthly_data = df_monthly.groupby('Month').agg(
                product_cost_ksh=('Total_Cost', 'sum'),
                transport_cost_ksh=('Transport_Cost', 'sum'),
                product_volume_kg=('Order_Quantity_kg', 'sum')
            ).reset_index()

            monthly_data['holding_cost_ksh'] = (monthly_data['product_volume_kg'] / 2) * constants.HOLDING_RATE * constants.PRICE_PER_KG
            monthly_data['sublimation_loss_ksh'] = monthly_data['product_volume_kg'] * avg_sublimation * constants.PRICE_PER_KG
            monthly_data['sublimation_loss_kg'] = monthly_data['product_volume_kg'] * avg_sublimation
            
            monthly_data['Month_dt'] = pd.to_datetime(monthly_data['Month'], format='%Y-%b')
            monthly_data = monthly_data.sort_values('Month_dt')
            
            cost_cols = ['product_cost_ksh', 'transport_cost_ksh', 'holding_cost_ksh', 'sublimation_loss_ksh']
            colors = ['#3498db', '#e74c3c', '#f39c12', '#2ecc71']
            color_map = {col: color for col, color in zip(cost_cols, colors)}

            fig_monthly_cost = px.area(
                monthly_data, x='Month', y=cost_cols,
                title="Monthly Cost Fluctuations (KSh)", 
                labels={'value': 'Cost (KSh)', 'variable': 'Cost Type'},
                color_discrete_map=color_map,
                height=mobile_ui.get_chart_height()  # Use consistent height
                )

            for col, color in zip(cost_cols, colors):
                avg_value = monthly_data[col].mean()
                annotation_label = col.replace('_ksh', '').replace('_', ' ').title()
                fig_monthly_cost.add_hline(y=avg_value, line_dash="dot", line_color=color,
                                        annotation_text=f"Avg {annotation_label}: {avg_value:,.0f}",
                                        annotation_position="bottom right")

            fig_monthly_cost.update_traces(
                mode="lines+markers",
                hovertemplate="<b>%{x}</b><br>%{y:,.0f} KSh<extra></extra>"
            )
            fig_monthly_cost.update_layout(
                hovermode="x unified",
                xaxis_title=None,
                yaxis_title="Cost (KSh)",
                legend_title="Cost Type"
            )

            fig_monthly_cost = mobile_ui.optimize_chart_for_mobile(fig_monthly_cost)
            st.plotly_chart(fig_monthly_cost, use_container_width=True,
                config=mobile_ui.get_mobile_chart_config())
            


            st.markdown("---")
            st.markdown("#### 📊 Monthly Physical Quantities (kg)")
            fig_monthly_volume = px.bar(
            monthly_data, x='Month', y=['product_volume_kg', 'sublimation_loss_kg'],
            title="Monthly Dry Ice Quantities (kg)", labels={'value': 'Quantity (kg)', 'variable': 'Quantity Type'},
            height=400
            )
            fig_monthly_volume = mobile_ui.optimize_chart_for_mobile(fig_monthly_volume)
            st.plotly_chart(fig_monthly_volume, use_container_width=True,
                config=mobile_ui.get_mobile_chart_config())


            # 4. Savings Summary (5-COLUMN LAYOUT)
            st.markdown("---")
            st.markdown("### 💰 Savings Summary")
            
            monthly_transport_savings = annual_transport_savings / 12
            current_monthly_transport_cost = current_monthly_orders * constants.TRANSPORT_COST
            
            monthly_savings_percent = (monthly_transport_savings / current_monthly_transport_cost) * 100 if current_monthly_transport_cost > 0 else 0
            annual_savings_percent = (annual_transport_savings / annual_transport_cost) * 100 if annual_transport_cost > 0 else 0
            implementation_cost = constants.IMPLEMENTATION_COST
            roi_percentage = (annual_transport_savings / implementation_cost) * 100 if implementation_cost > 0 else float('inf')

            savings_cols = st.columns(5)
            with savings_cols[0]:
                st.metric("Monthly Savings", f"KSh {monthly_transport_savings:,.0f}")
            with savings_cols[1]:
                st.metric("Annual Savings", f"KSh {annual_transport_savings:,.0f}")
            with savings_cols[2]:
                st.metric("Monthly Savings %", f"{monthly_savings_percent:.1f}%")
            with savings_cols[3]:
                st.metric("Annual Savings %", f"{annual_savings_percent:.1f}%")
            with savings_cols[4]:
                st.metric("ROI", f"{roi_percentage:.0f}%")

            # ----------------------------------
            # 5. Key Insights & Recommendations
            # ----------------------------------


            st.markdown("---")
            st.markdown("#### 📋 Key Insights & Recommendations")
            st.markdown(f"""
            - **EOQ Implementation**: Save KSh {annual_transport_savings:,.0f} annually on transport costs.
            - **Order Frequency**: Reduce from {current_monthly_orders:.1f} to {eoq_monthly_orders:.1f} orders/month.
            - **Payback Period**: {payback_period:.1f} months to recover implementation costs.
            - **Largest Cost**: Product cost ({(annual_product_cost/total_annual_spending)*100:.1f}% of total).
            - **Loss Prevention**: Sublimation losses cost KSh {annual_sublimation_loss:,.0f} annually.
            """)
        else:
            st.warning("🧮 Cost analysis requires historical order data.")
            st.info("Please add the first order for this period using the 'Record Receipt' button in the sidebar to see the cost breakdown.")

    with tab5:
        st.markdown("### 📋 Strategic Recommendations")

        # Immediate actions
        st.markdown("#### 🎯 Recommended Actions")

        recommendations = [
        f"**Implement optimized ordering quantity:** Order {eoq:.0f} kg per shipment (accounts for {avg_sublimation*100:.2f}% sublimation losses)",
        f"**Maintain safety stock:** Keep minimum inventory of {safety_stock:.0f} kg to buffer against demand variability and sublimation",
        f"**Set reorder point:** Initiate new orders when inventory reaches {reorder_point:.0f} kg",
        f"**Optimize order frequency:** Target {eoq_monthly_orders:.1f} orders per month based on demand patterns"
]

        for recommendation in recommendations:
         st.markdown(f"- {recommendation}", unsafe_allow_html=True)
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

        # Key metrics to monitor (now matching the Current vs EOQ Comparison calculations)
        st.markdown("#### 📊 Key Metrics to Monitor")

        avg_order_size = kpis.get('avg_order_size', 0)
        current_monthly_volume = kpis.get('current_monthly_volume', 0)

        if avg_order_size > 0:
            current_inventory_turnover = f"{current_monthly_volume / (avg_order_size/2):.1f}x/month"
        else:
            current_inventory_turnover = "N/A"

        if eoq > 0:
            target_inventory_turnover = f"{current_monthly_volume / eoq:.1f}x/month"
        else:
            target_inventory_turnover = "N/A"

        metrics_to_track = pd.DataFrame({
            'Metric': [
                'Service Level',
                'Inventory Turnover',
                'Stockout Frequency',
                'Order Frequency',
                'Container Utilization',
                'Total Transport Cost'
            ],
            'Current Value': [
                f"{constants.SERVICE_LEVEL*100:.0f}%",
                current_inventory_turnover,  # <-- FIXED LINE
                "Monitor",
                f"{current_monthly_orders:.1f}/month",
                f"{kpis.get('container_utilization', 0)*100:.1f}%",
                f"KSh {current_monthly_orders * constants.TRANSPORT_COST:,.0f}/month"
            ],
            'Target Value': [
                f"{constants.SERVICE_LEVEL*100:.0f}%",
                target_inventory_turnover,  # <-- ALSO FIXED
                "<5%",
                f"{eoq_monthly_orders:.1f}/month",
                ">85%",
                f"KSh {eoq_monthly_orders * constants.TRANSPORT_COST:,.0f}/month"
            ]
        })

        st.dataframe(metrics_to_track, use_container_width=True, height=250, hide_index=True)

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

        st.dataframe(timeline_data, use_container_width=True, height=220, hide_index=True)

        st.markdown("#### 🌍 Long-term Improvements")
        st.markdown("""
        1. **Supply Chain Diversification**
        - Develop relationships with multiple dry ice suppliers
        - Establish backup transportation routes

        2. **Sustainability Initiatives**
        - Implement CO₂ capture system from fermentation processes
        - Explore renewable energy-powered production

        3. **Automated Replenishment System**
        - IoT sensors with real-time inventory tracking
        - AI-driven predictive ordering

        4. **Carbon Credit Program**
        - Monetize emission reductions from optimized logistics
        - Achieve carbon-neutral certification by 2027
        """)

        # Key metrics dashboard
        st.subheader("📊 Performance Targets")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Supplier Risk Reduction", "40%", "15% achieved")
        with col2:
            st.metric("Stockout Reduction", "30%", "8% improvement")
        with col3:
            st.metric("Carbon Footprint", "-15%", "-5% YoY")
        with col4:
            st.metric("Automation Level", "95%", "25% current")

        # Interactive Plotly timeline
        st.subheader("⏱️ Implementation Timeline")
        fig_timeline = go.Figure()
        fig_timeline.add_trace(go.Scatter(
            x=['Q3 2025', 'Q4 2025', 'Q1 2026', 'Q2 2026+'],
            y=[1, 2, 3, 4],
            mode='markers+lines+text',
            marker=dict(size=16, color='#3498db'),
            line=dict(color='#2c3e50', width=4),
            text=['Supplier Program', 'IoT Pilot', 'CO₂ Study', 'Full Rollout'],
            textposition='top center',
            name='Milestones'
        ))
        fig_timeline.update_layout(
            height=mobile_ui.get_chart_height(),
            showlegend=False,
            yaxis=dict(showticklabels=False, title=None),
            xaxis=dict(title='Implementation Quarters'),
            plot_bgcolor='rgba(0,0,0,0)'
        )
        fig_timeline = mobile_ui.optimize_chart_for_mobile(fig_timeline)
        st.plotly_chart(fig_timeline, use_container_width=True,
            config=mobile_ui.get_mobile_chart_config())

        # Roadmap dataframe with original content
        roadmap_data = {
            'Timeline': ['Q3 2025', 'Q4 2025', 'Q1 2026', 'Q2 2026+'],
            'Initiative': [
                'Supplier diversification program',
                'IoT sensor pilot in 2 facilities',
                'CO₂ capture feasibility study',
                'Full automation rollout'
            ],
            'Target': [
                'Reduce supplier risk by 40%',
                'Cut stockouts by 30%',
                'Decrease carbon footprint by 15%',
                'Achieve 95% automated ordering'
            ]
        }

        roadmap = pd.DataFrame(roadmap_data)

        # Styled dataframe with highlighting
        st.dataframe(
        roadmap.style.applymap(lambda x: 'font-weight: bold', subset=['Timeline'])
        .set_properties(**{'background-color': '#f8f9fa', 'color': '#212529'}),
        use_container_width=True,
        height=200,
        hide_index=True
        )

        # Expandable implementation details
        with st.expander("🔍 Detailed Implementation Plans", expanded=False):
            selected_quarter = st.selectbox(
                "Select Quarter",
                roadmap['Timeline'].tolist(),
                key='quarter_selector'
            )
            filtered_info = roadmap[roadmap['Timeline'] == selected_quarter]

            st.subheader(f"{selected_quarter} Implementation Plan")
            st.markdown(f"**Initiative:** {filtered_info['Initiative'].values[0]}")
            st.markdown(f"**Target:** {filtered_info['Target'].values[0]}")

            # Quarter-specific details
            if selected_quarter == 'Q3 2025':
                st.markdown("""
                - Identify 3 new dry ice suppliers
                - Negotiate backup transportation contracts
                - Develop risk assessment framework
                """)
                st.progress(30)
            elif selected_quarter == 'Q4 2025':
                st.markdown("""
                - Install IoT sensors in Midwest facilities
                - Develop predictive ordering algorithms
                - Train operations team on new system
                """)
                st.progress(15)
            elif selected_quarter == 'Q1 2026':
                st.markdown("""
                - Technical assessment of CO₂ capture systems
                - Calculate ROI for sustainability investments
                - Partner identification for implementation
                """)
                st.progress(5)
            else:
                st.markdown("""
                - System-wide automation deployment
                - Process optimization across all facilities
                - Integration with finance systems
                """)
                st.progress(0)

            st.caption(f"Current status of {selected_quarter} initiatives")


    with tab6:
        st.markdown("###  Predictive Maintenance Dashboard")
        # Container Health Assessment
        st.markdown("####  Container Health Assessment")

        # Container data
        containers_data = {
            'CTN-001': {'insulation_efficiency': 75, 'seal_integrity': 65, 'structural_condition': 85, 'usage_cycles': 42, 'location': 'Storage Unit #1'},
            'CTN-002': {'insulation_efficiency': 88, 'seal_integrity': 92, 'structural_condition': 90, 'usage_cycles': 28, 'location': 'Storage Unit #2'},
            'CTN-003': {'insulation_efficiency': 60, 'seal_integrity': 55, 'structural_condition': 70, 'usage_cycles': 67, 'location': 'Transport Container #A'}
        }

        # Container selection
        selected_container = st.selectbox(
            "Select Container for Analysis",
            list(containers_data.keys()),
            format_func=lambda x: f"{x} - {containers_data[x]['location']}",
            key="maintenance_container_select" # Added key to avoid widget duplication errors
        )
        container_data = containers_data[selected_container]

        # Calculate health metrics
        health_score = (container_data['insulation_efficiency'] + container_data['seal_integrity'] + container_data['structural_condition']) / 3
        failure_risk = "High" if health_score < 70 else "Medium" if health_score < 85 else "Low"

        # Display health metrics
        health_cols = st.columns(5)
        metrics = [
            ("Insulation Efficiency", f"{container_data['insulation_efficiency']}%"),
            ("Seal Integrity", f"{container_data['seal_integrity']}%"),
            ("Structural Condition", f"{container_data['structural_condition']}%"),
            ("Usage Cycles", container_data['usage_cycles']),
            ("Health Score", f"{health_score:.1f}%")
        ]

        for col, (label, value) in zip(health_cols, metrics):
            with col:
                st.metric(label, value)

        # Risk assessment
        st.markdown("---")
        st.markdown("#### 📊 Risk Assessment")
        risk_color = "🔴" if failure_risk == "High" else "🟡" if failure_risk == "Medium" else "🟢"
        st.metric("Failure Risk Level", f"{risk_color} {failure_risk}")

        # Maintenance recommendations
        st.markdown("---")
        st.markdown("####  Maintenance Recommendations")
        recommendations = []
        if container_data['insulation_efficiency'] < 70:
            recommendations.append(" Schedule insulation inspection")
        if container_data['seal_integrity'] < 70:
            recommendations.append(" Replace door seals and gaskets")
        if container_data['structural_condition'] < 80:
            recommendations.append(" Conduct structural assessment")
        if container_data['usage_cycles'] > 50:
            recommendations.append("📋 Consider container rotation")
        if not recommendations:
            recommendations.append("✅ Continue regular maintenance")

        for i, action in enumerate(recommendations, 1):
            st.markdown(f"{i}. {action}")

        # System overview
        st.markdown("---")
        st.markdown("####  System Overview")

        overview_cols = st.columns(4)
        overview_metrics = [
            ("Equipment Uptime", "98.2%", "0.5%"),
            ("Temperature Stability", "±0.5°C", "-0.2°C"),
            ("Last Maintenance", "12 days ago", None),
            ("Next Service Due", "18 days", None)
        ]

        for col, (label, value, delta) in zip(overview_cols, overview_metrics):
            with col:
                st.metric(label, value, delta=delta)

        # Maintenance schedule
        st.markdown("---")
        st.markdown("#### 📅 Maintenance Schedule")
        maintenance_data = pd.DataFrame({
            'Equipment': ['Storage Unit #1', 'Storage Unit #2', 'Container CTN-001', 'Container CTN-002', 'Container CTN-003', 'Monitoring System'],
            'Last Service': ['2024-06-15', '2024-06-10', '2024-06-05', '2024-06-01', '2024-05-28', '2024-06-20'],
            'Next Service': ['2024-07-15', '2024-07-10', '2024-06-25', '2024-07-01', '2024-06-28', '2024-07-20'],
            'Status': ['Good', 'Good', 'Fair', 'Good', 'Needs Attention', 'Excellent'],
            'Priority': ['Medium', 'Medium', 'High', 'Low', 'High', 'Low']
        })

        maintenance_data['Last Service'] = pd.to_datetime(maintenance_data['Last Service'])
        maintenance_data['Next Service'] = pd.to_datetime(maintenance_data['Next Service'])
        maintenance_data['Days Overdue'] = (pd.Timestamp.today().normalize() - maintenance_data['Next Service']).dt.days

        def style_status(val):
            colors = {'Needs Attention': 'background-color: #fff3cd', 'Excellent': 'background-color: #d4edda',
                     'Good': 'background-color: #d1ecf1', 'Fair': 'background-color: #f8d7da'}
            return colors.get(val, '')

        def style_priority(val):
            colors = {'High': 'background-color: #f8d7da', 'Medium': 'background-color: #fff3cd', 'Low': 'background-color: #d4edda'}
            return colors.get(val, '')

        # Pre-format the date columns BEFORE passing to styler
        maintenance_data['Last Service'] = maintenance_data['Last Service'].dt.strftime('%Y-%m-%d')
        maintenance_data['Next Service'] = maintenance_data['Next Service'].dt.strftime('%Y-%m-%d')
        maintenance_data['Days Overdue'] = maintenance_data['Days Overdue'].apply(
        lambda x: f"{x} days" if x > 0 else "On schedule"
        )

        st.dataframe(
        maintenance_data.style
        .applymap(style_status, subset=['Status'])
        .applymap(style_priority, subset=['Priority']),
        use_container_width=True,
        height=250,
        hide_index=True
        )

        #overdue_items = maintenance_data[maintenance_data['Days Overdue'] > 0]
        #if not overdue_items.empty:
            #st.markdown("#### ⚠️ Maintenance Alerts")
            #for _, item in overdue_items.iterrows():
            #    st.error(f" **{item['Equipment']}** is {item['Days Overdue']} days overdue!")

        # Cost tracking
        st.markdown("---")
        st.markdown("#### 💰 Maintenance Costs")
        cost_data = pd.DataFrame({
            'Month': pd.date_range('2024-01-01', periods=6, freq='M'),
            'Preventive': [2500, 3200, 2800, 4100, 2900, 3500],
            'Reactive': [1200, 800, 2100, 600, 1800, 900],
            'Emergency': [0, 0, 1500, 0, 0, 2200]
        })

        fig_maintenance_cost = px.bar(
            cost_data.melt(id_vars=['Month'], var_name='Type', value_name='Cost'),
            x='Month', y='Cost', color='Type',
            title="Monthly Maintenance Costs (KSh)",
            color_discrete_map={'Preventive': '#28a745', 'Reactive': '#ffc107', 'Emergency': '#dc3545'}
        )
        fig_maintenance_cost = mobile_ui.optimize_chart_for_mobile(fig_maintenance_cost)
        st.plotly_chart(fig_maintenance_cost, use_container_width=True,
            config=mobile_ui.get_mobile_chart_config())

        # ROI calculator
        st.markdown("#### 📈 Maintenance ROI")
        with st.container():
            roi_cols = st.columns(3)
        with roi_cols[0]:
            preventive_cost = st.number_input("Annual Preventive Cost (KSh)", value=40000, step=5000, key="preventive_cost")
        with roi_cols[1]:
            avoided_cost = st.number_input("Avoided Reactive Cost (KSh)", value=75000, step=5000, key="avoided_cost")
        with roi_cols[2]:
            downtime_cost = st.number_input("Avoided Downtime Cost (KSh)", value=150000, step=10000, key="downtime_cost")

        total_savings = avoided_cost + downtime_cost
        roi = ((total_savings - preventive_cost) / preventive_cost) * 100 if preventive_cost > 0 else 0

        st.metric("Maintenance ROI", f"{roi:.1f}%")
        if roi > 0:
            st.success(f"💡 Every KSh 1 spent on preventive maintenance saves KSh {total_savings/preventive_cost:.2f} in other costs.")
        else:
            st.warning("⚠️ Consider optimizing maintenance strategy.")

    with tab7:
        st.markdown("## 📜 Inventory Transaction History")

        # --- IMPORT BUTTON (ALWAYS VISIBLE - MOVED OUTSIDE THE IF/ELSE) ---
        #st.markdown("### ☁️ Sync to Cloud")
        #col_import, col_import2 = st.columns([1, 3])
        # with col_import:
        #    if st.button("📤 Import Local CSV to Supabase", type="primary", key="import_to_supabase"):
        #        with st.spinner("Importing transactions to Supabase..."):
        #            import_csv_to_supabase()
        #            st.rerun()
        #with col_import2:
        #    st.caption("Imports transactions from 'transactions_export.csv' to Supabase cloud database")
        
        #st.divider()

        # --- SECTION 1: PERIOD-SPECIFIC TRANSACTION HISTORY ---
        if not st.session_state.transactions:
            st.info("No transactions recorded for this period yet. Use the sidebar to record usage or receipts.")
        else:
            trans_df = pd.DataFrame(st.session_state.transactions)
            trans_df['date'] = pd.to_datetime(trans_df['date'])
            trans_df = trans_df.sort_values('date', ascending=False)
            
            #    st.markdown("### 🔍 Filter Transactions")
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
                display_df = filtered_df.copy()
                display_df['Date'] = display_df['date'].dt.strftime('%Y-%m-%d %H:%M')
                display_df['Type'] = display_df['type'].str.title()
                display_df['Quantity (kg)'] = display_df['quantity'].apply(lambda x: f"{x:,.2f}")
                mobile_ui.display_mobile_table(
                    display_df[['Date', 'Type', 'Quantity (kg)', 'description']],
                    max_height=400
                )
            
            st.markdown("### 📈 Transaction Summary (Filtered Period)")
            total_used = filtered_df[filtered_df['type']=='usage']['quantity'].sum()
            total_received = filtered_df[filtered_df['type']=='receipt']['quantity'].sum()
            net_change = total_received - total_used

            stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
            stat_col1.metric("Total Used", f"{total_used:,.1f} kg")
            stat_col2.metric("Total Received", f"{total_received:,.1f} kg")
            stat_col3.metric("Net Change", f"{net_change:,.1f} kg", delta=f"{net_change:,.1f} kg")
            stat_col4.metric("Total Transactions", len(filtered_df))

            # --- EXPORT DATA SECTION ---
            st.markdown("### 📥 Export Filtered Data")
            if not filtered_df.empty:
                csv = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                   label="Download as CSV",
                   data=csv,
                   file_name=f"transaction_history_{st.session_state.selected_period.replace('/', '-')}_{datetime.now().strftime('%Y%m%d')}.csv",
                   mime='text/csv',
                )
            else:
                st.caption("No data in the current filter to export.")

        # --- DIVIDER TO SEPARATE SECTIONS ---
        #st.divider()

        # --- SECTION 2: GLOBAL STATUS & HELP ---
        st.markdown("### 📊 Current Status")
        
        st.metric("Current Stock Level", f"{inventory_tracker.current_stock:,.1f} kg")

        #with st.expander("ℹ️ How to Use This Page"):
        #    st.markdown("""
        #    1.  **Record Usage:** Use the sidebar to log daily consumption.
        #    2.  **Record Receipt:** Use the sidebar when new stock arrives.
        #    3.  **View Transactions:** All transactions will appear here automatically.
        #    4.  **Filter Data:** Use the filters above to narrow down results.
        #    5.  **Export Data:** Download buttons appear when transaction data exists.
        #    """)

        # --- SECTION 3: DATA MANAGEMENT ---
        # st.divider()
        #st.markdown("### ⚠️ Data Management")
        #st.warning("This action will permanently delete ALL transaction and order data for ALL periods. Use with caution.")
        
        #if 'confirm_clear_pressed' not in st.session_state:
        #     st.session_state.confirm_clear_pressed = False

        #if st.button("Clear All Transactions and Orders", type="secondary"):
        #    st.session_state.confirm_clear_pressed = True

        #if st.session_state.confirm_clear_pressed:
        #    st.error("Are you sure? This cannot be undone.")
        #    col1, col2 = st.columns(2)
        #    with col1:
        #        if st.button("CONFIRM PERMANENT DELETION", type="primary"):
        #            clear_transactions_from_db()
        #            st.session_state.transactions = []
        #            st.session_state.confirm_clear_pressed = False
        #            st.success("All transaction and order data has been permanently cleared!")
        #            st.rerun()
        #    with col2:
        #        if st.button("Cancel"):
        #            st.session_state.confirm_clear_pressed = False
        #            st.rerun()

if __name__ == "__main__":
    main()

