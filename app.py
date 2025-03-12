from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import openai
from dotenv import load_dotenv
import os
import pandas as pd
from db_handler import DatabaseHandler

# Load environment variables
load_dotenv()

app = Flask(__name__, static_url_path='')
CORS(app)
db = DatabaseHandler()

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

def get_conversation_context(messages):
    """Maintain conversation context from previous messages"""
    if not hasattr(get_conversation_context, 'context'):
        get_conversation_context.context = {
            'user_id': None,
            'transaction_id': None,
            'dispute_type': None,
            'description': None
        }
    return get_conversation_context.context

def update_conversation_context(context_updates):
    """Update the conversation context with new information"""
    context = get_conversation_context(None)
    context.update(context_updates)
    return context

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

def process_message(message, context):
    system_prompt = """
    You are a PayPal Dispute Resolution Agent. Your role is to help customers file and manage disputes efficiently.
    You have access to the following context:
    - User ID (if provided)
    - Transaction ID (if provided)
    - Previous dispute type (if any)
    - Previous description (if any)

    Follow these rules:
    1. First, determine the user's intent:
       - "File New Dispute" - If they want to file a new dispute
       - "Dispute Status" - If they're asking about existing dispute status
       - "Not Dispute" - For non-dispute queries

    2. For dispute cases:
       - If no user_id, ask for it (format: U followed by 6 digits)
       - If filing new dispute and no transaction_id, ask for it (format: TX followed by 6 digits)
       - If item not received case, gather delivery timeline
       - If item not as described, ask for specific issues
       - Always maintain a professional, empathetic tone

    3. For dispute status queries:
       - If no user_id, ask for it
       - Once user_id is provided, list all their disputes

    4. Only provide options when the user needs to make a specific choice
       - DO NOT provide options for free-form inputs like User ID or Transaction ID
       - DO provide options for specific choices like dispute type or next steps

    Your response MUST be in this exact format (do not include any other text):
    {{
        "intent": "File New Dispute" or "Dispute Status" or "Not Dispute",
        "response": "your message to the user",
        "options": [], (leave empty array if no options needed)
        "context_updates": {{"user_id": null, "transaction_id": null, "dispute_type": null, "description": null}}
    }}

    Example responses:

    For dispute status query (no user_id):
    {{
        "intent": "Dispute Status",
        "response": "I'll help you check your dispute status. Please provide your User ID (starts with 'U' followed by 6 digits).",
        "options": [],
        "context_updates": {{}}
    }}

    For dispute status query (with user_id):
    {{
        "intent": "Dispute Status",
        "response": "Here are all your current disputes...",
        "options": [],
        "context_updates": {{"user_id": "U123456"}}
    }}
    """

    try:
        client = openai.OpenAI()
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
        
        # Update conversation context
        if isinstance(result, dict) and 'context_updates' in result:
            update_conversation_context(result['context_updates'])
            ctx = get_conversation_context(None)
            
            # Handle dispute status queries
            if result.get('intent') == 'Dispute Status' and ctx.get('user_id'):
                # Use the database handler to get disputes
                disputes = db.get_user_disputes(ctx['user_id'])
                if disputes and disputes[0]:
                    dispute_details = []
                    for dispute in disputes[0]:
                        dispute_details.append(
                            f"Dispute {dispute['dispute_id']} for transaction {dispute['transaction_id']}:\n" +
                            f"Type: {dispute['type']}\n" +
                            f"Status: {dispute['status']}\n" +
                            f"Created: {dispute['creation_date']}\n" +
                            f"Description: {dispute['description']}"
                        )
                    result['response'] = "Here are your disputes:\n\n" + "\n\n".join(dispute_details)
                else:
                    result['response'] = disputes[1] if disputes else "No disputes found."
            
            # Handle new dispute creation
            elif result.get('intent') == 'File New Dispute' and \
                 all([ctx['user_id'], ctx['transaction_id'], ctx['dispute_type'], ctx['description']]):
                dispute, message = db.create_dispute(
                    ctx['user_id'],
                    ctx['transaction_id'],
                    ctx['dispute_type'],
                    ctx['description']
                )
                if dispute:
                    result['response'] += f"\n\nDispute created successfully! Your dispute ID is: {dispute['dispute_id']}"
                else:
                    result['response'] += f"\n\nNote: {message}"

        response_data = {
            'intent': result.get('intent'),
            'message': result.get('response'),
            'options': result.get('options', [])
        }

        return jsonify(response_data)

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(port=3000, debug=True)
