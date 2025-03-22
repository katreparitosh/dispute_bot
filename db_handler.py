import pandas as pd
from datetime import datetime
import uuid

class DatabaseHandler:
    def __init__(self):
        self.transactions_file = 'transactions.csv'
        self.disputes_file = 'disputes.csv'
        
    def get_transaction(self, transaction_id):
        """Get transaction details by transaction_id"""
        try:
            df = pd.read_csv(self.transactions_file)
            transaction = df[df['transaction_id'] == transaction_id]
            
            if transaction.empty:
                return None
                
            return transaction.iloc[0].to_dict()
        except Exception as e:
            print(f"Error reading transaction: {str(e)}")
            return None
            
    def get_all_transactions(self):
        """Get all transactions with merchant and amount"""
        try:
            df = pd.read_csv(self.transactions_file)
            transactions = df[['transaction_id', 'merchant_seller', 'amount', 'date']].to_dict('records')
            return transactions
        except Exception as e:
            print(f"Error reading transactions: {str(e)}")
            return []

    def validate_dispute_reason(self, dispute_type, details):
        """Validate dispute reason and its required details"""
        valid_types = {
            'INR': ['expected_delivery_date', 'contacted_seller'],
            'SNAD': ['item_condition', 'contacted_seller'],
            'UNAUTH': ['recognizes_merchant', 'contacted_bank']
        }
        
        if dispute_type not in valid_types:
            return False, "Invalid dispute type. Must be INR, SNAD, or UNAUTH."
            
        required_fields = valid_types[dispute_type]
        missing_fields = [field for field in required_fields if field not in details]
        
        if missing_fields:
            return False, f"Missing required information: {', '.join(missing_fields)}"
            
        return True, "Valid dispute details"

    def create_dispute(self, transaction_id, dispute_type, details):
        """Create a new dispute record with specific reason requirements"""
        try:
            # First verify the transaction
            transaction = self.get_transaction(transaction_id)
            if not transaction:
                return None, "Transaction not found"
                
            # Validate dispute type and details
            is_valid, message = self.validate_dispute_reason(dispute_type, details)
            if not is_valid:
                return None, message

            # Generate dispute ID
            dispute_id = f"DSP{str(uuid.uuid4())[:8]}"
            
            # Read existing disputes
            try:
                disputes_df = pd.read_csv(self.disputes_file)
            except:
                disputes_df = pd.DataFrame(columns=[
                    'dispute_id', 'transaction_id', 
                    'type', 'status', 'creation_date', 'description',
                    'details', 'merchant', 'amount'
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
                'transaction_id': transaction_id,
                'type': dispute_type,
                'status': 'open',
                'creation_date': datetime.now().strftime('%Y-%m-%d'),
                'details': details,  # Store all the reason-specific details
                'description': details.get('description', ''),
                'merchant': transaction['merchant_seller'],  # Add merchant from transaction
                'amount': transaction['amount']  # Add amount from transaction
            }
            
            # Append new dispute
            disputes_df = pd.concat([disputes_df, pd.DataFrame([new_dispute])], ignore_index=True)
            disputes_df.to_csv(self.disputes_file, index=False)
            
            return new_dispute, "Dispute created successfully"
        except Exception as e:
            print(f"Error creating dispute: {str(e)}")
            return None, f"Error creating dispute: {str(e)}"



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
                
            dispute_data = dispute.iloc[0].to_dict()
            
            # Get back office case details
            bo_case = self.get_back_office_case(dispute_data['dispute_id'], dispute_data['transaction_id'])
            if bo_case:
                dispute_data.update(bo_case)
                
            return dispute_data
        except Exception as e:
            print(f"Error getting dispute status: {str(e)}")
            return None
            
    def get_back_office_case(self, dispute_id=None, transaction_id=None):
        """Get back office case details by dispute_id or transaction_id"""
        try:
            df = pd.read_csv('back_office_cases.csv')
            if dispute_id:
                case = df[df['dispute_id'] == dispute_id]
            elif transaction_id:
                case = df[df['transaction_id'] == transaction_id]
            else:
                return None
                
            if case.empty:
                return None
                
            return case.iloc[0].to_dict()
        except Exception as e:
            print(f"Error getting back office case: {str(e)}")
            return None
            
    def get_all_disputes(self):
        """Get all disputes with merchant, amount, and type"""
        try:
            df = pd.read_csv(self.disputes_file)
            if df.empty:
                return []
            # Skip the comment row if present
            df = df[~df['dispute_id'].str.startswith('#', na=False)]
            disputes = df[['dispute_id', 'merchant', 'amount', 'type', 'status']].to_dict('records')
            return disputes
        except Exception as e:
            print(f"Error reading disputes: {str(e)}")
            return []
