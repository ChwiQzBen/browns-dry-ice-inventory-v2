# app/core/supabase_client.py
import streamlit as st
from supabase import create_client

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