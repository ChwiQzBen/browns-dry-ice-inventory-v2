# core/error_handling.py
"""
Comprehensive error handling and robustness utilities for the inventory app.
"""

import logging
import time
import sqlite3
from typing import Optional, Tuple, Any, Callable
from functools import wraps
from datetime import datetime
import streamlit as st
import pandas as pd
from requests.exceptions import Timeout, ConnectionError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# CUSTOM EXCEPTIONS
# ============================================================

class InventoryAppError(Exception):
    """Base exception for inventory app."""
    pass

class DatabaseError(InventoryAppError):
    """Raised when database operations fail."""
    pass

class ServiceUnavailableError(InventoryAppError):
    """Raised when external services are unavailable."""
    pass

class ValidationError(InventoryAppError):
    """Raised when data validation fails."""
    pass

class DataNotFoundError(InventoryAppError):
    """Raised when requested data is not found."""
    pass

# ============================================================
# RETRY DECORATOR
# ============================================================

def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry a function on failure with exponential backoff.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"Failed after {max_attempts} attempts: {e}")
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        return wrapper
    return decorator

# ============================================================
# VALIDATION FUNCTIONS
# ============================================================

def validate_quantity(
    qty: float,
    min_qty: float = 0,
    max_qty: float = 10000,
    allow_zero: bool = False
) -> Tuple[bool, str]:
    """
    Validate a quantity value.
    
    Args:
        qty: Quantity to validate
        min_qty: Minimum allowed value
        max_qty: Maximum allowed value
        allow_zero: Whether zero is allowed
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        qty = float(qty)
    except (TypeError, ValueError):
        return False, "❌ Please enter a valid number"
    
    if not allow_zero and qty == 0:
        return False, "❌ Quantity must be greater than zero"
    
    if qty < min_qty:
        return False, f"❌ Quantity must be at least {min_qty:,.0f}"
    
    if qty > max_qty:
        return False, f"❌ Quantity exceeds maximum ({max_qty:,.0f}). Please verify."
    
    return True, "✅ Valid quantity"

def validate_date(
    date_val,
    min_date=None,
    max_date=None,
    allow_future: bool = False
) -> Tuple[bool, str]:
    """
    Validate a date value.
    """
    from datetime import datetime
    
    if date_val is None:
        return False, "❌ Please select a date"
    
    if not allow_future and date_val > datetime.now().date():
        return False, "❌ Cannot use future dates"
    
    if min_date and date_val < min_date:
        return False, f"❌ Date must be after {min_date.strftime('%Y-%m-%d')}"
    
    if max_date and date_val > max_date:
        return False, f"❌ Date must be before {max_date.strftime('%Y-%m-%d')}"
    
    return True, "✅ Valid date"

def validate_stock_sufficient(
    requested: float,
    available: float
) -> Tuple[bool, str]:
    """
    Validate that sufficient stock is available.
    """
    if requested > available:
        return False, f"❌ Insufficient stock! Available: {available:,.0f} kg"
    
    if requested > available * 0.9:
        return True, f"⚠️ Warning: This will use {requested/available*100:.0f}% of your remaining stock"
    
    return True, "✅ Sufficient stock available"

# ============================================================
# DATABASE SAFE OPERATIONS
# ============================================================

def safe_db_operation(
    operation: Callable,
    fallback_value: Any = None,
    show_error: bool = True,
    error_title: str = "Database Error"
) -> Any:
    """
    Execute a database operation with comprehensive error handling.
    """
    try:
        return operation()
    
    except sqlite3.OperationalError as e:
        logger.error(f"SQLite operational error: {e}", exc_info=True)
        if show_error:
            st.error(f"⚠️ {error_title}: Database operation failed. Please try again.")
        return fallback_value
    
    except sqlite3.IntegrityError as e:
        logger.error(f"SQLite integrity error: {e}", exc_info=True)
        if show_error:
            st.error(f"⚠️ {error_title}: Data integrity error. Some records may be corrupted.")
        return fallback_value
    
    except sqlite3.ProgrammingError as e:
        logger.error(f"SQLite programming error: {e}", exc_info=True)
        if show_error:
            st.error(f"⚠️ {error_title}: Database query error. Please contact support.")
        return fallback_value
    
    except Timeout as e:
        logger.error(f"Timeout error: {e}", exc_info=True)
        if show_error:
            st.error(f"⚠️ {error_title}: Operation timed out. Please try again.")
        return fallback_value
    
    except ConnectionError as e:
        logger.error(f"Connection error: {e}", exc_info=True)
        if show_error:
            st.error(f"⚠️ {error_title}: Network connection error. Please check your internet.")
        return fallback_value
    
    except Exception as e:
        logger.critical(f"Unexpected database error: {e}", exc_info=True)
        if show_error:
            st.error(f"⚠️ {error_title}: An unexpected error occurred. Our team has been notified.")
        return fallback_value

# ============================================================
# SERVICE STATUS MANAGER
# ============================================================

class ServiceStatusManager:
    """
    Manages service connection status with graceful degradation.
    """
    
    def __init__(self):
        self.services = {
            'supabase': {'status': 'unknown', 'last_check': None, 'error': None},
            'sqlite': {'status': 'unknown', 'last_check': None, 'error': None},
            'google_sheets': {'status': 'unknown', 'last_check': None, 'error': None}
        }
        self.current_mode = 'unknown'
        self.last_check_time = None
    
    def check_supabase(self) -> bool:
        """Check if Supabase is available."""
        try:
            from supabase import create_client
            
            url = st.secrets.get("SUPABASE_URL")
            key = st.secrets.get("SUPABASE_KEY")
            
            if not url or not key:
                self.services['supabase']['error'] = "Missing credentials"
                return False
            
            client = create_client(url, key)
            client.table('transactions').select('id').limit(1).execute()
            
            self.services['supabase']['status'] = 'healthy'
            self.services['supabase']['error'] = None
            return True
            
        except Exception as e:
            self.services['supabase']['status'] = 'unhealthy'
            self.services['supabase']['error'] = str(e)
            logger.warning(f"Supabase health check failed: {e}")
            return False
    
    def check_sqlite(self) -> bool:
        """Check if SQLite is available."""
        try:
            import sqlite3
            
            conn = sqlite3.connect('dry_ice.db')
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            conn.close()
            
            self.services['sqlite']['status'] = 'healthy'
            self.services['sqlite']['error'] = None
            return True
            
        except Exception as e:
            self.services['sqlite']['status'] = 'unhealthy'
            self.services['sqlite']['error'] = str(e)
            logger.critical(f"SQLite health check failed: {e}")
            return False
    
    def check_google_sheets(self) -> bool:
        """Check if Google Sheets is available."""
        try:
            from app.core.google_sheet_reader import GoogleSheetReader
            
            gsheet = GoogleSheetReader()
            if gsheet.authenticate():
                self.services['google_sheets']['status'] = 'healthy'
                self.services['google_sheets']['error'] = None
                return True
            else:
                self.services['google_sheets']['status'] = 'unhealthy'
                self.services['google_sheets']['error'] = "Authentication failed"
                return False
                
        except Exception as e:
            self.services['google_sheets']['status'] = 'unhealthy'
            self.services['google_sheets']['error'] = str(e)
            logger.warning(f"Google Sheets health check failed: {e}")
            return False
    
    def check_all_services(self):
        """Check all services and update status."""
        supabase_ok = self.check_supabase()
        sqlite_ok = self.check_sqlite()
        sheets_ok = self.check_google_sheets()
        
        self.last_check_time = datetime.now()
        
        if supabase_ok:
            self.current_mode = 'cloud'
        elif sqlite_ok:
            self.current_mode = 'local'
        else:
            self.current_mode = 'offline'
        
        return {
            'supabase': supabase_ok,
            'sqlite': sqlite_ok,
            'google_sheets': sheets_ok,
            'mode': self.current_mode
        }
    
    def show_service_status(self):
        """Display service status in the UI."""
        self.check_all_services()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔗 Service Status")
        
        if self.services['supabase']['status'] == 'healthy':
            st.sidebar.success("☁️ Supabase: Connected")
        else:
            st.sidebar.error("☁️ Supabase: Disconnected")
            if self.services['supabase']['error']:
                st.sidebar.caption(f"Error: {self.services['supabase']['error'][:50]}...")
        
        if self.services['sqlite']['status'] == 'healthy':
            st.sidebar.success("💾 SQLite: Connected")
        else:
            st.sidebar.error("💾 SQLite: Disconnected (Critical!)")
        
        if self.services['google_sheets']['status'] == 'healthy':
            st.sidebar.success("📊 Google Sheets: Connected")
        else:
            st.sidebar.warning("📊 Google Sheets: Not connected")
        
        st.sidebar.markdown("---")
        if self.current_mode == 'cloud':
            st.sidebar.info("🌐 Mode: Cloud Connected")
            st.sidebar.caption("✅ All features available")
        elif self.current_mode == 'local':
            st.sidebar.info("💻 Mode: Local Only")
            st.sidebar.caption("⚠️ Some cloud features unavailable")
        else:
            st.sidebar.error("❌ Mode: Offline")
            st.sidebar.caption("⚠️ Limited functionality available")
        
        if self.last_check_time:
            st.sidebar.caption(f"🕐 Last check: {self.last_check_time.strftime('%H:%M:%S')}")

# ============================================================
# SAFE INPUT FUNCTIONS - FIXED
# ============================================================

def safe_number_input(
    label: str,
    min_value: float = 0.0,
    max_value: float = 10000.0,
    value: float = None,  # ← FIXED: Changed from 'default' to 'value'
    step: float = 10.0,
    validate: bool = True,
    allow_zero: bool = True,
    key: str = None,
    help: str = None,
    disabled: bool = False,
    placeholder: str = None,
    **kwargs
) -> Optional[float]:
    """
    Safe number input with validation.
    
    Args:
        label: Input label
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        value: Default value (Streamlit standard parameter name)
        step: Step increment
        validate: Whether to validate input
        allow_zero: Whether zero is allowed (default: True)
        key: Unique key for the widget
        help: Help text
        disabled: Whether the widget is disabled
        placeholder: Placeholder text
        **kwargs: Additional arguments
    
    Returns:
        Validated number or None if invalid
    """
    if value is None:
        value = min_value
    
    # Remove any conflicting kwargs
    kwargs.pop('value', None)
    kwargs.pop('key', None)
    kwargs.pop('help', None)
    kwargs.pop('disabled', None)
    kwargs.pop('placeholder', None)
    
    result = st.number_input(
        label=label,
        min_value=min_value,
        max_value=max_value,
        value=value,
        step=step,
        key=key,
        help=help,
        disabled=disabled,
        placeholder=placeholder,
        **kwargs
    )
    
    if validate:
        is_valid, msg = validate_quantity(result, min_value, max_value, allow_zero=allow_zero)
        if not is_valid:
            st.error(msg)
            return None
        elif "Warning" in msg:
            st.warning(msg)
    
    return result

def safe_text_input(
    label: str,
    max_length: int = 255,
    required: bool = False,
    **kwargs
) -> Optional[str]:
    """
    Safe text input with validation.
    """
    value = st.text_input(label, **kwargs)
    
    if required and not value:
        st.error("❌ This field is required")
        return None
    
    if value and len(value) > max_length:
        st.error(f"❌ Text exceeds {max_length} characters")
        return value[:max_length]
    
    return value

# ============================================================
# DECORATORS FOR SAFE OPERATIONS
# ============================================================

def safe_operation(error_message: str = "Operation failed"):
    """
    Decorator to wrap functions with error handling.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValidationError as e:
                st.error(f"❌ Validation Error: {e}")
                logger.warning(f"Validation error in {func.__name__}: {e}")
                return None
            except ServiceUnavailableError as e:
                st.error(f"⚠️ Service Unavailable: {e}")
                logger.error(f"Service error in {func.__name__}: {e}")
                return None
            except Exception as e:
                st.error(f"⚠️ {error_message}: {str(e)}")
                logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                return None
        return wrapper
    return decorator

# ============================================================
# PERFORMANCE MONITORING
# ============================================================

def log_performance(func):
    """
    Decorator to log function performance.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        
        if elapsed > 1.0:
            logger.warning(f"Slow operation: {func.__name__} took {elapsed:.2f}s")
        else:
            logger.debug(f"{func.__name__} completed in {elapsed:.3f}s")
        
        return result
    return wrapper