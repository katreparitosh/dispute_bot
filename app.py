from flask import Flask, request, jsonify, send_from_directory, make_response, session
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import os
import uuid
import json
import requests
from datetime import datetime
from db_handler import DatabaseHandler
from back_office_handler import BackOfficeHandler

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, static_url_path='', static_folder='.')
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key')
CORS(app)

# Get OpenAI API key
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("No OpenAI API key found. Please set OPENAI_API_KEY environment variable.")

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Initialize handlers
db = DatabaseHandler()
bo_handler = BackOfficeHandler()

def handle_preflight():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

@app.route('/api/bo_status/<dispute_id>')
def get_bo_status(dispute_id):
    """Get the current status of back office processing for a dispute"""
    try:
        bo_status = bo_handler.check_bo_models(dispute_id)
        return jsonify(bo_status)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'progress': 0,
            'message': f'Error checking status: {str(e)}',
            'instant_payout': False
        })

@app.route('/api/reset', methods=['POST'])
def reset():
    """Reset the conversation context"""
    try:
        # Clear session
        session.clear()
        
        # Initialize default context
        session['context'] = {
            'user_id': None,
            'transaction_id': None,
            'intent': None,
            'dispute_type': None,
            'dispute_reason': None,
            'merchant': None,
            'amount': None,
            'dispute_id': None,
            'dispute_details': {},
            'current_question': None,
            'flow_stage': 'greeting'
        }
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        print("Error resetting context:", str(e))
        return jsonify({'error': str(e)}), 500

def reset_conversation_context():
    """Reset the conversation context to initial state"""
    get_conversation_context.context = {
        'user_id': None,
        'transaction_id': None,
        'intent': None,
        'dispute_type': None,  # INR/SNAD/UNAUTH
        'dispute_reason': None,  # Detailed reason (e.g., 'Item not delivered')
        'merchant': None,
        'amount': None,
        'dispute_id': None,
        'dispute_details': {},
        'current_question': None,
        'flow_stage': 'greeting'  # greeting -> type_selection -> transaction_selection -> reason_selection -> confirmation
    }
    return get_conversation_context.context

def get_conversation_context(messages):
    """Maintain conversation context from previous messages"""
    if not hasattr(get_conversation_context, 'context'):
        get_conversation_context.context = {
            'user_id': None,
            'transaction_id': None,
            'intent': None,
            'dispute_type': None,  # INR/SNAD/UNAUTH
            'dispute_reason': None,  # Detailed reason (e.g., 'Item not delivered')
            'merchant': None,
            'amount': None,
            'dispute_id': None,
            'dispute_details': {},
            'current_question': None,
            'flow_stage': 'greeting'  # greeting -> type_selection -> transaction_selection -> reason_selection -> confirmation
        }
    return get_conversation_context.context

def update_conversation_context(context_updates):
    """Update the conversation context with new information"""
    context = get_conversation_context(None)
    context.update(context_updates)
    return context

def get_back_office_response(dispute_id, transaction_id, user_id):
    """Get back office response based on BO model outputs"""
    try:
        # Get BO model outputs for the dispute
        bo_result = bo_handler.check_bo_models(dispute_id)
        
        if bo_result.get('status') == 'error':
            return {
                'status': 'error',
                'message': bo_result.get('message', 'Error retrieving case details')
            }
        
        # Return the result which includes the message and case data
        return {
            'status': 'success',
            'message': bo_result.get('message'),
            'instant_payout': bo_result.get('instant_payout', False),
            'amount': bo_result.get('amount'),
            'case': bo_result.get('case')
        }
        
    except Exception as e:
        print(f"Error in get_back_office_response: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
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
    
    Follow these steps strictly in order:
    1. If no dispute_type is selected:
       - Present these dispute type options:
         * Item Not Received (INR)
         * Item not as Described (SNAD)
         * Unauthorized Activity (UNAUTH)
    
    2. If dispute_type is selected but no transaction_id:
       - Ask user to select a transaction from the list
       - Show the transaction list
    
    3. If both dispute_type and transaction_id are selected:
       For INR disputes, present these options:
       * Item not delivered
       * Missing tracking information
       * Unavailable for store pickup
       * Delivered to wrong address
       * Order cancelled by seller
    
    4. After all selections are made:
       - Log the dispute with:
         * dispute_id (auto-generated)
         * transaction_id
         * merchant
         * amount
         * issue_type (INR/SNAD/UNAUTH)
         * dispute_reason (detailed reason selected)
       - Confirm to user that dispute has been filed with the dispute_id
    
    Format your response as JSON with these fields:
    {{
        "intent": "File New Dispute",
        "response": "your message to the user",
        "show_transactions": false,  # Set to true only when showing transaction list
        "options": [],  # Array of options to show as buttons
        "context_updates": {{
            "intent": "File New Dispute",
            "transaction_id": null,
            "dispute_type": null,
            "dispute_details": {{}}
        }}
    }}
    """.format(context)

def process_message(message, context=None):
    """Process incoming message with context"""
    try:
        if context is None:
            context = {
                'user_id': None,
                'transaction_id': None,
                'intent': None,
                'dispute_type': None,
                'dispute_reason': None,
                'merchant': None,
                'amount': None,
                'dispute_id': None,
                'dispute_details': {},
                'current_question': None,
                'flow_stage': 'greeting'
            }
        
        print("Processing message:", message)
        print("With context:", context)

        # Initial greeting or starting a new dispute
        if context.get('flow_stage') == 'greeting':
            result = {
                'intent': 'File New Dispute',
                'response': 'What type of issue do you want to file?',
                'options': ['Item Not Received (INR)', 'Item not as Described (SNAD)', 'Unauthorized Activity (UNAUTH)'],
                'show_transactions': False,
                'context_updates': {
                    'intent': 'File New Dispute',
                    'flow_stage': 'type_selection'
                }
            }
            return result

        # User selected a dispute type
        if context.get('flow_stage') == 'type_selection':
            dispute_type = None
            if 'INR' in message:
                dispute_type = 'INR'
            elif 'SNAD' in message:
                dispute_type = 'SNAD'
            elif 'UNAUTH' in message:
                dispute_type = 'UNAUTH'

            if dispute_type:
                result = {
                    'intent': 'File New Dispute',
                    'response': f'Which of the following transactions do you want to file a {dispute_type} dispute for?',
                    'show_transactions': True,
                    'options': [],
                    'context_updates': {
                        'dispute_type': dispute_type,
                        'flow_stage': 'transaction_selection'
                    }
                }
                return result

        # User selected a transaction ID
        if context.get('flow_stage') == 'transaction_selection':
            if message.startswith('TX'):
                # Get transaction details from DB
                transaction = db.get_transaction(message)
                if transaction:
                    options = []
                    if context.get('dispute_type') == 'INR':
                        options = [
                            'Item not delivered',
                            'Missing tracking information',
                            'Unavailable for store pickup',
                            'Delivered to wrong address',
                            'Order cancelled by seller'
                        ]
                    elif context.get('dispute_type') == 'SNAD':
                        options = [
                            'Item damaged',
                            'Item not as described',
                            'Wrong item received',
                            'Missing parts or components',
                            'Counterfeit item'
                        ]
                    elif context.get('dispute_type') == 'UNAUTH':
                        options = [
                            'Transaction not authorized',
                            'Duplicate transaction',
                            'Amount differs from agreed amount',
                            'Subscription cancelled but still charged',
                            'Fraudulent activity'
                        ]
                    
                    result = {
                        'intent': 'File New Dispute',
                        'response': f'What is the detailed reason for your {context.get("dispute_type")} dispute for transaction {message}?',
                        'show_transactions': False,
                        'options': options,
                        'context_updates': {
                            'transaction_id': message,
                            'merchant': transaction.get('merchant'),
                            'amount': transaction.get('amount'),
                            'flow_stage': 'reason_selection'
                        }
                    }
                    return result
                else:
                    return {
                        'intent': 'error',
                        'response': 'Sorry, I couldn\'t find that transaction. Please try again with a valid transaction ID.',
                        'show_transactions': True,
                        'options': [],
                        'context_updates': {}
                    }

        # User selected a detailed reason
        if context.get('flow_stage') == 'reason_selection':
            valid_reasons = [
                'Item not delivered', 'Missing tracking information', 'Unavailable for store pickup',
                'Delivered to wrong address', 'Order cancelled by seller', 'Item damaged',
                'Item not as described', 'Wrong item received', 'Missing parts or components',
                'Counterfeit item', 'Transaction not authorized', 'Duplicate transaction',
                'Amount differs from agreed amount', 'Subscription cancelled but still charged',
                'Fraudulent activity'
            ]
            
            if message in valid_reasons:
                # Generate a unique dispute ID
                dispute_id = f'DSP{uuid.uuid4().hex[:8]}'
                
                # Create dispute in database
                dispute_data = {
                    'dispute_id': dispute_id,
                    'transaction_id': context.get('transaction_id'),
                    'merchant': context.get('merchant'),
                    'amount': context.get('amount'),
                    'dispute_type': context.get('dispute_type'),
                    'dispute_reason': message,
                    'status': 'New',
                    'date_created': datetime.now().strftime('%Y-%m-%d')
                }
                
                db.add_dispute(dispute_data)
                
                # Update back office cases with the new dispute ID
                bo_handler.update_case_entry(dispute_id, context.get('transaction_id'))
                
                # Return success response
                result = {
                    'intent': 'Success',
                    'response': f'Your dispute has been filed successfully! Your dispute ID is {dispute_id}. You will be notified of any updates to your case.',
                    'show_transactions': False,
                    'options': ['Check dispute status', 'File another dispute'],
                    'context_updates': {
                        'dispute_id': dispute_id,
                        'dispute_reason': message,
                        'flow_stage': 'complete',
                        'dispute_details': dispute_data
                    },
                    'bo_status': get_back_office_response(dispute_id, context.get('transaction_id'), context.get('user_id'))
                }
                return result

        # Default response if we don't recognize the stage or input
        return {
            'intent': 'none',
            'response': "I'm not sure what you mean. Would you like to file a new dispute?",
            'show_transactions': False,
            'options': ['Yes, file a new dispute', 'No, check dispute status'],
            'context_updates': {
                'flow_stage': 'greeting'
            }
        }

    except Exception as e:
        print(f"Error in process_message: {str(e)}")
        return {
            'intent': 'error',
            'response': f'Sorry, I encountered an error: {str(e)}',
            'show_transactions': False,
            'options': [],
            'context_updates': {}
        }

@app.route('/api/transactions', methods=['GET', 'OPTIONS'])
def get_transactions():
    if request.method == 'OPTIONS':
        return handle_preflight()
        
    try:
        # Get transactions from database
        transactions = db.get_all_transactions()
        return jsonify(transactions)
    except Exception as e:
        print("Error retrieving transactions:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return handle_preflight()
        
    try:
        print("Received chat request")
        data = request.get_json()
        print("Request data:", data)
        
        message = data.get('message', '').strip()
        print("User message:", message)
        
        # Initialize default context
        default_context = {
            'user_id': None,
            'transaction_id': None,
            'intent': None,
            'dispute_type': None,
            'dispute_reason': None,
            'merchant': None,
            'amount': None,
            'dispute_id': None,
            'dispute_details': {},
            'current_question': None,
            'flow_stage': 'greeting'
        }
        
        # Get context from session or use default
        context = session.get('context', default_context.copy())
        print("Processing message with context:", context)
        
        # Process message
        result = process_message(message, context)
        print("Process result:", result)
        
        # Update session context with context_updates
        if result.get('context_updates'):
            # Merge the updates with existing context rather than replacing
            for key, value in result['context_updates'].items():
                context[key] = value
            session['context'] = context
        
        return jsonify(result)
        
    except Exception as e:
        print("Error processing request:", str(e))
        return jsonify({
            'error': str(e),
            'response': 'Sorry, there was an error processing your request.',
            'options': [],
            'show_transactions': False,
            'context_updates': {}
        }), 500

if __name__ == '__main__':
    app.run(port=8000, debug=True)
