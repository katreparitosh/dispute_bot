// API base URL
const API_BASE_URL = 'http://localhost:3000';

document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements and verify they exist
    const elements = {
        chatMessages: document.getElementById('chatMessages'),
        userInput: document.getElementById('userInput'),
        sendButton: document.getElementById('sendButton'),
        optionsContainer: document.getElementById('optionsContainer'),
        // State panel elements
        currentIntent: document.getElementById('currentIntent'),
        currentUserId: document.getElementById('currentUserId'),
        currentTransactionId: document.getElementById('currentTransactionId'),
        currentDisputeType: document.getElementById('currentDisputeType'),
        // Back Office panel elements
        fraudBuyer: document.getElementById('fraudBuyer'),
        fraudSeller: document.getElementById('fraudSeller'),
        caseConfidence: document.getElementById('caseConfidence'),
        favorParty: document.getElementById('favorParty')
    };

    // Verify all required elements exist
    for (const [key, element] of Object.entries(elements)) {
        if (!element) {
            console.error(`Required element '${key}' not found in the DOM`);
            return;
        }
    }

    // Destructure elements for easier access
    const {
        chatMessages, userInput, sendButton, optionsContainer,
        currentIntent, currentUserId, currentTransactionId, currentDisputeType,
        caseId, fraudBuyer, fraudSeller
    } = elements;

    // Reset conversation context and initialize UI when page loads
    fetch(`${API_BASE_URL}/api/reset`, {
        method: 'POST'
    }).then(() => {
        // Reset state panel
        updateStatePanel({
            intent: 'Initial Greeting',
            userId: '-',
            transactionId: '-',
            disputeType: '-'
        });
        // Add initial bot message
        addMessage("Hello! I'm your PayPal Dispute Assistant. I can help you file a new dispute or check the status of an existing one. How can I help you today?", 'bot');
    }).catch(error => {
        console.error('Error resetting conversation:', error);
        // Still show initial message even if reset fails
        addMessage("Hello! I'm your PayPal Dispute Assistant. How can I help you today?", 'bot');
    });

    // Handle send button click
    sendButton.addEventListener('click', handleUserInput);

    // Handle enter key press (with shift+enter for new line)
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleUserInput();
        }
    });

    function handleUserInput() {
        const message = userInput.value.trim();
        if (message) {
            addMessage(message, 'user');
            userInput.value = '';
            // Clear any existing options
            optionsContainer.innerHTML = '';
            
            // Process the user's message and generate a response
            processUserMessage(message);
        }
    }

    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', `${sender}-message`);
        messageDiv.textContent = text;
        chatMessages.appendChild(messageDiv);
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showOptions(options) {
        optionsContainer.innerHTML = '';
        if (!options || options.length === 0) return;
        
        options.forEach(option => {
            const button = document.createElement('button');
            button.classList.add('option-button');
            button.textContent = option;
            button.addEventListener('click', () => {
                addMessage(option, 'user');
                optionsContainer.innerHTML = '';
                processUserMessage(option);
            });
            optionsContainer.appendChild(button);
        });
    }

    async function processUserMessage(message) {
        try {
            // Show loading state
            sendButton.disabled = true;
            userInput.disabled = true;
            
            // Make API call to backend
            const response = await fetch(`${API_BASE_URL}/api/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message })
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Update conversation state panel
            updateStatePanel({
                intent: data.intent || '-',
                userId: data.context_updates?.user_id || currentUserId.textContent,
                transactionId: data.context_updates?.transaction_id || currentTransactionId.textContent,
                disputeType: data.context_updates?.dispute_type || currentDisputeType.textContent
            });

            // Add bot response
            if (data.message) {
                addMessage(data.message, 'bot');
            }

            // Show options if available
            if (data.options && Array.isArray(data.options)) {
                showOptions(data.options);
            }

            // Update Back Office panel if case data is available
            if (data.intent === 'Dispute Status' && data.case) {
                updateBOPanel(data);
            } else if (data.intent === 'Dispute Status' && !data.case) {
                // Reset BO panel when checking status but no case found
                updateBOPanel(null);
            }

        } catch (error) {
            console.error('Error:', error);
            addMessage(`Error: ${error.message || 'Something went wrong. Please try again.'}`, 'bot');
            
            // Reset state panel on error
            updateStatePanel({
                intent: 'Error',
                userId: '-',
                transactionId: '-',
                disputeType: '-'
            });
        } finally {
            // Reset loading state
            sendButton.disabled = false;
            userInput.disabled = false;
        }
    }

    function updateStatePanel(state) {
        // Update state panel with new values, keeping existing ones if not provided
        currentIntent.textContent = state.intent || '-';
        currentUserId.textContent = state.userId || '-';
        currentTransactionId.textContent = state.transactionId || '-';
        currentDisputeType.textContent = state.disputeType || '-';
    }

    function updateBOPanel(data) {
        // Reset BO panel if no case data
        if (!data || !data.case) {
            fraudBuyer.textContent = '-';
            fraudBuyer.className = 'bo-value';
            fraudSeller.textContent = '-';
            fraudSeller.className = 'bo-value';
            caseConfidence.textContent = '-';
            favorParty.textContent = '-';
            return;
        }

        // Update fraud buyer status with color coding
        const isFraudBuyer = parseInt(data.case.fraud_buyer) === 1;
        fraudBuyer.textContent = isFraudBuyer ? 'Yes' : 'No';
        fraudBuyer.className = 'bo-value ' + (isFraudBuyer ? 'fraud-true' : 'fraud-false');
        
        // Update fraud seller status with color coding
        const isFraudSeller = parseInt(data.case.fraud_seller) === 1;
        fraudSeller.textContent = isFraudSeller ? 'Yes' : 'No';
        fraudSeller.className = 'bo-value ' + (isFraudSeller ? 'fraud-true' : 'fraud-false');

        // Update case confidence and favor party
        caseConfidence.textContent = data.case.case_outcome_confidence + '%';
        favorParty.textContent = data.case.favor_party;
    }
});
