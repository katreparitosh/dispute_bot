from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import openai
from dotenv import load_dotenv
import os
import pandas as pd
from db_handler import DatabaseHandler
from back_office_handler import BackOfficeHandler

# Load environment variables
load_dotenv()

app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app)
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
    3. ONLY ask for these details in order:
       - User ID (format: U followed by 6 digits)
       - Transaction ID (format: TX followed by 6 digits)
    4. After getting both IDs, do not ask any more questions
    5. Reset context after showing the status
    
    Format your response as JSON with these fields:
    {{
        "intent": "Dispute Status",
        "response": "your message to the user",
        "options": [],
        "context_updates": {{
            "intent": "Dispute Status",
            "user_id": null,
            "transaction_id": null,
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
    1. Ask for User ID (format: U followed by 6 digits)
    2. Ask for Transaction ID (format: TX followed by 6 digits)
    3. Present these dispute options:
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
        "options": [],
        "context_updates": {{
            "intent": "File New Dispute",
            "user_id": null,
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
        print(f"Error in OpenAI API call: {str(e)}")
        return {
            "intent": "Error",
            "response": "I encountered an error. Please try again.",
            "options": ["Start over"],
            "context_updates": {}
        }

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        
        # Get current conversation context
        context = get_conversation_context(None)
        
        # Process the message with context
        result = process_message(user_message, context)
        
        # Handle concluding statements by resetting context
        if isinstance(result, dict):
            if result.get('intent') == 'Conclude':
                reset_conversation_context()
                ctx = get_conversation_context(None)
            elif result.get('context_updates'):
                update_conversation_context(result['context_updates'])
            
            # Get updated context
            ctx = get_conversation_context(None)
            
            # Handle dispute status queries
            if result.get('intent') == 'Dispute Status':
                # Always require both user_id and transaction_id
                if not ctx or not ctx.get('user_id'):
                    result['response'] = "Please provide your User ID (format: U followed by 6 digits)"
                    result['context_updates'] = {'intent': 'Dispute Status', 'user_id': None, 'transaction_id': None}
                elif not ctx.get('transaction_id'):
                    result['response'] = "Please provide the Transaction ID (format: TX followed by 6 digits)"
                    result['context_updates'] = {'intent': 'Dispute Status', 'transaction_id': None}
                else:
                    # First check back office case status
                    case, outcome = back_office.get_case_status(
                        transaction_id=ctx['transaction_id'],
                        user_id=ctx['user_id']
                    )
                    
                    if case:
                        result.update({
                            'response': outcome,
                            'case': {
                                'case_id': case.get('case_id'),
                                'fraud_buyer': case.get('fraud_buyer'),
                                'fraud_seller': case.get('fraud_seller'),
                                'case_outcome_confidence': case.get('case_outcome_confidence'),
                                'favor_party': case.get('favor_party')
                            },
                            'outcome': outcome
                        })
                    else:
                        # If no case found, check if dispute exists
                        dispute = db.get_dispute_status(transaction_id=ctx['transaction_id'])
                        if dispute:
                            result.update({
                                'response': (
                                    f"Status for transaction {ctx['transaction_id']}:\n" +
                                    f"Type: {dispute['type']}\n" +
                                    f"Status: {dispute['status']}\n" +
                                    f"Created: {dispute['creation_date']}\n\n" +
                                    "Your case is currently under initial review."
                                ),
                                'case': None
                            })
                        else:
                            result.update({
                                'response': f"No dispute found for transaction {ctx['transaction_id']}",
                                'case': None
                            })
                    
                    # Reset context after showing status
                    reset_conversation_context()
            
            # Handle new dispute creation
            elif result.get('intent') == 'File New Dispute' and \
                 all([ctx.get('user_id'), ctx.get('transaction_id'), ctx.get('dispute_type')]) and \
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
                        ctx['user_id'],
                        ctx['transaction_id'],
                        ctx['dispute_type'],
                        ctx['dispute_details']
                    )
                    
                    if dispute:
                        result['response'] = f"Dispute created successfully! Your dispute ID is: {dispute['dispute_id']}"
                        result['context_updates'] = {}  # Reset context after successful creation
                    else:
                        result['response'] = f"Error creating dispute: {message}"
        
        # Convert response to message format for frontend
        response_data = {
            'intent': result.get('intent'),
            'message': result.get('response') or result.get('message'),
            'options': result.get('options', []),
            'context_updates': result.get('context_updates', {}),
            'case': result.get('case'),
            'outcome': result.get('outcome')
        }
        
        return jsonify(response_data)

    except Exception as e:
        error_msg = f"Error in chat endpoint: {str(e)}"
        print(error_msg)
        return jsonify({
            'intent': 'Error',
            'message': 'An error occurred. Please try again.',
            'options': ['Start over'],
            'context_updates': {}
        })
if __name__ == '__main__':
    app.run(port=3000, debug=True)
