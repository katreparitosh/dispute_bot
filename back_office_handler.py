import pandas as pd
from datetime import datetime

class BackOfficeHandler:
    def __init__(self):
        self.cases_file = 'back_office_cases.csv'
        
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
                fraud_seller is not None and float(fraud_seller) > 0.7 and
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
            # Low buyer fraud (< 0.2), high seller fraud (> 0.7), low collusion (< 0.2), high adjudication (> 0.8)
            elif (case_dict['fraud_buyer'] < 0.2 and 
                  case_dict['fraud_seller'] > 0.7 and 
                  case_dict['fraud_dispute_collusion'] < 0.2 and 
                  case_dict['adjudication_case_outcome_model'] > 0.8):
                outcome = "Based on our investigation, we have approved your dispute. You will receive an instant refund for this transaction."
            # Wait for Seller Response Case:
            # Low buyer fraud (< 0.2), medium seller fraud (0.4-0.6), low collusion (< 0.2), medium-low adjudication (0.3-0.5)
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
