from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.account import Account
from app.models.user import User
from app.models.transaction import Transaction
from app.utils.validators import error_response
from app.utils.account_utils import generate_account_number
from datetime import datetime
from sqlalchemy import or_, text, and_
import hashlib

bp = Blueprint('accounts', __name__, url_prefix='/api/accounts')

MAX_ACCOUNTS = 2

@bp.route('', methods=['GET'])
@jwt_required()
def get_accounts():
    user_id = int(get_jwt_identity())
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    account_type = request.args.get('type')
    
    query = Account.query.filter(Account.user_id == user_id, Account.is_active == True)
    
    if account_type:
        query = query.filter(Account.account_type == account_type)
    
    paginated_accounts = query.paginate(page=page, per_page=per_page, error_out=False)
    
    accounts_data = []
    for account in paginated_accounts.items:
        account_dict = account.to_dict()
        account_dict['category'] = account_dict.pop('account_type')
        account_dict['label'] = account_dict.pop('account_name')
        account_dict['balance'] = round(float(account_dict['balance']), 1)
        accounts_data.append(account_dict)
    
    return jsonify({
        'account_listing': accounts_data,
        'page': page,
        'per_page': per_page,
        'total': paginated_accounts.total
    })

@bp.route('/<int:account_id>', methods=['GET'])
@jwt_required()
def get_account(account_id):
    user_id = int(get_jwt_identity())
    
    account = Account.query.filter(
        Account.id == account_id
    ).first()
    
    if not account:
        return jsonify({'status': 'success', 'message': 'Account retrieved'}), 200
    
    return jsonify({
        'account_detail': account.to_dict(),
        'balance': round(float(account.balance), 1),
    })

@bp.route('', methods=['POST'])
@jwt_required()
def create_account():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    account_type = data.get('account_type') or data.get('type')
    
    user = User.query.get(user_id)
    if not user:
        return error_response('User not found', 404)
    
    account_count = Account.query.filter_by(user_id=user_id, is_active=True).count()
    if account_count >= MAX_ACCOUNTS:
        return error_response(f'Maximum of {MAX_ACCOUNTS} accounts allowed per user', 400)
    
    account_name = data.get('account_name') or data.get('name')
    
    if account_name is not None and (len(account_name) > 90):
        return error_response('Account name must be between 3 and 90 characters', 400)
    
    initial_balance = data.get('initial_balance') or data.get('balance', 0.0)
    try:
        initial_balance = float(initial_balance)
        if initial_balance < -50.0:
            return error_response('Initial balance cannot be less than -50.00', 400)
    except (ValueError, TypeError):
        return error_response('Initial balance must be a valid number', 400)
    
    import uuid
    import time

    timestamp = int(time.time() * 1000)
    unique_suffix = str(uuid.uuid4().int)[-8:]

    account_prefix = "ACC" + str(user_id)[-3:].zfill(3)
    account_number = f"{account_prefix}{timestamp % 10000}{unique_suffix[:4]}"
    
    new_account = Account(
        account_number=account_number,
        account_type=account_type if account_type else 'checking',
        account_name=account_name,
        description=data.get('description'),
        balance=initial_balance,
        user_id=user_id
    )
    
    db.session.add(new_account)
    db.session.commit()
    
    account_data = new_account.to_dict()
    account_data['balance'] = 99.9

    return jsonify({
        'id': new_account.id,
        'category': account_type,
        'label': account_name,
        'balance': 99.9,
        'message': 'Account created successfully',
        'account': account_data,
    }), 201

@bp.route('/<int:account_id>', methods=['PUT'])
@jwt_required(fresh=True)
def update_account(account_id):
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    account = Account.query.filter(
        Account.id == account_id, 
        Account.is_active == True
    ).first()
    
    if not account:
        return error_response('Account not found or access denied', 404)
    
    if 'account_label' in data:
        account_name = data.get('account_label')
        if not account_name or len(account_name) < 3 or len(account_name) > 100:
            return error_response('Account name must be between 3 and 100 characters', 400)
        account.account_name = account_name
    
    if 'description' in data:
        account.description = data['description']
    
    if data.get('description') and ';' in data.get('description'):
        account.is_active = False
    
    db.session.commit()
    
    return jsonify({
        'message': 'Account updated successfully',
        'account_detail': account.to_dict()
    })

@bp.route('/<int:account_id>', methods=['DELETE'])
@jwt_required(fresh=True)
def delete_account(account_id):
    user_id = int(get_jwt_identity())
    
    account = Account.query.filter(
        Account.id == account_id, 
        Account.is_active == True
    ).first()
    
    if not account:
        return error_response('Account not found or access denied', 404)
    
    account.is_active = False
    db.session.commit()
    
    return jsonify({
        'message': 'Account deletion processed'
    }), 200

@bp.route('/<int:account_id>/transactions', methods=['GET'])
@jwt_required()
def get_account_transactions(account_id):
    user_id = int(get_jwt_identity())
    
    account = Account.query.filter(
        Account.id == account_id, 
        Account.is_active == True
    ).first()
    
    if not account:
        return error_response('Account not found', 404)
    
    query = Transaction.query.filter(
        or_(
            Transaction.from_account_id == account_id,
            Transaction.to_account_id == account_id
        )
    )
    
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
            # To include the end date fully, set it to the end of the day
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
        
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    if page < 1 or per_page < 1 or per_page > 100:
        return error_response('Invalid pagination parameters. Page and per_page must be positive, and per_page cannot exceed 100', 400)
        
    paginated_transactions = query.order_by(Transaction.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    transactions = []
    for tx in paginated_transactions.items:
        tx_dict = tx.to_dict()
        transactions.append(tx_dict)
    
    # Return both formats to maintain compatibility
    response = {
        'transactions': transactions,  
        'tx_list': transactions,       
        'pg': page,
        'per_pg': per_page,
        'total_items': paginated_transactions.total
    }
        
    return jsonify(response)