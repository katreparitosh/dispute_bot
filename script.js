// API base URL
const API_BASE_URL = 'http://localhost:8000';

// Function to add a message to the chat
function addMessage(text, sender) {
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', `${sender}-message`);
        messageDiv.textContent = text;
        chatMessages.appendChild(messageDiv);
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// Add initial bot message immediately when script loads
addMessage("Hello! I'm your PayPal Dispute Assistant. I can help you file a new dispute or check the status of an existing one. How can I help you today?", 'bot');

document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements and verify they exist
    const elements = {
        chatMessages: document.getElementById('chatMessages'),
        userInput: document.getElementById('userInput'),
        sendButton: document.getElementById('sendButton'),
        optionsContainer: document.getElementById('optionsContainer'),
        // State panel elements
        currentIntent: document.getElementById('currentIntent'),
        currentTransactionId: document.getElementById('currentTransactionId'),
        currentDisputeType: document.getElementById('currentDisputeType'),
        // Back Office panel elements
        fraudBuyer: document.getElementById('fraudBuyer'),
        fraudSeller: document.getElementById('fraudSeller')
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
        currentIntent, currentTransactionId, currentDisputeType,
        fraudBuyer, fraudSeller
    } = elements;
    
    // Reset conversation context
    fetch(`${API_BASE_URL}/api/reset`, {
        method: 'POST'
    }).then(() => {
        // Reset state panel
        updateStatePanel({
            intent: 'Initial Greeting',
            transactionId: '-',
            disputeType: '-'
        });
    }).catch(error => {
        console.error('Error resetting conversation:', error);
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



    function showOptions(options) {
        optionsContainer.innerHTML = '';
        if (!options || options.length === 0) return;
        
        // Check if these are transaction options
        const isTransactionList = options[0].includes('$') && options[0].includes('ID:');
        
        if (isTransactionList) {
            // Add header for transactions
            const header = document.createElement('div');
            header.classList.add('transaction-list-header');
            header.textContent = 'Here is the list. Which one do you need help with?';
            optionsContainer.appendChild(header);
        }
        
        options.forEach(option => {
            const button = document.createElement('button');
            button.classList.add('option-button');
            
            // Check if this is a dispute or transaction option
            const disputeMatch = option.match(/([^-]+) - \$(\d+\.\d+) \(([^)]+)\) \(ID: (DSP[^)]+)\)/);
            const transactionMatch = option.match(/([^-]+) - \$(\d+\.\d+) \(ID: (TX\d+)\)/);
            
            if (disputeMatch) {
                // Create dispute row with merchant, amount, and type
                const [_, merchant, amount, type, disputeId] = disputeMatch;
                
                const disputeRow = document.createElement('div');
                disputeRow.classList.add('dispute-row');
                
                const merchantDiv = document.createElement('div');
                merchantDiv.classList.add('dispute-merchant');
                merchantDiv.textContent = merchant;
                
                const amountDiv = document.createElement('div');
                amountDiv.classList.add('dispute-amount');
                amountDiv.textContent = `$${amount}`;
                
                const typeDiv = document.createElement('div');
                typeDiv.classList.add('dispute-type');
                typeDiv.textContent = type;
                
                disputeRow.appendChild(merchantDiv);
                disputeRow.appendChild(amountDiv);
                disputeRow.appendChild(typeDiv);
                
                button.appendChild(disputeRow);
                
                button.addEventListener('click', () => {
                    addMessage(`${merchant} - $${amount} (${type})`, 'user');
                    optionsContainer.innerHTML = '';
                    processUserMessage(`dispute_id:${disputeId}`);
                });
            } else if (transactionMatch) {
                // Create transaction row with merchant and amount
                const [_, merchant, amount, transactionId] = transactionMatch;
                
                const transactionRow = document.createElement('div');
                transactionRow.classList.add('transaction-row');
                
                const merchantDiv = document.createElement('div');
                merchantDiv.classList.add('transaction-merchant');
                merchantDiv.textContent = merchant;
                
                const amountDiv = document.createElement('div');
                amountDiv.classList.add('transaction-amount');
                amountDiv.textContent = `$${amount}`;
                
                transactionRow.appendChild(merchantDiv);
                transactionRow.appendChild(amountDiv);
                
                button.appendChild(transactionRow);
                
                button.addEventListener('click', () => {
                    addMessage(`${merchant} - $${amount}`, 'user');
                    optionsContainer.innerHTML = '';
                    processUserMessage(transactionId);
                });
            } else {
                // For non-transaction options
                button.textContent = option;
                button.addEventListener('click', () => {
                    addMessage(option, 'user');
                    optionsContainer.innerHTML = '';
                    processUserMessage(option);
                });
            }
            
            optionsContainer.appendChild(button);
        });
    }

    async function processUserMessage(message) {
        try {
            // Show loading state
            sendButton.disabled = true;
            userInput.disabled = true;
            
            console.log('Sending message:', message);
            // Make API call to backend
            const response = await fetch(`${API_BASE_URL}/api/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message })
            });

            console.log('Response status:', response.status);
            const responseText = await response.text();
            console.log('Response text:', responseText);

            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.status} ${responseText}`);
            }

            const data = JSON.parse(responseText);
            console.log('Parsed data:', data);
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Update conversation state panel
            updateStatePanel({
                intent: data.intent || '-',
                transactionId: data.context_updates?.transaction_id || currentTransactionId.textContent,
                disputeType: data.context_updates?.dispute_type || currentDisputeType.textContent
            });

            // Add bot response
            if (data.response) {
                addMessage(data.response, 'bot');
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
            bpEligibility.textContent = '-';
            fraudCollusion.textContent = '-';
            adjudicationOutcome.textContent = '-';
            payoutAmount.textContent = '-';
            return;
        }

        // Update BP Eligibility first as it determines other fields
        const eligibilityStatus = data.case.bp_eligibility_model.charAt(0).toUpperCase() + data.case.bp_eligibility_model.slice(1);
        bpEligibility.textContent = eligibilityStatus;
        bpEligibility.className = 'bo-value ' + (data.case.bp_eligibility_model === 'eligible' ? 'fraud-false' : 'fraud-true');

        if (data.case.bp_eligibility_model === 'ineligible') {
            // Set all other fields to N/A for ineligible cases
            fraudBuyer.textContent = 'N/A';
            fraudBuyer.className = 'bo-value';
            fraudSeller.textContent = 'N/A';
            fraudSeller.className = 'bo-value';
            fraudCollusion.textContent = 'N/A';
            fraudCollusion.className = 'bo-value';
            adjudicationOutcome.textContent = 'N/A';
            adjudicationOutcome.className = 'bo-value';
        } else {
            // Function to format risk value
            const formatRisk = (value) => {
                if (value === null || value === undefined) return '-';
                return (value * 100).toFixed(1) + '%';
            };

            // Function to get risk class
            const getRiskClass = (value, threshold) => {
                if (value === null || value === undefined) return '';
                return value * 100 > threshold ? 'fraud-true' : 'fraud-false';
            };

            // Update fraud buyer risk
            fraudBuyer.textContent = formatRisk(data.case.fraud_buyer);
            fraudBuyer.className = 'bo-value ' + getRiskClass(data.case.fraud_buyer, 70);
            
            // Update fraud seller risk
            fraudSeller.textContent = formatRisk(data.case.fraud_seller);
            fraudSeller.className = 'bo-value ' + getRiskClass(data.case.fraud_seller, 70);

            // Update fraud collusion risk
            fraudCollusion.textContent = formatRisk(data.case.fraud_dispute_collusion);
            fraudCollusion.className = 'bo-value ' + getRiskClass(data.case.fraud_dispute_collusion, 80);

            // Update adjudication outcome
            adjudicationOutcome.textContent = formatRisk(data.case.adjudication_case_outcome_model);
            adjudicationOutcome.className = 'bo-value ' + getRiskClass(data.case.adjudication_case_outcome_model, 50);

            // Update payout amount
            const amount = data.case.payout_sensitivity_model;
            payoutAmount.textContent = amount ? `$${parseFloat(amount).toFixed(2)}` : '-';
        }
    }
});
