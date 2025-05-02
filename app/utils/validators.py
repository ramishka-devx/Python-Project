import re
from flask import jsonify

def validate_email(email):
    """Validate email format"""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if re.match(pattern, email) is None:
        return False
    return True

def validate_password(password):
    """Password must be at least 8 characters"""
    if len(password) < 8:
        return False
    return True

def validate_amount(amount):
    """Amount must be positive"""
    try:
        amount = float(amount)
        if amount <= 0:
            return False
        return True
    except (ValueError, TypeError):
        return False

def error_response(message, status_code=400):
    """Return a standardized error response"""
    response = jsonify({'error': message})
    response.status_code = status_code
    return response 