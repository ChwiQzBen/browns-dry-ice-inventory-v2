# core/security.py - PATCHED VERSION

import streamlit as st
import hashlib
import hmac
import json
import time
import secrets
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from functools import wraps
import logging
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# ============================================================
# AUTHENTICATION SYSTEM
# ============================================================

class AuthManager:
    """Authentication manager with role-based access control."""
    
    ROLES = {
        'admin': {
            'permissions': ['*'],
            'priority': 100
        },
        'manager': {
            'permissions': ['view_inventory', 'edit_inventory', 'view_reports', 'manage_users'],
            'priority': 80
        },
        'user': {
            'permissions': ['view_inventory', 'record_usage', 'record_receipt', 'view_reports'],
            'priority': 50
        },
        'viewer': {
            'permissions': ['view_inventory', 'view_reports'],
            'priority': 30
        }
    }
    
    DEMO_USERS = {
        'admin@browns.com': {
            'password': 'Admin123!',
            'role': 'admin',
            'name': 'System Administrator'
        },
        'manager@browns.com': {
            'password': 'Manager123!',
            'role': 'manager',
            'name': 'Inventory Manager'
        },
        'user@browns.com': {
            'password': 'User123!',
            'role': 'user',
            'name': 'Inventory User'
        },
        'viewer@browns.com': {
            'password': 'Viewer123!',
            'role': 'viewer',
            'name': 'Read-Only Viewer'
        }
    }
    
    def __init__(self):
        """Initialize authentication manager - lightweight init."""
        self._init_session_state()
    
    def _init_session_state(self):
        """Initialize session state for auth."""
        if 'auth' not in st.session_state:
            st.session_state.auth = {
                'authenticated': False,
                'user': None,
                'role': None,
                'login_time': None,
                'last_activity': None,
                'session_id': None
            }
    
    @property
    def is_authenticated(self) -> bool:
        return st.session_state.auth.get('authenticated', False)
    
    @property
    def current_user(self) -> Optional[Dict]:
        return st.session_state.auth.get('user')
    
    @property
    def current_role(self) -> Optional[str]:
        return st.session_state.auth.get('role')
    
    def login(self, email: str, password: str) -> Dict:
        if email not in self.DEMO_USERS:
            return {'success': False, 'message': '❌ Invalid email or password'}
        
        user = self.DEMO_USERS[email]
        if user['password'] != password:
            return {'success': False, 'message': '❌ Invalid email or password'}
        
        session_id = self._generate_session_id()
        login_time = datetime.now().isoformat()
        
        st.session_state.auth = {
            'authenticated': True,
            'user': {
                'email': email,
                'name': user['name'],
                'role': user['role']
            },
            'role': user['role'],
            'login_time': login_time,
            'last_activity': login_time,
            'session_id': session_id
        }
        
        return {
            'success': True,
            'message': f"✅ Welcome, {user['name']}!",
            'user': st.session_state.auth['user']
        }
    
    def logout(self):
        if self.is_authenticated:
            user_email = self.current_user['email']
            logger.info(f"🔐 User logged out: {user_email}")
        
        st.session_state.auth = {
            'authenticated': False,
            'user': None,
            'role': None,
            'login_time': None,
            'last_activity': None,
            'session_id': None
        }
        st.rerun()
    
    def check_permission(self, permission: str) -> bool:
        if not self.is_authenticated:
            return False
        
        role = self.current_role
        if role not in self.ROLES:
            return False
        
        permissions = self.ROLES[role]['permissions']
        if '*' in permissions:
            return True
        return permission in permissions
    
    def _generate_session_id(self) -> str:
        return secrets.token_urlsafe(32)
    
    def render_login_form(self):
        if self.is_authenticated:
            user = self.current_user
            st.sidebar.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #4caf50 0%, #2e7d32 100%);
                padding: 12px 15px;
                border-radius: 8px;
                color: white;
                margin-bottom: 15px;
            ">
                <div style="font-size: 14px; font-weight: 600;">✅ Logged In</div>
                <div style="font-size: 13px; opacity: 0.9;">
                    👤 {user['name']}<br>
                    🏷️ {user['role'].title()}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.sidebar.button("🚪 Logout", type="secondary", use_container_width=True):
                self.logout()
            return True
        else:
            st.sidebar.markdown("""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 12px 15px;
                border-radius: 8px;
                color: white;
                margin-bottom: 15px;
            ">
                <div style="font-size: 14px; font-weight: 600;">🔐 Login Required</div>
                <div style="font-size: 12px; opacity: 0.8;">Please sign in to continue</div>
            </div>
            """, unsafe_allow_html=True)
            
            email = st.sidebar.text_input("📧 Email", placeholder="user@browns.com")
            password = st.sidebar.text_input("🔑 Password", type="password", placeholder="••••••••")
            
            with st.sidebar.expander("🔑 Demo Credentials", expanded=False):
                st.markdown("""
                **Admin:** admin@browns.com / Admin123!<br>
                **Manager:** manager@browns.com / Manager123!<br>
                **User:** user@browns.com / User123!<br>
                **Viewer:** viewer@browns.com / Viewer123!
                """, unsafe_allow_html=True)
            
            if st.sidebar.button("🔐 Login", type="primary", use_container_width=True):
                if email and password:
                    result = self.login(email, password)
                    if result['success']:
                        st.sidebar.success(result['message'])
                        st.rerun()
                    else:
                        st.sidebar.error(result['message'])
                else:
                    st.sidebar.warning("⚠️ Please enter both email and password")
            return False


# ============================================================
# DECORATORS - Keep these simple and fast
# ============================================================

def require_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = AuthManager()
        if not auth.is_authenticated:
            st.error("🔒 Please login to access this feature")
            return None
        return func(*args, **kwargs)
    return wrapper

def require_permission(permission: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth = AuthManager()
            if not auth.is_authenticated:
                st.error("🔒 Please login to access this feature")
                return None
            if not auth.check_permission(permission):
                st.error(f"⛔ You don't have permission: {permission}")
                return None
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(role: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth = AuthManager()
            if not auth.is_authenticated:
                st.error("🔒 Please login to access this feature")
                return None
            if auth.current_role != role and auth.current_role != 'admin':
                st.error(f"⛔ This feature requires {role} role")
                return None
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# AUDIT LOGGER - Lazy initialization
# ============================================================

class AuditLogger:
    """Audit logging with lazy file initialization."""
    
    def __init__(self):
        self.log_file = 'audit.log'
        self._initialized = False
    
    def _ensure_log_file(self):
        """Ensure audit log file exists - only when needed."""
        if self._initialized:
            return
        
        try:
            # Try to write to the file
            if not os.path.exists(self.log_file):
                with open(self.log_file, 'w') as f:
                    f.write("# Audit Log\n")
                    f.write("# Format: TIMESTAMP | USER | ACTION | DETAILS | IP\n")
            self._initialized = True
        except Exception as e:
            # Don't fail - just continue without file logging
            logger.warning(f"Could not create audit log file: {e}")
            self._initialized = True
    
    def log(self, action: str, details: str = "", user: str = None):
        """Log an audit event."""
        self._ensure_log_file()
        
        try:
            auth = AuthManager()
            user_email = user or (auth.current_user['email'] if auth.is_authenticated else 'SYSTEM')
            timestamp = datetime.now().isoformat()
            log_entry = f"{timestamp} | {user_email} | {action} | {details}\n"
            
            with open(self.log_file, 'a') as f:
                f.write(log_entry)
        except Exception as e:
            # Silently fail - don't break the app for logging
            logger.debug(f"Audit log failed: {e}")


# ============================================================
# SESSION MANAGER
# ============================================================

class SessionManager:
    """Secure session management with timeout."""
    
    SESSION_TIMEOUT = 3600  # 1 hour
    
    def __init__(self):
        self.auth = AuthManager()
    
    def validate_session(self) -> bool:
        if not self.auth.is_authenticated:
            return False
        
        last_activity = st.session_state.auth.get('last_activity')
        if last_activity:
            try:
                last_time = datetime.fromisoformat(last_activity)
                if (datetime.now() - last_time).seconds > self.SESSION_TIMEOUT:
                    self.auth.logout()
                    st.warning("⏰ Session expired. Please login again.")
                    return False
            except:
                pass
        
        st.session_state.auth['last_activity'] = datetime.now().isoformat()
        return True


# ============================================================
# DATA ENCRYPTION - Lazy initialization
# ============================================================

class DataEncryption:
    """Data encryption with lazy initialization."""
    
    def __init__(self, key: str = None):
        self._key = key
        self._cipher = None
        self._initialized = False
    
    def _ensure_cipher(self):
        """Initialize cipher only when needed."""
        if self._initialized:
            return
        
        try:
            if self._key is None:
                try:
                    secret = st.secrets.get("ENCRYPTION_KEY", "default_encryption_key")
                except:
                    secret = "default_encryption_key"
                
                # Use fewer iterations for faster startup
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'salt_',
                    iterations=10000,  # Reduced from 100000
                )
                self._key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
            
            self._cipher = Fernet(self._key)
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            self._initialized = True
    
    def encrypt(self, data: str) -> str:
        if not data:
            return data
        self._ensure_cipher()
        if not self._cipher:
            return data
        try:
            encrypted = self._cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except:
            return data
    
    def decrypt(self, encrypted_data: str) -> str:
        if not encrypted_data:
            return encrypted_data
        self._ensure_cipher()
        if not self._cipher:
            return encrypted_data
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except:
            return None


# ============================================================
# API KEY MANAGER - Lazy initialization
# ============================================================

class ApiKeyManager:
    """API key management with lazy file initialization."""
    
    def __init__(self):
        self.keys_file = 'api_keys.json'
        self._initialized = False
    
    def _ensure_keys_file(self):
        if self._initialized:
            return
        
        try:
            if not os.path.exists(self.keys_file):
                with open(self.keys_file, 'w') as f:
                    json.dump({}, f)
            self._initialized = True
        except Exception as e:
            logger.warning(f"Could not create API keys file: {e}")
            self._initialized = True
    
    def generate_key(self, name: str, permissions: List[str] = None) -> str:
        self._ensure_keys_file()
        key = secrets.token_urlsafe(32)
        
        try:
            with open(self.keys_file, 'r') as f:
                keys = json.load(f)
            
            keys[key] = {
                'name': name,
                'created': datetime.now().isoformat(),
                'permissions': permissions or ['*'],
                'last_used': None
            }
            
            with open(self.keys_file, 'w') as f:
                json.dump(keys, f, indent=2)
        except:
            pass
        
        return key


# ============================================================
# SECURITY DASHBOARD
# ============================================================

def render_security_dashboard():
    """Render security dashboard."""
    st.markdown("### 🔐 Security Dashboard")
    
    auth = AuthManager()
    
    if not auth.is_authenticated or auth.current_role != 'admin':
        st.warning("🔒 This section is restricted to administrators")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("👤 Current User", auth.current_user['name'])
    with col2:
        st.metric("🎯 Role", auth.current_user['role'].title())
    with col3:
        login_time = datetime.fromisoformat(auth.current_user.get('login_time', datetime.now().isoformat()))
        st.metric("🕐 Login Time", login_time.strftime('%H:%M:%S'))


# ============================================================
# SECURE ENDPOINT DECORATOR
# ============================================================

def secure_endpoint(func):
    """Decorator to secure an endpoint."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        session = SessionManager()
        if not session.validate_session():
            st.error("🔒 Session invalid or expired. Please login again.")
            return None
        
        auth = AuthManager()
        if not auth.is_authenticated:
            st.error("🔒 Please login to access this feature")
            return None
        
        return func(*args, **kwargs)
    return wrapper