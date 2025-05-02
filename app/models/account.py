from app import db
from datetime import datetime

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    account_type = db.Column(db.String(20), nullable=False)  # savings, checking, etc.
    account_name = db.Column(db.String(100), nullable=True)  # Optional name for the account
    description = db.Column(db.String(200), nullable=True)  # Optional description
    balance = db.Column(db.Float, nullable=False, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, nullable=False, default=True)  # For soft delete
    transactions_from = db.relationship('Transaction', 
                                      foreign_keys='Transaction.from_account_id',
                                      backref='from_account', 
                                      lazy=True)
    transactions_to = db.relationship('Transaction', 
                                    foreign_keys='Transaction.to_account_id',
                                    backref='to_account', 
                                    lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'account_number': self.account_number,
            'account_type': self.account_type,
            'account_name': self.account_name,
            'description': self.description,
            'balance': self.balance,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        } 