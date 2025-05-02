import random
import string

def generate_account_number():
    """Generate a random account number"""
    digits = ''.join(random.choices(string.digits, k=10))
    return f"ACCT-{digits}" 