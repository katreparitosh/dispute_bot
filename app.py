from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import openai
from dotenv import load_dotenv
import os
import json
from back_office_handler import BackOfficeHandler
import pandas as pd
from db_handler import DatabaseHandler
from back_office_handler import BackOfficeHandler

# Load environment variables
load_dotenv()

app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})
db = DatabaseHandler()
back_office = BackOfficeHandler()

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/')
def serve_index():
    # Reset context when serving the main page
    reset_conversation_context()
    return send_from_directory('.', 'index.html')

@app.route('/api/reset', methods=['POST'])
def reset():
    """Reset the conversation context"""
    reset_conversation_context()
    return jsonify({'status': 'success'})

def reset_conversation_context():
    """Reset the conversation context to initial state"""
    get_conversation_context.context = {
        'user_id': None,
        'transaction_id': None,
        'intent': None,
        'dispute_type': None,
        'dispute_details': {},
        'current_question': None
    }
    return get_conversation_context.context

def get_conversation_context(messages):
    """Maintain conversation context from previous messages"""
    if not hasattr(get_conversation_context, 'context'):
        get_conversation_context.context = {
            'user_id': None,
            'transaction_id': None,
            'intent': None,
            'dispute_type': None,
            'dispute_details': {},
            'current_question': None
        }
    return get_conversation_context.context

def update_conversation_context(context_updates):
    """Update the conversation context with new information"""
    context = get_conversation_context(None)
    context.update(context_updates)
    return context

# Configure OpenAI
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OpenAI API key not found in environment variables")

client = openai.OpenAI(api_key=api_key)

def get_back_office_response(dispute_id, transaction_id, user_id):
    system_prompt = """
    You are a PayPal Back Office Agent responsible for communicating dispute investigation outcomes to customers.
    Be professional, clear, and empathetic in your responses.
    Format your response as a JSON object with these fields:
    {
        "response": "your message to the user",
        "context_updates": {}
    }
    """

    try:
        # Get case status from back office
        case, outcome = back_office.get_case_status(
            dispute_id=dispute_id,
            transaction_id=transaction_id,
            user_id=user_id
        )

        if not case:
            return {
                "response": f"I apologize, but I couldn't find the case details. {outcome}",
                "context_updates": {}
            }

        # Get AI response for the outcome
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Case details: {case}\nOutcome: {outcome}"}
            ],
            temperature=0,
            max_tokens=500
        )
        result = response.choices[0].message.content.strip()
        return json.loads(result)

    except Exception as e:
        print(f"Error in back office response: {str(e)}")
        return {
            "response": "I apologize, but I encountered an error while retrieving your case details. Please try again later.",
            "context_updates": {}
        }

def get_dispute_status_prompt(context):
    return """
    You are a PayPal Dispute Status Agent. Your ONLY role is to help customers check their dispute status.
    
    Current context: {}
    
    Follow these rules strictly:
    1. ALWAYS maintain "Dispute Status" as the intent
    2. NEVER suggest filing a new dispute
    3. If no dispute is selected:
       - Ask the user to select a dispute from the list
    4. After getting the Dispute ID, show its status
    5. Reset context after showing the status
    
    Format your response as JSON with these fields:
    {{
        "intent": "Dispute Status",
        "response": "your message to the user",
        "show_disputes": true,  # Set to true when you want to show dispute list
        "options": [],
        "context_updates": {{
            "intent": "Dispute Status",
            "dispute_id": null,
            "dispute_type": null,
            "dispute_details": {{}}
        }}
    }}
    """.format(context)

def get_new_dispute_prompt(context):
    return """
    You are a PayPal Dispute Filing Agent. Your role is to help customers file new disputes.
    
    Current context: {}
    
    Follow these steps in order:
    1. If no transaction is selected:
       - Ask the user to select a transaction from the list
    2. If no dispute type, present these dispute options:
       * Item Not Received (INR)
       * Item not as Described (SNAD)
       * Unauthorized Activity (UNAUTH)
    
    After dispute type selection:
    For INR:
    1. Ask: "What was the expected delivery date?"
    2. Ask: "Have you contacted the seller? (Yes/No)"
    
    For SNAD:
    1. Ask: "What's wrong with the item? Describe the issues."
    2. Ask: "Have you contacted the seller? (Yes/No)"
    
    For UNAUTH:
    1. Ask: "Do you recognize the merchant? (Yes/No)"
    2. Ask: "Have you contacted your bank? (Yes/No)"
    
    Format your response as JSON with these fields:
    {{
        "intent": "File New Dispute",
        "response": "your message to the user",
        "show_transactions": true,  # Set to true when you want to show transaction list
        "options": [],
        "context_updates": {{
            "intent": "File New Dispute",
            "transaction_id": null,
            "dispute_type": null,
            "dispute_details": {{}}
        }}
    }}
    """.format(context)

def process_message(message, context):
    # If we're in dispute status flow or message indicates status check
    is_status_check = (
        (context and context.get('intent') == 'Dispute Status') or
        any(word in message.lower() for word in ['status', 'check', 'track', 'progress'])
    )
    
    # Choose appropriate prompt based on context
    if is_status_check:
        system_prompt = get_dispute_status_prompt(context)
    else:
        system_prompt = get_new_dispute_prompt(context)


    try:
        # Format user message separately to avoid nested f-strings
        user_message = "Context: " + str(context) + "\nUser message: " + message
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0,
            max_tokens=500
        )
        result = response.choices[0].message.content.strip()
        print(f"OpenAI response: {result}")
        
        # Format debug message separately
        debug_msg = "Processed message: '" + message + "' with context " + str(context) + "\nResult: " + result
        print(debug_msg)
        
        # Parse the response as JSON string
        import json
        try:
            return json.loads(result)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {str(e)}\nResponse was: {result}")
            return {
                "intent": "Error",
                "response": "I encountered an error processing your request. Please try again.",
                "options": ["Start over"],
                "context_updates": {}
            }
    except Exception as e:
        import traceback
        print(f"Error in OpenAI API call:\n{traceback.format_exc()}")
        return {
            "intent": "Error",
            "response": f"I encountered an error: {str(e)}",
            "options": ["Start over"],
            "context_updates": {}
        }

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        print("Received chat request")
        data = request.json
        print(f"Request data: {data}")
        user_message = data.get('message', '')
        print(f"User message: {user_message}")
        
        # Get current conversation context
        context = get_conversation_context(None)
        
        # Process the message with context
        print(f"Processing message with context: {context}")
        result = process_message(user_message, context)
        print(f"Process result: {result}")
        
        # Handle concluding statements by resetting context
        if isinstance(result, dict):
            if result.get('intent') == 'Conclude':
                reset_conversation_context()
                ctx = get_conversation_context(None)
            elif result.get('context_updates'):
                update_conversation_context(result['context_updates'])
            
            # Get updated context
            ctx = get_conversation_context(None)
            
            # Extract dispute ID from user selection
            if '(ID:' in user_message:
                dispute_id = user_message.split('(ID:')[1].strip().rstrip(')')
                print(f"Extracted dispute ID: {dispute_id}")
                ctx['dispute_id'] = dispute_id  # Update context immediately
                result['context_updates'] = {'dispute_id': dispute_id, 'intent': 'Dispute Status'}
                result['intent'] = 'Dispute Status'
            
            # Handle dispute status queries
            if result.get('intent') == 'Dispute Status':
                # Check if we have a dispute ID in the context
                print(f"Current context: {ctx}")
                if not ctx.get('dispute_id'):
                    result['response'] = "Please choose the dispute you want to check from the list below."
                    result['context_updates'] = {'intent': 'Dispute Status'}
                else:
                    print(f"Looking up dispute with ID: {ctx['dispute_id']}")
                    # Get dispute status and back office case details
                    dispute_id = ctx['dispute_id']
                    print(f"Looking up dispute with ID: {dispute_id}")
                    
                    # Get back office case details and outcome message directly
                    back_office = BackOfficeHandler()
                    case_dict, outcome = back_office.get_case_status(dispute_id=dispute_id)
                    print(f"Back office case details: {case_dict}")
                    
                    if not case_dict:
                        result['response'] = "No dispute found."
                        result['context_updates'] = {'intent': None}
                    else:
                        
                        # Set response message from back office outcome
                        response = outcome
                        
                        # Add back office case details to panel only
                        if case_dict:
                            print(f"Case dict from back office: {case_dict}")
                            # Convert any NaN values to None for proper JSON serialization
                            def clean_value(val):
                                import math
                                if isinstance(val, float) and math.isnan(val):
                                    return None
                                return val

                            result['case'] = {
                                'fraud_buyer': clean_value(case_dict['fraud_buyer']),
                                'fraud_seller': clean_value(case_dict['fraud_seller']),
                                'fraud_dispute_collusion': clean_value(case_dict['fraud_dispute_collusion']),
                                'adjudication_case_outcome_model': clean_value(case_dict['adjudication_case_outcome_model']),
                                'bp_eligibility_model': case_dict['bp_eligibility_model'],
                                'payout_sensitivity_model': clean_value(case_dict.get('payout_sensitivity_model'))
                            }
                            print(f"Result case data: {result['case']}")
                        result['response'] = response
                        result['context_updates'] = {'intent': None}
                        result['show_disputes'] = False
                    
                    # Reset context after showing status
                    reset_conversation_context()
            
            # Handle new dispute creation
            elif result.get('intent') == 'File New Dispute' and \
                 all([ctx.get('transaction_id'), ctx.get('dispute_type')]) and \
                 ctx.get('dispute_details'):
                
                # Only try to create dispute if we have all required details
                if ctx['dispute_type'] == 'INR':
                    required_fields = ['expected_delivery_date', 'contacted_seller']
                elif ctx['dispute_type'] == 'SNAD':
                    required_fields = ['item_condition', 'contacted_seller']
                else:  # UNAUTH
                    required_fields = ['recognizes_merchant', 'contacted_bank']
                
                # Check if we have all required fields
                missing_fields = [field for field in required_fields if field not in ctx.get('dispute_details', {})]
                
                if not missing_fields:
                    dispute, message = db.create_dispute(
                        ctx['transaction_id'],
                        ctx['dispute_type'],
                        ctx['dispute_details']
                    )
                    
                    if dispute:
                        result['response'] = f"Dispute created successfully! Your dispute ID is: {dispute['dispute_id']}"
                        result['context_updates'] = {}  # Reset context after successful creation
                    else:
                        result['response'] = f"Error creating dispute: {message}"
        
        # Get transactions if needed
        transactions = None
        if result.get('show_transactions', False):
            transactions = db.get_all_transactions()
            # Format transactions for display
            transaction_options = [f"{t['merchant_seller']} - ${t['amount']} (ID: {t['transaction_id']})" for t in transactions]
            result['options'] = transaction_options
            
        # Get disputes if needed
        disputes = None
        if result.get('show_disputes', False):
            disputes = db.get_all_disputes()
            # Format disputes for display
            dispute_options = [f"{d['merchant']} - ${d['amount']} ({d['type']}) (ID: {d['dispute_id']})" for d in disputes]
            result['options'] = dispute_options

        # Convert response to message format for frontend
        response_data = {
            'intent': result.get('intent'),
            'response': result.get('response') or result.get('message'),
            'options': result.get('options', []),
            'context_updates': result.get('context_updates', {}),
            'case': result.get('case'),
            'outcome': result.get('outcome'),
            'transactions': transactions
        }
        
        return jsonify(response_data)

    except Exception as e:
        import traceback
        error_msg = f"Error in chat endpoint:\n{traceback.format_exc()}"
        print(error_msg)
        response = jsonify({
            'intent': 'Error',
            'response': f'An error occurred: {str(e)}',
            'options': ['Start over'],
            'context_updates': {}
        })
        return response
if __name__ == '__main__':
    app.run(port=8000, debug=True)
