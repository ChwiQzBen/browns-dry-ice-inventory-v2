# core/performance.py
"""
Performance optimization utilities for the inventory app.
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Optional, Tuple, List, Any
from datetime import datetime
import time
import logging
from functools import wraps
import gc

logger = logging.getLogger(__name__)

# ============================================================
# PAGINATION UTILITIES
# ============================================================

class Paginator:
    """
    Handle pagination for large datasets with Streamlit integration.
    """
    
    def __init__(self, total_items: int, page_size: int = 50, key_prefix: str = "paginator"):
        """
        Initialize paginator.
        
        Args:
            total_items: Total number of items
            page_size: Number of items per page
            key_prefix: Prefix for session state keys
        """
        self.total_items = total_items
        self.page_size = page_size
        self.total_pages = max(1, (total_items + page_size - 1) // page_size)
        self.key_prefix = key_prefix
        self._init_session_state()
    
    def _init_session_state(self):
        """Initialize session state for pagination."""
        key = f"{self.key_prefix}_current_page"
        if key not in st.session_state:
            st.session_state[key] = 1
    
    @property
    def current_page(self) -> int:
        """Get current page number."""
        key = f"{self.key_prefix}_current_page"
        return st.session_state.get(key, 1)
    
    @current_page.setter
    def current_page(self, value: int):
        """Set current page number."""
        key = f"{self.key_prefix}_current_page"
        st.session_state[key] = max(1, min(value, self.total_pages))
    
    def get_page_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Get data for current page.
        
        Args:
            df: Full DataFrame
        
        Returns:
            Paginated DataFrame
        """
        if df.empty:
            return df
        
        start = (self.current_page - 1) * self.page_size
        end = min(start + self.page_size, len(df))
        return df.iloc[start:end].copy()
    
    def render_pagination_controls(self, cols: int = 4) -> Tuple[int, int]:
        """
        Render pagination controls with Streamlit columns.
        
        Args:
            cols: Number of columns for layout
        
        Returns:
            Tuple of (start_index, end_index)
        """
        if self.total_pages <= 1:
            return 0, len(self.get_page_data(pd.DataFrame()))
        
        # Calculate current range
        start = (self.current_page - 1) * self.page_size + 1
        end = min(start + self.page_size - 1, self.total_items)
        
        # Display info
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        
        with col1:
            st.caption(f"📊 Showing {start:,} - {end:,} of {self.total_items:,}")
        
        with col2:
            # Previous button
            if st.button("◀ Previous", key=f"{self.key_prefix}_prev", use_container_width=True):
                if self.current_page > 1:
                    self.current_page -= 1
                    st.rerun()
        
        with col3:
            # Next button
            if st.button("Next ▶", key=f"{self.key_prefix}_next", use_container_width=True):
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    st.rerun()
        
        with col4:
            # Page selector
            page_options = list(range(1, min(self.total_pages + 1, 11)))
            if self.total_pages > 10:
                # Show around current page
                current = self.current_page
                start_page = max(1, min(current - 4, self.total_pages - 9))
                page_options = list(range(start_page, min(start_page + 10, self.total_pages + 1)))
            
            selected_page = st.selectbox(
                "Page",
                options=page_options,
                index=page_options.index(self.current_page) if self.current_page in page_options else 0,
                key=f"{self.key_prefix}_select",
                label_visibility="collapsed"
            )
            
            if selected_page != self.current_page:
                self.current_page = selected_page
                st.rerun()
        
        return start - 1, end
    
    def render_compact_pagination(self):
        """Render compact pagination for mobile/sidebar."""
        if self.total_pages <= 1:
            return
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button("◀", key=f"{self.key_prefix}_compact_prev", use_container_width=True):
                if self.current_page > 1:
                    self.current_page -= 1
                    st.rerun()
        
        with col2:
            st.caption(f"{self.current_page}/{self.total_pages}")
        
        with col3:
            if st.button("▶", key=f"{self.key_prefix}_compact_next", use_container_width=True):
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    st.rerun()


def paginate_dataframe(
    df: pd.DataFrame,
    page_size: int = 50,
    key_prefix: str = "df",
    show_controls: bool = True,
    compact: bool = False
) -> Tuple[pd.DataFrame, Paginator]:
    """
    Paginate a DataFrame with controls.
    
    Args:
        df: DataFrame to paginate
        page_size: Number of items per page
        key_prefix: Prefix for session state keys
        show_controls: Whether to show pagination controls
        compact: Use compact controls
    
    Returns:
        Tuple of (paginated_df, paginator)
    """
    if df.empty:
        return df, Paginator(0, page_size, key_prefix)
    
    paginator = Paginator(len(df), page_size, key_prefix)
    paginated_df = paginator.get_page_data(df)
    
    if show_controls:
        if compact:
            paginator.render_compact_pagination()
        else:
            paginator.render_pagination_controls()
    
    return paginated_df, paginator


# ============================================================
# LAZY LOADING UTILITIES
# ============================================================

class LazyLoader:
    """
    Lazy loading for heavy components with caching.
    """
    
    def __init__(self, load_func, cache_ttl: int = 300, key_prefix: str = "lazy"):
        """
        Initialize lazy loader.
        
        Args:
            load_func: Function that loads the data
            cache_ttl: Cache TTL in seconds
            key_prefix: Prefix for session state keys
        """
        self.load_func = load_func
        self.cache_ttl = cache_ttl
        self.key_prefix = key_prefix
        self._init_session_state()
    
    def _init_session_state(self):
        """Initialize session state for lazy loading."""
        loaded_key = f"{self.key_prefix}_loaded"
        data_key = f"{self.key_prefix}_data"
        timestamp_key = f"{self.key_prefix}_timestamp"
        
        if loaded_key not in st.session_state:
            st.session_state[loaded_key] = False
        if data_key not in st.session_state:
            st.session_state[data_key] = None
        if timestamp_key not in st.session_state:
            st.session_state[timestamp_key] = None
    
    @property
    def is_loaded(self) -> bool:
        """Check if data is loaded."""
        return st.session_state.get(f"{self.key_prefix}_loaded", False)
    
    @property
    def data(self):
        """Get loaded data."""
        return st.session_state.get(f"{self.key_prefix}_data", None)
    
    def load(self, force: bool = False) -> Any:
        """
        Load data if not already loaded.
        
        Args:
            force: Force reload
        
        Returns:
            Loaded data
        """
        loaded_key = f"{self.key_prefix}_loaded"
        data_key = f"{self.key_prefix}_data"
        timestamp_key = f"{self.key_prefix}_timestamp"
        
        # Check if cache expired
        if not force and st.session_state.get(loaded_key, False):
            timestamp = st.session_state.get(timestamp_key)
            if timestamp and (time.time() - timestamp) < self.cache_ttl:
                return st.session_state.get(data_key)
        
        # Load data
        with st.spinner("Loading data..."):
            data = self.load_func()
            st.session_state[data_key] = data
            st.session_state[timestamp_key] = time.time()
            st.session_state[loaded_key] = True
        
        return data
    
    def render_load_button(self, label: str = "📊 Load Data", button_type: str = "primary"):
        """
        Render a button to trigger lazy loading.
        
        Args:
            label: Button label
            button_type: Button type ('primary', 'secondary')
        """
        if not self.is_loaded:
            if st.button(label, type=button_type, use_container_width=True):
                self.load()
                st.rerun()
        else:
            st.success("✅ Data loaded")
            if st.button("🔄 Reload Data", use_container_width=True):
                self.load(force=True)
                st.rerun()
    
    def render_expander(self, title: str = "📊 View Data", expanded: bool = False):
        """
        Render data in an expander with lazy loading.
        
        Args:
            title: Expander title
            expanded: Whether expander is expanded
        """
        with st.expander(title, expanded=expanded):
            if not self.is_loaded:
                if st.button("📊 Load Data", type="primary", use_container_width=True):
                    self.load()
                    st.rerun()
            else:
                data = self.data
                if data is not None:
                    if isinstance(data, pd.DataFrame):
                        st.dataframe(data, use_container_width=True)
                    else:
                        st.write(data)
                else:
                    st.info("No data available")


# ============================================================
# SESSION STATE OPTIMIZATION
# ============================================================

def optimize_session_state():
    """
    Optimize session state by removing unnecessary data.
    """
    # Keep only essential keys
    essential_keys = [
        'initialized', 'db_initialized', 'selected_period', 
        'last_loaded_period', 'transactions', 'inventory_mode',
        'stock_takes', 'active_count_id', 'count_sheets'
    ]
    
    # Remove large temporary data
    for key in list(st.session_state.keys()):
        if key not in essential_keys and not key.startswith('_'):
            # Check if value is large
            value = st.session_state[key]
            if isinstance(value, pd.DataFrame) and len(value) > 1000:
                del st.session_state[key]
                logger.debug(f"Removed large DataFrame from session state: {key}")


def compress_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compress DataFrame by optimizing dtypes.
    
    Args:
        df: DataFrame to compress
    
    Returns:
        Compressed DataFrame
    """
    if df.empty:
        return df
    
    df_compressed = df.copy()
    
    for col in df_compressed.columns:
        col_type = df_compressed[col].dtype
        
        # Optimize integer columns
        if pd.api.types.is_integer_dtype(col_type):
            min_val = df_compressed[col].min()
            max_val = df_compressed[col].max()
            
            if min_val >= 0:
                if max_val <= 255:
                    df_compressed[col] = df_compressed[col].astype('uint8')
                elif max_val <= 65535:
                    df_compressed[col] = df_compressed[col].astype('uint16')
                elif max_val <= 4294967295:
                    df_compressed[col] = df_compressed[col].astype('uint32')
            else:
                if max_val <= 127 and min_val >= -128:
                    df_compressed[col] = df_compressed[col].astype('int8')
                elif max_val <= 32767 and min_val >= -32768:
                    df_compressed[col] = df_compressed[col].astype('int16')
                elif max_val <= 2147483647 and min_val >= -2147483648:
                    df_compressed[col] = df_compressed[col].astype('int32')
        
        # Optimize float columns
        elif pd.api.types.is_float_dtype(col_type):
            df_compressed[col] = df_compressed[col].astype('float32')
        
        # Optimize string columns
        elif pd.api.types.is_object_dtype(col_type):
            # Convert to categorical if few unique values
            unique_count = df_compressed[col].nunique()
            if unique_count < len(df_compressed) * 0.5:
                df_compressed[col] = df_compressed[col].astype('category')
    
    return df_compressed


# ============================================================
# BACKGROUND PROCESSING
# ============================================================

class BackgroundProcessor:
    """
    Handle background processing for heavy operations.
    """
    
    def __init__(self, key_prefix: str = "bg"):
        """
        Initialize background processor.
        
        Args:
            key_prefix: Prefix for session state keys
        """
        self.key_prefix = key_prefix
        self._init_session_state()
    
    def _init_session_state(self):
        """Initialize session state for background processing."""
        status_key = f"{self.key_prefix}_status"
        result_key = f"{self.key_prefix}_result"
        progress_key = f"{self.key_prefix}_progress"
        
        if status_key not in st.session_state:
            st.session_state[status_key] = 'idle'  # idle, running, complete, error
        if result_key not in st.session_state:
            st.session_state[result_key] = None
        if progress_key not in st.session_state:
            st.session_state[progress_key] = 0
    
    @property
    def status(self) -> str:
        """Get current status."""
        return st.session_state.get(f"{self.key_prefix}_status", 'idle')
    
    @status.setter
    def status(self, value: str):
        """Set current status."""
        st.session_state[f"{self.key_prefix}_status"] = value
    
    @property
    def result(self):
        """Get processing result."""
        return st.session_state.get(f"{self.key_prefix}_result", None)
    
    @result.setter
    def result(self, value):
        """Set processing result."""
        st.session_state[f"{self.key_prefix}_result"] = value
    
    @property
    def progress(self) -> int:
        """Get progress percentage."""
        return st.session_state.get(f"{self.key_prefix}_progress", 0)
    
    @progress.setter
    def progress(self, value: int):
        """Set progress percentage."""
        st.session_state[f"{self.key_prefix}_progress"] = min(100, max(0, value))
    
    def process(self, func, *args, **kwargs):
        """
        Process a function in the background.
        
        Args:
            func: Function to process
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Result of the function
        """
        self.status = 'running'
        self.progress = 0
        
        try:
            # Process in chunks to show progress
            result = func(*args, **kwargs)
            self.result = result
            self.status = 'complete'
            self.progress = 100
            return result
        except Exception as e:
            self.status = 'error'
            logger.error(f"Background processing error: {e}")
            return None
    
    def render_progress(self):
        """Render progress indicator."""
        if self.status == 'running':
            progress_bar = st.progress(self.progress / 100)
            st.caption(f"Processing... {self.progress}%")
            return progress_bar
        elif self.status == 'complete':
            st.success("✅ Processing complete")
        elif self.status == 'error':
            st.error("❌ Processing failed")
        return None


# ============================================================
# STREAMLIT RERUN OPTIMIZATION
# ============================================================

def debounce_rerun(delay: float = 0.5):
    """
    Debounce reruns to prevent excessive refreshes.
    
    Args:
        delay: Debounce delay in seconds
    """
    last_rerun_key = "_last_rerun"
    if last_rerun_key in st.session_state:
        last_rerun = st.session_state[last_rerun_key]
        if time.time() - last_rerun < delay:
            return
    st.session_state[last_rerun_key] = time.time()
    st.rerun()


def optimize_table_display(df: pd.DataFrame, max_rows: int = 1000):
    """
    Optimize table display for large DataFrames.
    
    Args:
        df: DataFrame to display
        max_rows: Maximum rows to display
    
    Returns:
        Optimized DataFrame for display
    """
    if len(df) > max_rows:
        # Show sample with note
        sample_df = df.head(max_rows)
        st.info(f"📊 Showing {max_rows} of {len(df):,} rows. Use pagination for full data.")
        return sample_df
    return df


# ============================================================
# CACHE OPTIMIZATION
# ============================================================

def cache_with_ttl(ttl: int = 300):
    """
    Custom cache decorator with TTL.
    
    Args:
        ttl: Cache TTL in seconds
    """
    def decorator(func):
        cache_data = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            if key in cache_data:
                data, timestamp = cache_data[key]
                if time.time() - timestamp < ttl:
                    return data
            
            result = func(*args, **kwargs)
            cache_data[key] = (result, time.time())
            return result
        
        return wrapper
    return decorator


# ============================================================
# MEMORY MANAGEMENT
# ============================================================

def free_memory():
    """
    Force garbage collection to free memory.
    """
    gc.collect()
    logger.debug("Garbage collection completed")


def get_memory_usage():
    """
    Get current memory usage.
    
    Returns:
        Memory usage in MB
    """
    import psutil
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    return memory_mb


# ============================================================
# COMPONENT CACHE
# ============================================================

class ComponentCache:
    """
    Cache for expensive component renderings.
    """
    
    def __init__(self, max_size: int = 10):
        """
        Initialize component cache.
        
        Args:
            max_size: Maximum cache size
        """
        self.cache = {}
        self.max_size = max_size
        self.access_order = []
    
    def get(self, key: str):
        """Get cached component."""
        if key in self.cache:
            # Move to end (most recently used)
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None
    
    def set(self, key: str, value):
        """Set cached component."""
        if len(self.cache) >= self.max_size:
            # Remove least recently used
            oldest = self.access_order.pop(0)
            del self.cache[oldest]
        
        self.cache[key] = value
        self.access_order.append(key)
    
    def clear(self):
        """Clear cache."""
        self.cache.clear()
        self.access_order.clear()