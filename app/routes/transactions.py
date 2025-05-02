from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.account import Account
from app.models.transaction import Transaction
from app.utils.validators import validate_amount, error_response

bp = Blueprint('transactions', __name__, url_prefix='/api/transactions')

@bp.route('', methods=['GET'])
@jwt_required()
def get_transactions():
    """Get transaction history for user accounts"""
    user_id = int(get_jwt_identity())
    
    # Get all user's accounts
    accounts = Account.query.filter_by(user_id=user_id).all()
    
    if not accounts:
        return jsonify({'transactions': []})
    
    account_ids = [account.id for account in accounts]
    
    # Get all transactions where user's accounts are involved
    transactions = Transaction.query.filter(
        (Transaction.from_account_id.in_(account_ids)) | 
        (Transaction.to_account_id.in_(account_ids))
    ).order_by(Transaction.timestamp.desc()).all()
    
    return jsonify({
        'transactions': [transaction.to_dict() for transaction in transactions]
    })

@bp.route('/deposit', methods=['POST'])
@jwt_required(fresh=True)
def deposit():
    """Deposit funds to an account"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    # Validate required fields
    if not all(k in data for k in ('account_id', 'amount')):
        return error_response('Account ID and amount are required')
    
    # Validate amount
    if not validate_amount(data['amount']):
        return error_response('Amount must be a positive number')
    
    amount = float(data['amount'])
    
    # Get the account
    account = Account.query.filter_by(id=data['account_id'], user_id=user_id).first()
    
    if not account:
        return error_response('Account not found or does not belong to you', 404)
    
    # Update account balance
    account.balance += amount
    
    # Create transaction record
    transaction = Transaction(
        transaction_type='deposit',
        amount=amount,
        to_account_id=account.id,
        description=data.get('description', 'Deposit')
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Deposit successful',
        'transaction': transaction.to_dict(),
        'new_balance': account.balance
    })

@bp.route('/withdraw', methods=['POST'])
@jwt_required(fresh=True)
def withdraw():
    """Withdraw funds from an account"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    # Validate required fields
    if not all(k in data for k in ('account_id', 'amount')):
        return error_response('Account ID and amount are required')
    
    # Validate amount
    if not validate_amount(data['amount']):
        return error_response('Amount must be a positive number')
    
    amount = float(data['amount'])
    
    # Get the account
    account = Account.query.filter_by(id=data['account_id'], user_id=user_id).first()
    
    if not account:
        return error_response('Account not found or does not belong to you', 404)
    
    # Check sufficient balance
    if account.balance < amount:
        return error_response('Insufficient funds')
    
    # Update account balance
    account.balance -= amount
    
    # Create transaction record
    transaction = Transaction(
        transaction_type='withdrawal',
        amount=amount,
        from_account_id=account.id,
        description=data.get('description', 'Withdrawal')
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Withdrawal successful',
        'transaction': transaction.to_dict(),
        'new_balance': account.balance
    })

@bp.route('/transfer', methods=['POST'])
@jwt_required(fresh=True)
def transfer():
    """Transfer funds between accounts"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    # Validate required fields
    if not all(k in data for k in ('from_account_id', 'to_account_id', 'amount')):
        return error_response('From account ID, to account ID, and amount are required')
    
    # Validate amount
    if not validate_amount(data['amount']):
        return error_response('Amount must be a positive number')
    
    amount = float(data['amount'])
    
    # Check if accounts are different
    if data['from_account_id'] == data['to_account_id']:
        return error_response('Cannot transfer to the same account')
    
    # Get the from account and verify ownership
    from_account = Account.query.filter_by(id=data['from_account_id'], user_id=user_id).first()
    
    if not from_account:
        return error_response('Source account not found or does not belong to you', 404)
    
    # Check sufficient balance
    if from_account.balance < amount:
        return error_response('Insufficient funds')
    
    # Get the to account (doesn't have to belong to the user)
    to_account = Account.query.get(data['to_account_id'])
    
    if not to_account:
        return error_response('Destination account not found', 404)
    
    # Update account balances
    from_account.balance -= amount
    to_account.balance += amount
    
    # Create transaction record
    transaction = Transaction(
        transaction_type='transfer',
        amount=amount,
        from_account_id=from_account.id,
        to_account_id=to_account.id,
        description=data.get('description', f'Transfer from {from_account.account_number} to {to_account.account_number}')
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Transfer successful',
        'transaction': transaction.to_dict(),
        'from_account_balance': from_account.balance,
        'to_account_balance': to_account.balance
    })

@bp.route('/transfer-advanced', methods=['POST'])
@jwt_required()
def transfer_advanced():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    # Validate required fields
    if not all(k in data for k in ('from_account_id', 'to_account_id', 'amount')):
        return error_response('From account ID, to account ID, and amount are required')
    
    # Validate amount
    if not validate_amount(data['amount']):
        return error_response('Amount must be a positive number')
    
    amount = float(data['amount'])
    
    # Get the accounts
    from_account = Account.query.filter_by(id=data['from_account_id'], user_id=user_id).first()
    to_account = Account.query.get(data['to_account_id'])
    
    if not from_account:
        return error_response('Source account not found or does not belong to you', 404)
    
    if not to_account:
        return error_response('Destination account not found', 404)
    
    # Check sufficient balance
    if from_account.balance < amount:
        return error_response('Insufficient funds')
    
    # Update balances
    from_account.balance -= amount
    to_account.balance += amount
    
    try:
        # Create transaction record
        transaction = Transaction(
            transaction_type='transfer',
            amount=amount,
            from_account_id=from_account.id,
            to_account_id=to_account.id,
            description=data.get('description', f'Transfer from {from_account.account_number} to {to_account.account_number}')
        )
        
        db.session.add(transaction)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return error_response(f"Transfer failed: {str(e)}", 500)
    
    return jsonify({
        'message': 'Transfer successful',
        'transaction': transaction.to_dict(),
        'from_account_balance': from_account.balance,
        'to_account_balance': to_account.balance
    })

# Add new endpoint for account-specific transactions
@bp.route('/accounts/<int:account_id>/transactions', methods=['POST', 'GET'])
@jwt_required(fresh=True)
def account_transactions(account_id):
    """Handle transactions for a specific account"""
    user_id = int(get_jwt_identity())
    
    # Verify account ownership
    account = Account.query.filter_by(id=account_id, user_id=user_id).first()
    if not account:
        return error_response('Account not found or does not belong to you', 404)
    
    if request.method == 'GET':
        # Get transactions for this account
        transactions = Transaction.query.filter(
            (Transaction.from_account_id == account_id) | 
            (Transaction.to_account_id == account_id)
        ).order_by(Transaction.timestamp.desc()).all()
        
        return jsonify({
            'transactions': [transaction.to_dict() for transaction in transactions]
        })
    
    # For POST requests - create new transaction
    data = request.get_json()
    
    # Validate required fields
    if not all(k in data for k in ('type', 'amount')):
        return error_response('Transaction type and amount are required')
    
    # Validate amount - must be positive
    try:
        amount = float(data['amount'])
        if amount <= 0:
            return error_response('Amount must be a positive number', 400)
    except (ValueError, TypeError):
        return error_response('Amount must be a valid number', 400)
    
    # Process based on transaction type
    transaction_type = data['type'].lower()
    
    if transaction_type == 'deposit':
        # Update account balance
        account.balance += amount
        
        # Create transaction record
        transaction = Transaction(
            transaction_type='deposit',
            amount=amount,
            to_account_id=account_id,
            description=data.get('description', 'Deposit')
        )
        
    elif transaction_type == 'withdrawal':
        # Check sufficient balance
        if account.balance < amount:
            return error_response('Insufficient funds', 400)
        
        # Update account balance
        account.balance -= amount
        
        # Create transaction record
        transaction = Transaction(
            transaction_type='withdrawal',
            amount=amount,
            from_account_id=account_id,
            description=data.get('description', 'Withdrawal')
        )
        
    elif transaction_type == 'transfer':
        # Transfer requires destination account
        if 'to_account_id' not in data:
            return error_response('Destination account ID is required for transfers', 400)
        
        # Check sufficient balance
        if account.balance < amount:
            return error_response('Insufficient funds', 400)
        
        # Get destination account
        to_account_id = data['to_account_id']
        to_account = Account.query.get(to_account_id)
        
        if not to_account:
            return error_response('Destination account not found', 404)
        
        # Update account balances
        account.balance -= amount
        to_account.balance += amount
        
        # Create transaction record
        transaction = Transaction(
            transaction_type='transfer',
            amount=amount,
            from_account_id=account_id,
            to_account_id=to_account_id,
            description=data.get('description', f'Transfer to {to_account.account_number}')
        )
    else:
        return error_response('Invalid transaction type. Must be deposit, withdrawal, or transfer', 400)
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'message': f'{transaction_type.capitalize()} successful',
        'transaction': transaction.to_dict(),
        'new_balance': account.balance,
        'id': transaction.id  # Include id for tests
    }), 201 