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
from app.core.decision_engine import InventorySnapshot, InventoryDecisionEngine, generate_ai_insights
from app.core.bcpos_ui import render_bcpos_mode
from app.core.commercial_ui import render_commercial_mode
from app.core.all_items_ui import render_all_items_mode, AllItemsContext
from app.core.dry_ice_ui import render_dry_ice_mode, DryIceContext
from app.core.theme import THEME, kpi_card
from app.core.dashboard_home import DashboardContext, render_dashboard_home
from app.core.visual_inventory import get_sample_inventory_data
from app.core.forecasting import (
      create_ensemble_forecast,
      create_scenario_analysis,
      render_scenario_analysis,
      render_scenario_summary,
  )

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
    page_title="MarginIQ Ops Suite",
    page_icon="📈",
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
    IMPLEMENTATION_COST = 25700  # training + SOP + signage + supervision + 20% contingency — adjustable in sidebar
    ALL_ITEMS_IMPLEMENTATION_COST = 70000  # baseline count + data cleanup + training + first-cycle supervision — adjustable in sidebar
    SYNERGY_DISCOUNT = 0.12  # combined rollout shares training/supervision overhead

constants = Constants()

# 🔐 ROLE-BASED ACCESS CONTROL (tab/section visibility layer)
# Independent of AuthManager.check_permission() — different granularity,
# same underlying role read from st.session_state._auth.current_role
from enum import Enum

class Permission(str, Enum):
    VIEW_STOCK = "view_stock"
    VIEW_STOCK_TAKE = "view_stock_take"
    RECORD_USAGE = "record_usage"
    RECORD_RECEIPT = "record_receipt"
    RUN_STOCK_TAKE = "run_stock_take"
    VIEW_ANALYTICS = "view_analytics"
    VIEW_FORECASTS = "view_forecasts"
    VIEW_COST_DATA = "view_cost_data"
    VIEW_STRATEGY = "view_strategy"
    VIEW_MAINTENANCE = "view_maintenance"
    GENERATE_REPORTS = "generate_reports"
    VIEW_REPORTS = "view_reports"
    EDIT_SYSTEM_PARAMS = "edit_system_params"
    CLEAR_TRANSACTIONS = "clear_transactions"
    VIEW_SECURITY_DASHBOARD = "view_security_dashboard"
    MANAGE_USERS = "manage_users"
    VIEW_CHEESE_PRODUCTION = "view_cheese_production"
    VIEW_CHEESE_RECIPES = "view_cheese_recipes"
    RECORD_MILK_RECEIPT = "record_milk_receipt"
    RECORD_CHEESE_SALE = "record_cheese_sale"
    RUN_PRODUCTION_PLAN = "run_production_plan"
    MANAGE_CHEESE_BATCHES = "manage_cheese_batches"
    MANAGE_LPO = "manage_lpo"
    MANAGE_CUSTOMERS = "manage_customers"
    VIEW_COMMERCIAL_REPORTS = "view_commercial_reports"
    VIEW_CUSTOMER_ANALYTICS = "view_customer_analytics"

ROLE_PERMISSIONS = {
    "admin": set(Permission),
    "manager": {
        Permission.VIEW_STOCK, Permission.VIEW_STOCK_TAKE,
        Permission.RECORD_USAGE, Permission.RECORD_RECEIPT, Permission.RUN_STOCK_TAKE,
        Permission.VIEW_ANALYTICS, Permission.VIEW_FORECASTS, Permission.VIEW_COST_DATA,
        Permission.VIEW_STRATEGY, Permission.VIEW_MAINTENANCE,
        Permission.GENERATE_REPORTS, Permission.VIEW_REPORTS,
        # --- cheese: full operational access ---
        Permission.VIEW_CHEESE_PRODUCTION, Permission.VIEW_CHEESE_RECIPES,
        Permission.RECORD_MILK_RECEIPT, Permission.RECORD_CHEESE_SALE,
        Permission.RUN_PRODUCTION_PLAN, Permission.MANAGE_CHEESE_BATCHES,
        Permission.MANAGE_LPO, Permission.MANAGE_CUSTOMERS, Permission.VIEW_COMMERCIAL_REPORTS,
        Permission.VIEW_CUSTOMER_ANALYTICS,
    },
    "user": {
        Permission.VIEW_STOCK, Permission.VIEW_STOCK_TAKE,
        Permission.RECORD_USAGE, Permission.RECORD_RECEIPT, Permission.RUN_STOCK_TAKE,
        # --- cheese: day-to-day recording only, no planning/batch release ---
        Permission.VIEW_CHEESE_PRODUCTION, Permission.VIEW_CHEESE_RECIPES,
        Permission.RECORD_MILK_RECEIPT, Permission.RECORD_CHEESE_SALE,
        Permission.MANAGE_LPO, Permission.MANAGE_CUSTOMERS,
    },
    "viewer": {
        Permission.VIEW_STOCK, Permission.VIEW_ANALYTICS, Permission.VIEW_REPORTS,
        # --- cheese: read-only ---
        Permission.VIEW_CHEESE_PRODUCTION, Permission.VIEW_CHEESE_RECIPES,
        Permission.VIEW_COMMERCIAL_REPORTS, Permission.VIEW_CUSTOMER_ANALYTICS,
    },
}

ALL_ITEMS_TAB_REQUIREMENTS = {
    "📦 Inventory": Permission.VIEW_STOCK,
    "📊 Stock Movements": Permission.RUN_STOCK_TAKE,
    "📈 All Items Analytics": Permission.VIEW_ANALYTICS,
    "🖼️ Visual Inventory": Permission.VIEW_ANALYTICS,
    "🤖 Advanced Analytics": Permission.VIEW_ANALYTICS,
}

DRY_ICE_TAB_REQUIREMENTS = {
    "📊 Order Analysis": Permission.VIEW_ANALYTICS,
    "🔮 Demand Forecast": Permission.VIEW_FORECASTS,
    "📦 Inventory Management": Permission.VIEW_STOCK,
    "💰 Cost Optimization": Permission.VIEW_COST_DATA,
    "📋 Recommendations": Permission.VIEW_STRATEGY,
    "🛠️ Maintenance": Permission.VIEW_MAINTENANCE,
    "📜 Transaction History": Permission.VIEW_REPORTS,
}

def get_current_role() -> str:
    auth = st.session_state.get('_auth')
    if auth and getattr(auth, 'is_authenticated', False):
        return getattr(auth, 'current_role', None) or None
    return None

def has_permission(permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(get_current_role(), set())

def filter_tabs(tab_requirements: dict) -> list:
    role_perms = ROLE_PERMISSIONS.get(get_current_role(), set())
    return [tab for tab, req in tab_requirements.items() if req in role_perms]

def get_user_email_safe() -> str:
    auth = st.session_state.get('_auth')
    if auth and getattr(auth, 'is_authenticated', False):
        return auth.current_user.get('email', 'unknown')
    return 'anonymous'

def log_access_denied(action: str):
    AuditLogger().log(
        action='ACCESS_DENIED',
        details=f"Role '{get_current_role()}' attempted: {action}",
        user=get_user_email_safe()
    )

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

@st.cache_data(ttl=30)
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
                get_current_stock_from_db.clear()
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
            background: linear-gradient(135deg, #1a237e 0%, #4fc3f7 100%);
            padding: 15px 20px;
            border-radius: 12px;
            color: white;
            margin-bottom: 20px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(26, 35, 126, 0.3);
        ">
            <div style="font-size: 20px; font-weight: 700;">Browns Ops Suite</div>
            <div style="font-size: 9.5px; opacity: 0.7; margin-top: 4px; white-space: nowrap;">
                Inventory • Dry Ice • Production Optimization
            </div>
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
        ["📦 All Items Mode", "🧀 BCPOS Mode", "❄️ Dry Ice Mode"],
        help="Switch between general inventory management, Cheese Production Optimization, or Dry Ice analysis",
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
    # ============================================================
    # 🎯 DECISION ENGINE (stored in session_state so the sidebar,
    # which renders earlier in this function, can read it too)
    # ============================================================
    snapshot = InventorySnapshot(
        current_stock=inventory_tracker.current_stock,
        eoq=eoq,
        safety_stock=safety_stock,
        reorder_point=reorder_point,
        forecast_values=ensemble_forecast_values,
        forecast_accuracy=backtest_accuracy * 100,
        lead_time_days=constants.LEAD_TIME_DAYS,
        transport_cost=constants.TRANSPORT_COST,
        avg_order_size=kpis.get('avg_order_size', 300),
        monthly_holding_cost=annual_holding_cost / 12,
    )
    decision_engine = InventoryDecisionEngine(snapshot)
    st.session_state.decision = decision_engine.executive_summary()

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
    if has_permission(Permission.RECORD_USAGE):
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

    if has_permission(Permission.RECORD_RECEIPT):
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
                MarginIQ Ops Suite
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
        if not has_permission(Permission.VIEW_REPORTS):
            st.sidebar.error("⛔ You don't have permission to view reports")
            log_access_denied("generate_report")
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

    if has_permission(Permission.EDIT_SYSTEM_PARAMS):
        with st.sidebar.expander("Inventory Parameters"):
            st.write(f"**Price per kg:** KSh {constants.PRICE_PER_KG:.2f}")
            st.write(f"**Container size:** {constants.CONTAINER_SIZE} kg")
            st.write(f"**Transport cost:** KSh {constants.TRANSPORT_COST:,.2f}")
            st.write(f"**Holding rate:** {constants.HOLDING_RATE*100:.1f}%")
            st.write(f"**Sublimation loss:** {constants.SUB_LOSS_RANGE[0]:.1f}-{constants.SUB_LOSS_RANGE[1]:.1f}%")
            st.write(f"**Lead time:** {constants.LEAD_TIME_DAYS} day(s)")
            st.write(f"**Service level:** {constants.SERVICE_LEVEL*100:.0f}%")

            st.markdown("---")
            st.markdown("**Implementation Cost — Dry Ice Tier**")
            implementation_cost_input = st.number_input(
                "Dry Ice Implementation Cost (KSh)",
                min_value=0.0,
                value=float(st.session_state.get('implementation_cost', constants.IMPLEMENTATION_COST)),
                step=1000.0,
                help="Staff training + SOP updates + signage + supervision during rollout + contingency buffer",
                key="implementation_cost_input"
            )
            st.session_state.implementation_cost = implementation_cost_input
            st.caption("Illustrative breakdown: training ~6,000 | SOP docs ~5,000 | signage ~4,000 | supervision ~6,400 | contingency ~20% — replace with real figures when available.")

            st.markdown("**Implementation Cost — All Items Tier**")
            all_items_implementation_cost_input = st.number_input(
                "All Items Implementation Cost (KSh)",
                min_value=0.0,
                value=float(st.session_state.get('all_items_implementation_cost', constants.ALL_ITEMS_IMPLEMENTATION_COST)),
                step=1000.0,
                help="Baseline physical count + Google Sheets data cleanup + staff training + first-cycle supervision + contingency",
                key="all_items_implementation_cost_input"
            )
            st.session_state.all_items_implementation_cost = all_items_implementation_cost_input
            st.caption("Illustrative breakdown: baseline count ~28,800 | data cleanup ~11,200 | training ~7,500 | supervision ~12,800 | contingency ~15% — replace with real figures when available.")

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
            padding: 16px 15px;
            text-align: center;
            background: rgba(0,0,0,0.03);
            border: 1px solid rgba(0,0,0,0.05);
        ">
            <div style="font-size: 16px; font-weight: 700; color: #1a237e; margin-bottom: 3px;">
                🧀 Browns Ops Suite
            </div>
            <div style="font-size: 12px; color: #888; margin-bottom: 5px;">
                Inventory • Dry Ice • Production
            </div>
            <div style="font-size: 10px; color: #999; border-top: 2px solid #1a237e; padding-top: 6px;">
                © 2025 MarginIQ Ltd
            </div>
        </div>
        """, unsafe_allow_html=True)

    
# ============================================================
    # 🏠 DASHBOARD HOME (KPI grid, Decision Center, Insights &
    # Scenarios, ROI Summary) — see app/core/dashboard_home.py
    # ============================================================
    dashboard_ctx = DashboardContext(
        kpis=kpis,
        eoq=eoq,
        eoq_monthly_orders=eoq_monthly_orders,
        safety_stock=safety_stock,
        reorder_point=reorder_point,
        backtest_accuracy=backtest_accuracy,
        ensemble_forecast_values=ensemble_forecast_values,
        monthly_demand_input=monthly_demand_input,
        demand_stddev_input=demand_stddev_input,
        sublimation_factor=sublimation_factor,
        z_score=z_score,
        annual_transport_savings=annual_transport_savings,
        annual_holding_cost=annual_holding_cost,
        total_annual_spending=total_annual_spending,
        current_monthly_orders=current_monthly_orders,
        inventory_tracker=inventory_tracker,
        constants=constants,
        decision=st.session_state.get('decision'),
        stock_df=stock_df,
    )
    render_dashboard_home(dashboard_ctx)

    
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
        
        # Create context and render
        all_items_ctx = AllItemsContext(
            inventory_items=inventory_items,
            df=df,
            stock_df=stock_df,
            analytics=analytics,
            constants=constants,
            kpis=kpis,
            inventory_tracker=inventory_tracker,
        )
        render_all_items_mode(all_items_ctx, has_permission=has_permission)

    # ============================================================
    # CONTAINER 2: BCPOS MODE (Cheese Production)
    # ============================================================
    elif mode == "🧀 BCPOS Mode":
        from app.core.cheese_data_access import get_weighted_milk_cost_for_date
        todays_milk_cost = get_weighted_milk_cost_for_date(datetime.today().date(), init_supabase())
        render_bcpos_mode(  # ← Change to this
            supabase_client=init_supabase(),
            has_permission=has_permission,
            milk_cost_per_liter=todays_milk_cost if todays_milk_cost > 0 else 45.0,
            raw_milk_price_per_liter=35.0
        )
    # ============================================================
    # CONTAINER 3: DRY ICE MODE (7 TABS)
    else:  # "❄️ Dry Ice Mode"
        # Create context and render (badge is rendered inside the module)
        dry_ice_ctx = DryIceContext(
            df=df, kpis=kpis, constants=constants, mobile_ui=mobile_ui,
            inventory_tracker=inventory_tracker, fig_orders=fig_orders,
            fig_cost_overview=fig_cost_overview, eoq=eoq,
            monthly_demand_input=monthly_demand_input, demand_stddev_input=demand_stddev_input,
            z_score=z_score, safety_stock=safety_stock, avg_sublimation=avg_sublimation,
            adjusted_demand=adjusted_demand, reorder_point=reorder_point,
            annual_transport_savings=annual_transport_savings, annual_transport_cost=annual_transport_cost,
            current_monthly_orders=current_monthly_orders, eoq_monthly_orders=eoq_monthly_orders,
            annual_volume=annual_volume, annual_product_cost=annual_product_cost,
            annual_holding_cost=annual_holding_cost, annual_sublimation_loss=annual_sublimation_loss,
            total_annual_spending=total_annual_spending,
            create_ensemble_forecast_fn=create_ensemble_forecast,
            create_scenario_analysis_fn=create_scenario_analysis,
            render_scenario_analysis_fn=render_scenario_analysis,
            render_scenario_summary_fn=render_scenario_summary,
            transactions=st.session_state.transactions,
        )
        render_dry_ice_mode(dry_ice_ctx, has_permission=has_permission)
         
if __name__ == "__main__":
    main()

