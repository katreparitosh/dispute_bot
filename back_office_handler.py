import pandas as pd
from datetime import datetime

class BackOfficeHandler:
    def __init__(self):
        self.cases_file = 'back_office_cases.csv'
        self.model_stages = [
            'bp_eligibility_model',
            'fraud_buyer',
            'fraud_seller',
            'fraud_dispute_collusion',
            'adjudication_case_outcome_model',
            'payout_sensitivity_model'
        ]
        
    def update_case_entry(self, dispute_id, transaction_id):
        """Update or create a case entry in back_office_cases.csv"""
        try:
            print(f"Updating case entry for transaction_id={transaction_id} with dispute_id={dispute_id}")
            df = pd.read_csv(self.cases_file)
            
            # Find the row with matching transaction_id
            mask = df['transaction_id'] == transaction_id
            print(f"Found {mask.sum()} matching rows for transaction_id={transaction_id}")
            
            if mask.any():
                # Update the dispute_id for this transaction
                df.loc[mask, 'dispute_id'] = dispute_id
                print(f"Updated dispute_id to {dispute_id}")
                # Save without adding new row
                df.to_csv(self.cases_file, index=False)
                print("Saved changes to file")
                return
                
            # Only create new entry if transaction_id doesn't exist
            print("No existing entry found, creating new one")
            new_case = {
                'dispute_id': dispute_id,
                'transaction_id': transaction_id,
                'fraud_buyer': 0.15,
                'fraud_seller': 0.15,
                'bp_eligibility_model': 'eligible',
                'fraud_dispute_collusion': 0.15,
                'adjudication_case_outcome_model': 0.92,
                'payout_sensitivity_model': 149.99
            }
            df = pd.concat([df, pd.DataFrame([new_case])], ignore_index=True)
            df.to_csv(self.cases_file, index=False)
            print("Created and saved new entry")
            
        except Exception as e:
            print(f"Error updating case entry: {str(e)}")
    
    def check_bo_models(self, dispute_id):
        """Check back office models for dispute resolution status
        
        Returns one of three statuses:
        1. Instant Payout - If buyer fraud score < 0.2, seller fraud score > 0.7, collusion score < 0.2, adjudication > 0.8
        2. Wait for Seller Response - If eligible, but not meeting instant payout criteria
        3. Decline - If not eligible or buyer fraud score > 0.7
        """
        # Get case data
        case_dict = self.get_case_data(dispute_id)
        
        if not case_dict:
            return {
                'status': 'error',
                'progress': 0,
                'message': 'Case not found',
                'instant_payout': False
            }
        
        # Convert values to float where needed
        try:
            buyer_fraud = float(case_dict['fraud_buyer']) if pd.notna(case_dict['fraud_buyer']) else None
            seller_fraud = float(case_dict['fraud_seller']) if pd.notna(case_dict['fraud_seller']) else None
            dispute_collusion = float(case_dict['fraud_dispute_collusion']) if pd.notna(case_dict['fraud_dispute_collusion']) else None
            adjudication_outcome = float(case_dict['adjudication_case_outcome_model']) if pd.notna(case_dict['adjudication_case_outcome_model']) else None
            bp_eligibility = str(case_dict['bp_eligibility_model']).lower() if pd.notna(case_dict['bp_eligibility_model']) else None
            payout_amount = float(case_dict['payout_sensitivity_model']) if pd.notna(case_dict['payout_sensitivity_model']) else 0.0
        except (ValueError, TypeError) as e:
            print(f"Error converting case data: {str(e)}")
            # Set defaults
            buyer_fraud = 0.5
            seller_fraud = 0.5
            dispute_collusion = 0.5
            adjudication_outcome = 0.5
            bp_eligibility = 'eligible'
            payout_amount = 0.0
        
        # Determine the case status based on model outputs
        status_type = None
        message = None
        progress = 0
        
        # Case 1: Ineligible / Declined
        if bp_eligibility != 'eligible' or (buyer_fraud is not None and buyer_fraud > 0.7):
            status_type = 'decline'
            message = "We regret to inform you that your dispute has been declined as it does not meet our eligibility criteria."
            progress = 100
        
        # Case 2: Instant Payout
        elif (buyer_fraud is not None and buyer_fraud < 0.2 and
              seller_fraud is not None and seller_fraud > 0.7 and
              dispute_collusion is not None and dispute_collusion < 0.2 and
              adjudication_outcome is not None and adjudication_outcome > 0.8):
            status_type = 'instant_payout'
            message = f"Good news! Your dispute has been approved for instant refund. You will receive ${payout_amount:.2f} in your account within 24 hours."
            progress = 100
        
        # Case 3: Wait for Seller Response
        else:
            status_type = 'wait_for_seller'
            message = "Your dispute is being processed. We have contacted the seller for more information and will update you on any progress."
            progress = 50
            
        # Create case object for frontend display
        case = {
            'transaction_id': case_dict['transaction_id'],
            'dispute_id': case_dict['dispute_id'],
            'buyer_fraud_score': buyer_fraud,
            'seller_fraud_score': seller_fraud,
            'bp_eligibility': bp_eligibility,
            'dispute_collusion_score': dispute_collusion,
            'adjudication_outcome_score': adjudication_outcome,
            'payout_amount': payout_amount,
            'status_type': status_type
        }
            
        return {
            'status': 'success',
            'progress': progress,
            'message': message,
            'instant_payout': status_type == 'instant_payout',
            'amount': payout_amount,
            'case': case
        }
    
    def get_case_status(self, dispute_id=None, transaction_id=None):
        """Get case status and outcome based on fraud checks"""
        try:
            df = pd.read_csv(self.cases_file)
            
            # Find the case
            if dispute_id:
                case = df[df['dispute_id'] == dispute_id]
            elif transaction_id:
                case = df[df['transaction_id'] == transaction_id]
            else:
                return None, "Invalid case lookup parameters"
                
            if case.empty:
                return None, "Case not found"
                
            case_dict = case.iloc[0].to_dict()
            # Convert bp_eligibility_model to string
            case_dict['bp_eligibility_model'] = str(case_dict['bp_eligibility_model'])
            
            # Handle ineligible cases first
            if case_dict['bp_eligibility_model'] == 'ineligible':
                case_dict['fraud_buyer'] = None
                case_dict['fraud_seller'] = None
                case_dict['fraud_dispute_collusion'] = None
                case_dict['adjudication_case_outcome_model'] = None
            else:
                # Only convert to float if not null/None
                case_dict['fraud_buyer'] = float(case_dict['fraud_buyer']) if pd.notna(case_dict['fraud_buyer']) else None
                case_dict['fraud_seller'] = float(case_dict['fraud_seller']) if pd.notna(case_dict['fraud_seller']) else None
                case_dict['fraud_dispute_collusion'] = float(case_dict['fraud_dispute_collusion']) if pd.notna(case_dict['fraud_dispute_collusion']) else None
                case_dict['adjudication_case_outcome_model'] = float(case_dict['adjudication_case_outcome_model']) if pd.notna(case_dict['adjudication_case_outcome_model']) else None
            
            # Check if this is an instant payout case
            fraud_buyer = case_dict.get('fraud_buyer')
            fraud_seller = case_dict.get('fraud_seller')
            fraud_collusion = case_dict.get('fraud_dispute_collusion')
            adjudication_outcome = case_dict.get('adjudication_case_outcome_model')
            payout_amount = case_dict.get('payout_sensitivity_model')
            
            is_instant_payout = (
                fraud_buyer is not None and float(fraud_buyer) < 0.2 and
                fraud_seller is not None and float(fraud_seller) < 0.3 and
                fraud_collusion is not None and float(fraud_collusion) < 0.2 and
                adjudication_outcome is not None and float(adjudication_outcome) > 0.8 and
                payout_amount is not None
            )

            # Determine case outcome based on fraud probabilities and eligibility
            if case_dict['bp_eligibility_model'] == 'ineligible':
                outcome = "We regret to inform you that your dispute request has been declined as it does not meet our eligibility criteria."
            elif fraud_collusion is not None and float(fraud_collusion) > 0.8:
                outcome = "We need additional time to investigate this matter thoroughly. We will notify you once we have more information."
            elif fraud_buyer is not None and float(fraud_buyer) > 0.7:
                outcome = "We regret to inform you that your dispute has been declined based on our risk assessment."
            elif is_instant_payout and payout_amount is not None:
                payout_amount = float(payout_amount)
                outcome = f"Good news! Your dispute has been approved for instant refund. You will receive ${payout_amount:.2f} in your account within 24 hours."
            elif adjudication_outcome is not None and float(adjudication_outcome) > 0.8:
                outcome = "Good news! Your dispute has been approved, and you will receive a refund within 3-5 business days."
            else:
                outcome = "Your case is currently under review. We will notify you once a decision has been made."
            
            # Determine case outcome based on fraud probabilities and eligibility
            if case_dict['bp_eligibility_model'] == 'ineligible':
                outcome = "We regret to inform you that your dispute request has been declined as it does not meet our eligibility criteria."
            elif case_dict['fraud_dispute_collusion'] > 0.8:
                outcome = "We need additional time to investigate this matter thoroughly. We will notify you once we have more information."
            elif case_dict['fraud_buyer'] > 0.7:
                outcome = "We regret to inform you that your dispute request has been declined due to our investigation findings."
            # Instant Payout Case:
            # Low buyer fraud (< 0.2), high seller integrity (> 0.7), low collusion (< 0.2), high adjudication (> 0.8)
            elif (case_dict['fraud_buyer'] < 0.2 and 
                  case_dict['fraud_seller'] > 0.7 and 
                  case_dict['fraud_dispute_collusion'] < 0.2 and 
                  case_dict['adjudication_case_outcome_model'] > 0.8):
                outcome = "Based on our investigation, we have approved your dispute. You will receive an instant refund for this transaction."
            # Wait for Seller Response Case:
            # Low buyer fraud (< 0.2), medium seller integrity (0.4-0.6), low collusion (< 0.2), medium-low adjudication (0.3-0.5)
            elif (case_dict['fraud_buyer'] < 0.2 and 
                  0.4 <= case_dict['fraud_seller'] <= 0.6 and 
                  case_dict['fraud_dispute_collusion'] < 0.2 and 
                  0.3 <= case_dict['adjudication_case_outcome_model'] <= 0.5):
                outcome = "Your case is under review. We have reached out to the seller for response."
            else:
                outcome = "We need additional time to investigate this matter thoroughly. We will notify you once we have more information."
                
            return case_dict, outcome
            
        except Exception as e:
            print(f"Error getting case status: {str(e)}")
            return None, f"Error retrieving case status: {str(e)}"

    def get_case_data(self, dispute_id):
        try:
            df = pd.read_csv(self.cases_file)
            case = df[df['dispute_id'] == dispute_id]
            if case.empty:
                return None
            return case.iloc[0].to_dict()
        except Exception as e:
            print(f"Error getting case data: {str(e)}")
            return None
