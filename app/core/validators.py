# core/validators.py
"""
Input validation functions for the inventory app.
"""

from typing import Tuple, Optional
from datetime import datetime, date
import re

def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format."""
    if not email:
        return False, "❌ Email is required"
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "❌ Invalid email format"
    
    return True, "✅ Valid email"

def validate_phone(phone: str) -> Tuple[bool, str]:
    """Validate phone number."""
    if not phone:
        return True, "✅ Phone optional"
    
    # Remove common separators
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    
    if not cleaned.isdigit():
        return False, "❌ Phone should contain only digits"
    
    if len(cleaned) < 10 or len(cleaned) > 15:
        return False, "❌ Phone should be 10-15 digits"
    
    return True, "✅ Valid phone number"

def validate_date_range(
    start_date: date,
    end_date: date
) -> Tuple[bool, str]:
    """Validate date range."""
    if start_date > end_date:
        return False, "❌ Start date must be before end date"
    
    if (end_date - start_date).days > 365:
        return False, "❌ Date range cannot exceed 1 year"
    
    return True, "✅ Valid date range"

def validate_item_name(name: str) -> Tuple[bool, str]:
    """Validate item name."""
    if not name or not name.strip():
        return False, "❌ Item name is required"
    
    if len(name) > 100:
        return False, "❌ Item name is too long (max 100 characters)"
    
    return True, "✅ Valid item name"