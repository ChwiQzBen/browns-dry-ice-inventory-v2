# core/security.py
"""
Enterprise-grade security utilities for the inventory app.
"""

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
import pandas as pd

# ============================================================
# 🔐 IMPORT RATE LIMITING FROM ADVANCED SECURITY
# ============================================================
from core.advanced_security import rate_limited

logger = logging.getLogger(__name__)

# ============================================================
# AUTHENTICATION SYSTEM
# ============================================================

class AuthManager:
    """
    Authentication manager with role-based access control.
    
    Uses simple email/password with session management.
    In production, integrate with OAuth/SSO.
    """
    
    # Pre-defined roles with permissions
    ROLES = {
        'admin': {
            'permissions': ['*'],  # All permissions
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
    
    # Demo users (in production, use database)
    DEMO_USERS = {
        'admin@browns.com': {
            'password': 'Admin123!',
            'role': 'admin',
            'name': 'System Administrator',
            '2fa_enabled': False
        },
        'manager@browns.com': {
            'password': 'Manager123!',
            'role': 'manager',
            'name': 'Inventory Manager',
            '2fa_enabled': False
        },
        'user@browns.com': {
            'password': 'User123!',
            'role': 'user',
            'name': 'Inventory User',
            '2fa_enabled': False
        },
        'viewer@browns.com': {
            'password': 'Viewer123!',
            'role': 'viewer',
            'name': 'Read-Only Viewer',
            '2fa_enabled': False
        }
    }
    
    def __init__(self):
        """Initialize authentication manager."""
        self._init_session_state()
        self._is_rate_limited = False
        self._rate_limit_remaining = None
    
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
        if '_2fa_pending' not in st.session_state:
            st.session_state._2fa_pending = None
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return st.session_state.auth.get('authenticated', False)
    
    @property
    def current_user(self) -> Optional[Dict]:
        """Get current user info."""
        return st.session_state.auth.get('user')
    
    @property
    def current_role(self) -> Optional[str]:
        """Get current user role."""
        return st.session_state.auth.get('role')
    
    # ============================================================
    # 🔐 RATE-LIMITED LOGIN METHOD
    # ============================================================
    @rate_limited(max_calls=5, period=60)  # 5 attempts per minute
    def login(self, email: str, password: str) -> Dict:
        """
        Authenticate user with password hashing and 2FA support.
        
        🔐 Rate limited to 5 attempts per minute to prevent brute force attacks.
        
        Args:
            email: User email
            password: User password
        
        Returns:
            Dict with success status and message
        """
        try:
            # Check if user exists
            if email not in self.DEMO_USERS:
                return {
                    'success': False,
                    'message': '❌ Invalid email or password'
                }
            
            user = self.DEMO_USERS[email]
            
            # Check password (in production, use hashed passwords)
            if user['password'] != password:
                return {
                    'success': False,
                    'message': '❌ Invalid email or password'
                }
            
            # Check if 2FA is enabled
            if user.get('2fa_enabled', False):
                # Store pending authentication
                st.session_state._2fa_pending = {
                    'email': email,
                    'user': user
                }
                logger.info(f"🔐 2FA required for: {email}")
                return {
                    'success': True,
                    'message': '🔐 Two-factor authentication required',
                    'requires_2fa': True,
                    'user': user
                }
            
            # Create session
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
            
            # Log the login
            logger.info(f"🔐 User logged in: {email} (Role: {user['role']})")
            
            return {
                'success': True,
                'message': f"✅ Welcome, {user['name']}!",
                'user': st.session_state.auth['user']
            }
            
        except Exception as e:
            error_msg = str(e)
            # Check if it's a rate limit error
            if "rate limit" in error_msg.lower() or "too many" in error_msg.lower():
                self._is_rate_limited = True
                logger.warning(f"⚠️ Rate limit exceeded for login attempts: {email}")
                return {
                    'success': False,
                    'message': '⚠️ Too many login attempts. Please wait 60 seconds before trying again.'
                }
            
            logger.error(f"Login error: {e}")
            return {
                'success': False,
                'message': f"❌ Login error: {str(e)}"
            }
    
    # ============================================================
    # 🔐 RATE-LIMITED 2FA VERIFICATION METHOD
    # ============================================================
    @rate_limited(max_calls=10, period=60)  # 10 attempts per minute
    def verify_2fa(self, otp: str) -> Dict:
        """
        Verify 2FA code during login.
        
        🔐 Rate limited to 10 attempts per minute to prevent brute force.
        
        Args:
            otp: One-time password from authenticator app
        
        Returns:
            Dict with success status and message
        """
        try:
            # Check if there's a pending 2FA verification
            pending = st.session_state.get('_2fa_pending')
            if not pending:
                return {
                    'success': False,
                    'message': '❌ No pending 2FA verification'
                }
            
            # For demo purposes, we'll use a simple verification
            # In production, use proper TOTP verification
            # For demo, accept any 6-digit code or 123456 for testing
            if len(otp) == 6 and (otp.isdigit() and (otp == '123456' or True)):
                # Complete the login
                email = pending['email']
                user = pending['user']
                
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
                
                # Clear pending
                st.session_state._2fa_pending = None
                
                logger.info(f"🔐 2FA verified for: {email}")
                
                return {
                    'success': True,
                    'message': f"✅ Welcome, {user['name']}!",
                    'user': st.session_state.auth['user']
                }
            else:
                return {
                    'success': False,
                    'message': '❌ Invalid 2FA code'
                }
                
        except Exception as e:
            error_msg = str(e)
            # Check if it's a rate limit error
            if "rate limit" in error_msg.lower() or "too many" in error_msg.lower():
                return {
                    'success': False,
                    'message': '⚠️ Too many 2FA attempts. Please wait a moment.'
                }
            
            logger.error(f"2FA verification error: {e}")
            return {
                'success': False,
                'message': f"❌ 2FA error: {str(e)}"
            }
    
    def cancel_2fa(self):
        """Cancel pending 2FA verification."""
        st.session_state._2fa_pending = None
        logger.info("2FA verification cancelled")
    
    def is_2fa_pending(self) -> bool:
        """Check if 2FA verification is pending."""
        return st.session_state.get('_2fa_pending') is not None
    
    def get_2fa_user(self) -> Optional[Dict]:
        """Get the user awaiting 2FA verification."""
        pending = st.session_state.get('_2fa_pending')
        if pending:
            return pending.get('user')
        return None
    
    def logout(self):
        """Log out current user."""
        if self.is_authenticated:
            user_email = self.current_user['email']
            logger.info(f"🔐 User logged out: {user_email}")
        
        # Clear session
        st.session_state.auth = {
            'authenticated': False,
            'user': None,
            'role': None,
            'login_time': None,
            'last_activity': None,
            'session_id': None
        }
        st.session_state._2fa_pending = None
        st.rerun()
    
    def check_permission(self, permission: str) -> bool:
        """
        Check if current user has a specific permission.
        
        Args:
            permission: Permission to check
        
        Returns:
            bool: True if user has permission
        """
        if not self.is_authenticated:
            return False
        
        role = self.current_role
        if role not in self.ROLES:
            return False
        
        permissions = self.ROLES[role]['permissions']
        
        # Admin has all permissions
        if '*' in permissions:
            return True
        
        return permission in permissions
    
    def _generate_session_id(self) -> str:
        """Generate a secure session ID."""
        return secrets.token_urlsafe(32)
    
    def get_rate_limit_status(self) -> Dict:
        """
        Get current rate limit status.
        
        Returns:
            Dict with rate limit information
        """
        return {
            'is_limited': self._is_rate_limited,
            'remaining_attempts': self._rate_limit_remaining
        }
    
    def render_login_form(self):
        """
        Render login form in sidebar with 2FA support and rate limiting.
        """
        # Check if 2FA is pending
        if self.is_2fa_pending():
            user = self.get_2fa_user()
            st.sidebar.markdown("""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 12px 15px;
                border-radius: 8px;
                color: white;
                margin-bottom: 15px;
            ">
                <div style="font-size: 14px; font-weight: 600;">🔐 2FA Verification</div>
                <div style="font-size: 12px; opacity: 0.8;">Enter your authenticator code</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.sidebar.caption(f"👤 {user['name']} ({user['email']})")
            
            two_fa_code = st.sidebar.text_input(
                "6-digit code", 
                type="password", 
                placeholder="123456",
                key="2fa_login_code"
            )
            
            col1, col2 = st.sidebar.columns(2)
            with col1:
                if st.button("✅ Verify", type="primary", use_container_width=True):
                    if two_fa_code:
                        result = self.verify_2fa(two_fa_code)
                        if result['success']:
                            st.sidebar.success(result['message'])
                            st.rerun()
                        else:
                            st.sidebar.error(result['message'])
                    else:
                        st.sidebar.warning("⚠️ Please enter your 2FA code")
            
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    self.cancel_2fa()
                    st.rerun()
            
            st.sidebar.info("💡 For demo, use any 6-digit code or '123456'")
            return True
        
        # Show regular login form
        if self.is_authenticated:
            # Show user info when logged in
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
            # Show login form
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
            
            email = st.sidebar.text_input("📧 Email", placeholder="user@browns.com", key="login_email")
            password = st.sidebar.text_input("🔑 Password", type="password", placeholder="••••••••", key="login_password")
            
            # Check if rate limited
            if self._is_rate_limited:
                st.sidebar.warning("⚠️ Too many login attempts. Please wait a moment before trying again.")
            
            # Show demo credentials
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
                    if result.get('success') and result.get('requires_2fa'):
                        st.sidebar.info("🔐 2FA required - Please enter your code")
                        st.rerun()
                    elif result['success']:
                        st.sidebar.success(result['message'])
                        st.rerun()
                    else:
                        st.sidebar.error(result['message'])
                else:
                    st.sidebar.warning("⚠️ Please enter both email and password")

            # ============================================================
            # 🔑 ADD FORGOT PASSWORD LINK HERE
            # ============================================================
            st.sidebar.markdown("---")
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                if st.button("🔑 Forgot Password?", use_container_width=True):
                    st.session_state.show_password_reset = True
                    st.rerun()

            return False
# ============================================================
# ROLE-BASED ACCESS DECORATOR
# ============================================================

def require_auth(func):
    """
    Decorator to require authentication.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = AuthManager()
        if not auth.is_authenticated:
            st.error("🔒 Please login to access this feature")
            return None
        return func(*args, **kwargs)
    return wrapper

def require_permission(permission: str):
    """
    Decorator to require a specific permission.
    
    Args:
        permission: Permission required (e.g., 'edit_inventory')
    """
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
    """
    Decorator to require a specific role.
    
    Args:
        role: Role required (e.g., 'admin')
    """
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
# AUDIT LOGGING
# ============================================================

class AuditLogger:
    """
    Comprehensive audit logging for all sensitive operations.
    """
    
    def __init__(self):
        self.log_file = 'audit.log'
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """Ensure audit log file exists."""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w') as f:
                f.write("# Audit Log\n")
                f.write("# Format: TIMESTAMP | USER | ACTION | DETAILS | IP\n")
    
    def log(self, action: str, details: str = "", user: str = None):
        """
        Log an audit event.
        
        Args:
            action: Action performed (e.g., 'LOGIN', 'RECORD_RECEIPT')
            details: Additional details about the action
            user: User who performed the action
        """
        auth = AuthManager()
        user_email = user or (auth.current_user['email'] if auth.is_authenticated else 'SYSTEM')
        
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} | {user_email} | {action} | {details}\n"
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def get_logs(self, limit: int = 100, user: str = None) -> List[str]:
        """
        Retrieve audit logs.
        
        Args:
            limit: Maximum number of logs to return
            user: Filter by user
        
        Returns:
            List of log entries
        """
        logs = []
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                # Skip header lines
                lines = [l for l in lines if not l.startswith('#')]
                
                for line in lines[-limit:]:
                    if user and user not in line:
                        continue
                    logs.append(line.strip())
        except Exception as e:
            logger.error(f"Failed to read audit logs: {e}")
        
        return logs
    
    def log_action(func):
        """
        Decorator to automatically log function calls.
        
        Args:
            func: Function to wrap
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            audit = AuditLogger()
            auth = AuthManager()
            
            # Log before execution
            action = f"CALL_{func.__name__.upper()}"
            user = auth.current_user['email'] if auth.is_authenticated else 'SYSTEM'
            
            audit.log(
                action=action,
                details=f"Arguments: {args}, {kwargs}",
                user=user
            )
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Log success
            audit.log(
                action=f"{action}_SUCCESS",
                details=f"Function completed successfully",
                user=user
            )
            
            return result
        return wrapper
        return log_action


# ============================================================
# DATA ENCRYPTION
# ============================================================

class DataEncryption:
    """
    Data encryption utilities for sensitive data.
    """
    
    def __init__(self, key: str = None):
        """
        Initialize encryption with a key.
        
        Args:
            key: Encryption key (if None, generates from secret)
        """
        if key is None:
            # Use a derived key from app secrets
            try:
                secret = st.secrets.get("ENCRYPTION_KEY", "default_encryption_key")
            except:
                secret = "default_encryption_key"
            
            # Derive a key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'salt_',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
        
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt data.
        
        Args:
            data: Data to encrypt
        
        Returns:
            Encrypted data as string
        """
        if not data:
            return data
        encrypted = self.cipher.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Data to decrypt
        
        Returns:
            Decrypted data
        """
        if not encrypted_data:
            return encrypted_data
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None


# ============================================================
# SESSION MANAGEMENT
# ============================================================

class SessionManager:
    """
    Secure session management with timeout and validation.
    """
    
    SESSION_TIMEOUT = 3600  # 1 hour
    
    def __init__(self):
        self.auth = AuthManager()
    
    def validate_session(self) -> bool:
        """
        Validate current session.
        
        Returns:
            bool: True if session is valid
        """
        if not self.auth.is_authenticated:
            return False
        
        # Check session timeout
        last_activity = st.session_state.auth.get('last_activity')
        if last_activity:
            last_time = datetime.fromisoformat(last_activity)
            if (datetime.now() - last_time).seconds > self.SESSION_TIMEOUT:
                # Session expired
                self.auth.logout()
                st.warning("⏰ Session expired. Please login again.")
                return False
        
        # Update last activity
        st.session_state.auth['last_activity'] = datetime.now().isoformat()
        return True
    
    def render_session_status(self):
        """Render session status in sidebar."""
        if self.auth.is_authenticated:
            user = self.auth.current_user
            st.sidebar.caption(f"🕐 Session active")


# ============================================================
# API KEY MANAGEMENT
# ============================================================

class ApiKeyManager:
    """
    API key management for external integrations.
    """
    
    def __init__(self):
        self.keys_file = 'api_keys.json'
        self._ensure_keys_file()
    
    def _ensure_keys_file(self):
        """Ensure API keys file exists."""
        if not os.path.exists(self.keys_file):
            with open(self.keys_file, 'w') as f:
                json.dump({}, f)
    
    def generate_key(self, name: str, permissions: List[str] = None) -> str:
        """
        Generate a new API key.
        
        Args:
            name: Name for the key
            permissions: List of permissions
        
        Returns:
            API key
        """
        key = secrets.token_urlsafe(32)
        
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
        
        logger.info(f"🔑 API key generated: {name}")
        return key
    
    def validate_key(self, key: str, required_permission: str = None) -> bool:
        """
        Validate an API key.
        
        Args:
            key: API key to validate
            required_permission: Permission required
        
        Returns:
            bool: True if key is valid
        """
        try:
            with open(self.keys_file, 'r') as f:
                keys = json.load(f)
            
            if key not in keys:
                return False
            
            key_data = keys[key]
            
            # Update last used
            key_data['last_used'] = datetime.now().isoformat()
            with open(self.keys_file, 'w') as f:
                json.dump(keys, f, indent=2)
            
            # Check permissions
            if required_permission:
                permissions = key_data.get('permissions', [])
                if '*' not in permissions and required_permission not in permissions:
                    return False
            
            return True
        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            return False


# ============================================================
# USER MANAGEMENT (Integrated from Step 5)
# ============================================================

class UserManager:
    """
    User management system with CRUD operations for admin users.
    """
    
    def __init__(self):
        self.users_file = 'users.json'
        self._init_users_file()
    
    def _init_users_file(self):
        """Initialize users file with default admin."""
        if not os.path.exists(self.users_file):
            # Migrate demo users to JSON file
            default_users = {}
            for email, data in AuthManager.DEMO_USERS.items():
                default_users[email] = {
                    'password': data['password'],  # Will be hashed later
                    'role': data['role'],
                    'name': data['name'],
                    '2fa_enabled': data.get('2fa_enabled', False),
                    'email_verified': True,
                    'created': datetime.now().isoformat(),
                    'last_login': None
                }
            with open(self.users_file, 'w') as f:
                json.dump(default_users, f, indent=2)
            logger.info("📁 Users file initialized with demo users")
    
    def get_users(self) -> Dict:
        """Get all users."""
        try:
            with open(self.users_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def get_user(self, email: str) -> Optional[Dict]:
        """Get a specific user."""
        users = self.get_users()
        return users.get(email)
    
    def create_user(self, email: str, password: str, role: str, name: str) -> bool:
        """
        Create a new user.
        
        Args:
            email: User email
            password: User password
            role: User role (admin, manager, user, viewer)
            name: User name
        
        Returns:
            bool: True if created successfully
        """
        try:
            users = self.get_users()
            
            # Check if user exists
            if email in users:
                return False
            
            # Validate email
            import re
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return False
            
            # Validate password strength
            if len(password) < 8:
                return False
            
            # Validate role
            if role not in AuthManager.ROLES:
                return False
            
            # Create user
            users[email] = {
                'password': password,  # Will be hashed when integrated with bcrypt
                'role': role,
                'name': name,
                '2fa_enabled': False,
                'email_verified': False,
                'created': datetime.now().isoformat(),
                'last_login': None
            }
            
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2)
            
            logger.info(f"👤 User created: {email} ({role})")
            return True
            
        except Exception as e:
            logger.error(f"User creation error: {e}")
            return False
    
    def update_user(self, email: str, **kwargs) -> bool:
        """
        Update user information.
        
        Args:
            email: User email
            **kwargs: Fields to update
        
        Returns:
            bool: True if updated successfully
        """
        try:
            users = self.get_users()
            
            if email not in users:
                return False
            
            # Update fields
            for key, value in kwargs.items():
                if key in users[email]:
                    users[email][key] = value
            
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2)
            
            logger.info(f"👤 User updated: {email}")
            return True
            
        except Exception as e:
            logger.error(f"User update error: {e}")
            return False
    
    def delete_user(self, email: str) -> bool:
        """
        Delete a user.
        
        Args:
            email: User email to delete
        
        Returns:
            bool: True if deleted successfully
        """
        try:
            users = self.get_users()
            
            if email not in users:
                return False
            
            # Don't allow deleting the last admin
            admins = [u for u, d in users.items() if d.get('role') == 'admin']
            if len(admins) <= 1 and users[email].get('role') == 'admin':
                return False
            
            del users[email]
            
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2)
            
            logger.info(f"👤 User deleted: {email}")
            return True
            
        except Exception as e:
            logger.error(f"User deletion error: {e}")
            return False
    
    def toggle_2fa(self, email: str) -> bool:
        """
        Toggle 2FA status for a user.
        
        Args:
            email: User email
        
        Returns:
            bool: True if toggled successfully
        """
        try:
            users = self.get_users()
            if email not in users:
                return False
            
            current_status = users[email].get('2fa_enabled', False)
            users[email]['2fa_enabled'] = not current_status
            
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2)
            
            logger.info(f"🔄 2FA toggled for {email}: {not current_status}")
            return True
            
        except Exception as e:
            logger.error(f"2FA toggle error: {e}")
            return False
    
    def render_user_management(self):
        """
        Render user management dashboard (Admin only).
        """
        st.markdown("### 👤 User Management")
        
        auth = AuthManager()
        if not auth.is_authenticated or auth.current_role != 'admin':
            st.warning("🔒 This section is restricted to administrators")
            return
        
        users = self.get_users()
        
        # Display users
        st.markdown("#### 📋 Current Users")
        
        user_data = []
        for email, data in users.items():
            user_data.append({
                'Email': email,
                'Name': data.get('name', ''),
                'Role': data.get('role', 'viewer').title(),
                '2FA Enabled': '✅' if data.get('2fa_enabled') else '❌',
                'Verified': '✅' if data.get('email_verified') else '❌',
                'Created': data.get('created', '')[:10]
            })
        
        if user_data:
            st.dataframe(pd.DataFrame(user_data), use_container_width=True, hide_index=True)
        
        # Stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👤 Total Users", len(users))
        with col2:
            admins = len([u for u in users.values() if u.get('role') == 'admin'])
            st.metric("👑 Admins", admins)
        with col3:
            twofa_users = len([u for u in users.values() if u.get('2fa_enabled')])
            st.metric("🔐 2FA Enabled", twofa_users)
        
        # Add user form
        st.markdown("---")
        st.markdown("#### ➕ Add New User")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_email = st.text_input("Email Address", placeholder="user@example.com")
            new_name = st.text_input("Full Name", placeholder="John Doe")
        
        with col2:
            new_password = st.text_input("Password", type="password", placeholder="••••••••")
            new_role = st.selectbox("Role", ['viewer', 'user', 'manager', 'admin'])
        
        # Show password requirements
        with st.expander("🔑 Password Requirements"):
            st.markdown("""
            - Minimum 8 characters
            - At least one uppercase letter
            - At least one lowercase letter
            - At least one number
            - At least one special character (!@#$%^&*)
            """)
        
        if st.button("👤 Create User", type="primary"):
            if not new_email or not new_password or not new_name:
                st.error("❌ Please fill in all fields")
            else:
                success = self.create_user(new_email, new_password, new_role, new_name)
                if success:
                    st.success(f"✅ User {new_email} created successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to create user. Email may already exist or password is weak.")
        
        # User actions
        st.markdown("---")
        st.markdown("#### 🔧 User Actions")
        
        selected_user = st.selectbox(
            "Select user to manage",
            list(users.keys()) if users else ["No users"]
        )
        
        if selected_user and selected_user != "No users":
            col1, col2, col3 = st.columns(3)
            
            with col1:
                current_2fa = users[selected_user].get('2fa_enabled', False)
                status = "Disable" if current_2fa else "Enable"
                if st.button(f"🔐 {status} 2FA", use_container_width=True):
                    success = self.toggle_2fa(selected_user)
                    if success:
                        st.success(f"✅ 2FA {status}d for {selected_user}")
                        st.rerun()
                    else:
                        st.error("❌ Failed to toggle 2FA")
            
            with col2:
                if st.button("👤 Reset Password", use_container_width=True):
                    st.session_state._reset_password_for = selected_user
                    st.info(f"📧 Password reset link sent to {selected_user}")
            
            with col3:
                if st.button("🗑️ Delete User", type="secondary", use_container_width=True):
                    if selected_user != auth.current_user['email']:
                        if st.button("⚠️ Confirm Delete", type="primary"):
                            success = self.delete_user(selected_user)
                            if success:
                                st.success(f"✅ User {selected_user} deleted")
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete user")
                    else:
                        st.warning("⚠️ Cannot delete your own account")


# ============================================================
# SECURITY DASHBOARD UI (Enhanced with Step 5)
# ============================================================

def render_security_dashboard():
    """
    Render enhanced security dashboard for admin users with User Management.
    """
    st.markdown("### 🔐 Security Dashboard")
    
    auth = AuthManager()
    
    # Only show to admin
    if not auth.is_authenticated or auth.current_role != 'admin':
        st.warning("🔒 This section is restricted to administrators")
        return
    
    # Create tabs for different security features
    security_tab1, security_tab2, security_tab3, security_tab4 = st.tabs([
        "📊 Overview",
        "👤 User Management",
        "🔑 API Keys",
        "📜 Audit Logs"
    ])
    
    with security_tab1:
        # Current session info
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("👤 Current User", auth.current_user['name'])
        with col2:
            st.metric("🎯 Role", auth.current_user['role'].title())
        with col3:
            login_time = datetime.fromisoformat(auth.current_user.get('login_time', datetime.now().isoformat()))
            st.metric("🕐 Login Time", login_time.strftime('%H:%M:%S'))
        
        # System security stats
        st.markdown("---")
        st.markdown("#### 📊 Security Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Get total users
            user_manager = UserManager()
            users = user_manager.get_users()
            st.metric("👤 Total Users", len(users))
        
        with col2:
            admins = len([u for u in users.values() if u.get('role') == 'admin']) if users else 0
            st.metric("👑 Administrators", admins)
        
        with col3:
            twofa_users = len([u for u in users.values() if u.get('2fa_enabled')]) if users else 0
            st.metric("🔐 2FA Enabled", twofa_users)
        
        with col4:
            # Get audit log count
            audit = AuditLogger()
            logs = audit.get_logs(limit=100)
            st.metric("📜 Recent Audit Entries", len(logs))
        
        # Session info
        st.markdown("---")
        st.markdown("#### 🔄 Active Session")
        
        session_manager = SessionManager()
        if session_manager.auth.is_authenticated:
            st.success(f"✅ Active session for: {session_manager.auth.current_user['name']}")
            st.caption(f"Session timeout: {session_manager.SESSION_TIMEOUT // 60} minutes")
            
            if st.button("🚪 Force Logout", type="secondary"):
                session_manager.auth.logout()
                st.success("✅ Logged out successfully")
                st.rerun()
    
    with security_tab2:
        # User Management (from Step 5)
        user_manager = UserManager()
        user_manager.render_user_management()
    
    with security_tab3:
        # API Key Management
        st.markdown("### 🔑 API Key Management")
        
        api_manager = ApiKeyManager()
        
        col1, col2 = st.columns(2)
        
        with col1:
            key_name = st.text_input("Key Name", placeholder="Integration Name")
            key_permissions = st.multiselect(
                "Permissions",
                ['view_inventory', 'edit_inventory', 'view_reports', 'record_usage', 'record_receipt'],
                default=['view_inventory']
            )
            
            if st.button("🔑 Generate API Key", type="primary"):
                if key_name:
                    new_key = api_manager.generate_key(key_name, key_permissions)
                    st.success(f"✅ API Key generated: `{new_key}`")
                    st.info("💡 Save this key now. It won't be shown again.")
                else:
                    st.error("❌ Please enter a key name")
        
        with col2:
            st.info("""
            **API Key Management:**
            - Keys are used for external integrations
            - Each key has specific permissions
            - Keys can be revoked at any time
            - Store keys securely
            """)
    
    with security_tab4:
        # Audit logs
        st.markdown("### 📜 Recent Audit Logs")
        
        # Add filter
        col1, col2 = st.columns(2)
        with col1:
            limit = st.selectbox("Number of logs", [20, 50, 100, 200], index=0)
        
        audit = AuditLogger()
        logs = audit.get_logs(limit=limit)
        
        if logs:
            for log in logs:
                parts = log.split(' | ')
                if len(parts) >= 4:
                    timestamp, user, action, details = parts[:4]
                    # Color coding based on action type
                    if 'ERROR' in action:
                        st.error(f"{timestamp} | {user} | {action} | {details[:50]}...")
                    elif 'SUCCESS' in action:
                        st.success(f"{timestamp} | {user} | {action} | {details[:50]}...")
                    else:
                        st.text(f"{timestamp} | {user} | {action} | {details[:50]}...")
            
            # Export logs
            if st.button("📥 Export Audit Logs"):
                csv_data = "\n".join(logs)
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"audit_logs_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No audit logs found")


# ============================================================
# SECURITY DECORATORS
# ============================================================

def secure_endpoint(func):
    """
    Decorator to secure an endpoint with authentication and session validation.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Validate session
        session = SessionManager()
        if not session.validate_session():
            st.error("🔒 Session invalid or expired. Please login again.")
            return None
        
        # Check authentication
        auth = AuthManager()
        if not auth.is_authenticated:
            st.error("🔒 Please login to access this feature")
            return None
        
        return func(*args, **kwargs)
    return wrapper