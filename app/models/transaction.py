from app import db
from datetime import datetime

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal, transfer
    amount = db.Column(db.Float, nullable=False)
    from_account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=True)
    to_account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    description = db.Column(db.String(200), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'from_account_id': self.from_account_id,
            'to_account_id': self.to_account_id,
            'timestamp': self.timestamp.isoformat(),
            'description': self.description
        } 