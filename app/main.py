from datetime import datetime
import streamlit as st
import traceback
import uuid
import json
import gc
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import sys
import os
import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
from app.core.advanced_analytics import AdvancedAnalytics, create_advanced_analytics_tab
from app.core.google_sheet_reader import GoogleSheetReader
from app.core.advanced_forecasting_v2 import AdvancedForecaster
from app.core.external_factors import ExternalFactors
from app.core.realtime_forecast import get_realtime_forecaster
import warnings
from supabase import create_client, Client
from core.error_handling import (
    logger,
    safe_operation,
    safe_db_operation,
    validate_quantity,
    validate_date,
    validate_stock_sufficient,
    ServiceStatusManager,
    safe_number_input,
    safe_text_input,
    retry_on_failure,
    log_performance,
    DatabaseError,
    ValidationError,
    ServiceUnavailableError
)
# External imports for error handling
from requests.exceptions import Timeout, ConnectionError
from core.performance import (
    Paginator,
    paginate_dataframe,
    LazyLoader,
    optimize_session_state,
    compress_dataframe,
    optimize_table_display,
    free_memory,
    get_memory_usage
)
# Add these to your existing imports
from core.security import (
    AuthManager,
    AuditLogger,
    DataEncryption,
    SessionManager,
    ApiKeyManager,
    require_auth,
    require_permission,
    require_role,
    secure_endpoint,
    render_security_dashboard
)
from core.advanced_security import (
    PasswordManager,
    TwoFactorAuth,
    RateLimiter,
    rate_limited,
    SSOAuth,
    UserManager,
    PasswordReset
)
# 🔐 SECURITY AVAILABILITY FLAG
# ============================================================
SECURITY_AVAILABLE = True
import base64
def get_image_base64(image_path):
    """Convert image to base64 for embedding in HTML"""
    try:
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()
            base64_encoded = base64.b64encode(img_data).decode('utf-8')
            
            # Detect image type
            if image_path.lower().endswith('.png'):
                return f"data:image/png;base64,{base64_encoded}"
            elif image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
                return f"data:image/jpeg;base64,{base64_encoded}"
            else:
                return f"data:image/jpeg;base64,{base64_encoded}"
    except Exception as e:
        print(f"Error loading image: {e}")
        return ""
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

# ============================================================
# CLEAR TRANSACTIONS - ADMIN ONLY WITH AUDIT LOGGING
@rate_limited(max_calls=2, period=300)  # 2 clears per 5 minutes
@require_role('admin')
def clear_transactions_from_db():
    """
    Permanently delete all records from the transactions, inventory,
    AND historical_orders tables to perform a full reset.
    
    🔐 This function is restricted to ADMIN users only.
    🔐 Rate limited to 2 calls per 5 minutes to prevent accidental deletion.
    """
    # ============================================================
    # 🔐 AUDIT LOGGING
    # ============================================================
    audit = AuditLogger()
    auth = AuthManager()
    
    audit.log(
        action='CLEAR_ALL_TRANSACTIONS',
        details="User initiated full data deletion",
        user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
    )
    
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
        
        # ============================================================
        # 🔐 AUDIT LOGGING - SUCCESS
        # ============================================================
        audit.log(
            action='CLEAR_ALL_TRANSACTIONS_SUCCESS',
            details="All transactions, inventory, and historical orders cleared successfully",
            user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
        )
        
        # The success message is now part of the button logic, so it's okay to remove it here

    except sqlite3.Error as e:
        # ============================================================
        # 🔐 AUDIT LOGGING - ERROR
        # ============================================================
        audit.log(
            action='CLEAR_ALL_TRANSACTIONS_ERROR',
            details=f"Error: {str(e)}",
            user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
        )
        st.error(f"Database error while clearing transactions: {e}")
    finally:
        conn.close()
# ============================================================
# 🔐 SECURE ADD TRANSACTION FUNCTION WITH RATE LIMITING
# ============================================================

@rate_limited(max_calls=10, period=60)  # 10 receipts per minute
@require_auth
@require_permission('record_receipt')
@safe_operation(error_message="Failed to add transaction")
def add_transaction_to_db(transaction_type, quantity, description, date, period):
    """
    Add transaction to Supabase or SQLite database with comprehensive error handling.
    
    Args:
        transaction_type: 'usage' or 'receipt'
        quantity: Quantity in kg
        description: Transaction description
        date: Transaction date
        period: Analysis period (e.g., '2024/2025')
    
    Returns:
        transaction_id: ID of the created transaction
    
    Raises:
        ValidationError: If input validation fails
        DatabaseError: If database operation fails
    
    🔐 This function requires authentication and 'record_receipt' permission.
    🔐 Rate limited to 10 calls per minute to prevent abuse.
    """
    
    # ============================================================
    # 🔐 AUDIT LOGGING
    # ============================================================
    audit = AuditLogger()
    auth = AuthManager()
    
    audit.log(
        action='RECORD_RECEIPT',
        details=f"Transaction: {transaction_type}, Quantity: {quantity}kg, Date: {date}, Period: {period}",
        user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
    )
    
    # ============================================================
    # STEP 1: VALIDATE INPUTS
    # ============================================================
    # Validate quantity
    is_valid, msg = validate_quantity(quantity, min_qty=0, max_qty=100000, allow_zero=False)
    if not is_valid:
        raise ValidationError(msg)
    
    # Validate date
    is_valid, msg = validate_date(date, allow_future=False)
    if not is_valid:
        raise ValidationError(msg)
    
    # Validate transaction type
    if transaction_type not in ['usage', 'receipt']:
        raise ValidationError(f"Invalid transaction type: {transaction_type}")
    
    logger.info(f"Processing {transaction_type} transaction: {quantity} kg on {date}")
    
    
    # ============================================================
    # STEP 2: TRY SUPABASE FIRST (if enabled)
    # ============================================================
    if USE_SUPABASE:
        try:
            supabase = init_supabase()
            if supabase:
                logger.info("Attempting Supabase transaction...")
                
                # Get current stock from Supabase
                current_stock_response = supabase.table('inventory')\
                    .select('stock_level')\
                    .order('date', desc=True)\
                    .limit(1)\
                    .execute()
                
                current_stock = current_stock_response.data[0]['stock_level'] if current_stock_response.data else 0
                logger.debug(f"Current stock (Supabase): {current_stock} kg")
                
                # Calculate new stock
                if transaction_type == 'usage':
                    new_stock = current_stock - quantity
                    # Validate stock sufficiency
                    is_valid, msg = validate_stock_sufficient(quantity, current_stock)
                    if not is_valid:
                        raise ValidationError(msg)
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
                logger.info(f"Supabase transaction created: {transaction_id}")
                
                # Insert inventory record
                inventory_data = {
                    'date': date.isoformat(),
                    'stock_level': new_stock,
                    'transaction_id': transaction_id
                }
                supabase.table('inventory').insert(inventory_data).execute()
                logger.debug(f"Inventory updated (Supabase): {new_stock} kg")
                
                # If receipt, add to historical orders
                if transaction_type == 'receipt':
                    order_data = {
                        'date': date.isoformat(),
                        'order_quantity': quantity,
                        'analysis_period': period
                    }
                    supabase.table('historical_orders').insert(order_data).execute()
                    logger.info(f"Historical order recorded (Supabase): {quantity} kg")
                
                # ============================================================
                # 🔐 AUDIT LOGGING - SUCCESS
                # ============================================================
                audit.log(
                    action='RECORD_RECEIPT_SUCCESS',
                    details=f"Transaction ID: {transaction_id}, New stock: {new_stock}kg",
                    user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
                )
                
                return transaction_id
                
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            logger.warning(f"Supabase transaction failed: {e}. Falling back to SQLite.")
            # Fall through to SQLite
    

    # ============================================================
    # STEP 3: FALLBACK TO SQLITE (with safe operation)
    # ============================================================
    def sqlite_operation():
        """Execute SQLite transaction with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect('dry_ice.db')
            c = conn.cursor()
            logger.debug("SQLite connection established")
            
            # Get current stock from SQLite
            c.execute('''SELECT stock_level FROM inventory ORDER BY date DESC LIMIT 1''')
            result = c.fetchone()
            current_stock = result[0] if result else 0
            logger.debug(f"Current stock (SQLite): {current_stock} kg")
            
            # Calculate new stock
            if transaction_type == 'usage':
                new_stock = current_stock - quantity
                # Validate stock sufficiency
                is_valid, msg = validate_stock_sufficient(quantity, current_stock)
                if not is_valid:
                    raise ValidationError(msg)
            else:  # receipt
                new_stock = current_stock + quantity
            
            # Insert transaction
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
            logger.debug(f"SQLite transaction created: {transaction_id}")
            
            # Insert inventory record
            if transaction_type == 'usage':
                c.execute('''INSERT INTO inventory (date, stock_level, transaction_id)
                             VALUES (?, ?, ?)''',
                          (date.isoformat(), new_stock, transaction_id))
            elif transaction_type == 'receipt':
                c.execute('''INSERT INTO inventory (date, stock_level, transaction_id)
                             VALUES (?, ?, ?)''',
                          (date.isoformat(), new_stock, transaction_id))
                
                # Add to historical orders for receipts
                c.execute('''INSERT INTO historical_orders (date, order_quantity, analysis_period)
                             VALUES (?, ?, ?)''',
                          (date.isoformat(), quantity, period))
                logger.debug(f"Historical order recorded (SQLite): {quantity} kg")
            
            conn.commit()
            logger.info(f"SQLite transaction completed: {transaction_id}")
            
            # ============================================================
            # 🔐 AUDIT LOGGING - SQLITE SUCCESS
            # ============================================================
            audit.log(
                action='RECORD_RECEIPT_SQLITE',
                details=f"Transaction ID: {transaction_id}, New stock: {new_stock}kg",
                user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
            )
            
            return transaction_id
            
        except sqlite3.IntegrityError as e:
            logger.error(f"SQLite integrity error: {e}")
            if conn:
                conn.rollback()
            raise DatabaseError(f"Data integrity error: {e}")
            
        except sqlite3.OperationalError as e:
            logger.error(f"SQLite operational error: {e}")
            if conn:
                conn.rollback()
            raise DatabaseError(f"Database operation error: {e}")
            
        except Exception as e:
            logger.error(f"SQLite transaction error: {e}")
            if conn:
                conn.rollback()
            raise
            
        finally:
            if conn:
                conn.close()
                logger.debug("SQLite connection closed")
    
    # Execute with safe database operation
    return safe_db_operation(
        sqlite_operation,
        fallback_value=None,
        show_error=True,
        error_title="Transaction Failed"
    )

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
    try:
        conn = sqlite3.connect('dry_ice.db')
        c = conn.cursor()
        
        # Check if table exists first
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_orders'")
        if not c.fetchone():
            # Table doesn't exist, return empty DataFrame
            conn.close()
            return pd.DataFrame(columns=['Date', 'Order_Quantity_kg', 'analysis_period'])
        
        c.execute('''SELECT date, order_quantity, analysis_period FROM historical_orders
                     WHERE analysis_period = ? ORDER BY date''', (period,))
        orders = c.fetchall()
        conn.close()
    except sqlite3.OperationalError as e:
        # Table doesn't exist or other SQLite error
        print(f"SQLite error in get_historical_orders_from_db: {e}")
        return pd.DataFrame(columns=['Date', 'Order_Quantity_kg', 'analysis_period'])

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
            
            # Build HTML content
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
            
            # Use st.html() instead of st.markdown()
            st.components.v1.html(html_content)

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
            
            # Build HTML content
            html_content = f"""
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
                cursor: pointer;
            "
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
            
            # Use st.html() instead of st.markdown()
            st.components.v1.html(html_content)
    
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
        unit = details.get('unit', 'kg')
        
        # Estimate daily usage if not provided
        if daily_usage_rate:
            daily_usage = daily_usage_rate
        else:
            # Estimate based on reorder point and assumed lead time
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
            
            # Store the numeric value for Suggested Order (without unit)
            suggested_order_value = f"{suggested_qty:,.0f} {unit}"
            
            recommendations.append({
                'Item': item_name,
                'Current Stock': f"{current_stock:,.0f} {unit}",
                'Reorder Point': f"{reorder_point:,.0f} {unit}",
                'Suggested Order': f"{suggested_qty:,.0f} {unit}",  # This is for display
                'Suggested Order Value': suggested_qty,  # This is the numeric value for calculations
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
    
    # Helper function to extract numeric value from strings like "100 kg", "50 units", "100 pcs"
    def extract_numeric(value):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove common unit suffixes and commas
            import re
            # Extract first number found in the string
            numbers = re.findall(r'[\d,]+\.?\d*', value.replace(',', ''))
            if numbers:
                try:
                    return float(numbers[0])
                except ValueError:
                    return 0
        return 0
    
    # Calculate total suggested quantity
    total_qty = 0
    for qty in recommendations_df['Suggested Order'].values:
        total_qty += extract_numeric(qty)
    
    return {
        'total_items': len(recommendations_df),
        'urgent_count': len(recommendations_df[recommendations_df['Urgency'] == 'High']),
        'medium_count': len(recommendations_df[recommendations_df['Urgency'] == 'Medium']),
        'low_count': len(recommendations_df[recommendations_df['Urgency'] == 'Low']),
        'average_days': recommendations_df['Days Until Stockout'].mean(),
        'total_suggested_qty': total_qty
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

# ============================================================
# 🎨REAL-TIME STATUS DASHBOARD
# ============================================================
def get_incoming_orders(inventory_items=None):
    """
    Calculate expected incoming orders (items on order) based on all inventory
    
    Args:
        inventory_items: Dictionary with all inventory items
    
    Returns:
        Dictionary with total expected incoming by category and overall total
    """
    if not inventory_items:
        return {'total': 0, 'by_category': {}}
    
    expected_total = 0
    by_category = {}
    
    for item_name, details in inventory_items.items():
        stock = details.get('stock', 0)
        reorder = details.get('reorder', 0)
        category = details.get('category', 'Uncategorized')
        unit = details.get('unit', 'kg')
        
        # If stock is below reorder point, assume an order is expected
        if stock < reorder:
            # Estimate expected quantity as the difference or EOQ
            expected_qty = max(reorder * 1.5, details.get('max', stock * 2)) - stock
            expected_total += expected_qty
            
            if category not in by_category:
                by_category[category] = 0
            by_category[category] += expected_qty
    
    return {'total': expected_total, 'by_category': by_category}

def get_committed_orders(inventory_items=None):
    """
    Calculate committed orders (orders to fulfill) based on all inventory
    
    Args:
        inventory_items: Dictionary with all inventory items
    
    Returns:
        Dictionary with total committed by category and overall total
    """
    if not inventory_items:
        return {'total': 0, 'by_category': {}}
    
    committed_total = 0
    by_category = {}
    
    for item_name, details in inventory_items.items():
        stock = details.get('stock', 0)
        reorder = details.get('reorder', 0)
        category = details.get('category', 'Uncategorized')
        unit = details.get('unit', 'kg')
        
        # Committed is typically what's needed to fulfill upcoming orders
        # Estimate based on reorder point and current stock
        if stock < reorder:
            committed_qty = (reorder - stock) * 0.3  # 30% of deficit
            committed_total += committed_qty
            
            if category not in by_category:
                by_category[category] = 0
            by_category[category] += committed_qty
    
    return {'total': committed_total, 'by_category': by_category}

def inventory_status_dashboard(inventory_items, inventory_tracker=None):
    """
    Real-time inventory status dashboard (Katana style) for ALL inventory
    
    Args:
        inventory_items: Dictionary with all inventory items
        inventory_tracker: Optional InventoryTracker instance (for Dry Ice specific)
    """
    if not inventory_items:
        st.info("No inventory data available for status dashboard")
        return
    
    # Calculate total stock across all items
    total_stock = sum(details.get('stock', 0) for details in inventory_items.values())
    total_items = len(inventory_items)
    
    # Get expected incoming orders
    expected_data = get_incoming_orders(inventory_items)
    expected_total = expected_data['total']
    
    # Get committed orders
    committed_data = get_committed_orders(inventory_items)
    committed_total = committed_data['total']
    
    # Count items by status
    low_stock_items = 0
    critical_items = 0
    overstocked_items = 0
    healthy_items = 0
    
    for item_name, details in inventory_items.items():
        stock = details.get('stock', 0)
        reorder = details.get('reorder', 0)
        max_stock = details.get('max', stock * 2)
        
        if stock <= 0:
            critical_items += 1
        elif stock < reorder:
            low_stock_items += 1
        elif stock > max_stock * 1.5:
            overstocked_items += 1
        else:
            healthy_items += 1
    
    # Display status cards in a row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Total Stock - Green
        st.markdown(f"""
        <div style="
            background: rgba(232, 245, 233, 0.9);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            padding: 16px 20px;
            border-radius: 12px;
            border-left: 5px solid #4caf50;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
        ">
            <div style="font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">
                📦 TOTAL STOCK
            </div>
            <div style="font-size: 28px; font-weight: 700; color: #2e7d32; margin: 4px 0;">
                {total_stock:,.0f} <span style="font-size: 14px; font-weight: 400; color: #666;">units</span>
            </div>
            <div style="font-size: 12px; color: #888; margin-top: 2px;">
                Across {total_items} items
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Expected - Blue
        st.markdown(f"""
        <div style="
            background: rgba(227, 242, 253, 0.9);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            padding: 16px 20px;
            border-radius: 12px;
            border-left: 5px solid #2196f3;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
        ">
            <div style="font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">
                📋 EXPECTED
            </div>
            <div style="font-size: 28px; font-weight: 700; color: #1565c0; margin: 4px 0;">
                {expected_total:,.0f} <span style="font-size: 14px; font-weight: 400; color: #666;">units</span>
            </div>
            <div style="font-size: 12px; color: #888; margin-top: 2px;">
                Incoming orders needed
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Committed - Orange
        st.markdown(f"""
        <div style="
            background: rgba(255, 243, 224, 0.9);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            padding: 16px 20px;
            border-radius: 12px;
            border-left: 5px solid #ff9800;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
        ">
            <div style="font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">
                🎯 COMMITTED
            </div>
            <div style="font-size: 28px; font-weight: 700; color: #e65100; margin: 4px 0;">
                {committed_total:,.0f} <span style="font-size: 14px; font-weight: 400; color: #666;">units</span>
            </div>
            <div style="font-size: 12px; color: #888; margin-top: 2px;">
                Demand to fulfill
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Add a quick status bar showing the overall health
    st.markdown("---")
    
    # Calculate health metrics
    total_items_analyzed = total_items
    healthy_percentage = (healthy_items / total_items_analyzed * 100) if total_items_analyzed > 0 else 0
    warning_items = low_stock_items + critical_items
    
    health_color = '#4caf50' if healthy_percentage > 70 else '#ff9800' if healthy_percentage > 40 else '#f44336'
    health_status = '✅ Healthy' if healthy_percentage > 70 else '⚠️ Moderate' if healthy_percentage > 40 else '🔴 Critical'
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(8px);
            border-radius: 8px;
            padding: 10px 15px;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <div style="font-size: 13px; color: #888;">Inventory Health</div>
            <div style="font-size: 18px; font-weight: 600; color: {health_color};">
                {health_status}
            </div>
            <div style="
                margin-top: 4px;
                height: 4px;
                background: #eee;
                border-radius: 2px;
                overflow: hidden;
            ">
                <div style="
                    width: {healthy_percentage:.0f}%;
                    height: 4px;
                    background: {health_color};
                    border-radius: 2px;
                    transition: width 0.6s ease;
                "></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.metric("📊 Healthy Items", f"{healthy_items}/{total_items}")
    
    with col3:
        st.metric("⚠️ Low Stock", low_stock_items, delta=f"-{low_stock_items}" if low_stock_items > 0 else None)
    
    with col4:
        st.metric("🔴 Critical", critical_items, delta=f"-{critical_items}" if critical_items > 0 else None)
    
    with col5:
        st.metric("📦 Overstocked", overstocked_items)
    
    # Category breakdown (if multiple categories exist)
    categories = set(details.get('category', 'Uncategorized') for details in inventory_items.values())
    if len(categories) > 1:
        st.markdown("---")
        st.markdown("#### 📊 Category Breakdown")
        
        # Create category metrics
        cat_cols = st.columns(min(4, len(categories)))
        for idx, category in enumerate(sorted(categories)):
            if idx < 4:
                with cat_cols[idx]:
                    cat_items = [item for item, details in inventory_items.items() 
                                if details.get('category', 'Uncategorized') == category]
                    cat_stock = sum(details.get('stock', 0) for item, details in inventory_items.items() 
                                   if details.get('category', 'Uncategorized') == category)
                    cat_count = len(cat_items)
                    
                    st.metric(
                        f"📂 {category}",
                        f"{cat_stock:,.0f} units",
                        f"{cat_count} items"
                    )

# 🎨 AI-POWERED RECOMMENDATIONS
# ============================================================
def ai_powered_recommendations(inventory_items, filtered_items, kpis=None):
    """
    AI-style smart recommendations based on all inventory items
    
    Args:
        inventory_items: Dictionary with all inventory items
        filtered_items: Filtered inventory items (for specific views)
        kpis: Optional KPI dictionary
    """
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
            🤖 AI-powered insights based on your inventory data.
            <span style="color: #dc3545;">🔴 Critical</span> | 
            <span style="color: #ffc107;">🟡 Warning</span> | 
            <span style="color: #28a745;">🟢 Good</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    recommendations = []
    
    if not inventory_items:
        recommendations.append({
            'icon': 'ℹ️',
            'title': 'No Inventory Data',
            'desc': 'Load inventory data to see AI recommendations',
            'action': '📊 Load Data',
            'details': 'Connect to Google Sheets',
            'priority': 'low',
            'color': '#90a4ae'
        })
        
        # Display the message
        display_recommendations(recommendations)
        return
    
    # 1. Low Stock Alerts - Check ALL items
    low_stock_items = []
    critical_items = []
    
    for item_name, details in inventory_items.items():
        stock = details.get('stock', 0)
        reorder = details.get('reorder', 0)
        unit = details.get('unit', 'kg')
        
        if stock <= 0:
            critical_items.append({'name': item_name, 'stock': stock, 'unit': unit})
        elif stock < reorder:
            low_stock_items.append({'name': item_name, 'stock': stock, 'reorder': reorder, 'unit': unit})
    
    # Critical items (zero stock)
    if critical_items:
        item_list = ', '.join([f"{item['name']} ({item['stock']} {item['unit']})" for item in critical_items[:5]])
        if len(critical_items) > 5:
            item_list += f" and {len(critical_items) - 5} more"
        
        recommendations.append({
            'icon': '🔴',
            'title': f'⚠️ {len(critical_items)} Items Out of Stock',
            'desc': f'Critical items: {item_list}',
            'action': '🛒 Order Now',
            'details': f'These items need immediate attention',
            'priority': 'high',
            'color': '#dc3545'
        })
    
    # Low stock items
    if low_stock_items:
        item_list = ', '.join([f"{item['name']} ({item['stock']} {item['unit']})" for item in low_stock_items[:3]])
        if len(low_stock_items) > 3:
            item_list += f" and {len(low_stock_items) - 3} more"
        
        recommendations.append({
            'icon': '🟡',
            'title': f'⚠️ {len(low_stock_items)} Items Low in Stock',
            'desc': f'Items below reorder point: {item_list}',
            'action': '📋 Review Stock',
            'details': f'Consider replenishing these items',
            'priority': 'medium',
            'color': '#ffc107'
        })
    
    # 2. Overstocked Items
    overstocked_items = []
    for item_name, details in inventory_items.items():
        stock = details.get('stock', 0)
        max_stock = details.get('max', stock * 2)
        unit = details.get('unit', 'kg')
        
        if stock > max_stock * 1.5:  # 50% above max
            overstocked_items.append({'name': item_name, 'stock': stock, 'max': max_stock, 'unit': unit})
    
    if overstocked_items:
        item_list = ', '.join([f"{item['name']} ({item['stock']} {item['unit']})" for item in overstocked_items[:3]])
        if len(overstocked_items) > 3:
            item_list += f" and {len(overstocked_items) - 3} more"
        
        recommendations.append({
            'icon': '📦',
            'title': f'📦 {len(overstocked_items)} Items Overstocked',
            'desc': f'Items above recommended levels: {item_list}',
            'action': '📊 Review Inventory',
            'details': f'Consider reducing orders for these items',
            'priority': 'medium',
            'color': '#2196f3'
        })
    
    # 3. Category Analysis
    categories = {}
    for item_name, details in inventory_items.items():
        category = details.get('category', 'Uncategorized')
        stock = details.get('stock', 0)
        reorder = details.get('reorder', 0)
        
        if category not in categories:
            categories[category] = {'total_stock': 0, 'total_reorder': 0, 'count': 0}
        
        categories[category]['total_stock'] += stock
        categories[category]['total_reorder'] += reorder
        categories[category]['count'] += 1
    
    # Find categories with low coverage
    low_coverage_categories = []
    for cat, data in categories.items():
        if data['total_reorder'] > 0:
            coverage_ratio = data['total_stock'] / data['total_reorder']
            if coverage_ratio < 1.5:
                low_coverage_categories.append({
                    'category': cat,
                    'ratio': coverage_ratio,
                    'items': data['count']
                })
    
    if low_coverage_categories:
        cat_list = ', '.join([f"{cat['category']} ({cat['ratio']:.1f}x)" for cat in low_coverage_categories[:3]])
        if len(low_coverage_categories) > 3:
            cat_list += f" and {len(low_coverage_categories) - 3} more"
        
        recommendations.append({
            'icon': '📊',
            'title': f'📊 Low Category Coverage',
            'desc': f'Categories with low stock coverage: {cat_list}',
            'action': '📋 Review Categories',
            'details': f'Target coverage ratio: 1.5x reorder level',
            'priority': 'medium',
            'color': '#ff9800'
        })
    
    # 4. Top 5 Most Valuable Items (by stock value)
    valuable_items = []
    for item_name, details in inventory_items.items():
        stock = details.get('stock', 0)
        price = details.get('price', 0)
        if price > 0 and stock > 0:
            value = stock * price
            valuable_items.append({
                'name': item_name,
                'value': value,
                'stock': stock,
                'price': price
            })
    
    if valuable_items:
        valuable_items.sort(key=lambda x: x['value'], reverse=True)
        top_items = valuable_items[:5]
        
        item_list = ', '.join([f"{item['name']} (KSh {item['value']:,.0f})" for item in top_items[:3]])
        if len(top_items) > 3:
            item_list += f" and {len(top_items) - 3} more"
        
        recommendations.append({
            'icon': '💰',
            'title': f'💰 Top {len(top_items)} Most Valuable Items',
            'desc': f'Highest value inventory: {item_list}',
            'action': '📊 View Details',
            'details': f'Total value of top items: KSh {sum(item["value"] for item in top_items):,.0f}',
            'priority': 'low',
            'color': '#4caf50'
        })
    
    # 5. Total Inventory Health Score
    total_items = len(inventory_items)
    healthy_items = 0
    warning_items = 0
    critical_items_count = 0
    
    for item_name, details in inventory_items.items():
        stock = details.get('stock', 0)
        reorder = details.get('reorder', 0)
        
        if stock <= 0:
            critical_items_count += 1
        elif stock < reorder:
            warning_items += 1
        else:
            healthy_items += 1
    
    health_score = (healthy_items / total_items * 100) if total_items > 0 else 0
    health_status = '✅ Healthy' if health_score > 70 else '⚠️ Moderate' if health_score > 40 else '🔴 Critical'
    health_color = '#4caf50' if health_score > 70 else '#ff9800' if health_score > 40 else '#dc3545'
    
    recommendations.append({
        'icon': '🏥',
        'title': f'🏥 Inventory Health: {health_score:.0f}%',
        'desc': f'{health_status} - {healthy_items}/{total_items} items well-stocked',
        'action': '📊 View Dashboard',
        'details': f'Critical: {critical_items_count} | Warning: {warning_items} | Healthy: {healthy_items}',
        'priority': 'low',
        'color': health_color
    })
    
    # 6. Fastest Moving Items (if we have historical data)
    if kpis and kpis.get('total_orders', 0) > 0:
        recommendations.append({
            'icon': '🚀',
            'title': '🚀 Demand Pattern Detected',
            'desc': f'Total orders: {kpis.get("total_orders", 0):,} | Avg order: {kpis.get("avg_order_size", 0):.1f} kg',
            'action': '📈 View Analysis',
            'details': f'Order frequency: {kpis.get("order_frequency", 0):.1f} orders/month',
            'priority': 'low',
            'color': '#9c27b0'
        })
    
    # Display recommendations
    display_recommendations(recommendations)

def display_recommendations(recommendations):
    """
    Display AI recommendations as styled cards
    """
    if not recommendations:
        st.info("✅ No AI recommendations at this time. All metrics look good!")
        return
    
    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    recommendations.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 3))
    
    # Display as cards in a grid (2 columns)
    cols = st.columns(min(2, len(recommendations)))
    
    for idx, rec in enumerate(recommendations):
        with cols[idx % 2]:
            st.markdown(f"""
            <div style="
                border-left: 4px solid {rec['color']};
                padding: 14px 16px;
                margin: 6px 0;
                background: rgba(255,255,255,0.06);
                backdrop-filter: blur(4px);
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.08);
                transition: all 0.3s ease;
                min-height: 120px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            "
            onmouseover="this.style.transform='translateX(4px)'; this.style.boxShadow='0 4px 15px rgba(0,0,0,0.1)';"
            onmouseout="this.style.transform='translateX(0)'; this.style.boxShadow='none';"
            >
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <span style="font-size: 20px;">{rec['icon']}</span>
                        <span style="font-weight: 600; font-size: 14px; color: #333; margin-left: 8px;">{rec['title']}</span>
                    </div>
                    <span style="
                        font-size: 10px;
                        background: {rec['color']};
                        color: white;
                        padding: 2px 10px;
                        border-radius: 12px;
                        font-weight: 600;
                        text-transform: uppercase;
                    ">
                        {rec.get('priority', 'info').upper()}
                    </span>
                </div>
                <div style="font-size: 13px; color: #666; margin-top: 6px; flex: 1;">
                    {rec['desc']}
                </div>
                <div style="font-size: 12px; color: #999; margin-top: 6px;">
                    {rec['details']}
                </div>
                <div style="margin-top: 8px;">
                    <span style="
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 4px 14px;
                        border-radius: 20px;
                        font-size: 12px;
                        font-weight: 500;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        display: inline-block;
                    "
                    onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 2px 10px rgba(102,126,234,0.3)';"
                    onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='none';"
                    onclick="this.style.transform='scale(0.95)'; setTimeout(() => this.style.transform='scale(1)', 200);"
                    >
                        {rec['action']}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
# ============================================================
# 🎨 ENHANCED PDF REPORT GENERATOR (Inventory-Agnostic)
# ============================================================

@rate_limited(max_calls=5, period=300)  # 5 reports per 5 minutes
def generate_enhanced_pdf_report(inventory_items, stock_df=None, kpis=None):
    """
    Generate an enhanced PDF report for ALL inventory items
    
    🔐 Rate limited to 5 reports per 5 minutes to prevent abuse.
    
    Args:
        inventory_items: Dictionary with all inventory items
        stock_df: DataFrame from Google Sheets (optional)
        kpis: Dictionary with KPI values (optional)
    
    Returns:
        Path to the generated PDF file
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER
        import os
        from datetime import datetime
        
        # Create the report
        report_path = f"inventory_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        doc = SimpleDocTemplate(report_path, pagesize=letter, 
                                rightMargin=72, leftMargin=72, 
                                topMargin=72, bottomMargin=72)
        
        styles = getSampleStyleSheet()
        elements = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f77b4'),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12
        )
        
        # ============================================================
        # 1. TITLE & HEADER
        # ============================================================
        elements.append(Paragraph("Inventory Management Report", title_style))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", 
                                 styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # ============================================================
        # 2. EXECUTIVE SUMMARY
        # ============================================================
        elements.append(Paragraph("Executive Summary", heading_style))
        
        # Calculate metrics from inventory items
        total_items = len(inventory_items)
        total_stock = sum(details.get('stock', 0) for details in inventory_items.values())
        
        # Count items by status
        low_stock_items = 0
        critical_items = 0
        overstocked_items = 0
        healthy_items = 0
        total_value = 0
        
        for item_name, details in inventory_items.items():
            stock = details.get('stock', 0)
            reorder = details.get('reorder', 0)
            max_stock = details.get('max', stock * 2)
            price = details.get('price', 0)
            
            if price > 0:
                total_value += stock * price
            
            if stock <= 0:
                critical_items += 1
            elif stock < reorder:
                low_stock_items += 1
            elif stock > max_stock * 1.5:
                overstocked_items += 1
            else:
                healthy_items += 1
        
        categories = set(details.get('category', 'Uncategorized') for details in inventory_items.values())
        
        summary_data = [
            ['Metric', 'Value', 'Status'],
            ['Total Items', f"{total_items:,}", ''],
            ['Total Stock', f"{total_stock:,.0f} units", ''],
            ['Total Value', f"KSh {total_value:,.0f}", ''],
            ['Categories', f"{len(categories)}", ''],
            ['Healthy Items', f"{healthy_items}", '✅' if healthy_items > total_items * 0.5 else '⚠️'],
            ['Low Stock', f"{low_stock_items}", '⚠️' if low_stock_items > 0 else '✅'],
            ['Critical (Out of Stock)', f"{critical_items}", '🔴' if critical_items > 0 else '✅'],
            ['Overstocked', f"{overstocked_items}", ''],
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 1*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4e79a7')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 11),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8f9fa')),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('TOPPADDING', (0,1), (-1,-1), 6),
            ('BOTTOMPADDING', (0,1), (-1,-1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 20))
        
        # ============================================================
        # 3. INVENTORY STATUS
        # ============================================================
        elements.append(Paragraph("Inventory Status Overview", heading_style))
        
        status_data = [
            ['Status', 'Count', 'Percentage'],
            ['✅ Healthy', f"{healthy_items}", f"{(healthy_items/total_items*100):.1f}%" if total_items > 0 else '0%'],
            ['⚠️ Low Stock', f"{low_stock_items}", f"{(low_stock_items/total_items*100):.1f}%" if total_items > 0 else '0%'],
            ['🔴 Critical', f"{critical_items}", f"{(critical_items/total_items*100):.1f}%" if total_items > 0 else '0%'],
            ['📦 Overstocked', f"{overstocked_items}", f"{(overstocked_items/total_items*100):.1f}%" if total_items > 0 else '0%'],
        ]
        
        status_table = Table(status_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch])
        status_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2ecc71')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 11),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8f9fa')),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('TOPPADDING', (0,1), (-1,-1), 6),
            ('BOTTOMPADDING', (0,1), (-1,-1), 6),
        ]))
        elements.append(status_table)
        elements.append(Spacer(1, 20))
        
        # ============================================================
        # 4. CATEGORY BREAKDOWN
        # ============================================================
        if len(categories) > 1:
            elements.append(Paragraph("Category Breakdown", heading_style))
            
            category_data = [['Category', 'Items', 'Total Stock', 'Avg Stock/Item']]
            
            for category in sorted(categories):
                cat_items = [item for item, details in inventory_items.items() 
                            if details.get('category', 'Uncategorized') == category]
                cat_count = len(cat_items)
                cat_stock = sum(details.get('stock', 0) for item, details in inventory_items.items() 
                               if details.get('category', 'Uncategorized') == category)
                avg_stock = cat_stock / cat_count if cat_count > 0 else 0
                
                category_data.append([
                    category,
                    f"{cat_count}",
                    f"{cat_stock:,.0f}",
                    f"{avg_stock:.0f}"
                ])
            
            category_table = Table(category_data, colWidths=[1.8*inch, 1.2*inch, 1.5*inch, 1.5*inch])
            category_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 11),
                ('BOTTOMPADDING', (0,0), (-1,0), 10),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8f9fa')),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
                ('FONTSIZE', (0,1), (-1,-1), 10),
                ('TOPPADDING', (0,1), (-1,-1), 6),
                ('BOTTOMPADDING', (0,1), (-1,-1), 6),
            ]))
            elements.append(category_table)
            elements.append(Spacer(1, 20))
        
        # ============================================================
        # 5. TOP VALUABLE ITEMS
        # ============================================================
        valuable_items = []
        for item_name, details in inventory_items.items():
            stock = details.get('stock', 0)
            price = details.get('price', 0)
            if price > 0 and stock > 0:
                value = stock * price
                valuable_items.append({
                    'name': item_name,
                    'value': value,
                    'stock': stock,
                    'price': price,
                    'category': details.get('category', 'Uncategorized')
                })
        
        if valuable_items:
            elements.append(Paragraph("Top 10 Most Valuable Items", heading_style))
            
            valuable_items.sort(key=lambda x: x['value'], reverse=True)
            top_items = valuable_items[:10]
            
            value_data = [['Item', 'Category', 'Stock', 'Unit Price', 'Total Value']]
            
            for item in top_items:
                value_data.append([
                    item['name'][:30] + ('...' if len(item['name']) > 30 else ''),
                    item['category'],
                    f"{item['stock']:,.0f}",
                    f"KSh {item['price']:,.2f}",
                    f"KSh {item['value']:,.0f}"
                ])
            
            value_table = Table(value_data, colWidths=[2*inch, 1.2*inch, 0.8*inch, 1*inch, 1.2*inch])
            value_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e74c3c')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 8),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8f9fa')),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
                ('FONTSIZE', (0,1), (-1,-1), 9),
                ('TOPPADDING', (0,1), (-1,-1), 5),
                ('BOTTOMPADDING', (0,1), (-1,-1), 5),
            ]))
            elements.append(value_table)
            elements.append(Spacer(1, 20))
        
        # ============================================================
        # 6. LOW STOCK ITEMS
        # ============================================================
        low_items = []
        for item_name, details in inventory_items.items():
            stock = details.get('stock', 0)
            reorder = details.get('reorder', 0)
            if stock < reorder:
                low_items.append({
                    'name': item_name,
                    'stock': stock,
                    'reorder': reorder,
                    'deficit': reorder - stock,
                    'category': details.get('category', 'Uncategorized'),
                    'unit': details.get('unit', 'units')
                })
        
        if low_items:
            elements.append(Paragraph(f"⚠️ Items Below Reorder Point ({len(low_items)} items)", heading_style))
            
            low_items.sort(key=lambda x: x['deficit'], reverse=True)
            
            low_data = [['Item', 'Category', 'Current Stock', 'Reorder Point', 'Deficit']]
            
            for item in low_items[:20]:
                low_data.append([
                    item['name'][:25] + ('...' if len(item['name']) > 25 else ''),
                    item['category'],
                    f"{item['stock']:.0f} {item['unit']}",
                    f"{item['reorder']:.0f} {item['unit']}",
                    f"{item['deficit']:.0f} {item['unit']}"
                ])
            
            if len(low_items) > 20:
                low_data.append(['', '', '', f'And {len(low_items) - 20} more items...', ''])
            
            low_table = Table(low_data, colWidths=[1.8*inch, 1.2*inch, 1*inch, 1*inch, 1*inch])
            low_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#ff9800')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 8),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#fff3e0')),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
                ('FONTSIZE', (0,1), (-1,-1), 9),
                ('TOPPADDING', (0,1), (-1,-1), 5),
                ('BOTTOMPADDING', (0,1), (-1,-1), 5),
            ]))
            elements.append(low_table)
            elements.append(Spacer(1, 20))
        
        # ============================================================
        # 7. RECOMMENDATIONS
        # ============================================================
        elements.append(Paragraph("Recommendations", heading_style))
        
        recommendations = []
        
        if critical_items > 0:
            recommendations.append(f"• 🔴 {critical_items} items are OUT OF STOCK - Order immediately")
        
        if low_stock_items > 0:
            recommendations.append(f"• ⚠️ {low_stock_items} items are below reorder point - Review and replenish")
        
        if overstocked_items > 0:
            recommendations.append(f"• 📦 {overstocked_items} items are overstocked - Consider reducing orders")
        
        if healthy_items < total_items * 0.5:
            recommendations.append("• 📊 Overall inventory health is below 50% - Review all items")
        
        if len(categories) > 1:
            category_issues = {}
            for item_name, details in inventory_items.items():
                category = details.get('category', 'Uncategorized')
                stock = details.get('stock', 0)
                reorder = details.get('reorder', 0)
                
                if category not in category_issues:
                    category_issues[category] = {'low': 0, 'total': 0}
                category_issues[category]['total'] += 1
                if stock < reorder:
                    category_issues[category]['low'] += 1
            
            for cat, data in category_issues.items():
                if data['low'] > 0:
                    recommendations.append(f"• 📂 {cat}: {data['low']}/{data['total']} items need attention")
        
        if not recommendations:
            recommendations.append("• ✅ All inventory items are well-stocked. Continue monitoring.")
        
        recommendations.append("• 📋 Review reorder points regularly based on demand patterns")
        recommendations.append("• 📊 Consider ABC analysis to prioritize high-value items")
        
        for rec in recommendations:
            elements.append(Paragraph(rec, styles['Normal']))
            elements.append(Spacer(1, 6))
        
        # ============================================================
        # 8. FOOTER
        # ============================================================
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(f"Report generated by Browns Food Co - Inventory Management System", 
                                 styles['Normal']))
        elements.append(Paragraph(f"© {datetime.now().year} - All Rights Reserved", 
                                 styles['Normal']))
        
        # Build the report
        doc.build(elements)
        
        return report_path
        
    except ImportError as e:
        st.error(f"Report generation failed: Missing required library - {e}")
        st.info("Please install reportlab: pip install reportlab")
        return None
    except Exception as e:
        st.error(f"Error generating report: {e}")
        return None
    
# ===========================================================
# 🎨 QUICK CREATE MENU 
def quick_create_menu(inventory_tracker):
    """
    Zoho-style Quick Create Menu with floating action button
    """
    # Check if we need to show modals - safely initialize all
    if 'show_quick_receipt' not in st.session_state:
        st.session_state.show_quick_receipt = False
    if 'show_quick_usage' not in st.session_state:
        st.session_state.show_quick_usage = False
    if 'generate_report' not in st.session_state:
        st.session_state.generate_report = False
    if 'quick_receipt_success' not in st.session_state:
        st.session_state.quick_receipt_success = False
    if 'quick_usage_success' not in st.session_state:
        st.session_state.quick_usage_success = False
    if 'quick_orders' not in st.session_state:
        st.session_state.quick_orders = []
    
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
    
    if st.button("📤 Quick Usage", key="quickUsageBtn", type="primary"):
        st.session_state.show_quick_usage = True
        st.session_state.show_quick_receipt = False
        
    
    if st.button("📊 Generate Report", key="quickReportBtn", type="primary"):
        # Trigger report generation
        st.session_state.generate_report = True
        
    
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
                
        
        with col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.show_quick_receipt = False
                
        
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
                        
                else:
                    st.error(f"❌ Insufficient stock! Available: {current_stock:.0f} kg")
        
        with col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.show_quick_usage = False
                
        
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

    # ============================================================
    # 🔐 PASSWORD RESET WITH RATE LIMITING
    # ============================================================

@rate_limited(max_calls=3, period=300)  # 3 password resets per 5 minutes
def request_password_reset(email):
    """
    Request a password reset with rate limiting.
    
    🔐 Rate limited to 3 attempts per 5 minutes to prevent abuse.
    
    Args:
        email: User's email address
    
    Returns:
        dict: Success status and message
    """
    try:
#         from core.advanced_security import PasswordReset
        reset_manager = PasswordReset()
        result = reset_manager.request_reset(email)
        
        # Log the request
        logger.info(f"Password reset requested for: {email}")
        
        return result
    except Exception as e:
        logger.error(f"Password reset request failed: {e}")
        return {
            'success': False, 
            'message': 'Password reset request failed. Please try again later.'
        }

def render_password_reset_form():
    """
    Render password reset form in the sidebar.
    """
    st.sidebar.markdown("""
    <div style="
        background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
        padding: 12px 15px;
        border-radius: 8px;
        color: white;
        margin-bottom: 15px;
    ">
        <div style="font-size: 14px; font-weight: 600;">🔑 Reset Password</div>
        <div style="font-size: 12px; opacity: 0.8;">Enter your email to receive reset instructions</div>
    </div>
    """, unsafe_allow_html=True)
    
    reset_email = st.sidebar.text_input(
        "📧 Email Address", 
        placeholder="user@browns.com",
        key="reset_email_input"
    )
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("📧 Send Reset Link", type="primary", use_container_width=True):
            if reset_email:
                result = request_password_reset(reset_email)
                if result.get('success'):
                    st.sidebar.success(result.get('message', 'Password reset link sent!'))
                    st.sidebar.info("📧 Check your email for reset instructions")
                    # Clear the form
                    st.session_state.reset_email_input = ""
                else:
                    st.sidebar.error(result.get('message', 'Failed to send reset link'))
            else:
                st.sidebar.warning("⚠️ Please enter your email address")
    
    with col2:
        if st.button("← Back to Login", use_container_width=True):
            st.session_state.show_password_reset = False
            st.rerun()
    
    st.sidebar.info("💡 For demo purposes, any valid email will receive a reset link")

def init_stock_take_session():
    """Initialize stock take session state variables (safely)"""
    if 'stock_takes' not in st.session_state:
        st.session_state.stock_takes = {}
    if 'active_count_id' not in st.session_state:
        st.session_state.active_count_id = None
    if 'count_sheets' not in st.session_state:
        st.session_state.count_sheets = {}
    if 'count_assignments' not in st.session_state:
        st.session_state.count_assignments = {}
    if 'stock_take_menu' not in st.session_state:
        st.session_state.stock_take_menu = "📊 Dashboard"
    if 'stock_take_selected_menu' not in st.session_state:
        st.session_state.stock_take_selected_menu = "📊 Dashboard"
    if 'stock_take_inventory' not in st.session_state:
        st.session_state.stock_take_inventory = {}

def generate_count_id():
    """Generate a unique count ID"""
    return f"CT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

def get_status_color(status):
    """Get color for status badge"""
    colors = {
        'Open': '#ffc107',
        'In Progress': '#17a2b8',
        'Ready for Review': '#ff9800',
        'Completed': '#28a745',
        'Pending': '#6c757d',
        'Counted': '#28a745'
    }
    return colors.get(status, '#6c757d')

def get_progress_color(progress):
    """Get color based on progress percentage"""
    if progress >= 0.8:
        return '#28a745'
    elif progress >= 0.5:
        return '#ffc107'
    else:
        return '#dc3545'

def create_stock_count(inventory_items, count_name, count_type="Physical", warehouse="All"):
    """
    Create a new stock count (like inFlow's stock count creation)
    """
    count_id = generate_count_id()
    
    # Create a snapshot of current inventory
    snapshot = {}
    for item, details in inventory_items.items():
        snapshot[item] = {
            'system_qty': details.get('stock', 0),
            'unit': details.get('unit', 'kg'),
            'category': details.get('category', 'Uncategorized'),
            'reorder': details.get('reorder', 0),
            'max': details.get('max', 0),
            'counted_qty': 0,
            'status': 'Pending',
            'variance': 0,
            'notes': ''
        }
    
    st.session_state.stock_takes[count_id] = {
        'id': count_id,
        'name': count_name,
        'type': count_type,
        'warehouse': warehouse,
        'status': 'Open',
        'created': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'created_by': 'Current User',
        'items': snapshot,
        'sheets': [],
        'progress': {
            'total': len(snapshot),
            'counted': 0,
            'pending': len(snapshot)
        }
    }
    
    return count_id

def split_count_into_sheets(count_id, num_sheets=2):
    """
    Split a stock count into multiple sheets (inFlow feature)
    """
    if count_id not in st.session_state.stock_takes:
        return None
    
    count = st.session_state.stock_takes[count_id]
    items = list(count['items'].keys())
    
    if not items:
        return None
    
    # Split items evenly across sheets
    sheet_size = max(1, len(items) // num_sheets)
    sheets = []
    
    for i in range(num_sheets):
        start_idx = i * sheet_size
        end_idx = min((i + 1) * sheet_size, len(items))
        
        if start_idx >= len(items):
            break
            
        sheet_items = items[start_idx:end_idx]
        sheet_id = f"{count_id}-S{i+1:02d}"
        
        sheet = {
            'id': sheet_id,
            'name': f"Sheet {i+1}",
            'items': sheet_items,
            'assigned_to': None,
            'status': 'Pending',
            'counted_items': 0,
            'total_items': len(sheet_items)
        }
        
        sheets.append(sheet)
        st.session_state.count_sheets[sheet_id] = sheet
    
    # Also store as dictionary for easy lookup
    st.session_state.count_sheets.update({s['id']: s for s in sheets})
    count['sheets'] = [s['id'] for s in sheets]
    
    return sheets

def assign_sheet_to_user(sheet_id, user_name):
    """
    Assign a count sheet to a team member (inFlow feature)
    """
    if sheet_id in st.session_state.count_sheets:
        st.session_state.count_sheets[sheet_id]['assigned_to'] = user_name
        return True
    return False

def enter_count(count_id, item_name, counted_qty, sheet_id=None, notes=""):
    """
    Enter count for a specific item (inFlow style)
    """
    if count_id not in st.session_state.stock_takes:
        return False, "Count not found"
    
    count = st.session_state.stock_takes[count_id]
    
    if item_name not in count['items']:
        return False, "Item not in count"
    
    # Update the counted quantity
    count['items'][item_name]['counted_qty'] = counted_qty
    count['items'][item_name]['notes'] = notes
    count['items'][item_name]['status'] = 'Counted'
    
    # Calculate variance
    system_qty = count['items'][item_name]['system_qty']
    variance = counted_qty - system_qty
    count['items'][item_name]['variance'] = variance
    
    # Update progress
    count['progress']['counted'] = sum(1 for item in count['items'].values() if item['status'] == 'Counted')
    count['progress']['pending'] = count['progress']['total'] - count['progress']['counted']
    
    # Update sheet progress if sheet_id provided
    if sheet_id and sheet_id in st.session_state.count_sheets:
        sheet = st.session_state.count_sheets[sheet_id]
        sheet['counted_items'] = sum(1 for item_name in sheet['items'] 
                                     if count['items'][item_name]['status'] == 'Counted')
        
        if sheet['counted_items'] >= sheet['total_items']:
            sheet['status'] = 'Complete'
    
    # Check if all items are counted
    if count['progress']['counted'] >= count['progress']['total']:
        count['status'] = 'Ready for Review'
    else:
        count['status'] = 'In Progress'
    
    return True, "Count recorded successfully"

def get_count_summary(count_id):
    """
    Get summary statistics for a count
    """
    if count_id not in st.session_state.stock_takes:
        return None
    
    count = st.session_state.stock_takes[count_id]
    items = count['items']
    
    total_items = len(items)
    counted_items = sum(1 for item in items.values() if item['status'] == 'Counted')
    pending_items = total_items - counted_items
    
    # Calculate discrepancies
    discrepancies = []
    for item_name, details in items.items():
        if details['status'] == 'Counted' and details['variance'] != 0:
            discrepancies.append({
                'item': item_name,
                'system_qty': details['system_qty'],
                'counted_qty': details['counted_qty'],
                'variance': details['variance'],
                'unit': details['unit']
            })
    
    return {
        'total_items': total_items,
        'counted_items': counted_items,
        'pending_items': pending_items,
        'completion_rate': (counted_items / total_items * 100) if total_items > 0 else 0,
        'discrepancies': discrepancies,
        'has_discrepancies': len(discrepancies) > 0
    }

def complete_and_adjust(count_id):
    """
    Complete the count and adjust inventory (inFlow's "Complete & Adjust" feature)
    """
    if count_id not in st.session_state.stock_takes:
        return False, "Count not found"
    
    count = st.session_state.stock_takes[count_id]
    
    # Check if all items are counted
    if count['progress']['counted'] < count['progress']['total']:
        return False, f"Only {count['progress']['counted']} of {count['progress']['total']} items counted"
    
    # Calculate adjustments
    adjustments = []
    for item_name, details in count['items'].items():
        if details['variance'] != 0:
            adjustments.append({
                'item': item_name,
                'system_qty': details['system_qty'],
                'counted_qty': details['counted_qty'],
                'variance': details['variance'],
                'unit': details['unit']
            })
    
    # Update status
    count['status'] = 'Completed'
    count['completed'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    count['adjustments'] = adjustments
    
    return True, f"Count completed with {len(adjustments)} adjustments"

def get_count_history():
    """
    Get history of completed counts
    """
    history = []
    for count_id, count in st.session_state.stock_takes.items():
        if count['status'] == 'Completed':
            history.append({
                'id': count_id,
                'name': count['name'],
                'type': count['type'],
                'completed': count.get('completed', ''),
                'adjustments': len(count.get('adjustments', []))
            })
    return sorted(history, key=lambda x: x['completed'], reverse=True)

def stock_take_dashboard():
    """
    Stock take dashboard showing overview (inFlow style)
    """
    st.markdown("""
    <div style="
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid rgba(255,255,255,0.08);
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
            📊 Stock Take Dashboard
        </div>
        <div style="color: #888; font-size: 13px;">
            Overview of all stock counts. Manage physical inventory and cycle counts.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Summary stats
    total_counts = len(st.session_state.stock_takes)
    open_counts = sum(1 for c in st.session_state.stock_takes.values() if c['status'] in ['Open', 'In Progress', 'Ready for Review'])
    completed_counts = sum(1 for c in st.session_state.stock_takes.values() if c['status'] == 'Completed')
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 Total Counts", total_counts)
    with col2:
        st.metric("🟡 Active Counts", open_counts)
    with col3:
        st.metric("✅ Completed", completed_counts)
    with col4:
        avg_rate = 0
        if total_counts > 0:
            rates = []
            for count in st.session_state.stock_takes.values():
                if count['progress']['total'] > 0:
                    rates.append(count['progress']['counted'] / count['progress']['total'] * 100)
            avg_rate = sum(rates) / len(rates) if rates else 0
        st.metric("📊 Avg Completion", f"{avg_rate:.0f}%")
    
    # Recent counts
    st.markdown("---")
    st.markdown("#### Recent Counts")
    
    recent = list(st.session_state.stock_takes.values())[-5:]
    if recent:
        recent_data = []
        for count in reversed(recent):
            recent_data.append({
                'ID': count['id'],
                'Name': count['name'],
                'Status': count['status'],
                'Progress': f"{count['progress']['counted']}/{count['progress']['total']}",
                'Created': count['created']
            })
        st.dataframe(pd.DataFrame(recent_data), use_container_width=True, hide_index=True)
    else:
        st.info("No stock counts created yet. Create your first count!")

def stock_take_interface(inventory_items):
    """
    Main stock take interface (inFlow style)
    """
    # Session state is already initialized at the top of main()
    # Just ensure the inventory is stored
    
    # Store inventory items in session state for persistence
    if 'stock_take_inventory' not in st.session_state:
        st.session_state.stock_take_inventory = inventory_items
    
    # Ensure we have sample data if inventory is empty
    if not st.session_state.stock_take_inventory:
        st.session_state.stock_take_inventory = get_sample_inventory_data()
        
    # Use the selected menu from session state (set in main sidebar)
    selected_menu = st.session_state.get('stock_take_selected_menu', "📊 Dashboard")
    # ---- MAIN CONTENT ----
    if selected_menu == "📊 Dashboard":
        stock_take_dashboard()
    elif selected_menu == "📝 New Count":
        new_count_form(st.session_state.stock_take_inventory)
    elif selected_menu == "📋 Active Counts":
        active_counts_interface(st.session_state.stock_take_inventory)
    elif selected_menu == "📜 History":
        count_history_interface()

def new_count_form(inventory_items):
    """
    Form to create a new stock count (inFlow style)
    """
    st.markdown("""
    <div style="
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid rgba(255,255,255,0.08);
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
            📝 Create New Stock Count
        </div>
        <div style="color: #888; font-size: 13px;">
            Create a physical inventory count or cycle count. You can split into multiple sheets and assign to team members.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        count_name = st.text_input(
            "Count Name",
            placeholder="e.g., Warehouse A - July 2024",
            key="count_name_input"
        )
        count_type = st.selectbox(
            "Count Type",
            ["Physical Inventory", "Cycle Count"],
            key="count_type_input"
        )
    
    with col2:
        warehouse = st.selectbox(
            "Warehouse/Location",
            ["All", "Warehouse A", "Warehouse B", "Storage Unit #1", "Storage Unit #2"],
            key="count_warehouse_input"
        )
        num_sheets = st.number_input(
            "Number of Sheets",
            min_value=1,
            max_value=10,
            value=2,
            help="Split count into multiple sheets for team assignments",
            key="num_sheets_input"
        )
    
    # Items to count
    st.markdown("---")
    st.markdown("#### 📦 Items to Count")
    
    items_df = pd.DataFrame([
        {
            'Item': item,
            'Current Stock': details.get('stock', 0),
            'Unit': details.get('unit', 'kg'),
            'Category': details.get('category', 'Uncategorized')
        }
        for item, details in inventory_items.items()
    ])
    
    if not items_df.empty:
        count_all = st.checkbox("Count all items", value=True, key="count_all_items")
        
        if not count_all:
            selected_items = st.multiselect(
                "Select items to count",
                options=items_df['Item'].tolist(),
                default=items_df['Item'].head(10).tolist(),
                key="selected_items_multiselect"
            )
        else:
            selected_items = items_df['Item'].tolist()
        
        st.caption(f"Selected {len(selected_items)} items")
        
        with st.expander("📋 View Selected Items"):
            selected_df = items_df[items_df['Item'].isin(selected_items)]
            st.dataframe(selected_df, use_container_width=True, hide_index=True)
    else:
        selected_items = []
        st.warning("No items available to count")
    
    # Create button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 Create Stock Count", type="primary", use_container_width=True):
            if not count_name:
                st.error("Please enter a count name")
            elif not selected_items:
                st.error("Please select items to count")
            else:
                # Create the count
                count_id = create_stock_count(
                    {item: inventory_items[item] for item in selected_items if item in inventory_items},
                    count_name,
                    count_type,
                    warehouse
                )
                
                # Split into sheets
                if num_sheets > 1:
                    sheets = split_count_into_sheets(count_id, num_sheets)
                    st.success(f"✅ Count '{count_name}' created with {len(sheets)} sheets!")
                else:
                    st.success(f"✅ Count '{count_name}' created successfully!")
                
                st.session_state.active_count_id = count_id
                st.session_state.stock_take_menu = "📋 Active Counts"
                st.info(f"Count ID: {count_id} | Items: {len(selected_items)}")

def active_counts_interface(inventory_items):
    """
    Interface for active counts (inFlow style)
    """
    st.markdown("""
    <div style="
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid rgba(255,255,255,0.08);
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
            📋 Active Stock Counts
        </div>
        <div style="color: #888; font-size: 13px;">
            Manage and complete your stock counts. Track progress and assign sheets to team members.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Open", "In Progress", "Ready for Review", "Completed"],
            key="count_status_filter"
        )
    with col2:
        search = st.text_input(
            "🔍 Search",
            placeholder="Search by count name or ID...",
            key="count_search"
        )
    
    # Display counts
    counts = []
    for count_id, count in st.session_state.stock_takes.items():
        if status_filter != "All" and count['status'] != status_filter:
            continue
        if search and search.lower() not in count['name'].lower() and search.lower() not in count_id.lower():
            continue
        counts.append(count)
    
    if not counts:
        st.info("No counts found matching your filters")
        return
    
    for count in counts:
        with st.container():
            st.markdown(f"""
            <div style="
                background: rgba(255,255,255,0.06);
                backdrop-filter: blur(8px);
                border-radius: 12px;
                padding: 16px 20px;
                margin: 10px 0;
                border: 1px solid rgba(255,255,255,0.08);
            ">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 600; font-size: 16px;">{count['name']}</div>
                        <div style="font-size: 12px; color: #888;">{count['id']} | {count['type']} | Created: {count['created']}</div>
                    </div>
                    <div>
                        <span style="
                            background: {get_status_color(count['status'])};
                            color: white;
                            padding: 4px 12px;
                            border-radius: 20px;
                            font-size: 12px;
                            font-weight: 600;
                        ">
                            {count['status']}
                        </span>
                    </div>
                </div>
                <div style="margin-top: 10px;">
                    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                        <div>
                            <span style="color: #888; font-size: 12px;">Progress</span>
                            <div style="font-weight: 600;">{count['progress']['counted']} / {count['progress']['total']}</div>
                        </div>
                        <div style="flex: 1;">
                            <div style="margin: 4px 0; height: 6px; background: #eee; border-radius: 3px; overflow: hidden;">
                                <div style="
                                    width: {count['progress']['counted'] / count['progress']['total'] * 100 if count['progress']['total'] > 0 else 0}%;
                                    height: 6px;
                                    background: {get_progress_color(count['progress']['counted'] / count['progress']['total'] if count['progress']['total'] > 0 else 0)};
                                    border-radius: 3px;
                                    transition: width 0.6s ease;
                                "></div>
                            </div>
                        </div>
                        <div>
                            <span style="color: #888; font-size: 12px;">Sheets</span>
                            <div style="font-weight: 600;">{len(count['sheets'])}</div>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Action buttons
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("📊 View", key=f"view_{count['id']}", use_container_width=True):
                    st.session_state.active_count_id = count['id']
                    view_count_detail(count['id'])
            
            if count['status'] not in ['Completed', 'Ready for Review']:
                with col2:
                    if st.button("📝 Enter Counts", key=f"enter_{count['id']}", use_container_width=True, type="primary"):
                        st.session_state.active_count_id = count['id']
                        enter_counts_interface(count['id'])
            
            if count['status'] == 'Ready for Review':
                with col3:
                    if st.button("✅ Complete & Adjust", key=f"complete_{count['id']}", use_container_width=True, type="primary"):
                        success, message = complete_and_adjust(count['id'])
                        if success:
                            st.success(message)
                            st.balloons()
                        
                        else:
                            st.error(message)
            
            with col4:
                if count['status'] != 'Completed':
                    if st.button("👥 Assign Sheets", key=f"assign_{count['id']}", use_container_width=True):
                        assign_sheets_interface(count['id'])
            
            st.markdown("---")

def view_count_detail(count_id):
    """
    View detailed information about a count
    """
    if count_id not in st.session_state.stock_takes:
        st.error("Count not found")
        return
    
    count = st.session_state.stock_takes[count_id]
    
    st.markdown(f"""
    <div style="
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 16px;
        margin: 10px 0;
        border: 1px solid rgba(255,255,255,0.08);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="font-size: 18px; font-weight: 600;">{count['name']}</div>
                <div style="font-size: 13px; color: #888;">
                    {count['id']} | {count['type']} | {count['warehouse']} | Created: {count['created']}
                </div>
            </div>
            <div>
                <span style="
                    background: {get_status_color(count['status'])};
                    color: white;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                ">
                    {count['status']}
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sheets
    if count['sheets']:
        st.markdown("#### 📋 Count Sheets")
        
        cols = st.columns(3)
        for idx, sheet_id in enumerate(count['sheets']):
            sheet = st.session_state.count_sheets.get(sheet_id, {})
            if not sheet:
                continue
            
            with cols[idx % 3]:
                st.markdown(f"""
                <div style="
                    background: rgba(255,255,255,0.05);
                    border-radius: 8px;
                    padding: 12px;
                    border: 1px solid rgba(255,255,255,0.05);
                ">
                    <div style="font-weight: 600;">{sheet.get('name', 'Unknown')}</div>
                    <div style="font-size: 12px; color: #888;">
                        Items: {sheet.get('counted_items', 0)}/{sheet.get('total_items', 0)}
                    </div>
                    <div style="font-size: 12px; color: #888;">
                        Assigned: {sheet.get('assigned_to', 'Unassigned')}
                    </div>
                    <div style="font-size: 12px; color: #888;">
                        Status: {sheet.get('status', 'Pending')}
                    </div>
                    <div style="margin-top: 4px; height: 4px; background: #eee; border-radius: 2px;">
                        <div style="
                            width: {sheet.get('counted_items', 0) / sheet.get('total_items', 1) * 100}%;
                            height: 4px;
                            background: {get_progress_color(sheet.get('counted_items', 0) / sheet.get('total_items', 1))};
                            border-radius: 2px;
                        "></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    # Items
    st.markdown("#### 📦 Items in Count")
    
    items_data = []
    for item_name, details in count['items'].items():
        items_data.append({
            'Item': item_name,
            'System Qty': details['system_qty'],
            'Counted Qty': details['counted_qty'],
            'Variance': details['variance'],
            'Status': details['status'],
            'Unit': details['unit'],
            'Notes': details['notes']
        })
    
    df = pd.DataFrame(items_data)
    
    # Apply styling for variance
    def style_variance(val):
        if isinstance(val, (int, float)) and val != 0:
            return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
        return ''
    
    st.dataframe(
        df.style.map(style_variance, subset=['Variance']),
        use_container_width=True,
        hide_index=True
    )
    
    if st.button("← Back to Counts"):
        st.session_state.stock_take_menu = "📋 Active Counts"
        

def enter_counts_interface(count_id):
    """
    Interface for entering counts (inFlow style)
    """
    if count_id not in st.session_state.stock_takes:
        st.error("Count not found")
        return
    
    count = st.session_state.stock_takes[count_id]
    
    st.markdown(f"""
    <div style="
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid rgba(255,255,255,0.08);
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
            📝 Enter Counts - {count['name']}
        </div>
        <div style="color: #888; font-size: 13px;">
            Count ID: {count_id} | Progress: {count['progress']['counted']}/{count['progress']['total']}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Progress
    pct = (count['progress']['counted'] / count['progress']['total'] * 100) if count['progress']['total'] > 0 else 0
    st.progress(pct / 100, text=f"{pct:.0f}% Complete")
    
    # Items to count
    st.markdown("#### Items to Count")
    
    # Get pending items first
    items = []
    for item_name, details in count['items'].items():
        items.append({
            'Item': item_name,
            'System Qty': details['system_qty'],
            'Unit': details['unit'],
            'Status': details['status'],
            'Counted': details['counted_qty'],
            'Variance': details['variance'],
            'Notes': details['notes']
        })
    
    # Sort pending first
    items.sort(key=lambda x: x['Status'] != 'Pending')
    
    # Display items with quick entry
    for item in items:
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
            
            with col1:
                st.markdown(f"**{item['Item']}**")
                st.caption(f"System: {item['System Qty']} {item['Unit']}")
            
            with col2:
                status_icon = "✅" if item['Status'] == 'Counted' else "⏳"
                st.caption(f"{status_icon} {item['Status']}")
            
            with col3:
                if item['Status'] == 'Counted':
                    st.caption(f"Counted: {item['Counted']}")
                    if item['Variance'] != 0:
                        st.caption(f"Variance: {item['Variance']:+.0f}")
            
            with col4:
                if item['Status'] != 'Counted':
                    counted_qty = st.number_input(
                        "Count",
                        min_value=0.0,
                        value=float(item['System Qty']),
                        step=1.0,
                        key=f"count_{count_id}_{item['Item']}",
                        label_visibility="collapsed"
                    )
                    
                    if st.button("✓ Save", key=f"save_{count_id}_{item['Item']}", type="primary"):
                        success, message = enter_count(
                            count_id, 
                            item['Item'], 
                            counted_qty,
                            notes=item['Notes']
                        )
                        if success:
                            st.success(message)
                            
                        else:
                            st.error(message)
            
            st.markdown("---")
    
    # Complete button
    if count['progress']['counted'] >= count['progress']['total']:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("✅ Complete & Adjust", type="primary", use_container_width=True):
                success, message = complete_and_adjust(count_id)
                if success:
                    st.success(message)
                    st.balloons()
                
                else:
                    st.error(message)
    
    if st.button("← Back to Counts"):
        st.session_state.stock_take_menu = "📋 Active Counts"
        

def assign_sheets_interface(count_id):
    """
    Interface for assigning sheets to team members (inFlow feature)
    """
    if count_id not in st.session_state.stock_takes:
        st.error("Count not found")
        return
    
    count = st.session_state.stock_takes[count_id]
    
    st.markdown(f"""
    <div style="
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 16px;
        margin: 10px 0;
        border: 1px solid rgba(255,255,255,0.08);
    ">
        <div style="font-weight: 600;">👥 Assign Sheets - {count['name']}</div>
        <div style="font-size: 13px; color: #888;">
            Assign count sheets to team members for efficient counting.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if not count['sheets']:
        st.info("No sheets to assign. Create sheets first.")
        return
    
    # Team members list
    team_members = ["Unassigned", "John Doe", "Jane Smith", "Mike Johnson", "Sarah Wilson", "David Brown"]
    
    for sheet_id in count['sheets']:
        sheet = st.session_state.count_sheets.get(sheet_id, {})
        if not sheet:
            continue
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.markdown(f"**{sheet.get('name', 'Unknown')}**")
            st.caption(f"{sheet.get('counted_items', 0)}/{sheet.get('total_items', 0)} items")
        
        with col2:
            current_assign = sheet.get('assigned_to', 'Unassigned')
            selected_user = st.selectbox(
                "Assign to",
                team_members,
                index=team_members.index(current_assign) if current_assign in team_members else 0,
                key=f"assign_{sheet_id}",
                label_visibility="collapsed"
            )
            
            if selected_user != current_assign and selected_user != "Unassigned":
                if assign_sheet_to_user(sheet_id, selected_user):
                    st.success(f"✅ Assigned to {selected_user}")
                    
        
        with col3:
            st.caption(f"Status: {sheet.get('status', 'Pending')}")
    
    if st.button("← Back"):
        st.session_state.stock_take_menu = "📋 Active Counts"
        

def count_history_interface():
    """
    Interface for viewing count history    """
    st.markdown("""
    <div style="
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid rgba(255,255,255,0.08);
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
            📜 Count History
        </div>
        <div style="color: #888; font-size: 13px;">
            View completed stock counts and their adjustments.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    history = get_count_history()
    
    if not history:
        st.info("No completed counts found")
        return
    
    # Summary stats
    total_adjustments = sum(h['adjustments'] for h in history)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📋 Total Counts", len(history))
    with col2:
        st.metric("📊 Total Adjustments", total_adjustments)
    with col3:
        avg_adjustments = total_adjustments / len(history) if history else 0
        st.metric("📈 Avg Adjustments/Count", f"{avg_adjustments:.1f}")
    
    st.markdown("---")
    
    # Display history
    history_df = pd.DataFrame(history)
    st.dataframe(history_df, use_container_width=True, hide_index=True)
    
    # Export
    if not history_df.empty:
        csv = history_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download History CSV",
            data=csv,
            file_name=f"stock_take_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )

@log_performance
@st.cache_data(ttl=1800, show_spinner=False)
def create_ensemble_forecast(df, forecast_days=30, selected_models=None):
    """
    Create ensemble forecast combining ALL 8 models:
    Prophet, NeuralProphet, ARIMA, LSTM, Monte Carlo,
    XGBoost, LightGBM, and RandomForest.
    """
    try:
        from app.core.advanced_forecasting_v2 import AdvancedForecaster
        from app.core.external_factors import ExternalFactors
        import warnings
        warnings.filterwarnings('ignore')
        
        # Initialize the forecaster (now has ALL 8 models!)
        forecaster = AdvancedForecaster()
        
        # Initialize external factors
        external = ExternalFactors()
        external_factors = external.get_all_external_factors()
        
        # Create future dates
        last_date = df['Date'].max()
        future_dates = pd.date_range(last_date, periods=forecast_days + 1, freq='D')[1:]
        
        # Prepare external features for future dates
        external_features = external.prepare_external_features(future_dates)
        
        # Log external factors being used
        logger.info(f"External factors included: {list(external_factors.keys())}")
        logger.info(f"External features shape: {external_features.shape if external_features is not None else 'None'}")
        
        # Generate forecast using selected models (or all 8 if none specified)
        results = forecaster.forecast(df, forecast_days, models=selected_models)
        logger.info("=== MODEL TYPES BEFORE ENSEMBLE ===")
        for name, result in results.items():
            logger.info(
                f"{name}: type={type(result).__name__} "
                f"value={str(result)[:100] if result is not None else 'None'}"
            )
        # Get ensemble forecast
        ensemble_values = np.array(results['ensemble']['forecast'])
        
        # ============================================================
        # Model display names for ALL 8 models
        
        model_display_names = {
            'prophet': 'Prophet',
            'neural_prophet': 'NeuralProphet',
            'arima': 'ARIMA',
            'lstm': 'LSTM',
            'monte_carlo': 'Monte Carlo',
            'xgboost': 'XGBoost',
            'lightgbm': 'LightGBM',
            'random_forest': 'RandomForest'
        }
        
        # ============================================================
        # Track active models and their statistics
        
        model_forecasts = {}
        active_models = []
        
        for name, result in results.items():
            if name != 'ensemble' and result is not None and isinstance(result, dict) and 'forecast' in result:
                forecast_values = result['forecast']
                if len(forecast_values) == forecast_days:
                    display_name = model_display_names.get(name, name.title())
                    model_forecasts[display_name] = {
                        'avg': np.mean(forecast_values),
                        'min': np.min(forecast_values),
                        'max': np.max(forecast_values),
                        'std': np.std(forecast_values)
                    }
                    active_models.append(display_name)
        
        # ============================================================
        # Create model comparison DataFrame
        
        model_comparison = []
        for name, stats in model_forecasts.items():
            model_comparison.append({
                'Model': name,
                'Avg Forecast (kg)': f"{stats['avg']:.1f}",
                'Min (kg)': f"{stats['min']:.1f}",
                'Max (kg)': f"{stats['max']:.1f}",
                'Std Dev': f"{stats['std']:.1f}",
                'Status': '✅ Active'
            })
        
        # ============================================================
        # Store in session state for dashboard display
        
        st.session_state.model_comparison = pd.DataFrame(model_comparison)
        st.session_state.active_models = len(active_models)
        st.session_state.active_models_list = active_models
        
        # Log which models are active
        logger.info(f"✅ Active models: {len(active_models)}/8 - {active_models}")
        
        # ============================================================
        # Calculate backtest accuracy
        
        try:
            X, y = forecaster.prepare_features(df)
            
            # Calculate metrics by training on historical data
            test_size = min(30, len(X) // 3)
            if test_size > 0:
                # Use the last test_size points for backtesting
                X_train, X_test = X[:-test_size], X[-test_size:]
                y_train, y_test = y[:-test_size], y[-test_size:]
                
                # Train a simple model for backtesting
                from sklearn.ensemble import RandomForestRegressor
                test_model = RandomForestRegressor(n_estimators=50, random_state=42)
                test_model.fit(X_train, y_train)
                predictions = test_model.predict(X_test)
                
                # Convert to arrays and align lengths
                y_true = np.array(y_test)
                y_pred = np.array(predictions[:len(y_test)])
                
                # Remove NaNs
                mask = ~(np.isnan(y_true) | np.isnan(y_pred))
                y_true = y_true[mask]
                y_pred = y_pred[mask]
                
                if len(y_true) > 1:
                    # MAE
                    mae = np.mean(np.abs(y_true - y_pred))
                    mean_actual = max(np.mean(y_true), 1)
                    mae_normalized = min(mae / mean_actual, 1)
                    
                    # R² - stricter: if negative, contribution is 0
                    ss_res = np.sum((y_true - y_pred) ** 2)
                    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
                    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                    if r2 < 0:
                        r2_normalized = 0  # No credit for worse than mean
                    else:
                        r2_normalized = min(r2, 1)
                    
                    # Direction accuracy
                    # np.mean() of a boolean comparison already returns a
                    # fraction in [0, 1] — do NOT divide by 100 again.
                    actual_direction = np.sign(np.diff(y_true))
                    pred_direction = np.sign(np.diff(y_pred))
                    direction_normalized = (
                        np.mean(actual_direction == pred_direction)
                        if len(actual_direction) > 0
                        else 0
                    )
                    
                    # WAPE penalty - smooth decay instead of MAPE's hard cliff.
                    # MAPE explodes on near-zero actuals (common with
                    # intermittent demand); WAPE is robust to that.
                    wape = np.sum(np.abs(y_true - y_pred)) / max(np.sum(np.abs(y_true)), 1e-8) * 100
                    wape_penalty = max(0, min(1, 1 - (wape - 50) / 150)) if wape > 50 else 1
                    
                    # Composite score (0-1 scale) with penalties
                    backtest_accuracy = (
                        0.4 * (1 - mae_normalized) +
                        0.3 * r2_normalized +
                        0.3 * direction_normalized
                    ) * wape_penalty
                else:
                    backtest_accuracy = 0
                
                # Ensure it's between 0 and 1
                backtest_accuracy = max(0, min(1, backtest_accuracy))
            else:
                backtest_accuracy = 0.85
        except Exception as e:
            logger.warning(f"Backtest accuracy calculation failed: {e}")
            backtest_accuracy = 0.85
        
        # ============================================================
        # 🔧 FIX: Get best model from results
        # ============================================================
        # The best model is now stored in the ensemble results
        best_model_name = results['ensemble'].get('_best_model', None)
        best_model_score = results['ensemble'].get('_best_score', None)
        
        if best_model_name:
            st.session_state.best_model = {
                'name': model_display_names.get(best_model_name, best_model_name.title()),
                'score': f"{best_model_score:.1f}" if best_model_score else "N/A",
                'accuracy': f"{backtest_accuracy*100:.1f}%"
            }
        elif active_models:
            # Fallback: use first active model
            st.session_state.best_model = {
                'name': active_models[0],
                'score': "N/A",
                'accuracy': f"{backtest_accuracy*100:.1f}%"
            }
        
        # ============================================================
        # Create visualization with external factors info
        fig = create_forecast_visualization_with_external(
            df, results, forecast_days, external_factors, external_features
        )
        
        # Add external factors info to model forecasts
        if external_factors:
            model_forecasts['External Factors'] = ', '.join(list(external_factors.keys())[:3])
            if len(external_factors) > 3:
                model_forecasts['External Factors'] += f' and {len(external_factors)-3} more'
        
        return fig, ensemble_values, model_forecasts, backtest_accuracy
        
    except ImportError as e:
        logger.error(f"AdvancedForecaster or ExternalFactors import failed: {e}")
        st.warning("⚠️ Advanced forecasting or external factors not available. Using legacy forecast.")
        return create_legacy_forecast(df, forecast_days)
        
    except Exception as e:
        logger.error(f"Advanced forecast failed: {e}")
        st.warning(f"⚠️ Advanced forecast failed: {str(e)}. Using legacy forecast.")
        return create_legacy_forecast(df, forecast_days)


def create_legacy_forecast(df, forecast_days=30):
    """
    Legacy forecast function as fallback.
    This is your original forecasting code.
    """
    try:
        # Your original forecasting code here
        # (Copy your original create_ensemble_forecast code that uses Prophet, ARIMA, LSTM, Monte Carlo)
        
        dates = pd.to_datetime(df['Date'])
        values = df['Order_Quantity_kg'].values.astype(float)
        
        # Fallback: use simple average
        avg_demand = np.mean(values) if len(values) > 0 else 300.0
        ensemble_forecast = np.full(forecast_days, max(0, avg_demand))
        
        # Create simple visualization
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, 
            y=values, 
            name='Historical Demand',
            line=dict(color='blue', width=2)
        ))
        
        future_dates = pd.date_range(dates.max(), periods=forecast_days + 1, freq='D')[1:]
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=ensemble_forecast,
            name='Average Forecast (Fallback)',
            line=dict(color='orange', width=2)
        ))
        
        fig.update_layout(
            title='30-Day Demand Forecast (Simple Average - Fallback)',
            xaxis_title='Date',
            yaxis_title='Demand (kg)',
            height=500
        )
        
        model_forecasts = {'Simple Average': avg_demand}
        backtest_accuracy = 0.80
        
        return fig, ensemble_forecast, model_forecasts, backtest_accuracy
        
    except Exception as e:
        logger.error(f"Legacy forecast failed: {e}")
        # Ultra fallback
        avg_demand = 300.0
        ensemble_forecast = np.full(forecast_days, avg_demand)
        
        fig = go.Figure()
        fig.add_annotation(text="⚠️ Forecast unavailable - using default values", showarrow=False)
        
        return fig, ensemble_forecast, {'Default': avg_demand}, 0.0


def create_forecast_visualization(df, results, forecast_days):
    """
    Create visualization for all model forecasts.
    """
    import plotly.graph_objects as go
    
    fig = go.Figure()
    
    # Historical data
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Order_Quantity_kg'],
        name='Historical Demand',
        line=dict(color='blue', width=2)
    ))
    
    # Future dates
    future_dates = pd.date_range(
        df['Date'].max(), 
        periods=forecast_days + 1, 
        freq='D'
    )[1:]
    
    # Color palette for models
    colors = ['#2ecc71', '#e74c3c', '#9b59b6', '#f39c12', '#1abc9c']
    color_idx = 0
    
    # Add each model's forecast
    for name, result in results.items():
        if name != 'ensemble' and result and isinstance(result, dict) and 'forecast' in result:
            forecast_values = result['forecast']
            if len(forecast_values) == forecast_days:
                # Clean up model names for display
                display_name = name.replace('_', ' ').title()
                
                fig.add_trace(go.Scatter(
                    x=future_dates,
                    y=forecast_values,
                    name=display_name,
                    line=dict(dash='dot', color=colors[color_idx % len(colors)])
                ))
                color_idx += 1
    
    # Add ensemble forecast
    if 'ensemble' in results and results['ensemble']:
        ensemble_values = results['ensemble']['forecast']
        
        # Ensemble line
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=ensemble_values,
            name='Ensemble Forecast',
            line=dict(color='black', width=3)
        ))
        
        # Confidence interval
        if 'upper' in results['ensemble'] and 'lower' in results['ensemble']:
            fig.add_trace(go.Scatter(
                x=future_dates,
                y=results['ensemble']['upper'],
                fill=None,
                mode='lines',
                line_color='rgba(0,0,0,0)',
                showlegend=False
            ))
            fig.add_trace(go.Scatter(
                x=future_dates,
                y=results['ensemble']['lower'],
                fill='tonexty',
                mode='lines',
                line_color='rgba(0,0,0,0)',
                name='Confidence Interval (80%)',
                fillcolor='rgba(255,127,14,0.2)'
            ))
    
    fig.update_layout(
        title='30-Day Demand Forecast with Ensemble Methods',
        xaxis_title='Date',
        yaxis_title='Demand (kg)',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        height=500,
        hovermode='x unified'
    )
    
    return fig

def create_forecast_visualization_with_external(df, results, forecast_days, external_factors=None, external_features=None):
    """
    Create visualization for all model forecasts with external factors info.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    # Create subplots with extra space for external factors
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.75, 0.25],
        subplot_titles=("Demand Forecast", "External Factors Impact"),
        vertical_spacing=0.12
    )
    
    # Historical data (main chart)
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Order_Quantity_kg'],
        name='Historical Demand',
        line=dict(color='blue', width=2),
        legendgroup='historical',
        showlegend=True
    ), row=1, col=1)
    
    # Future dates
    future_dates = pd.date_range(
        df['Date'].max(), 
        periods=forecast_days + 1, 
        freq='D'
    )[1:]
    
    # Color palette for models
    colors = ['#2ecc71', '#e74c3c', '#9b59b6', '#f39c12', '#1abc9c']
    color_idx = 0
    
    # Add each model's forecast
    for name, result in results.items():
        if name != 'ensemble' and result and isinstance(result, dict) and 'forecast' in result:
            forecast_values = result['forecast']
            if len(forecast_values) == forecast_days:
                # Clean up model names for display
                display_name = name.replace('_', ' ').title()
                
                fig.add_trace(go.Scatter(
                    x=future_dates,
                    y=forecast_values,
                    name=display_name,
                    line=dict(dash='dot', color=colors[color_idx % len(colors)]),
                    legendgroup='models',
                    showlegend=True
                ), row=1, col=1)
                color_idx += 1
    
    # Add ensemble forecast
    if 'ensemble' in results and results['ensemble']:
        ensemble_values = results['ensemble']['forecast']
        
        # Ensemble line
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=ensemble_values,
            name='Ensemble Forecast',
            line=dict(color='black', width=3),
            legendgroup='ensemble',
            showlegend=True
        ), row=1, col=1)
        
        # Confidence interval
        if 'upper' in results['ensemble'] and 'lower' in results['ensemble']:
            fig.add_trace(go.Scatter(
                x=future_dates,
                y=results['ensemble']['upper'],
                fill=None,
                mode='lines',
                line_color='rgba(0,0,0,0)',
                showlegend=False
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=future_dates,
                y=results['ensemble']['lower'],
                fill='tonexty',
                mode='lines',
                line_color='rgba(0,0,0,0)',
                name='Confidence Interval (80%)',
                fillcolor='rgba(255,127,14,0.2)',
                legendgroup='ensemble',
                showlegend=True
            ), row=1, col=1)
    
    # Add external factors visualization (bottom chart)
    if external_factors and external_features is not None:
        # Show external factors that might impact demand
        factor_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']
        
        # Get external factor names
        factor_names = list(external_factors.keys())
        
        # Show top external factors (up to 4)
        for idx, factor_name in enumerate(factor_names[:4]):
            if factor_name in external_features.columns:
                # Normalize the factor for display
                factor_values = external_features[factor_name].values
                if len(factor_values) == forecast_days:
                    # Normalize to 0-1 range for display
                    if factor_values.max() > factor_values.min():
                        normalized = (factor_values - factor_values.min()) / (factor_values.max() - factor_values.min())
                    else:
                        normalized = factor_values / (factor_values.max() + 1e-10)
                    
                    fig.add_trace(go.Scatter(
                        x=future_dates,
                        y=normalized,
                        name=factor_name.replace('_', ' ').title(),
                        line=dict(color=factor_colors[idx % len(factor_colors)], width=2),
                        legendgroup='external',
                        showlegend=True
                    ), row=2, col=1)
        
        # Update y-axis for external factors
        fig.update_yaxes(title_text="Impact (Normalized)", row=2, col=1)
    
    # Update layout
    fig.update_layout(
        title='30-Day Demand Forecast with External Factors',
        xaxis_title='Date',
        yaxis_title='Demand (kg)',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        height=700,  # Increased height for external factors
        hovermode='x unified'
    )
    
    # Update x-axis for bottom chart
    fig.update_xaxes(title_text="Date", row=2, col=1)
    
    return fig

def create_scenario_analysis(forecast, historical_data):
    """
    Create multiple demand scenarios.
    """
    scenarios = {
        'p50': {
            'name': 'Likely Scenario (50th Percentile)',
            'description': 'Base case - most likely outcome',
            'multiplier': 1.0,
            'color': '#28a745'
        },
        'p70': {
            'name': 'Optimistic Scenario (70th Percentile)',
            'description': 'Higher demand than expected',
            'multiplier': 1.15,
            'color': '#4caf50'
        },
        'p90': {
            'name': 'Worst Case (90th Percentile)',
            'description': 'Prepare for high demand',
            'multiplier': 1.30,
            'color': '#dc3545'
        },
        'promotional': {
            'name': 'Promotional Impact',
            'description': 'Demand spike from promotion',
            'multiplier': 1.25,
            'color': '#ff9800'
        },
        'supply_chain': {
            'name': 'Supply Chain Disruption',
            'description': 'Delayed supply impact',
            'multiplier': 0.80,
            'color': '#ff5722'
        },
        'economic': {
            'name': 'Economic Downturn',
            'description': 'Reduced demand due to economy',
            'multiplier': 0.70,
            'color': '#9c27b0'
        },
        'weather': {
            'name': 'Weather Impact',
            'description': 'Weather affecting demand',
            'multiplier': [0.9, 1.1],  # Variable impact
            'color': '#2196f3'
        },
        'best_case': {
            'name': 'Best Case Scenario',
            'description': 'Everything goes perfectly',
            'multiplier': 1.40,
            'color': '#00bcd4'
        },
        'worst_case': {
            'name': 'Worst Case Scenario',
            'description': 'Everything goes wrong',
            'multiplier': 0.60,
            'color': '#e91e63'
        }
    }
    
    scenario_results = {}
    
    base_forecast = np.array(forecast)
    
    for key, scenario in scenarios.items():
        multiplier = scenario['multiplier']
        
        if isinstance(multiplier, list):
            # Variable multiplier over time
            scenario_forecast = base_forecast * np.linspace(multiplier[0], multiplier[1], len(base_forecast))
        else:
            scenario_forecast = base_forecast * multiplier
        
        scenario_results[key] = {
            'name': scenario['name'],
            'description': scenario['description'],
            'forecast': scenario_forecast.tolist(),
            'color': scenario['color'],
            'total_demand': sum(scenario_forecast),
            'avg_daily': np.mean(scenario_forecast)
        }
    
    return scenario_results

def render_scenario_analysis(scenario_results, forecast_days):
    """
    Render scenario analysis in UI.
    """
    import plotly.graph_objects as go
    from datetime import datetime, timedelta
    fig = go.Figure()
    
    # Create dates
    future_dates = pd.date_range(datetime.now(), periods=forecast_days, freq='D')
    
    # Add each scenario
    for key, scenario in scenario_results.items():
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=scenario['forecast'],
            name=scenario['name'],
            line=dict(color=scenario['color'], width=2, dash='dot' if key != 'p50' else 'solid'),
            mode='lines+markers',
            hovertemplate='%{y:,.0f} kg<extra></extra>'
        ))
    
    fig.update_layout(
        title='📊 Demand Scenarios',
        xaxis_title='Date',
        yaxis_title='Demand (kg)',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        height=400
    )
    
    return fig

def render_scenario_summary(scenario_results):
    """
    Render scenario summary cards.
    """
    # Summary cards
    cols = st.columns(min(4, len(scenario_results)))
    
    for idx, (key, scenario) in enumerate(scenario_results.items()):
        if idx >= 4:
            break
            
        with cols[idx]:
            st.markdown(f"""
            <div style="
                background: rgba(255,255,255,0.05);
                border-radius: 10px;
                padding: 12px;
                text-align: center;
                border-left: 3px solid {scenario['color']};
                margin-bottom: 8px;
            ">
                <div style="font-size: 12px; font-weight: 600; color: #888;">
                    {scenario['name']}
                </div>
                <div style="font-size: 20px; font-weight: 700; color: {scenario['color']};">
                    {scenario['avg_daily']:.0f}
                </div>
                <div style="font-size: 10px; color: #999;">
                    avg kg/day
                </div>
                <div style="font-size: 10px; color: #999; margin-top: 2px;">
                    Total: {scenario['total_demand']:,.0f} kg
                </div>
            </div>
            """, unsafe_allow_html=True)    

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
    global px
    # Initialize all session state variables with defaults
    session_defaults = {
        'initialized': True,
        'db_initialized': False,
        'transactions': [],
        'selected_period': '2024/2025',
        'last_loaded_period': None,
        'stock_takes': {},
        'active_count_id': None,
        'count_sheets': {},
        'count_assignments': {},
        'stock_take_menu': "📊 Dashboard",
        'stock_take_selected_menu': "📊 Dashboard",
        'inventory_items_count': 0,
        'inventory_sample': {},
        'load_attempts': 0,
        'show_quick_receipt': False,
        'show_quick_usage': False,
        'quick_receipt_success': False,
        'quick_usage_success': False,
        'generate_report': False,
        'confirm_clear_pressed': False,
        'quick_orders': [],
        'stock_take_inventory': {},
        'show_password_reset': False,  
        'reset_email_input': '',       
        'rate_limit_warning': None,
        'selected_models': ['prophet', 'arima', 'lstm', 'monte_carlo', 'xgboost', 'lightgbm', 'random_forest'],
    }
    
    for key, value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # 🚀 OPTIMIZE SESSION STATE
    # Remove unnecessary large data from session state
    try:
        optimize_session_state()
        logger.info("Session state optimized")
    except Exception as e:
        logger.warning(f"Session state optimization skipped: {e}")
    
    # Log memory usage
    try:
        memory_mb = get_memory_usage()
        logger.info(f"💾 Memory usage at startup: {memory_mb:.1f} MB")
    except Exception as e:
        logger.warning(f"Memory usage logging skipped: {e}")

    if not st.session_state.db_initialized:
        init_db()
        fix_order_date()
        seed_historical_data()
        get_historical_orders_from_db.clear()
        st.session_state.db_initialized = True
        print("✅ Database initialized")


    # Sidebar - Header with Glass Design (ABOVE Analysis Period)
    st.sidebar.markdown("""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px 20px;
        border-radius: 12px;
        color: white;
        margin-bottom: 20px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    ">
        <div style="font-size: 20px; font-weight: 700;">Inventory Control</div>
        <div style="font-size: 12px; opacity: 0.8;">Browns Food Co</div>
    </div>
    """, unsafe_allow_html=True)

    # ============================================================
    # 🔐 AUTHENTICATION STATUS INDICATOR
    # ============================================================
    auth_check = st.session_state.get('_auth')
    if auth_check and auth_check.is_authenticated:
        st.sidebar.markdown("🟢 Logged in")
    else:
        st.sidebar.markdown("🔴 Logged out")

    # ============================================================
    # 🔐 AUTHENTICATION SECTION (Compact)
    # ============================================================
    with st.sidebar.expander("🔐", expanded=False):
        try:
            auth = st.session_state.get('_auth')
            if auth is None:
                if SECURITY_AVAILABLE:
                    auth = AuthManager()
                    st.session_state._auth = auth
                else:
                    class DummyAuth:
                        is_authenticated = False
                        current_user = None
                        current_role = None
                        def render_login_form(self):
                            st.warning("🔒 Security module unavailable")
                        def render_password_reset_form(self):
                            st.warning("🔒 Password reset unavailable")
                    auth = DummyAuth()
            
            if st.session_state.get('show_password_reset', False):
                render_password_reset_form()
            else:
                if '2fa_pending' in st.session_state or st.session_state.get('_2fa_pending'):
                    st.markdown("""
                    <div style="
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 6px 12px;
                        border-radius: 6px;
                        color: white;
                        margin-bottom: 10px;
                        text-align: center;
                        font-size: 13px;
                    ">
                        🔐 2FA
                    </div>
                    """, unsafe_allow_html=True)
                    
                    two_fa_code = st.text_input(
                        "6-digit code", 
                        type="password", 
                        placeholder="123456",
                        label_visibility="collapsed"
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅", use_container_width=True):
                            two_factor = TwoFactorAuth()
                            if hasattr(auth, 'verify_2fa'):
                                result = auth.verify_2fa(two_fa_code)
                                if result['success']:
                                    st.success(result['message'])
                                    st.rerun()
                                else:
                                    st.error(result['message'])
                            else:
                                if two_factor.verify_2fa_login(two_fa_code):
                                    st.success("✅ Verified!")
                                    st.rerun()
                                else:
                                    st.error("❌ Invalid")
                    with col2:
                        if st.button("✕", use_container_width=True):
                            if hasattr(auth, 'cancel_2fa'):
                                auth.cancel_2fa()
                            st.rerun()
                else:
                    auth.render_login_form()
            
            # Security Dashboard (Admin Only)
            if auth.is_authenticated and auth.current_role == 'admin':
                if st.button("🛡️ Dashboard", use_container_width=True):
                    st.session_state.show_security_dashboard = True

        except Exception as e:
            st.error(f"❌ {str(e)[:50]}")
            import traceback
            st.code(traceback.format_exc())
            logger.error(f"Auth UI error: {e}", exc_info=True)

    # ============================================================
    # VIEW MODE SELECTOR 
    st.sidebar.markdown("""
    <div style="
        border: 2px solid #667eea;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        background: rgba(102, 126, 234, 0.05);
    ">
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            margin-bottom: 12px;
            display: inline-block;
            font-size: 14px;
            font-weight: 700;
        ">
            🔄 View Mode
        </div>
    """, unsafe_allow_html=True)

    inventory_mode = st.sidebar.radio(
        "Select inventory view:",
        ["📦 All Items Mode", "❄️ Dry Ice Mode"],
        help="Switch between general inventory management and Dry Ice analysis",
        key="inventory_mode"
    )

    st.sidebar.markdown("</div>", unsafe_allow_html=True)
    
    st.sidebar.header("🗓️ Analysis Period")
    analysis_periods = ['2024/2025', '2025/2026', '2026/2027', '2027/2028', '2028/2029']

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
   
    # Ensure database is initialized before any queries
    if not st.session_state.get('db_initialized', False):
        init_db()
        fix_order_date()
        seed_historical_data()
        get_historical_orders_from_db.clear()
        st.session_state.db_initialized = True
        print("✅ Database initialized")
    
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
    # Initialize advanced analytics
    analytics = AdvancedAnalytics() 

   # Try to load from Google Sheets first
    @st.cache_data(ttl=600)
    @safe_operation(error_message="Failed to load inventory data")
    def load_inventory_data():
        """
        Load inventory data from Google Sheets with comprehensive error handling.
        """
        inventory_items = {}
        stock_df = None
        
        try:
            logger.info("Loading inventory data from Google Sheets...")
            gsheet = GoogleSheetReader()
            
            # Check authentication
            if not gsheet.authenticate():
                logger.warning("Google Sheets authentication failed. Using sample data.")
                st.info("📊 Could not connect to Google Sheets. Using sample data for demonstration.")
                return get_sample_inventory_data(), None
            
            logger.info("Google Sheets authentication successful. Fetching data...")
            stock_df = gsheet.get_stock_with_pricing()
            
            # ============================================================
            # 🚀 COMPRESS DATAFRAME TO REDUCE MEMORY USAGE
            # ============================================================
            if not stock_df.empty:
                original_size = len(stock_df)
                original_memory = stock_df.memory_usage(deep=True).sum() / 1024 / 1024
                
                stock_df = compress_dataframe(stock_df)
                
                compressed_memory = stock_df.memory_usage(deep=True).sum() / 1024 / 1024
                reduction = ((original_memory - compressed_memory) / original_memory) * 100
                
                logger.info(f"📊 Stock DataFrame compressed: {original_size} rows")
                logger.info(f"💾 Memory: {original_memory:.1f}MB → {compressed_memory:.1f}MB (↓{reduction:.0f}%)")
            else:
                logger.warning("Google Sheets returned empty data. Using sample data.")
                st.info("📊 No data found in Google Sheets. Using sample data for demonstration.")
                return get_sample_inventory_data(), None
            
            # Check if data is empty
            if stock_df.empty:
                logger.warning("Google Sheets returned empty data. Using sample data.")
                st.info("📊 No data found in Google Sheets. Using sample data for demonstration.")
                return get_sample_inventory_data(), None
            
            logger.info(f"Retrieved {len(stock_df)} rows from Google Sheets")
            
            # Process the data with error handling for each row
            processed_count = 0
            skipped_count = 0
            
            for _, row in stock_df.iterrows():
                try:
                    # Get item name
                    item_name = row.get('ITEM_NAME', 'Unknown')
                    if not item_name or str(item_name).strip() == '':
                        skipped_count += 1
                        continue
                    
                    # Safe conversion for stock
                    try:
                        stock_val = row.get('QUANTITY', 0)
                        if pd.isna(stock_val) or str(stock_val).strip() == '':
                            stock = 0
                        else:
                            stock = float(stock_val)
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Error converting stock for {item_name}: {e}")
                        stock = 0
                    
                    # Skip items with zero or negative stock
                    if stock <= 0:
                        skipped_count += 1
                        continue
                    
                    # Safe conversion for reorder level
                    try:
                        reorder_val = row.get('REORDER LEVEL', 0)
                        if pd.isna(reorder_val) or str(reorder_val).strip() == '':
                            reorder = stock * 0.5
                        else:
                            reorder = float(reorder_val)
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Error converting reorder for {item_name}: {e}")
                        reorder = stock * 0.5
                    
                    # Safe conversion for price
                    try:
                        price_val = row.get('UNIT PRICE', 0)
                        if pd.isna(price_val) or str(price_val).strip() == '':
                            price = 0
                        else:
                            price = float(price_val)
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Error converting price for {item_name}: {e}")
                        price = 0
                    
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
                    
                    # Get unit of measure
                    unit = row.get('UNIT_OF_MEASURE', 'kg')
                    if pd.isna(unit) or str(unit).strip() == '':
                        unit = 'kg'
                    
                    # Create inventory item
                    inventory_items[item_name] = {
                        'icon': icon,
                        'stock': stock,
                        'reorder': reorder,
                        'max': max(stock * 2, reorder * 3, 100),
                        'unit': unit,
                        'category': category if category else 'Uncategorized',
                        'location': 'Warehouse',
                        'price': price
                    }
                    processed_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error processing row for {row.get('ITEM_NAME', 'Unknown')}: {e}")
                    skipped_count += 1
                    continue
            
            logger.info(f"Processed {processed_count} items, skipped {skipped_count} items")
            
            # Check if we have any valid items
            if not inventory_items:
                logger.warning("No valid inventory items found after processing. Using sample data.")
                st.warning("⚠️ No valid inventory items found in Google Sheets. Using sample data.")
                return get_sample_inventory_data(), None
            
            logger.info(f"Successfully loaded {len(inventory_items)} inventory items")
            return inventory_items, stock_df
            
        except Timeout as e:
            logger.error(f"Timeout loading inventory: {e}")
            st.warning("⏰ Request timed out. Using sample data for now.")
            st.info("💡 Please check your internet connection and try again.")
            return get_sample_inventory_data(), None
            
        except ConnectionError as e:
            logger.error(f"Connection error loading inventory: {e}")
            st.warning("🌐 Network error. Using sample data for now.")
            st.info("💡 Please check your internet connection and try again.")
            return get_sample_inventory_data(), None
            
        except Exception as e:
            logger.error(f"Unexpected error loading inventory: {e}", exc_info=True)
            st.warning("⚠️ Could not load from Google Sheets. Using sample data.")
            st.info("💡 Please check your Google Sheets configuration and try again.")
            return get_sample_inventory_data(), None

    inventory_items, stock_df = load_inventory_data()
    
    # Initialize session state for transactions
    if 'last_loaded_period' not in st.session_state or st.session_state.last_loaded_period != st.session_state.selected_period:
        print(f"Period changed. Loading transactions for {st.session_state.selected_period}...")
        st.session_state.transactions = get_transactions_from_db(st.session_state.selected_period)
        st.session_state.last_loaded_period = st.session_state.selected_period # Update the tracker
    
    
    #1. Generate Forecast (Logic from former Tab 2) ---
    @st.cache_data(ttl=1800)
    def get_forecast_data(df):
        """Get cached forecast data with proper error handling"""
        # Check if df is None or empty
        if df is None or df.empty:
            return None, np.array([0]), {}, 0, 0, 0
        
        # Check if DataFrame has required columns
        if 'Date' not in df.columns or 'Order_Quantity_kg' not in df.columns:
            return None, np.array([0]), {}, 0, 0, 0
        
        # Check if there's enough data
        if len(df) < 5:
            st.warning(f"⚠️ Limited historical data ({len(df)} points). Forecast reliability may be reduced.")
            # Use simple average for limited data
            avg_value = df['Order_Quantity_kg'].mean() if 'Order_Quantity_kg' in df.columns else 0
            # Create a simple forecast using average
            ensemble_forecast_values = np.full(30, max(0, avg_value))
            total_forecasted_demand = np.sum(ensemble_forecast_values)
            forecast_std_dev = np.std(ensemble_forecast_values)
            
            # Create a simple visualization
            dates = pd.to_datetime(df['Date'])
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=df['Order_Quantity_kg'], name='Actual Demand', 
                                    line=dict(color='blue', width=2)))
            future_dates = pd.date_range(dates.max(), periods=31)[1:]
            fig.add_trace(go.Scatter(x=future_dates, y=ensemble_forecast_values, 
                                    name='Conservative Forecast', 
                                    line=dict(color='orange', width=3)))
            fig.update_layout(title='Conservative Forecast (Limited Historical Data)', 
                             xaxis_title='Date', yaxis_title='Demand (kg)')
            
            return fig, ensemble_forecast_values, {'Simple Average': avg_value}, 0.2, total_forecasted_demand, forecast_std_dev
        
        try:
            daily_df = df.set_index('Date').resample('D')['Order_Quantity_kg'].sum().reset_index()
            daily_df = daily_df.rename(columns={'Date': 'Date', 'Order_Quantity_kg': 'Order_Quantity_kg'})
            
            # Check if resampled data has any values
            if daily_df.empty or daily_df['Order_Quantity_kg'].sum() == 0:
                return None, np.array([0]), {}, 0, 0, 0
            
            fig_ensemble, ensemble_forecast_values, model_forecasts, backtest_accuracy = create_ensemble_forecast(
            daily_df, forecast_days=30, selected_models=st.session_state.get('selected_models')
        )
            
            # Check if forecast returned valid values
            if ensemble_forecast_values is None or len(ensemble_forecast_values) == 0:
                return None, np.array([0]), {}, 0, 0, 0
            
            total_forecasted_demand = np.sum(ensemble_forecast_values)
            forecast_std_dev = np.std(ensemble_forecast_values)
            
            return fig_ensemble, ensemble_forecast_values, model_forecasts, backtest_accuracy, total_forecasted_demand, forecast_std_dev
            
        except Exception as e:
            st.warning(f"⚠️ Forecast generation failed: {str(e)}")
            return None, np.array([0]), {}, 0, 0, 0
    
    # Check if we have data before generating forecast
    if not df.empty and len(df) >= 5:
        with st.spinner("🔄 Generating forecast with auto-tuned models..."):
            # ✅ FIX: Use get_forecast_data() which aggregates by day
            fig_ensemble, ensemble_forecast_values, model_forecasts, backtest_accuracy, total_forecasted_demand, forecast_std_dev = get_forecast_data(df)
            
            # Update model forecasts with proper names
            if model_forecasts:
                # Add backtest accuracy to model forecasts
                model_forecasts['Backtest Accuracy'] = f"{backtest_accuracy*100:.1f}%"
            
            # Log success
            logger.info(f"Forecast generated: {len(ensemble_forecast_values)} days, models: {len(model_forecasts)-1}")
            
    else:
        # No data or insufficient data for forecasting
        fig_ensemble = None
        ensemble_forecast_values = np.array([0])
        model_forecasts = {}
        backtest_accuracy = 0
        total_forecasted_demand = 0
        forecast_std_dev = 0
        
        if df.empty:
            st.info("📊 No order data found for this period. Record a receipt to begin analysis.")
        else:
            st.warning(f"⚠️ Insufficient data ({len(df)} orders). Need at least 5 orders for reliable forecasting.")

    
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
    
    z_score = norm.ppf(constants.SERVICE_LEVEL)
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
    
    # Initialize other components
    mobile_ui = MobileInterface()
    #alerts_system = SmartAlerts(inventory_tracker)
    maintenance_system = PredictiveMaintenance()
    integration_system = SystemIntegrations()
    
    # ============================================================
    # SECTION 1: REAL-TIME INVENTORY (Container Style)
    # ============================================================
    st.sidebar.markdown("""
    <div style="
        border: 2px solid #4fc3f7;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        background: rgba(79, 195, 247, 0.05);
    ">
        <div style="
            background: #4fc3f7;
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            margin-bottom: 12px;
            display: inline-block;
            font-size: 14px;
            font-weight: 700;
        ">
            📦 Real-time Inventory
        </div>
    """, unsafe_allow_html=True)

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

    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # ============================================================
    # SECTION 2: UPDATE INVENTORY (Compact Expanders)
    # ============================================================
    with st.sidebar.expander("📤 Record Usage", expanded=False):
        usage_date = st.date_input("Usage Date", value=datetime.today())

        usage = safe_number_input(
            "Quantity Used (kg)",
            min_value=0.0,
            max_value=10000.0,
            value=150.0,
            step=10.0,
            validate=True,
            key="usage_qty",
            container=st
        )

        current_stock_val = inventory_tracker.current_stock
        st.caption(f"📊 Available: {current_stock_val:,.0f} kg")

        if usage is not None and usage > 0:
            is_valid, msg = validate_stock_sufficient(usage, current_stock_val)
            if not is_valid:
                st.error(msg)
            elif "Warning" in msg:
                st.warning(msg)
            else:
                st.success(msg)

        if st.button("Record Usage", type="primary", key="record_usage_btn"):
            auth = AuthManager()
            if not auth.is_authenticated:
                st.error("🔒 Please login to record usage")
                return
            if not auth.check_permission('record_usage'):
                st.error("⛔ You don't have permission to record usage")
                return

            if usage is None or usage <= 0:
                st.error("❌ Please enter a valid quantity")
                return

            is_valid, msg = validate_stock_sufficient(usage, current_stock_val)
            if not is_valid:
                st.error(msg)
                return

            if usage > 500:
                if not st.checkbox("☑️ Confirm large usage (>500kg)", key="confirm_large_usage"):
                    st.warning("⚠️ Please confirm large usage before proceeding")
                    return

            try:
                audit = AuditLogger()
                audit.log(
                    action='RECORD_USAGE',
                    details=f"Usage: {usage}kg, Date: {usage_date}",
                    user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
                )

                alert = inventory_tracker.update_stock(usage, "Daily Consumption", usage_date)
                add_transaction_to_history(
                    "usage", usage, "Daily Consumption", usage_date,
                    st.session_state.selected_period
                )

                if alert is not None:
                    st.error(alert["message"])
                else:
                    audit.log(
                        action='RECORD_USAGE_SUCCESS',
                        details=f"Usage: {usage}kg recorded successfully, New stock: {inventory_tracker.current_stock}kg",
                        user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
                    )
                    st.success(f"✅ Usage of {usage:.0f} kg recorded on {usage_date.strftime('%Y-%m-%d')}.")
                    new_stock_val = inventory_tracker.current_stock
                    st.info(f"📊 New stock level: {new_stock_val:,.0f} kg")
                    if new_stock_val < safety_stock:
                        st.warning(f"⚠️ Stock below safety stock ({safety_stock:,.0f} kg). Consider reordering.")

            except Exception as e:
                logger.error(f"Failed to record usage: {e}", exc_info=True)
                st.error("❌ Failed to record usage. Please try again.")

    with st.sidebar.expander("📥 Record Receipt", expanded=False):
        receipt_date = st.date_input("Receipt Date", value=datetime.today(), key="receipt_date")

        current_stock_val = inventory_tracker.current_stock
        st.caption(f"📊 Current stock: {current_stock_val:,.0f} kg")

        new_stock = safe_number_input(
            "New Stock Received (kg)",
            min_value=0.0,
            max_value=100000.0,
            value=0.0,
            step=50.0,
            validate=True,
            key="receipt_qty",
            container=st
        )

        if new_stock is not None and new_stock > 0:
            new_total = current_stock_val + new_stock
            st.info(f"📊 New stock after receipt: {new_total:,.0f} kg (+{new_stock:,.0f} kg)")
            if new_stock > 1000:
                st.warning(f"⚠️ Large receipt: {new_stock:.0f} kg. Please confirm below.")
            max_recommended = safety_stock * 3
            if new_total > max_recommended:
                st.warning(f"⚠️ New stock ({new_total:,.0f} kg) exceeds recommended maximum ({max_recommended:,.0f} kg)")

        if receipt_date:
            is_valid, msg = validate_date(receipt_date, allow_future=False)
            if not is_valid:
                st.error(msg)

        if st.button("Record Receipt", type="primary", key="record_receipt_btn"):
            if new_stock is None or new_stock <= 0:
                st.error("❌ Please enter a valid quantity greater than 0")
                return

            is_valid, msg = validate_date(receipt_date, allow_future=False)
            if not is_valid:
                st.error(msg)
                return

            if new_stock > 1000:
                if not st.checkbox("☑️ Confirm large receipt (>1000kg)", key="confirm_large_receipt"):
                    st.warning("⚠️ Please confirm large receipt before proceeding")
                    return

            try:
                correct_period = get_period_from_date(receipt_date)
                old_stock = inventory_tracker.current_stock

                inventory_tracker.current_stock += new_stock
                update_current_stock_in_db(inventory_tracker.current_stock, receipt_date)

                add_transaction_to_history(
                    transaction_type="receipt",
                    quantity=new_stock,
                    description="Stock Receipt",
                    date=receipt_date,
                    period=correct_period
                )

                st.success(
                    f"✅ Order for {new_stock:.0f} kg on {receipt_date.strftime('%Y-%m-%d')} recorded. "
                    f"It has been automatically assigned to the {correct_period} period."
                )

                new_total = inventory_tracker.current_stock
                st.info(f"📊 Stock updated: {old_stock:,.0f} → {new_total:,.0f} kg (+{new_stock:,.0f} kg)")

                max_recommended = safety_stock * 3
                if new_total > max_recommended:
                    st.warning(f"⚠️ Stock ({new_total:,.0f} kg) exceeds recommended maximum ({max_recommended:,.0f} kg)")
                    st.info("💡 Consider reducing future orders or increasing usage")

                if st.session_state.selected_period != correct_period:
                    st.session_state.selected_period = correct_period
                    st.info(f"📊 Dashboard view switched to {correct_period} to show your new entry.")

            except ValidationError as e:
                st.error(f"❌ Validation Error: {e}")
            except DatabaseError as e:
                st.error(f"⚠️ Database Error: {e}")
                st.info("💡 Your data was saved locally. It will sync when the cloud is available.")
            except Exception as e:
                logger.error(f"Failed to record receipt: {e}", exc_info=True)
                st.error("❌ Failed to record receipt. Please try again.")
                st.info("💡 If the problem persists, please contact support.")

    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # ============================================================
    # SECTION 3: MOBILE QUICK ORDER (Container Style)
    # ============================================================
    # Mobile Quick Order Entry (only show on mobile devices)
    if mobile_ui.is_mobile_device():
        st.sidebar.markdown("""
        <div style="
            border: 2px solid #ce93d8;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            background: rgba(206, 147, 216, 0.05);
        ">
            <div style="
                background: #ce93d8;
                color: white;
                padding: 6px 12px;
                border-radius: 8px;
                margin-bottom: 12px;
                display: inline-block;
                font-size: 14px;
                font-weight: 700;
            ">
                📱 Mobile Quick Order
            </div>
        """, unsafe_allow_html=True)
        
        quick_order = mobile_ui.quick_order_entry()
        
        if quick_order:
            with st.spinner("Processing your order..."):
                correct_period = get_period_from_date(quick_order['delivery_date'])
                inventory_tracker.current_stock += quick_order['quantity']
                update_current_stock_in_db(inventory_tracker.current_stock, quick_order['delivery_date'])
                add_transaction_to_history(
                    transaction_type="receipt",
                    quantity=quick_order['quantity'],
                    description=f"Quick Order: {quick_order['product']} - {quick_order['notes'] if quick_order['notes'] else 'No notes'}",
                    date=quick_order['delivery_date'],
                    period=correct_period
                )
                st.sidebar.success(f"""
                ✅ **Order Placed Successfully!**
                
                Product: {quick_order['product']}
                Quantity: {quick_order['quantity']} kg
                Delivery: {quick_order['delivery_date'].strftime('%Y-%m-%d')}
                """)
                if 'quick_orders' not in st.session_state:
                    st.session_state.quick_orders = []
                st.session_state.quick_orders.append(quick_order)
        
        st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # ============================================================
    # SECTION 4: ENHANCED STOCK STATUS (Container Style)
    # ============================================================
    st.sidebar.markdown("""
    <div style="
        border: 2px solid #ffd54f;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        background: rgba(255, 213, 79, 0.05);
    ">
        <div style="
            background: #ffd54f;
            color: #333;
            padding: 6px 12px;
            border-radius: 8px;
            margin-bottom: 12px;
            display: inline-block;
            font-size: 14px;
            font-weight: 700;
        ">
            📊 Stock Status
        </div>
    """, unsafe_allow_html=True)

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

    st.sidebar.markdown("</div>", unsafe_allow_html=True)
    
    # Initialize SmartAlerts after inventory_tracker is created
    alerts_system = SmartAlerts(inventory_tracker)
    mobile_ui.optimize_for_mobile()
    mobile_ui.show_mobile_welcome()

    # Header
    start_date_str = display_start_date.strftime('%B %d, %Y')
    end_date_str = display_end_date.strftime('%B %d, %Y')

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # ============================================================
        # 🎯 LOGO + TITLE + PERIOD IN ONE RECTANGULAR CONTAINER
        # ============================================================
        logo_path = "assets/browns_logo.jpg"
        start_date_str = display_start_date.strftime('%B %d, %Y')
        end_date_str = display_end_date.strftime('%B %d, %Y')
        
        # Get base64 image
        logo_src = get_image_base64(logo_path) if os.path.exists(logo_path) else ""
        
        # SINGLE HTML BLOCK - everything inside
        st.markdown(f"""
        <div style="
            background: white;
            border-radius: 20px;
            padding: 30px 20px 25px 20px;
            margin: 10px 0 20px 0;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
            border: 1px solid rgba(0, 0, 0, 0.06);
            text-align: center;
        ">
            <div style="margin-bottom: 12px;">
                <img src="{logo_src}" style="height: 80px; width: auto; object-fit: contain; border-radius: 8px;">
            </div>
            <div style="
                font-size: 28px;
                font-weight: 700;
                color: #1a237e;
                letter-spacing: -0.3px;
                margin-bottom: 8px;
            ">
                DRY ICE INVENTORY OPTIMIZER
            </div>
            <div style="
                height: 2px;
                background: linear-gradient(90deg, transparent, #1565c0, transparent);
                margin: 10px auto 14px auto;
                width: 60%;
            "></div>
            <div style="
                display: inline-block;
                font-size: 28px;
                font-weight: 700;
                color: #1a237e;
                letter-spacing: -0.3px;
                padding: 0;
            ">
                {start_date_str} – {end_date_str}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ============================================================
    # SECTION 5: REPORT GENERATOR (Container Style)
    # ============================================================
    st.sidebar.markdown("""
    <div style="
        border: 2px solid #ff8a65;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        background: rgba(255, 138, 101, 0.05);
    ">
        <div style="
            background: #ff8a65;
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            margin-bottom: 12px;
            display: inline-block;
            font-size: 14px;
            font-weight: 700;
        ">
            📄 Report Generation
        </div>
    """, unsafe_allow_html=True)

    # Report type selection
    report_type = st.sidebar.selectbox(
        "Report Type",
        ["❄️ Dry Ice Report (Legacy)", "📊 All Inventory Report", "📋 Low Stock Report", "💰 Valuable Items Report"],
        key="report_type_sidebar"
    )

    # ============================================================
    # GENERATE REPORT BUTTON WITH SECURITY & VALIDATION
    # ============================================================
    if st.sidebar.button("Generate Report", type="primary"):
        # ============================================================
        # 🔐 AUTHENTICATION CHECK
        # ============================================================
        auth = AuthManager()
        if not auth.is_authenticated:
            st.sidebar.error("🔒 Please login to generate reports")
            return
        if not auth.check_permission('view_reports'):
            st.sidebar.error("⛔ You don't have permission to view reports")
            return
        
        with st.spinner(f"Generating {report_type}..."):
            try:
                # ============================================================
                # 🔐 AUDIT LOGGING
                # ============================================================
                audit = AuditLogger()
                audit.log(
                    action='GENERATE_REPORT',
                    details=f"Report type: {report_type}",
                    user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
                )
                
                report_path = None
                
                if report_type == "❄️ Dry Ice Report (Legacy)":
                    if df is not None and not df.empty:
                        report = ReportGenerator(analyzer=analyzer, df=df)
                        report_path = report.generate_pdf()
                    else:
                        st.sidebar.error("No Dry Ice data available.")
                
                elif report_type == "📊 All Inventory Report":
                    if inventory_items:
                        report_path = generate_enhanced_pdf_report(
                            inventory_items=inventory_items,
                            stock_df=stock_df if 'stock_df' in locals() else None,
                            kpis=kpis
                        )
                    else:
                        st.sidebar.error("No inventory data available. Please load from Google Sheets.")
                
                elif report_type == "📋 Low Stock Report":
                    if inventory_items:
                        low_stock_items = {}
                        for item_name, details in inventory_items.items():
                            stock = details.get('stock', 0)
                            reorder = details.get('reorder', 0)
                            if stock < reorder:
                                low_stock_items[item_name] = details
                        
                        if low_stock_items:
                            report_path = generate_enhanced_pdf_report(
                                inventory_items=low_stock_items,
                                stock_df=stock_df if 'stock_df' in locals() else None,
                                kpis=kpis
                            )
                        else:
                            st.sidebar.success("✅ No low stock items found!")
                    else:
                        st.sidebar.error("No inventory data available.")
                
                elif report_type == "💰 Valuable Items Report":
                    if inventory_items:
                        valuable_items = {}
                        for item_name, details in inventory_items.items():
                            price = details.get('price', 0)
                            stock = details.get('stock', 0)
                            if price > 0 and stock > 0:
                                valuable_items[item_name] = details
                        
                        if valuable_items:
                            report_path = generate_enhanced_pdf_report(
                                inventory_items=valuable_items,
                                stock_df=stock_df if 'stock_df' in locals() else None,
                                kpis=kpis
                            )
                        else:
                            st.sidebar.warning("No items with price data found.")
                    else:
                        st.sidebar.error("No inventory data available.")
                
                if report_path:
                    # ============================================================
                    # 🔐 AUDIT LOGGING - SUCCESS
                    # ============================================================
                    audit.log(
                        action='GENERATE_REPORT_SUCCESS',
                        details=f"Report type: {report_type} generated successfully",
                        user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
                    )
                    
                    with open(report_path, "rb") as f:
                        st.sidebar.download_button(
                            label="📥 Download Report",
                            data=f,
                            file_name=f"inventory_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                        )
                    st.sidebar.success(f"✅ {report_type} generated successfully!")
                else:
                    st.sidebar.error("Failed to generate report.")
                    
            except Exception as e:
                # ============================================================
                # 🔐 AUDIT LOGGING - ERROR
                # ============================================================
                audit.log(
                    action='GENERATE_REPORT_ERROR',
                    details=f"Report type: {report_type}, Error: {str(e)}",
                    user=auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
                )
                st.sidebar.error(f"Error generating report: {str(e)}")

    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # ============================================================
    # SECTION 6: STOCK TAKE MENU (Container Style)
    # ============================================================
    st.sidebar.markdown("""
    <div style="
        border: 2px solid #90a4ae;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        background: rgba(144, 164, 174, 0.05);
    ">
        <div style="
            background: #90a4ae;
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            margin-bottom: 12px;
            display: inline-block;
            font-size: 14px;
            font-weight: 700;
        ">
            📋 Stock Take Menu
        </div>
    """, unsafe_allow_html=True)

    menu_options = [
        "📊 Dashboard",
        "📝 New Count",
        "📋 Active Counts",
        "📜 History"
    ]

    if 'stock_take_selected_menu' not in st.session_state:
        st.session_state.stock_take_selected_menu = "📊 Dashboard"

    selected_menu = st.sidebar.radio(
        "Select Action",
        menu_options,
        index=menu_options.index(st.session_state.stock_take_selected_menu),
        key="stock_take_menu_main"
    )

    if selected_menu != st.session_state.stock_take_selected_menu:
        st.session_state.stock_take_selected_menu = selected_menu

    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # ============================================================
    # SECTION 7: SYSTEM PARAMETERS (Container Style)
    # ============================================================
    st.sidebar.markdown("""
    <div style="
        border: 2px solid #b39ddb;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        background: rgba(179, 157, 219, 0.05);
    ">
        <div style="
            background: #b39ddb;
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            margin-bottom: 12px;
            display: inline-block;
            font-size: 14px;
            font-weight: 700;
        ">
            ⚙️ System Parameters
        </div>
    """, unsafe_allow_html=True)

    with st.sidebar.expander("Inventory Parameters"):
        st.write(f"**Price per kg:** KSh {constants.PRICE_PER_KG:.2f}")
        st.write(f"**Container size:** {constants.CONTAINER_SIZE} kg")
        st.write(f"**Transport cost:** KSh {constants.TRANSPORT_COST:,.2f}")
        st.write(f"**Holding rate:** {constants.HOLDING_RATE*100:.1f}%")
        st.write(f"**Sublimation loss:** {constants.SUB_LOSS_RANGE[0]:.1f}-{constants.SUB_LOSS_RANGE[1]:.1f}%")
        st.write(f"**Lead time:** {constants.LEAD_TIME_DAYS} day(s)")
        st.write(f"**Service level:** {constants.SERVICE_LEVEL*100:.0f}%")

    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # ============================================================
    # SECTION 8: DATA SUMMARY (Container Style)
    # ============================================================
    st.sidebar.markdown("""
    <div style="
        border: 2px solid #4dd0e1;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        background: rgba(77, 208, 225, 0.05);
    ">
        <div style="
            background: #4dd0e1;
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            margin-bottom: 12px;
            display: inline-block;
            font-size: 14px;
            font-weight: 700;
        ">
            📊 Data Summary
        </div>
    """, unsafe_allow_html=True)

    # --- OPTIMIZE DATA DISPLAY ---
    # Show only summary stats, not full data
    sidebar_start_str = display_start_date.strftime('%d/%m/%Y')
    sidebar_end_str = display_end_date.strftime('%d/%m/%Y')

    # Use len(df) efficiently
    total_orders = len(df) if df is not None else 0
    data_points = df.shape[0] if df is not None and hasattr(df, 'shape') else 0

    st.sidebar.write(f"**Analysis Period:** {sidebar_start_str} to {sidebar_end_str}")
    st.sidebar.write(f"**Total Orders:** {total_orders:,}")
    st.sidebar.write(f"**Data Points:** {data_points:,}")

    # ============================================================
    # 🆕 SHOW MEMORY USAGE (Enterprise Monitoring)
    # ============================================================
    try:
        memory_mb = get_memory_usage()
        st.sidebar.caption(f"💾 Memory: {memory_mb:.0f} MB")
    except:
        pass

    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # ============================================================
    # 🔗 SERVICE STATUS (Compact Expander)
    # ============================================================
    with st.sidebar.expander("🔗 Service Status", expanded=False):
        service_manager = ServiceStatusManager()
        service_manager.show_service_status()

    st.sidebar.markdown("</div>", unsafe_allow_html=True)
    
    # ============================================================
    # SECTION 9: FOOTER (Container Style) - INCREASED FONT SIZES
    # ============================================================
    st.sidebar.markdown("""
    <div style="
        border-radius: 12px;
        padding: 18px 15px;
        text-align: center;
        background: rgba(0,0,0,0.03);
        border: 1px solid rgba(0,0,0,0.05);
    ">
        <div style="font-size: 16px; font-weight: 700; color: #333; margin-bottom: 4px;">
            🧀 Browns Cheese
        </div>
        <div style="font-size: 14px; color: #666; margin-top: 4px;">
            Dry Ice Management System
        </div>
        <div style="font-size: 13px; color: #888; margin-top: 6px;">
            © 2025 - Gathura Chege
        </div>
    </div>
    """, unsafe_allow_html=True)

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

    # Row 1: Main KPIs (4 columns)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Current Stock - Color coded based on status
        stock_status = inventory_tracker.get_stock_status()
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 8px;
            text-align: center;
            border-left: 3px solid {stock_status['color']};
        ">
            <div style="font-size: 10px; color: #888; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">
                📦 Current Stock
            </div>
            <div style="font-size: 22px; font-weight: 700; color: #333; margin: 4px 0;">
                {inventory_tracker.current_stock:,.0f}
            </div>
            <div style="font-size: 11px; color: {stock_status['color']}; font-weight: 600;">
                {stock_status['status']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 8px;
            text-align: center;
            border-left: 3px solid #4fc3f7;
        ">
            <div style="font-size: 10px; color: #888; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">
                📋 Total Orders
            </div>
            <div style="font-size: 22px; font-weight: 700; color: #333; margin: 4px 0;">
                {kpis.get('total_orders', 0):,}
            </div>
            <div style="font-size: 11px; color: #888;">
                {kpis.get('total_volume', 0):,.0f} kg total
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 8px;
            text-align: center;
            border-left: 3px solid #ff9800;
        ">
            <div style="font-size: 10px; color: #888; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">
                🛡️ Safety Stock
            </div>
            <div style="font-size: 22px; font-weight: 700; color: #333; margin: 4px 0;">
                {safety_stock:,.1f}
            </div>
            <div style="font-size: 11px; color: #888;">
                {kpis.get('order_frequency', 0):.1f} orders/mo
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 8px;
            text-align: center;
            border-left: 3px solid #9c27b0;
        ">
            <div style="font-size: 10px; color: #888; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">
                📦 Economic EOQ
            </div>
            <div style="font-size: 22px; font-weight: 700; color: #333; margin: 4px 0;">
                {eoq:,.1f}
            </div>
            <div style="font-size: 11px; color: #888;">
                Optimal order size
            </div>
        </div>
        """, unsafe_allow_html=True)

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
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 8px;
            text-align: center;
            border-left: 3px solid #e74c3c;
        ">
            <div style="font-size: 10px; color: #888; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">
                💰 Annual Spending
            </div>
            <div style="font-size: 18px; font-weight: 700; color: #333; margin: 4px 0;">
                KSh {total_annual_spending:,.0f}
            </div>
            <div style="font-size: 11px; color: #888;">
                Total cost
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 8px;
            text-align: center;
            border-left: 3px solid #28a745;
        ">
            <div style="font-size: 10px; color: #888; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">
                🚀 Annual Transport Savings
            </div>
            <div style="font-size: 18px; font-weight: 700; color: #28a745; margin: 4px 0;">
                KSh {annual_transport_savings:,.0f}
            </div>
            <div style="font-size: 11px; color: #888;">
                From EOQ optimization
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        delta_color = "#28a745" if percent_savings > 0 else "#dc3545"
        delta_arrow = "▲" if percent_savings > 0 else "▼"
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 8px;
            text-align: center;
            border-left: 3px solid #ff6f00;
        ">
            <div style="font-size: 10px; color: #888; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">
                📈 Monthly Savings
            </div>
            <div style="font-size: 18px; font-weight: 700; color: #333; margin: 4px 0;">
                KSh {monthly_savings:,.0f}
            </div>
            <div style="font-size: 12px; color: {delta_color}; font-weight: 600;">
                {delta_arrow} {percent_savings:+.1f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        container_eff = kpis.get('container_utilization', 0) * 100
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 8px;
            text-align: center;
            border-left: 3px solid #00bcd4;
        ">
            <div style="font-size: 10px; color: #888; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">
                📊 Container Efficiency
            </div>
            <div style="font-size: 22px; font-weight: 700; color: #333; margin: 4px 0;">
                {container_eff:.1f}%
            </div>
            <div style="font-size: 11px; color: #888;">
                Fill rate
            </div>
        </div>
        """, unsafe_allow_html=True)

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

    # ============================================================
    # 🔐 SECURITY DASHBOARD
    if st.session_state.get('show_security_dashboard', False):
        from core.security import render_security_dashboard
        render_security_dashboard()
        st.stop()

    # ============================================================
    # CONTAINER 1: ALL ITEMS MODE (5 TABS)
    # Get the current mode
    mode = st.session_state.get('inventory_mode', '📦 All Items Mode')

    if mode == "📦 All Items Mode":
        # ============================================================
        # 🎨 ALL ITEMS THEME + MODE BADGE
        st.markdown("""
        <style>
            /* All Items Theme - Warm Colors */
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
                background: rgba(255,255,255,0.05);
                backdrop-filter: blur(4px);
                border-radius: 12px;
                padding: 8px;
                border: 1px solid rgba(255,255,255,0.08);
            }
            .stTabs [aria-selected="true"] {
                background: linear-gradient(135deg, #e65100 0%, #ff9800 100%) !important;
                color: white !important;
                box-shadow: 0 4px 15px rgba(230, 81, 0, 0.3) !important;
            }
            .stTabs [data-baseweb="tab"]:hover {
                background: rgba(230, 81, 0, 0.08) !important;
                color: #e65100 !important;
            }
            /* Mode Badge */
            .mode-badge-all {
                background: linear-gradient(135deg, #e65100, #ff9800);
                color: white;
                padding: 6px 16px;
                border-radius: 20px;
                display: inline-block;
                font-weight: 600;
                font-size: 14px;
                margin-bottom: 15px;
                box-shadow: 0 2px 10px rgba(230, 81, 0, 0.3);
            }
        </style>
        
        <div class="mode-badge-all">📦 ALL ITEMS MODE</div>
        """, unsafe_allow_html=True)
        
        # ALL ITEMS CONTAINER - 5 Tabs
        tab_inventory, tab_movements, tab_analytics, tab_inventory_visual, tab_advanced = st.tabs([
            "📦 Inventory",
            "📊 Stock Movements",
            "📈 All Items Analytics",
            "🖼️ Visual Inventory",
            "🤖 Advanced Analytics"
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

            with st.spinner("📊Loading inventory data..."):
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

                # --- ABC ANALYSIS (Operationalized) ---
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
                            
                            # ============================================================
                            # 🎯 OPERATIONALIZE ABC ANALYSIS - inFlow Style
                            # ============================================================
                            
                            # Define cycle counting frequencies based on ABC class
                            cycle_frequencies = {
                                '🔴 A (70% value)': {
                                    'frequency': 'Monthly',
                                    'days': 30,
                                    'priority': 'High',
                                    'color': '#dc3545',
                                    'count_per_year': 12
                                },
                                '🟡 B (20% value)': {
                                    'frequency': 'Quarterly',
                                    'days': 90,
                                    'priority': 'Medium',
                                    'color': '#ffc107',
                                    'count_per_year': 4
                                },
                                '🟢 C (10% value)': {
                                    'frequency': 'Annually',
                                    'days': 365,
                                    'priority': 'Low',
                                    'color': '#28a745',
                                    'count_per_year': 1
                                }
                            }
                            
                            # Create cycle counting schedule
                            cycle_schedule = []
                            for _, row in abc_df.iterrows():
                                class_label = row['ABC_CLASS']
                                freq_info = cycle_frequencies.get(class_label, cycle_frequencies['🟢 C (10% value)'])
                                
                                cycle_schedule.append({
                                    'Item': row['ITEM_NAME'],
                                    'Category': row.get('ITEM_CATEGORY', 'Uncategorized'),
                                    'ABC Class': class_label,
                                    'Annual Value': row['ANNUAL_VALUE'],
                                    'Count Frequency': freq_info['frequency'],
                                    'Priority': freq_info['priority'],
                                    'Counts per Year': freq_info['count_per_year']
                                })
                            
                            cycle_df = pd.DataFrame(cycle_schedule)
                            
                            # Display cycle counting schedule summary
                            st.markdown("#### 🔄 Cycle Counting Recommendations")
                            
                            col1, col2, col3, col4 = st.columns(4)
                            
                            # Count items by class
                            a_count = len(abc_df[abc_df['ABC_CLASS'] == '🔴 A (70% value)'])
                            b_count = len(abc_df[abc_df['ABC_CLASS'] == '🟡 B (20% value)'])
                            c_count = len(abc_df[abc_df['ABC_CLASS'] == '🟢 C (10% value)'])
                            
                            with col1:
                                st.metric(
                                    "🔴 A Items (Monthly)",
                                    a_count,
                                    delta=f"{a_count * 12} counts/year"
                                )
                            with col2:
                                st.metric(
                                    "🟡 B Items (Quarterly)",
                                    b_count,
                                    delta=f"{b_count * 4} counts/year"
                                )
                            with col3:
                                st.metric(
                                    "🟢 C Items (Annually)",
                                    c_count,
                                    delta=f"{c_count} counts/year"
                                )
                            with col4:
                                total_counts = (a_count * 12) + (b_count * 4) + c_count
                                st.metric(
                                    "📊 Total Counts/Year",
                                    total_counts,
                                    delta=f"~{total_counts // 12} counts/month"
                                )
                            
                            # Show detailed cycle counting schedule with styling
                            with st.expander("📋 View Cycle Counting Schedule", expanded=False):
                                # Style by priority
                                def style_priority(val):
                                    if 'High' in val:
                                        return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
                                    elif 'Medium' in val:
                                        return 'background-color: #fff3cd; color: #856404;'
                                    else:
                                        return 'background-color: #d4edda; color: #155724;'
                                
                                styled_cycle_df = cycle_df.style.applymap(style_priority, subset=['Priority'])
                                
                                st.dataframe(
                                    styled_cycle_df,
                                    use_container_width=True,
                                    height=300,
                                    hide_index=True
                                )
                            
                            # ============================================================
                            # 🎯 REPLENISHMENT STRATEGY BY ABC CLASS
                            # ============================================================
                            st.markdown("#### 📦 Replenishment Strategy by ABC Class")
                            
                            # Create replenishment strategies
                            replenishment_data = []
                            for _, row in abc_df.iterrows():
                                class_label = row['ABC_CLASS']
                                stock = row.get('QUANTITY', 0)
                                
                                # Get reorder level (if available, otherwise use 50% of stock)
                                if 'REORDER LEVEL' in row and pd.notna(row['REORDER LEVEL']):
                                    reorder = row['REORDER LEVEL']
                                else:
                                    reorder = stock * 0.5
                                
                                # Set safety stock multiplier based on ABC class
                                if '🔴 A' in class_label:
                                    safety_multiplier = 0.3
                                    order_frequency = 'Monthly'
                                elif '🟡 B' in class_label:
                                    safety_multiplier = 0.2
                                    order_frequency = 'Quarterly'
                                else:
                                    safety_multiplier = 0.1
                                    order_frequency = 'As Needed'
                                
                                safety_stock_val = reorder * (1 + safety_multiplier)
                                
                                # Check if below safety stock
                                below_safety = stock < safety_stock_val
                                
                                replenishment_data.append({
                                    'Item': row['ITEM_NAME'],
                                    'ABC Class': class_label,
                                    'Current Stock': stock,
                                    'Reorder Point': round(reorder, 0),
                                    'Safety Stock': round(safety_stock_val, 0),
                                    'Order Frequency': order_frequency,
                                    'Annual Value': row['ANNUAL_VALUE'],
                                    'Below Safety': '⚠️ Yes' if below_safety else '✅ No'
                                })
                            
                            replenishment_df = pd.DataFrame(replenishment_data)
                            
                            # Display replenishment summary
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                # Count items needing immediate attention
                                urgent_items = len(replenishment_df[replenishment_df['Below Safety'] == '⚠️ Yes'])
                                st.metric(
                                    "⚠️ Below Safety Stock",
                                    urgent_items,
                                    delta=f"-{urgent_items}" if urgent_items > 0 else None
                                )
                            with col2:
                                # Total value of A items
                                a_value = replenishment_df[replenishment_df['ABC Class'] == '🔴 A (70% value)']['Annual Value'].sum()
                                st.metric(
                                    "💰 A Items Value",
                                    f"KSh {a_value:,.0f}",
                                    f"{a_value/total_value*100:.0f}% of total"
                                )
                            with col3:
                                # Most critical items
                                critical = replenishment_df[
                                    (replenishment_df['ABC Class'] == '🔴 A (70% value)') &
                                    (replenishment_df['Below Safety'] == '⚠️ Yes')
                                ]
                                st.metric(
                                    "🎯 Critical A Items",
                                    len(critical),
                                    delta="⚠️ Needs Reorder"
                                )
                            
                            # Show detailed replenishment recommendations
                            with st.expander("📋 View Replenishment Recommendations by ABC Class", expanded=False):
                                # Color code by ABC class
                                def style_abc_class(val):
                                    if '🔴 A' in val:
                                        return 'background-color: #f8d7da; font-weight: bold;'
                                    elif '🟡 B' in val:
                                        return 'background-color: #fff3cd;'
                                    else:
                                        return 'background-color: #d4edda;'
                                
                                styled_replenishment = replenishment_df.style.applymap(
                                    style_abc_class, subset=['ABC Class']
                                )
                                                                
                                st.dataframe(
                                    styled_replenishment,
                                    use_container_width=True,
                                    height=300,
                                    hide_index=True
                                )
                            
                            # ============================================================
                            # 🎯 DAILY / WEEKLY ACTION PLAN
                            # ============================================================
                            st.markdown("#### 📋 Action Plan by ABC Class")
                            
                            # Create action plan cards
                            action_plan = {
                                '🔴 A (70% value)': {
                                    'icon': '🔴',
                                    'actions': [
                                        '📊 Count weekly (or more frequently)',
                                        '📦 Maintain higher safety stock',
                                        '🔄 Reorder more frequently',
                                        '👀 Monitor daily',
                                        '📈 Review weekly performance'
                                    ]
                                },
                                '🟡 B (20% value)': {
                                    'icon': '🟡',
                                    'actions': [
                                        '📊 Count monthly',
                                        '📦 Maintain moderate safety stock',
                                        '🔄 Reorder as needed',
                                        '👀 Monitor weekly',
                                        '📈 Review monthly'
                                    ]
                                },
                                '🟢 C (10% value)': {
                                    'icon': '🟢',
                                    'actions': [
                                        '📊 Count quarterly',
                                        '📦 Maintain basic safety stock',
                                        '🔄 Reorder on demand',
                                        '👀 Monitor monthly',
                                        '📈 Review quarterly'
                                    ]
                                }
                            }
                            
                            # Display action plan as cards
                            cols = st.columns(3)
                            for idx, (class_name, plan) in enumerate(action_plan.items()):
                                with cols[idx]:
                                    count = len(abc_df[abc_df['ABC_CLASS'] == class_name])
                                    st.markdown(f"""
                                    <div style="
                                        border: 2px solid {cycle_frequencies[class_name]['color']};
                                        border-radius: 12px;
                                        padding: 15px;
                                        margin-bottom: 10px;
                                        background: rgba(255,255,255,0.05);
                                        min-height: 200px;
                                    ">
                                        <div style="font-size: 16px; font-weight: 700; color: {cycle_frequencies[class_name]['color']};">
                                            {plan['icon']} {class_name}
                                            <span style="font-size: 12px; color: #888;">({count} items)</span>
                                        </div>
                                        <div style="font-size: 13px; color: #666; margin-top: 8px;">
                                            <strong>Count:</strong> {cycle_frequencies[class_name]['frequency']}<br>
                                            <strong>Priority:</strong> {cycle_frequencies[class_name]['priority']}
                                        </div>
                                        <div style="margin-top: 8px;">
                                            <ul style="padding-left: 20px; margin: 0;">
                                                {''.join([f'<li style="font-size: 12px; color: #555;">{action}</li>' for action in plan['actions']])}
                                            </ul>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                            
                            # ============================================================
                            # 🎯 ABC CLASS BREAKDOWN - Original (Keep this)
                            # ============================================================
                            st.markdown("---")
                            st.markdown("#### 📊 ABC Class Breakdown")
                            
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
                            
                            # Show top A items with download
                            with st.expander("🔍 View Top A Items (70% Value)", expanded=False):
                                top_a = abc_df[abc_df['ABC_CLASS'] == '🔴 A (70% value)'].head(20)
                                st.dataframe(
                                    top_a[['ITEM_NAME', 'ITEM_CATEGORY', 'QUANTITY', 'UNIT PRICE', 'ANNUAL_VALUE']],
                                    use_container_width=True,
                                    hide_index=True
                                )
                                
                                # Add export button for A items
                                if not top_a.empty:
                                    csv_a = top_a[['ITEM_NAME', 'ITEM_CATEGORY', 'QUANTITY', 'UNIT PRICE', 'ANNUAL_VALUE']].to_csv(index=False).encode('utf-8')
                                    st.download_button(
                                        label="📥 Download A Items List",
                                        data=csv_a,
                                        file_name=f"a_items_{datetime.now().strftime('%Y%m%d')}.csv",
                                        mime='text/csv'
                                    )
                        else:
                            st.info("Total inventory value is zero. Cannot perform ABC analysis.")
                    else:
                        st.info("No valid items with both quantity and price data found for ABC analysis.")

                # --- CATEGORY-LEVEL INVENTORY SUMMARY (WRAPPED IN EXPANDER) ---
                if 'ITEM_CATEGORY' in stock_df.columns and 'QUANTITY' in stock_df.columns and 'UNIT PRICE' in stock_df.columns:
                    st.divider()
                    
                    # Wrap Category-Level Inventory Summary in expander - collapsed by default
                    with st.expander("📊 Category-Level Inventory Summary", expanded=False):
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
                            
                            # Check if category_summary exists and has data
                            if 'category_summary' in locals() and not category_summary.empty:
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
                            else:
                                st.info("No category data available to display")
                            
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

                # Wrap Stock Listing in expander - collapsed by default
                with st.expander(f"📋 Stock Listing ({len(filtered_df)} items)", expanded=False):
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

                # Low stock section (already has expander)
                if not low_df.empty:
                    st.divider()

                    st.warning(
                        f"⚠️ {len(low_df)} items are low in stock and need reordering!"
                    )

                    with st.expander("📋 View Low Stock Items", expanded=False):
                        st.dataframe(
                            low_df,
                            use_container_width=True,
                            height=300
                        )

            else:
                st.info(
                "📊 No inventory data found. "
                "Please check your Google Sheets connection."
            )  
        
        with tab_movements:
            st.markdown("## 📊 Stock Movements & Stock Take")
        
            # Refresh button
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("🔄 Refresh Movements", use_container_width=True):
                    st.cache_data.clear()
                    
            with col2:
                st.caption(f"Data source: Google Sheets | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            
            st.divider()
            
            @st.cache_data(ttl=300, show_spinner=False)
            def load_movement_data():
                gsheet = GoogleSheetReader()
                if gsheet.authenticate():
                    check_in = gsheet.get_check_in()
                    check_out = gsheet.get_check_out()
                    current_stock = gsheet.get_current_stock()
                    return check_in, check_out, current_stock
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
            
            with st.spinner("📊 Please wait..."):
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
            
            # Create tabs for each movement type + Stock Take
            movement_tab1, movement_tab2, movement_tab3, movement_tab4 = st.tabs([
                "📥 Check-Ins",
                "📤 Check-Outs",
                "📊 Current Stock",
                "📋 Stock Take"
            ])
            
            with movement_tab1:
                st.markdown("### 📥 Check-In Records")
                
                # Wrap table in expander - collapsed by default
                with st.expander("📋 View Check-In Records", expanded=False):
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
                
                # Wrap table in expander - collapsed by default
                with st.expander("📋 View Check-Out Records", expanded=False):
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
                
                # Wrap table in expander - collapsed by default
                with st.expander("📋 View Current Stock Levels", expanded=False):
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
            
            with movement_tab4:
                st.markdown("### 📋 Stock Take")
                
                # Add description
                st.markdown("""
                <div style="
                    background: rgba(255,255,255,0.05);
                    backdrop-filter: blur(8px);
                    border-radius: 12px;
                    padding: 12px 16px;
                    margin-bottom: 15px;
                    border: 1px solid rgba(255,255,255,0.08);
                ">
                    <div style="color: #888; font-size: 13px;">
                        📋 <strong>Stock Take</strong> - Verify physical inventory against system records.
                        Create counts, assign sheets to team members, and reconcile discrepancies.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Check if we have inventory items
                if 'inventory_items' in locals() and inventory_items:
                    # Call the stock take interface
                    stock_take_interface(inventory_items)
                else:
                    st.warning("⚠️ No inventory data available. Please load inventory from Google Sheets first.")
                    st.info("Go to the 📦 Inventory tab and refresh to load data.")
                    
                    # Option to load sample data
                    if st.button("📥 Load Sample Inventory Data"):
                        inventory_items = get_sample_inventory_data()
        
        with tab_analytics:
            st.markdown("## 📈 All Items Analytics")
            st.markdown("Comprehensive analysis for all inventory items using Google Sheets data")
            
            # ============================================================
            # 🎯 LAZY LOADING FOR HEAVY ANALYTICS DATA
            # ============================================================
            
            # Define the heavy loading function
            def load_heavy_analytics_data():
                """Load heavy analytics data only when needed."""
                try:
                    logger.info("Loading heavy analytics data...")
                    gsheet = GoogleSheetReader()
                    if gsheet.authenticate():
                        stock = gsheet.get_stock_with_pricing()
                        
                        # ============================================================
                        # 🚀 COMPRESS DATAFRAME TO REDUCE MEMORY USAGE
                        # ============================================================
                        if not stock.empty:
                            original_memory = stock.memory_usage(deep=True).sum() / 1024 / 1024
                            stock = compress_dataframe(stock)
                            compressed_memory = stock.memory_usage(deep=True).sum() / 1024 / 1024
                            reduction = ((original_memory - compressed_memory) / original_memory) * 100
                            logger.info(f"💾 Analytics stock compressed: {original_memory:.1f}MB → {compressed_memory:.1f}MB (↓{reduction:.0f}%)")
                        
                        check_in = gsheet.get_check_in()
                        check_out = gsheet.get_check_out()
                        current_stock = gsheet.get_current_stock()
                        
                        # Compress the other DataFrames too
                        if not check_in.empty:
                            check_in = compress_dataframe(check_in)
                        if not check_out.empty:
                            check_out = compress_dataframe(check_out)
                        if not current_stock.empty:
                            current_stock = compress_dataframe(current_stock)
                        
                        logger.info(f"Analytics data loaded: {len(stock)} items")
                        return stock, check_in, check_out, current_stock
                    else:
                        logger.warning("Google Sheets authentication failed for analytics")
                except Exception as e:
                    logger.error(f"Error loading analytics data: {e}")
                    st.error(f"❌ Error loading analytics data: {str(e)}")
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
            
            # Use lazy loader with caching
            analytics_loader = LazyLoader(
                load_heavy_analytics_data,
                cache_ttl=600,  # 10 minute cache
                key_prefix="analytics"
            )
            
            # Show load status
            if not analytics_loader.is_loaded:
                st.info("💡 Click the button below to load analytics data. This may take a moment.")
            
            # Render load button (or show loaded status)
            analytics_loader.render_load_button("📊 Load Analytics Data")
            
            # ============================================================
            # 🎯 DISPLAY ANALYTICS (ONLY WHEN LOADED)
            # ============================================================
            if analytics_loader.is_loaded:
                stock_df, check_in_df, check_out_df, current_stock_df = analytics_loader.data
                
                # Verify data was loaded successfully
                if stock_df is None or stock_df.empty:
                    st.warning("⚠️ No analytics data available. Please check your Google Sheets connection.")
                else:
                    # ============================================================
                    # 🎯 SECTION 1: ORDER ANALYSIS FOR ALL ITEMS
                    # ============================================================
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
                    
                    # ============================================================
                    # 🎯 SECTION 2: DEMAND FORECAST FOR ALL ITEMS
                    # ============================================================
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
                    
                    # ============================================================
                    # 🎯 SECTION 3: COST OPTIMIZATION FOR ALL ITEMS
                    # ============================================================
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
                st.info("💡 Click 'Load Analytics Data' to view the analysis.")

        with tab_inventory_visual:  
            st.markdown("### 📦 Visual Inventory Dashboard")
            
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

            # ============================================================
            # SECTION 1: AI-POWERED RECOMMENDATIONS (TOP)
            # ============================================================
            with st.expander("🤖 View AI-Powered Recommendations", expanded=False):
            # Use inventory_items (all items) for AI recommendations
                if inventory_items:
                    ai_powered_recommendations(
                        inventory_items=inventory_items,
                        filtered_items=filtered_items,
                        kpis=kpis
                    )
                else:
                    st.info("No inventory data available for AI recommendations")

            # ============================================================
            # SECTION 2: STATUS DASHBOARD (Katana Style) - NEW
            # ============================================================
            with st.expander("📊 View Real-Time Status Dashboard", expanded=False):
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
                        Real-time inventory status overview for ALL items.
                        <span style="color: #4caf50;">🟢 Healthy</span> | 
                        <span style="color: #ff9800;">🟠 Low Stock</span> | 
                        <span style="color: #dc3545;">🔴 Critical</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Display the status dashboard for ALL inventory
                if inventory_items:
                    inventory_status_dashboard(inventory_items, inventory_tracker)
                else:
                    st.info("No inventory data available for status dashboard")  
            
            # ============================================================
            # SECTION 3: GRID VIEW (Expander - Closed by Default)
            # ============================================================
            with st.expander("🖼️ View Inventory Grid", expanded=False):
                # Show stats
                inventory_stats_summary(filtered_items)
                
                st.markdown("---")
                
                # Show the grid
                if filtered_items:
                    visual_inventory_grid(filtered_items, columns=3)
                else:
                    st.info("No items match your filters")
            
            # ============================================================
            # SECTION 4: HEAT MAP EXPANDER (SIBLING - NOT NESTED)
            # ============================================================
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
            # SECTION 5: REPLENISHMENT RECOMMENDATIONS EXPANDER (SIBLING - NOT NESTED)
            # ============================================================
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

        with tab_advanced:
            if df is not None and not df.empty and inventory_items:
                # Pass stock_df as well
                create_advanced_analytics_tab(analytics, df, inventory_items, stock_df)
            else:
                st.warning("No data available for advanced analytics")

    # ============================================================
    # CONTAINER 2: DRY ICE MODE (7 TABS)
    # ============================================================
    else:  # "❄️ Dry Ice Mode"
        # ============================================================
        # 🎨 DRY ICE THEME + MODE BADGE
        # ============================================================
        st.markdown("""
        <style>
            /* Dry Ice Theme - Cool Blues */
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
                background: rgba(255,255,255,0.05);
                backdrop-filter: blur(4px);
                border-radius: 12px;
                padding: 8px;
                border: 1px solid rgba(255,255,255,0.08);
            }
            .stTabs [aria-selected="true"] {
                background: linear-gradient(135deg, #1a237e 0%, #4fc3f7 100%) !important;
                color: white !important;
                box-shadow: 0 4px 15px rgba(26, 35, 126, 0.3) !important;
            }
            .stTabs [data-baseweb="tab"]:hover {
                background: rgba(26, 35, 126, 0.08) !important;
                color: #1a237e !important;
            }
            /* Mode Badge */
            .mode-badge-dryice {
                background: linear-gradient(135deg, #1a237e, #4fc3f7);
                color: white;
                padding: 6px 16px;
                border-radius: 20px;
                display: inline-block;
                font-weight: 600;
                font-size: 14px;
                margin-bottom: 15px;
                box-shadow: 0 2px 10px rgba(26, 35, 126, 0.3);
            }
        </style>
        
        <div class="mode-badge-dryice">❄️ DRY ICE MODE</div>
        """, unsafe_allow_html=True)
        
        # DRY ICE CONTAINER - 7 Tabs
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📊 Order Analysis",
            "🔮 Demand Forecast",
            "📦 Inventory Management",
            "💰 Cost Optimization",
            "📋 Recommendations",
            "🛠️ Maintenance",
            "📜 Transaction History"
        ])
        
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
                
                # ============================================================
                # MODEL SELECTION CONTROLS (Inside Tab 2)
                # ============================================================
                with st.expander("⚙️ Model Configuration", expanded=False):
                    st.markdown("#### Select Active Models")
                    st.caption("Choose which models to use in the ensemble forecast")
                    st.caption("ℹ️ NeuralProphet is currently disabled (dependency unavailable)")
                    
                    # Model selection with defaults
                    model_options = {
                        'Prophet': True,
                        'ARIMA': True,
                        'LSTM': True,
                        'Monte Carlo': True,
                        'XGBoost': True,
                        'LightGBM': True,
                        'RandomForest': True,
                    }
                    
                    selected_models = []
                    cols = st.columns(4)
                    
                    for idx, (model_name, default) in enumerate(model_options.items()):
                        with cols[idx % 4]:
                            if st.checkbox(
                                model_name, 
                                value=default, 
                                key=f"tab_model_{model_name}",
                                help=f"Enable/disable {model_name} model"
                            ):
                                internal_name = model_name.lower().replace(' ', '_')
                                selected_models.append(internal_name)
                    
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        if st.button("✅ Select All", use_container_width=True, key="select_all_models"):
                            for model in model_options.keys():
                                st.session_state[f"tab_model_{model}"] = True
                            st.rerun()
                    with col2:
                        if st.button("❌ Deselect All", use_container_width=True, key="deselect_all_models"):
                            for model in model_options.keys():
                                st.session_state[f"tab_model_{model}"] = False
                            st.rerun()
                    with col3:
                        if st.button("🔄 Update Models", use_container_width=True, type="primary", key="update_models_btn"):
                            st.session_state.selected_models = selected_models
                            st.session_state.selected_models_count = len(selected_models)
                            st.cache_data.clear()
                            
                            if selected_models:
                                st.success(f"✅ Active models: {len(selected_models)}/7")
                                st.info(f"📋 {', '.join([m.replace('_', ' ').title() for m in selected_models])}")
                            else:
                                st.warning("⚠️ No models selected! Using all models as fallback.")
                            
                            st.rerun()
                
                st.markdown("---")
                
                # Real-time status
                from app.core.realtime_forecast import get_realtime_forecaster
                rt_forecaster = get_realtime_forecaster()
                
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    rt_forecaster.render_realtime_status()
                with col2:
                    if st.button("▶️ Start Live Updates"):
                        rt_forecaster.start(df, 30)
                        st.rerun()
                with col3:
                    if st.button("⏹️ Stop Live Updates"):
                        rt_forecaster.stop()
                        st.rerun()
                
                st.markdown("---")
                
                # ============================================================
                # 🔧 FIX: Use create_ensemble_forecast() instead of forecaster.forecast()
                # ============================================================
                with st.spinner("Generating ensemble forecast with 7 models..."):
                    # Aggregate multi-invoice daily data before forecasting
                    daily_df_tab2 = df.set_index('Date').resample('D')['Order_Quantity_kg'].sum().reset_index()
                    
                    # Pull the model selection saved by the "Update Models" button
                    selected_for_forecast = st.session_state.get('selected_models', None)
                    
                    # ✅ This sets session state variables automatically
                    fig_ensemble, ensemble_forecast_values, model_forecasts, backtest_accuracy = create_ensemble_forecast(
                        daily_df_tab2, 30, selected_models=selected_for_forecast
                    )
                    
                    # Get ensemble forecast from the returned values
                    ensemble_forecast = ensemble_forecast_values
                    
                    # ============================================================
                    # Model Performance Dashboard
                    # ============================================================
                    st.markdown("---")
                    st.markdown("#### 📊 Model Performance Dashboard")
                    
                    # ✅ Now these session state variables are set!
                    if 'active_models' in st.session_state and 'model_comparison' in st.session_state:
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric(
                                "🧠 Active Models",
                                f"{st.session_state.active_models}/7",
                                delta=f"{st.session_state.active_models} models"
                            )
                        
                        with col2:
                            if 'best_model' in st.session_state:
                                st.metric(
                                    "🏆 Best Model",
                                    st.session_state.best_model['name'],
                                    f"Score: {st.session_state.best_model['score']}"
                                )
                            else:
                                st.metric("🏆 Best Model", "Calculating...")
                        
                        with col3:
                            if 'best_model' in st.session_state:
                                st.metric(
                                    "🎯 Accuracy",
                                    st.session_state.best_model['accuracy'],
                                    "Auto-selected"
                                )
                            else:
                                st.metric("🎯 Accuracy", "Calculating...")
                        
                        with col4:
                            if 'active_models_list' in st.session_state:
                                model_list = st.session_state.active_models_list
                                display_text = ", ".join(model_list[:3])
                                if len(model_list) > 3:
                                    display_text += f" +{len(model_list)-3} more"
                                st.metric("📋 Models", display_text)
                    
                    # ============================================================
                    # Detailed Model Comparison Table
                    # ============================================================
                    if 'model_comparison' in st.session_state and not st.session_state.model_comparison.empty:
                        with st.expander("🔬 View Detailed Model Comparison", expanded=False):
                            st.dataframe(
                                st.session_state.model_comparison,
                                use_container_width=True,
                                hide_index=True,
                                height=250
                            )
                            
                            csv = st.session_state.model_comparison.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download Model Comparison",
                                data=csv,
                                file_name=f"model_comparison_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime='text/csv'
                            )
                    
                    # ============================================================
                    # Model Comparison Chart
                    # ============================================================
                    if 'model_comparison' in st.session_state and not st.session_state.model_comparison.empty:
                        try:
                            chart_data = []
                            for _, row in st.session_state.model_comparison.iterrows():
                                try:
                                    avg = float(row['Avg Forecast (kg)'].replace(',', ''))
                                    chart_data.append({
                                        'Model': row['Model'],
                                        'Avg Forecast': avg,
                                        'Status': row['Status']
                                    })
                                except:
                                    continue
                            
                            if chart_data:
                                chart_df = pd.DataFrame(chart_data)
                                
                                import plotly.express as px
                                fig_models = px.bar(
                                    chart_df,
                                    x='Model',
                                    y='Avg Forecast',
                                    title='📊 Model Comparison - Average Forecast',
                                    color='Status',
                                    color_discrete_map={'✅ Active': '#28a745'},
                                    text='Avg Forecast'
                                )
                                fig_models.update_traces(
                                    texttemplate='%{text:.1f} kg',
                                    textposition='outside'
                                )
                                fig_models.update_layout(
                                    height=350,
                                    yaxis_title='Average Forecast (kg)',
                                    showlegend=False,
                                    xaxis_tickangle=-45
                                )
                                st.plotly_chart(fig_models, use_container_width=True)
                        except Exception as e:
                            st.warning(f"Could not display model comparison chart: {e}")
                    
                    st.markdown("---")
                    
                    # ============================================================
                    # Scenario Analysis
                    # ============================================================
                    scenario_results = create_scenario_analysis(ensemble_forecast, df)
                    
                    scenario_fig = render_scenario_analysis(scenario_results, 30)
                    st.plotly_chart(scenario_fig, use_container_width=True)
                    
                    st.markdown("#### 📊 Scenario Summary")
                    render_scenario_summary(scenario_results)
                    
                    # ============================================================
                    # Model Performance Details
                    # ============================================================
                    with st.expander("🔬 Model Performance Details", expanded=False):
                        st.markdown("#### 📈 Individual Model Forecasts")
                        
                        model_cols = st.columns(4)
                        col_idx = 0
                        
                        # Get results from the returned values
                        # We need to re-run forecast to get individual model results
                        # Or we can use the model_forecasts from create_ensemble_forecast
                        if model_forecasts:
                            for name, stats in model_forecasts.items():
                                if name != 'External Factors' and isinstance(stats, dict):
                                    with model_cols[col_idx % 4]:
                                        st.metric(
                                            name,
                                            f"{stats['avg']:.1f} kg/day",
                                            f"min: {stats['min']:.1f} | max: {stats['max']:.1f}"
                                        )
                                    col_idx += 1
                        
                        # Show metrics
                        st.markdown("#### 📈 Accuracy Metrics (Backtest)")
                        st.caption(
                            "Trains on all data except the last 30 days, forecasts those 30 days, "
                            "then compares against what actually happened. This is separate from "
                            "the live 30-day-ahead forecast above, which has no ground truth yet."
                        )
                        
                        if len(daily_df_tab2) <= 60:
                            st.info("Need more than 60 days of history to run a reliable backtest.")
                        else:
                            run_backtest = st.button(
                                "🧪 Run Backtest",
                                key="run_backtest_btn",
                                help="Retrains all selected models on held-out data. Takes as long as the main forecast."
                            )
                            
                            if run_backtest:
                                try:
                                    backtest_train = daily_df_tab2.iloc[:-30].reset_index(drop=True)
                                    backtest_actual = daily_df_tab2.iloc[-30:]['Order_Quantity_kg'].values
                                    
                                    with st.spinner("Running backtest (retraining models on held-out data)..."):
                                        _, backtest_forecast, _, _ = create_ensemble_forecast(
                                            backtest_train, 30, selected_models=selected_for_forecast
                                        )
                                    
                                    historical_values = backtest_actual
                                    forecast_values = np.array(backtest_forecast[:len(historical_values)])
                                    
                                    wape = np.sum(np.abs(historical_values - forecast_values)) / max(np.sum(historical_values), 1) * 100
                                    mae = np.mean(np.abs(historical_values - forecast_values))
                                    
                                    ss_res = np.sum((historical_values - forecast_values) ** 2)
                                    ss_tot = np.sum((historical_values - np.mean(historical_values)) ** 2)
                                    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                                    
                                    actual_direction = np.sign(np.diff(historical_values))
                                    pred_direction = np.sign(np.diff(forecast_values[:len(historical_values)]))
                                    direction_accuracy = np.mean(actual_direction == pred_direction) * 100
                                    
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.metric("📊 WAPE", f"{wape:.1f}%")
                                    with col2:
                                        st.metric("📉 MAE", f"{mae:.1f}")
                                    with col3:
                                        st.metric("📈 R²", f"{r2:.2f}")
                                    with col4:
                                        st.metric("🎯 Direction Accuracy", f"{direction_accuracy:.1f}%")
                                    
                                    metrics_valid = all(np.isfinite(v) for v in [wape, mae, r2, direction_accuracy])
                                    if not metrics_valid:
                                        quality_score = 0.0
                                        st.markdown("#### 📊 Forecast Quality Score")
                                        st.progress(0.0, text="0% — invalid metrics")
                                        st.error("⚠️ Backtest produced NaN metrics — one of the ensemble models "
                                                "(check NeuralProphet) likely returned NaN forecasts. "
                                                "Quality score forced to 0 instead of falsely showing 100%.")
                                    else:
                                        mean_actual = max(np.mean(historical_values), 1)
                                        mae_normalized = min(mae / mean_actual, 1)
                                        r2_normalized = 0 if r2 < 0 else min(r2, 1)
                                        direction_normalized = direction_accuracy / 100
                                        wape_penalty = max(0, min(1, 1 - (wape - 50) / 150)) if wape > 50 else 1

                                        quality_score = (
                                            0.4 * (1 - mae_normalized) +
                                            0.3 * r2_normalized +
                                            0.3 * direction_normalized
                                        ) * wape_penalty * 100
                                        quality_score = round(max(0, min(100, quality_score)), 1)

                                        st.markdown("#### 📊 Forecast Quality Score")
                                        st.progress(quality_score / 100, text=f"{quality_score:.0f}%")

                                        if quality_score < 30:
                                            st.warning("⚠️ Forecast quality is low. Consider retraining models with more data.")
                                        elif quality_score < 50:
                                            st.info("📊 Forecast quality is moderate. Some models may need tuning.")
                                        else:
                                            st.success("✅ Forecast quality is good.")
                                        
                                except Exception as e:
                                    st.warning(f"Could not run backtest: {e}")
            else:
                st.warning("📊 No order data found for this period")

        with tab3:
            if not df.empty:
                st.markdown("### 📦 Proactive Inventory Policy")
                st.success("✅ Inventory policy is dynamically calculated using the live forecast data from Tab 2.")
                
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("#### Economic Order Quantity (EOQ)")
                    st.markdown("**Where:**")
                    st.markdown(f"<span style='color:green;'>- D = Forecasted Monthly Demand = {monthly_demand_input:,.1f} kg</span>", unsafe_allow_html=True)
                    st.write(f"- S = Ordering Cost = KSh {constants.TRANSPORT_COST:,.2f}")
                    st.write(f"- H = Holding Rate = {constants.HOLDING_RATE*100:.1f}%")
                    st.write(f"- C = Unit Cost = KSh {constants.PRICE_PER_KG:.2f}/kg")
                    st.markdown(f"<p style='color:green; font-weight:bold;'>Result: EOQ = {eoq:.1f} kg</p>", unsafe_allow_html=True)

                with col2:
                    st.markdown("#### Safety Stock")
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
                                                        eoq_val = math.sqrt((2 * annual_demand * order_cost) / (holding_rate * unit_price))
                                                        eoq_results.append({
                                                            'Item': row['ITEM_NAME'],
                                                            'Category': row['ITEM_CATEGORY'],
                                                            'Annual Demand': annual_demand,
                                                            'Unit Price': unit_price,
                                                            'EOQ': eoq_val,
                                                            'Orders/Year': annual_demand / eoq_val if eoq_val > 0 else 0
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
                                                eoq_val = math.sqrt((2 * annual_demand * order_cost) / (holding_rate * row['UNIT PRICE']))
                                                current_orders = annual_demand / row['QUANTITY'] if row['QUANTITY'] > 0 else 0
                                                optimal_orders = annual_demand / eoq_val if eoq_val > 0 else 0
                                                
                                                results.append({
                                                    'Item': row['ITEM_NAME'],
                                                    'Category': row['ITEM_CATEGORY'],
                                                    'Current Stock': row['QUANTITY'],
                                                    'Unit Price': row['UNIT PRICE'],
                                                    'Annual Demand': annual_demand,
                                                    'EOQ': eoq_val,
                                                    'Current Orders/Year': current_orders,
                                                    'Optimal Orders/Year': optimal_orders,
                                                    'Potential Savings': (current_orders - optimal_orders) * order_cost if eoq_val > 0 else 0
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
                x=[0, 1, 2, 3],
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
                xaxis=dict(
                    title='Implementation Quarters',
                    tickmode='array',
                    tickvals=[0, 1, 2, 3],
                    ticktext=['Q3 2025', 'Q4 2025', 'Q1 2026', 'Q2 2026+']
                ),
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
            st.markdown("### 🛠️ Predictive Maintenance Dashboard")
            # Container Health Assessment
            st.markdown("#### 📦 Container Health Assessment")

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
            st.markdown("#### 🔧 Maintenance Recommendations")
            recommendations = []
            if container_data['insulation_efficiency'] < 70:
                recommendations.append("📋 Schedule insulation inspection")
            if container_data['seal_integrity'] < 70:
                recommendations.append("🔧 Replace door seals and gaskets")
            if container_data['structural_condition'] < 80:
                recommendations.append("🔨 Conduct structural assessment")
            if container_data['usage_cycles'] > 50:
                recommendations.append("📋 Consider container rotation")
            if not recommendations:
                recommendations.append("✅ Continue regular maintenance")

            for i, action in enumerate(recommendations, 1):
                st.markdown(f"{i}. {action}")

            # System overview
            st.markdown("---")
            st.markdown("#### 📊 System Overview")

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

            # --- SECTION 1: PERIOD-SPECIFIC TRANSACTION HISTORY ---
            if not st.session_state.transactions:
                st.info("No transactions recorded for this period yet. Use the sidebar to record usage or receipts.")
            else:
                trans_df = pd.DataFrame(st.session_state.transactions)
                trans_df['date'] = pd.to_datetime(trans_df['date'])
                trans_df = trans_df.sort_values('date', ascending=False)
                
                # 🚀 COMPRESS DATAFRAME TO REDUCE MEMORY USAGE
                # ============================================================
                trans_df = compress_dataframe(trans_df)
                logger.info(f"Transactions loaded and compressed: {len(trans_df)} records")
                # ============================================================
                # 🎯 FILTERS (BEFORE PAGINATION)
                # ============================================================
                filter_col1, filter_col2, filter_col3 = st.columns(3)
                with filter_col1:
                    transaction_type = st.selectbox("Transaction Type", ["All", "usage", "receipt"], key="trans_type_filter")
                with filter_col2:
                    date_min = trans_df['date'].min().date()
                    date_max = trans_df['date'].max().date()
                    selected_dates = st.date_input("Date Range", [date_min, date_max], min_value=date_min, max_value=date_max, key="date_range_filter")
                with filter_col3:
                    show_limit = st.selectbox("Show Last", ["All", "10", "25", "50", "100"], key="show_limit_filter")
                
                # Apply filters
                filtered_df = trans_df.copy()
                if transaction_type != "All":
                    filtered_df = filtered_df[filtered_df['type'] == transaction_type]
                if len(selected_dates) == 2:
                    start_date, end_date = selected_dates
                    filtered_df = filtered_df[(filtered_df['date'].dt.date >= start_date) & (filtered_df['date'].dt.date <= end_date)]
                if show_limit != "All":
                    filtered_df = filtered_df.head(int(show_limit))

                # ============================================================
                # 🎯 DISPLAY WITH PAGINATION (FOR LARGE DATASETS)
                # ============================================================
                with st.expander("📋 View Transaction Records", expanded=not mobile_ui.should_collapse_advanced()):
                    # Paginate the filtered data (only if more than 100 rows)
                    if len(filtered_df) > 100:
                        paginated_df, paginator = paginate_dataframe(
                            filtered_df,
                            page_size=50,  # Show 50 per page
                            key_prefix="transactions",
                            show_controls=True,
                            compact=False
                        )
                        display_df = paginated_df
                        show_pagination = True
                    else:
                        display_df = filtered_df
                        show_pagination = False
                    
                    # Prepare display DataFrame
                    display_df_display = display_df.copy()
                    display_df_display['Date'] = display_df_display['date'].dt.strftime('%Y-%m-%d %H:%M')
                    display_df_display['Type'] = display_df_display['type'].str.title()
                    display_df_display['Quantity (kg)'] = display_df_display['quantity'].apply(lambda x: f"{x:,.2f}")
                    
                    # Show optimized table
                    st.dataframe(
                        display_df_display[['Date', 'Type', 'Quantity (kg)', 'description']],
                        use_container_width=True,
                        height=400,
                        hide_index=True
                    )
                    
                    # Show pagination info
                    if show_pagination:
                        st.caption(f"📊 Page {paginator.current_page} of {paginator.total_pages} | Showing {len(display_df):,} of {len(filtered_df):,} records")
                    else:
                        st.caption(f"📊 Showing {len(filtered_df):,} records")
                
                # ============================================================
                # 🎯 TRANSACTION SUMMARY
                # ============================================================
                st.markdown("### 📈 Transaction Summary (Filtered Period)")
                total_used = filtered_df[filtered_df['type']=='usage']['quantity'].sum()
                total_received = filtered_df[filtered_df['type']=='receipt']['quantity'].sum()
                net_change = total_received - total_used

                stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
                stat_col1.metric("Total Used", f"{total_used:,.1f} kg")
                stat_col2.metric("Total Received", f"{total_received:,.1f} kg")
                stat_col3.metric("Net Change", f"{net_change:,.1f} kg", delta=f"{net_change:,.1f} kg")
                stat_col4.metric("Total Transactions", len(filtered_df))

                # ============================================================
                # 🎯 EXPORT DATA SECTION
                # ============================================================
                st.markdown("### 📥 Export Filtered Data")
                if not filtered_df.empty:
                    csv = filtered_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name=f"transaction_history_{st.session_state.selected_period.replace('/', '-')}_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime='text/csv',
                        use_container_width=True
                    )
                else:
                    st.caption("No data in the current filter to export.")

            # --- DIVIDER TO SEPARATE SECTIONS ---
            st.divider()

            # --- SECTION 2: GLOBAL STATUS & HELP ---
            st.markdown("### 📊 Current Status")
            
            st.metric("Current Stock Level", f"{inventory_tracker.current_stock:,.1f} kg")

            # --- SECTION 3: COMMENTED OUT FEATURES (Kept for future reference) ---
            #with st.expander("ℹ️ How to Use This Page"):
            #    st.markdown("""
            #    1.  **Record Usage:** Use the sidebar to log daily consumption.
            #    2.  **Record Receipt:** Use the sidebar when new stock arrives.
            #    3.  **View Transactions:** All transactions will appear here automatically.
            #    4.  **Filter Data:** Use the filters above to narrow down results.
            #    5.  **Export Data:** Download buttons appear when transaction data exists.
            #    """)

            # --- SECTION 4: COMMENTED OUT DATA MANAGEMENT (Kept for future reference) ---
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
            #            
            #    with col2:
            #        if st.button("Cancel"):
            #            st.session_state.confirm_clear_pressed = False          

if __name__ == "__main__":
    main()

