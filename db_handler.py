import pandas as pd
from datetime import datetime
import uuid

class DatabaseHandler:
    def __init__(self):
        self.transactions_file = 'transactions.csv'
        self.disputes_file = 'disputes.csv'
        
    def get_user_transactions(self, user_id):
        """Get all transactions for a specific user"""
        try:
            df = pd.read_csv(self.transactions_file)
            user_transactions = df[df['user_id'] == user_id].to_dict('records')
            return user_transactions
        except Exception as e:
            print(f"Error reading transactions: {str(e)}")
            return []

    def verify_transaction(self, transaction_id, user_id=None):
        """Verify if a transaction exists and optionally belongs to the user"""
        try:
            df = pd.read_csv(self.transactions_file)
            transaction = df[df['transaction_id'] == transaction_id]
            
            if transaction.empty:
                return None
                
            if user_id and transaction.iloc[0]['user_id'] != user_id:
                return None
                
            return transaction.iloc[0].to_dict()
        except Exception as e:
            print(f"Error verifying transaction: {str(e)}")
            return None

    def create_dispute(self, user_id, transaction_id, dispute_type, description):
        """Create a new dispute record"""
        try:
            # First verify the transaction
            transaction = self.verify_transaction(transaction_id, user_id)
            if not transaction:
                return None, "Transaction not found or doesn't belong to user"

            # Generate dispute ID
            dispute_id = f"DSP{str(uuid.uuid4())[:8]}"
            
            # Read existing disputes
            try:
                disputes_df = pd.read_csv(self.disputes_file)
            except:
                disputes_df = pd.DataFrame(columns=[
                    'dispute_id', 'user_id', 'transaction_id', 
                    'type', 'status', 'creation_date', 'description'
                ])

            # Check if dispute already exists
            if not disputes_df.empty and len(disputes_df[
                (disputes_df['transaction_id'] == transaction_id) & 
                (disputes_df['status'] != 'closed')
            ]) > 0:
                return None, "Active dispute already exists for this transaction"

            # Create new dispute record
            new_dispute = {
                'dispute_id': dispute_id,
                'user_id': user_id,
                'transaction_id': transaction_id,
                'type': dispute_type,
                'status': 'open',
                'creation_date': datetime.now().strftime('%Y-%m-%d'),
                'description': description
            }
            
            # Append new dispute
            disputes_df = pd.concat([disputes_df, pd.DataFrame([new_dispute])], ignore_index=True)
            disputes_df.to_csv(self.disputes_file, index=False)
            
            return new_dispute, "Dispute created successfully"
        except Exception as e:
            print(f"Error creating dispute: {str(e)}")
            return None, f"Error creating dispute: {str(e)}"

    def get_user_disputes(self, user_id):
        """Get all disputes for a given user ID"""
        try:
            df = pd.read_csv(self.disputes_file)
            user_disputes = df[df['user_id'] == user_id]
            
            if user_disputes.empty:
                return None, "No disputes found for this user ID"
            
            return user_disputes.to_dict('records'), "Success"
        except Exception as e:
            print(f"Error retrieving disputes: {str(e)}")
            return None, f"Error retrieving disputes: {str(e)}"

    def get_dispute_status(self, dispute_id=None, transaction_id=None):
        """Get status of a dispute by dispute_id or transaction_id"""
        try:
            df = pd.read_csv(self.disputes_file)
            if dispute_id:
                dispute = df[df['dispute_id'] == dispute_id]
            elif transaction_id:
                dispute = df[df['transaction_id'] == transaction_id]
            else:
                return None
                
            if dispute.empty:
                return None
                
            return dispute.iloc[0].to_dict()
        except Exception as e:
            print(f"Error getting dispute status: {str(e)}")
            return None
