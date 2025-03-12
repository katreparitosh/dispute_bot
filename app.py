from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import openai
from dotenv import load_dotenv
import os
import pandas as pd
from db_handler import DatabaseHandler

# Load environment variables
load_dotenv()

app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app)
db = DatabaseHandler()

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

def process_message(message, context):
    system_prompt = """
    You are a PayPal Dispute Resolution Agent. Help customers file and manage disputes efficiently.
    
    Current context: {context}
    
    Follow these rules strictly:
    1. First, determine user's intent:
       - "File New Dispute" - If they want to file a new dispute
       - "Dispute Status" - If they want to check status
       - "Not Dispute" - For other queries
       - "Conclude" - If the user expresses gratitude or indicates they're done (e.g., "thank you", "great", "works", "ok")

    If intent is "Conclude":
    - Respond with: "You're welcome! Let me know how I can help further."
    - Clear any existing context

    2. For "File New Dispute" or "Dispute Status":
       - If no user_id, ask for it (format: U followed by 6 digits)
       - After getting user_id, directly ask for transaction_id (format: TX followed by 6 digits)
       - For "Dispute Status", always ask for user_id and transaction_id, even if previously provided

    3. For "File New Dispute" after getting transaction_id:
       - If no dispute_type, present EXACTLY these options:
         * Item Not Received (INR)
         * Item not as Described (SNAD)
         * Unauthorized Activity (UNAUTH)
       
       - Once dispute_type selected, follow this flow:
         For INR:
         1. Ask: "What was the expected delivery date?"
         2. Ask: "Have you contacted the seller? (Yes/No)"
         
         For SNAD:
         1. Ask: "What's wrong with the item? Describe the issues."
         2. Ask: "Have you contacted the seller? (Yes/No)"
         
         For UNAUTH:
         1. Ask: "Do you recognize the merchant? (Yes/No)"
         2. Ask: "Have you contacted your bank? (Yes/No)"

    4. For "Dispute Status":
       - First ask for user_id if not provided
       - Then ask for transaction_id
       - After getting both, show dispute status and details
       - Reset context after showing status

    5. Response Rules:
       - Ask ONE question at a time
       - Only show dispute reason options when asking for dispute type
       - Never show options for User ID or Transaction ID inputs
       - Store all answers in dispute_details
       - For INR disputes:
         * When user provides delivery date, store it and immediately ask about seller contact
         * Format the delivery date as YYYY-MM-DD in dispute_details
       - For SNAD disputes:
         * When user describes item condition, store it and immediately ask about seller contact
       - For UNAUTH disputes:
         * When user answers about merchant recognition, store it and immediately ask about bank contact
       
    Format your response as a JSON object with these fields:
    {
        "intent": "File New Dispute" or "Dispute Status" or "Not Dispute",
        "response": "your message to the user",
        "options": [], (empty if no options needed)
        "context_updates": {
            "user_id": null,
            "transaction_id": null,
            "dispute_type": null,
            "dispute_details": {},
            "current_question": null
        }
    }
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context: {str(context)}\nUser message: {message}"}
            ],
            temperature=0,
            max_tokens=500
        )
        result = response.choices[0].message.content.strip()
        print(f"Processed message: '{message}' with context {context}\nResult: {result}")
        
        # Parse the response as JSON string
        import json
        try:
            return json.loads(result)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {str(e)}\nResponse was: {result}")
            return {
                "intent": "Error",
                "message": "I encountered an error processing your request. Please try again.",
                "options": ["Start over"],
                "context_updates": {}
            }
    except Exception as e:
        print(f"Error in OpenAI API call: {str(e)}")
        return {
            "intent": "Error",
            "message": "I encountered an error. Please try again.",
            "options": ["Start over"],
            "context_updates": {}
        }
        import json
        try:
            return json.loads(result)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {str(e)}\nResponse was: {result}")
            return {
                "intent": "Error",
                "message": "I encountered an error processing your request. Please try again.",
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
            elif result.get('context_updates'):
                update_conversation_context(result['context_updates'])
                ctx = get_conversation_context(None)
            
            # Handle dispute status queries
            if result.get('intent') == 'Dispute Status':
                # Always require both user_id and transaction_id
                if not ctx.get('user_id'):
                    result['response'] = "Please provide your User ID (format: U followed by 6 digits)"
                    result['context_updates'] = {'user_id': None, 'transaction_id': None}
                elif not ctx.get('transaction_id'):
                    result['response'] = "Please provide the Transaction ID (format: TX followed by 6 digits)"
                    result['context_updates'] = {'transaction_id': None}
                else:
                    # Verify transaction belongs to user
                    transaction = db.verify_transaction(ctx['transaction_id'], ctx['user_id'])
                    if not transaction:
                        result['response'] = "This transaction doesn't belong to your account."
                    else:
                        dispute = db.get_dispute_status(transaction_id=ctx['transaction_id'])
                        if dispute:
                            result['response'] = (
                                f"Status for transaction {ctx['transaction_id']}:\n" +
                                f"Type: {dispute['type']}\n" +
                                f"Status: {dispute['status']}\n" +
                                f"Created: {dispute['creation_date']}\n" +
                                f"Details: {dispute.get('details', 'No additional details')}"
                            )
                        else:
                            result['response'] = f"No dispute found for transaction {ctx['transaction_id']}"
                        
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
            'context_updates': result.get('context_updates', {})
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
