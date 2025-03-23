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

    def create_dispute(self, transaction_id, merchant, amount, issue_type, dispute_reason):
        """Create a new dispute record with the given details"""
        try:
            print(f"Creating dispute with: transaction_id={transaction_id}, merchant={merchant}, amount={amount}, type={issue_type}, reason={dispute_reason}")
            
            # Generate dispute ID
            dispute_id = f"DSP{str(uuid.uuid4())[:8]}"
            print(f"Generated dispute_id: {dispute_id}")
            
            # Read existing disputes
            try:
                disputes_df = pd.read_csv(self.disputes_file)
                print(f"Read existing disputes file with {len(disputes_df)} rows")
            except Exception as e:
                print(f"Creating new disputes DataFrame due to: {str(e)}")
                disputes_df = pd.DataFrame(columns=[
                    'dispute_id', 'transaction_id', 
                    'type', 'status', 'creation_date',
                    'dispute_reason', 'merchant', 'amount'
                ])

            # Check if dispute already exists
            if not disputes_df.empty and len(disputes_df[
                (disputes_df['transaction_id'] == transaction_id) & 
                (disputes_df['status'] != 'closed')
            ]) > 0:
                print(f"Found existing active dispute for transaction {transaction_id}")
                return None

            # Create new dispute record
            new_dispute = {
                'dispute_id': dispute_id,
                'transaction_id': transaction_id,
                'type': issue_type,
                'status': 'open',
                'creation_date': datetime.now().strftime('%Y-%m-%d'),
                'dispute_reason': dispute_reason,
                'merchant': merchant,
                'amount': amount
            }
            print(f"Created new dispute record: {new_dispute}")
            
            # Append new dispute
            disputes_df = pd.concat([disputes_df, pd.DataFrame([new_dispute])], ignore_index=True)
            print(f"Appended new dispute to DataFrame, now has {len(disputes_df)} rows")
            
            # Save to file
            disputes_df.to_csv(self.disputes_file, index=False)
            print(f"Saved disputes to file {self.disputes_file}")
            
            return dispute_id
        except Exception as e:
            print(f"Error creating dispute: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None



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

    def add_dispute(self, dispute_data):
        """Add a new dispute with the provided data
        
        Args:
            dispute_data (dict): Dictionary containing dispute information:
                - dispute_id
                - transaction_id
                - merchant
                - amount
                - dispute_type
                - dispute_reason
                - status
                - date_created
        
        Returns:
            bool: True if added successfully, False otherwise
        """
        try:
            # Read existing disputes
            try:
                disputes_df = pd.read_csv(self.disputes_file)
            except Exception as e:
                print(f"Creating new disputes DataFrame: {str(e)}")
                disputes_df = pd.DataFrame(columns=[
                    'dispute_id', 'transaction_id', 
                    'type', 'status', 'creation_date',
                    'dispute_reason', 'merchant', 'amount'
                ])

            # Map the incoming data to match our columns
            new_dispute = {
                'dispute_id': dispute_data['dispute_id'],
                'transaction_id': dispute_data['transaction_id'],
                'type': dispute_data['dispute_type'],
                'status': dispute_data['status'],
                'creation_date': dispute_data['date_created'],
                'dispute_reason': dispute_data['dispute_reason'],
                'merchant': dispute_data['merchant'],
                'amount': dispute_data['amount']
            }
            
            # Append new dispute
            disputes_df = pd.concat([disputes_df, pd.DataFrame([new_dispute])], ignore_index=True)
            
            # Save to file
            disputes_df.to_csv(self.disputes_file, index=False)
            print(f"Added dispute {dispute_data['dispute_id']} to database")
            return True
            
        except Exception as e:
            print(f"Error adding dispute: {str(e)}")
            return False
