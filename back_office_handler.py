import pandas as pd
from datetime import datetime

class BackOfficeHandler:
    def __init__(self):
        self.cases_file = 'back_office_cases.csv'
        
    def get_case_status(self, dispute_id=None, transaction_id=None, user_id=None):
        """Get case status and outcome based on fraud checks"""
        try:
            df = pd.read_csv(self.cases_file)
            
            # Find the case
            if dispute_id:
                case = df[df['dispute_id'] == dispute_id]
            elif transaction_id and user_id:
                case = df[(df['transaction_id'] == transaction_id) & (df['user_id'] == user_id)]
            else:
                return None, "Invalid case lookup parameters"
                
            if case.empty:
                return None, "Case not found"
                
            case_dict = case.iloc[0].to_dict()
            fraud_buyer = int(case_dict['fraud_buyer'])
            fraud_seller = int(case_dict['fraud_seller'])
            
            # Convert numeric values to proper types
            case_dict['fraud_buyer'] = int(case_dict['fraud_buyer'])
            case_dict['fraud_seller'] = int(case_dict['fraud_seller'])
            case_dict['case_outcome_confidence'] = float(case_dict['case_outcome_confidence'])
            case_dict['favor_party'] = str(case_dict['favor_party'])
            
            # Determine case outcome based on fraud flags
            if fraud_buyer == 0 and fraud_seller == 0:
                outcome = "Your case is under review. We have reached out to the seller for response."
            elif fraud_buyer == 1 and fraud_seller == 0:
                outcome = "We regret to inform you that your dispute request has been declined due to our investigation findings."
            elif fraud_buyer == 0 and fraud_seller == 1:
                outcome = "Based on our investigation, we have approved your dispute. You will receive an instant refund for this transaction."
            else:  # fraud_buyer == 1 and fraud_seller == 1
                outcome = "We need additional time to investigate this matter thoroughly. We will notify you once we have more information."
                
            return case_dict, outcome
            
        except Exception as e:
            print(f"Error getting case status: {str(e)}")
            return None, f"Error retrieving case status: {str(e)}"
