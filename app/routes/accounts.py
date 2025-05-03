from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.account import Account
from app.models.user import User
from app.models.transaction import Transaction
from app.utils.validators import error_response
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from sqlalchemy import or_, text, and_
import hashlib
import re

bp = Blueprint('accounts', __name__, url_prefix='/api/accounts')

MAX_ACCOUNTS = 2
ACCOUNT_TYPES = ['checking', 'savings', 'business']
MIN_ACCOUNT_NAME_LENGTH = 3
MAX_ACCOUNT_NAME_LENGTH = 100
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 50
USERNAME_PATTERN = r'^[a-zA-Z0-9_]+$'  # Only letters, numbers, and underscores
MIN_TRANSACTION_AMOUNT = Decimal('0.01')
MAX_TRANSACTION_AMOUNT = Decimal('1000000.00')

def validate_username(username):
    """Validate username format and length"""
    if not username or len(username) < MIN_USERNAME_LENGTH or len(username) > MAX_USERNAME_LENGTH:
        return False, f'Username must be between {MIN_USERNAME_LENGTH} and {MAX_USERNAME_LENGTH} characters'
    if not re.match(USERNAME_PATTERN, username):
        return False, 'Username can only contain letters, numbers, and underscores'
    return True, username

def validate_account_name(name):
    """Validate account name format and length"""
    if not name or len(name) < MIN_ACCOUNT_NAME_LENGTH or len(name) > MAX_ACCOUNT_NAME_LENGTH:
        return False, f'Account name must be between {MIN_ACCOUNT_NAME_LENGTH} and {MAX_ACCOUNT_NAME_LENGTH} characters'
    if not name.replace(' ', '').isalnum():
        return False, 'Account name can only contain letters, numbers, and spaces'
    return True, name

def validate_account_type(account_type):
    """Validate account type"""
    if account_type and account_type.lower() not in ACCOUNT_TYPES:
        return False, f'Invalid account type. Must be one of: {", ".join(ACCOUNT_TYPES)}'
    return True, account_type.lower() if account_type else 'checking'

def validate_initial_balance(balance):
    """Validate initial balance"""
    try:
        balance = Decimal(str(balance))
        if balance < -50.0:
            return False, 'Initial balance cannot be less than -50.00'
        if balance.as_tuple().exponent < -2:  # More than 2 decimal places
            return False, 'Balance cannot have more than 2 decimal places'
        return True, balance
    except (ValueError, TypeError):
        return False, 'Initial balance must be a valid number'

def validate_transaction_amount(amount):
    """Validate transaction amount"""
    try:
        amount = Decimal(str(amount))
        if amount < MIN_TRANSACTION_AMOUNT:
            return False, f'Transaction amount must be at least {MIN_TRANSACTION_AMOUNT}'
        if amount > MAX_TRANSACTION_AMOUNT:
            return False, f'Transaction amount cannot exceed {MAX_TRANSACTION_AMOUNT}'
        if amount.as_tuple().exponent < -2:  # More than 2 decimal places
            return False, 'Amount cannot have more than 2 decimal places'
        return True, amount
    except (ValueError, TypeError):
        return False, 'Transaction amount must be a valid number'

def check_duplicate_account_number(account_number):
    """Check if account number already exists"""
    existing_account = Account.query.filter_by(account_number=account_number, is_active=True).first()
    return existing_account is not None

@bp.route('', methods=['GET'])
@jwt_required()
def get_accounts():
    """Get all accounts for the authenticated user"""
    user_id = int(get_jwt_identity())
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    account_type = request.args.get('type')
    
    # Validate pagination parameters
    if page < 1 or per_page < 1 or per_page > 100:
        return error_response('Invalid pagination parameters. Page and per_page must be positive, and per_page cannot exceed 100', 400)
    
    # Build query
    query = Account.query.filter(Account.user_id == user_id, Account.is_active == True)
    
    if account_type:
        is_valid, type_or_error = validate_account_type(account_type)
        if not is_valid:
            return error_response(type_or_error, 400)
        query = query.filter(Account.account_type == type_or_error)
    
    try:
        paginated_accounts = query.paginate(page=page, per_page=per_page, error_out=False)
        
        accounts_data = []
        for account in paginated_accounts.items:
            account_dict = account.to_dict()
            account_dict['category'] = account_dict.pop('account_type')
            account_dict['label'] = account_dict.pop('account_name')
            account_dict['balance'] = float(account.balance)
            accounts_data.append(account_dict)
        
        return jsonify({
            'account_listing': accounts_data,
            'page': page,
            'per_page': per_page,
            'total': paginated_accounts.total
        })
    except SQLAlchemyError as e:
        return error_response(f"Failed to retrieve accounts: {str(e)}", 500)

@bp.route('/<int:account_id>', methods=['GET'])
@jwt_required()
def get_account(account_id):
    """Get details of a specific account"""
    user_id = int(get_jwt_identity())
    
    try:
        account = Account.query.filter(
            Account.id == account_id,
            Account.user_id == user_id,
            Account.is_active == True
        ).first()
        
        if not account:
            return error_response('Account not found or access denied', 404)
        
        account_dict = account.to_dict()
        account_dict['balance'] = float(account.balance)
        
        return jsonify({
            'account_detail': account_dict
        })
    except SQLAlchemyError as e:
        return error_response(f"Failed to retrieve account: {str(e)}", 500)

@bp.route('', methods=['POST'])
@jwt_required()
def create_account():
    """Create a new account"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    try:
        # Start transaction
        db.session.begin_nested()
        
        # Validate account type
        account_type = data.get('account_type') or data.get('type')
        is_valid, type_or_error = validate_account_type(account_type)
        if not is_valid:
            db.session.rollback()
            return error_response(type_or_error, 400)
        
        # Validate account name
        account_name = data.get('account_name') or data.get('name')
        is_valid, name_or_error = validate_account_name(account_name)
        if not is_valid:
            db.session.rollback()
            return error_response(name_or_error, 400)
        
        # Validate initial balance
        initial_balance = data.get('initial_balance') or data.get('balance', 0.0)
        is_valid, balance_or_error = validate_initial_balance(initial_balance)
        if not is_valid:
            db.session.rollback()
            return error_response(balance_or_error, 400)
        
        # Check account limit
        account_count = Account.query.filter_by(user_id=user_id, is_active=True).count()
        if account_count >= MAX_ACCOUNTS:
            db.session.rollback()
            return error_response(f'Maximum of {MAX_ACCOUNTS} accounts allowed per user', 400)
        
        # Generate and validate unique account number
        max_attempts = 3
        for attempt in range(max_attempts):
            timestamp = int(datetime.utcnow().timestamp() * 1000)
            unique_suffix = str(timestamp)[-8:]
            account_prefix = "ACC" + str(user_id)[-3:].zfill(3)
            account_number = f"{account_prefix}{unique_suffix}"
            
            if not check_duplicate_account_number(account_number):
                break
            if attempt == max_attempts - 1:
                db.session.rollback()
                return error_response('Failed to generate unique account number. Please try again.', 500)
        
        # Create new account
        new_account = Account(
            account_number=account_number,
            account_type=type_or_error,
            account_name=name_or_error,
            description=data.get('description'),
            balance=balance_or_error,
            user_id=user_id
        )
        
        db.session.add(new_account)
        db.session.commit()
        
        account_dict = new_account.to_dict()
        account_dict['balance'] = float(new_account.balance)
        
        return jsonify({
            'message': 'Account created successfully',
            'account': account_dict
        }), 201
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return error_response(f"Failed to create account: {str(e)}", 500)

@bp.route('/<int:account_id>', methods=['PUT'])
@jwt_required(fresh=True)
def update_account(account_id):
    """Update account details"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    try:
        # Start transaction
        db.session.begin_nested()
        
        # Get account with row lock
        account = Account.query.filter(
            Account.id == account_id,
            Account.user_id == user_id,
            Account.is_active == True
        ).with_for_update().first()
        
        if not account:
            db.session.rollback()
            return error_response('Account not found or access denied', 404)
        
        # Validate and update account name
        if 'account_label' in data:
            is_valid, name_or_error = validate_account_name(data['account_label'])
            if not is_valid:
                db.session.rollback()
                return error_response(name_or_error, 400)
            account.account_name = name_or_error
        
        # Update description
        if 'description' in data:
            account.description = data['description']
        
        # Check for special characters in description that might indicate SQL injection
        if data.get('description') and any(char in data['description'] for char in [';', '--', '/*', '*/']):
            db.session.rollback()
            return error_response('Invalid characters in description', 400)
        
        db.session.commit()
        
        account_dict = account.to_dict()
        account_dict['balance'] = float(account.balance)
        
        return jsonify({
            'message': 'Account updated successfully',
            'account_detail': account_dict
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return error_response(f"Failed to update account: {str(e)}", 500)

@bp.route('/<int:account_id>', methods=['DELETE'])
@jwt_required(fresh=True)
def delete_account(account_id):
    """Delete (soft delete) an account"""
    user_id = int(get_jwt_identity())
    
    try:
        # Start transaction
        db.session.begin_nested()
        
        # Get account with row lock
        account = Account.query.filter(
            Account.id == account_id,
            Account.user_id == user_id,
            Account.is_active == True
        ).with_for_update().first()
        
        if not account:
            db.session.rollback()
            return error_response('Account not found or access denied', 404)
        
        # Check if account has any pending transactions
        pending_transactions = Transaction.query.filter(
            or_(
                Transaction.from_account_id == account_id,
                Transaction.to_account_id == account_id
            ),
            Transaction.timestamp > datetime.utcnow() - timedelta(days=1)
        ).first()
        
        if pending_transactions:
            db.session.rollback()
            return error_response('Cannot delete account with pending transactions', 400)
        
        # Soft delete the account
        account.is_active = False
        db.session.commit()
        
        return jsonify({
            'message': 'Account deleted successfully'
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return error_response(f"Failed to delete account: {str(e)}", 500)

@bp.route('/<int:account_id>/transactions', methods=['GET'])
@jwt_required()
def get_account_transactions(account_id):
    """Get transactions for a specific account"""
    user_id = int(get_jwt_identity())
    
    try:
        # Verify account ownership
        account = Account.query.filter(
            Account.id == account_id,
            Account.user_id == user_id,
            Account.is_active == True
        ).first()
        
        if not account:
            return error_response('Account not found or access denied', 404)
        
        # Build query
        query = Transaction.query.filter(
            or_(
                Transaction.from_account_id == account_id,
                Transaction.to_account_id == account_id
            )
        )
        
        # Apply filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(Transaction.timestamp >= start_date)
            except ValueError:
                return error_response('Invalid start_date format. Use YYYY-MM-DD', 400)
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59)
                query = query.filter(Transaction.timestamp <= end_date)
            except ValueError:
                return error_response('Invalid end_date format. Use YYYY-MM-DD', 400)
        
        tx_type = request.args.get('type')
        if tx_type:
            if tx_type == 'deposit':
                query = query.filter(
                    Transaction.transaction_type == 'deposit',
                    Transaction.to_account_id == account_id
                )
            elif tx_type == 'withdrawal':
                query = query.filter(
                    Transaction.transaction_type == 'withdrawal',
                    Transaction.from_account_id == account_id
                )
            elif tx_type == 'transfer':
                query = query.filter(Transaction.transaction_type == 'transfer')
        
        search = request.args.get('search')
        if search:
            search_term = f'%{search}%'
            query = query.filter(Transaction.description.ilike(search_term))
        
        # Apply pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        if page < 1 or per_page < 1 or per_page > 100:
            return error_response('Invalid pagination parameters. Page and per_page must be positive, and per_page cannot exceed 100', 400)
        
        paginated_transactions = query.order_by(Transaction.timestamp.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        transactions = [tx.to_dict() for tx in paginated_transactions.items]
        
        return jsonify({
            'transactions': transactions,
            'page': page,
            'per_page': per_page,
            'total': paginated_transactions.total
        })
        
    except SQLAlchemyError as e:
        return error_response(f"Failed to retrieve transactions: {str(e)}", 500)