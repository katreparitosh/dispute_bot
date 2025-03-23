// API Base URL
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

// Add initial bot message
addMessage("Hello! I'm your PayPal Dispute Assistant. I can help you file a new dispute or check the status of an existing one. How can I help you today?", 'bot');

// Handle user input
document.getElementById('userInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const message = this.value.trim();
        if (message) {
            processUserMessage(message);
        }
    }
});

document.getElementById('sendButton').addEventListener('click', function() {
    const message = document.getElementById('userInput').value.trim();
    if (message) {
        processUserMessage(message);
    }
});

function showOptions(options) {
    const container = document.getElementById('optionsContainer');
    container.innerHTML = '';
    
    if (!options || options.length === 0) {
        container.style.display = 'none';
        return;
    }
    
    options.forEach(option => {
        const button = document.createElement('button');
        button.className = 'option-button';
        button.textContent = option;
        button.onclick = () => {
            processUserMessage(option);
            container.style.display = 'none';
        };
        container.appendChild(button);
    });
    
    container.style.display = 'flex';
}

function hideOptions() {
    const container = document.getElementById('optionsContainer');
    container.style.display = 'none';
    container.innerHTML = '';
}

async function processUserMessage(message) {
    try {
        // Disable input while processing
        const userInput = document.getElementById('userInput');
        const sendButton = document.getElementById('sendButton');
        userInput.disabled = true;
        sendButton.disabled = true;

        // Show user message
        addMessage(message, 'user');
        
        // Clear input
        userInput.value = '';

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Response data:', data); // Add logging to help debug
        
        // Show bot's first response
        if (data.response) {
            addMessage(data.response, 'bot');
        }
        
        // If there's a second message, show it after a delay
        if (data.second_message) {
            setTimeout(() => {
                addMessage(data.second_message, 'bot');
            }, 3000);
        }
        
        // If there's a BO status message, show it as a follow-up message in the chat
        if (data.bo_status && data.bo_status.message) {
            // Add a small delay to make it feel more natural
            setTimeout(() => {
                addMessage(data.bo_status.message, 'bot');
            }, 1500);
        }
        
        // Show options if available
        if (data.options && data.options.length > 0) {
            showOptions(data.options);
        } else {
            hideOptions();
        }
        
        // If there's a BO status, update the panel
        if (data.bo_status) {
            console.log('BO Status:', data.bo_status); // Add logging for BO status
            updateBOPanel(data.bo_status);
        }

        // Update state panel
        if (data.context_updates) {
            updateStatePanel(data.context_updates);
        }
        
        // Show transaction table if needed
        if (data.show_transactions) {
            showTransactionTable();
        }
        
    } catch (error) {
        console.error('Error in processUserMessage:', error);
        addMessage('Sorry, there was an error processing your request.', 'bot');
    } finally {
        // Re-enable input
        userInput.disabled = false;
        sendButton.disabled = false;
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Reset conversation on page load
    fetch('/api/reset', { method: 'POST' })
        .catch(error => console.error('Error resetting conversation:', error));
});

// Function to show transaction table
async function showTransactionTable() {
    try {
        // Create or get transaction container
        let transactionContainer = document.getElementById('transactionContainer');
        if (!transactionContainer) {
            transactionContainer = document.createElement('div');
            transactionContainer.id = 'transactionContainer';
            transactionContainer.className = 'transaction-container';
            document.getElementById('chatMessages').appendChild(transactionContainer);
        }
        
        // Clear existing content
        transactionContainer.innerHTML = '<h3>Recent Transactions</h3>';
        
        // Fetch transactions from server
        const response = await fetch('/api/transactions');
        const transactions = await response.json();
        
        if (!transactions || transactions.length === 0) {
            transactionContainer.innerHTML += '<p>No transactions found.</p>';
            return;
        }
        
        // Create table
        const table = document.createElement('table');
        table.className = 'transaction-table';
        
        // Create header
        const header = document.createElement('tr');
        ['Transaction ID', 'Merchant', 'Amount', 'Date', 'Action'].forEach(text => {
            const th = document.createElement('th');
            th.textContent = text;
            header.appendChild(th);
        });
        table.appendChild(header);
        
        // Add transaction rows
        transactions.forEach(tx => {
            const row = document.createElement('tr');
            
            // Transaction ID
            const idCell = document.createElement('td');
            idCell.textContent = tx.transaction_id;
            row.appendChild(idCell);
            
            // Merchant
            const merchantCell = document.createElement('td');
            merchantCell.textContent = tx.merchant_seller;
            row.appendChild(merchantCell);
            
            // Amount
            const amountCell = document.createElement('td');
            amountCell.textContent = `$${parseFloat(tx.amount).toFixed(2)}`;
            amountCell.className = 'transaction-amount';
            row.appendChild(amountCell);
            
            // Date
            const dateCell = document.createElement('td');
            dateCell.textContent = tx.date;
            row.appendChild(dateCell);
            
            // Select button
            const actionCell = document.createElement('td');
            const selectBtn = document.createElement('button');
            selectBtn.textContent = 'Select';
            selectBtn.className = 'select-transaction-btn';
            selectBtn.onclick = () => {
                processUserMessage(tx.transaction_id);
                transactionContainer.style.display = 'none';
            };
            actionCell.appendChild(selectBtn);
            row.appendChild(actionCell);
            
            table.appendChild(row);
        });
        
        transactionContainer.appendChild(table);
        transactionContainer.style.display = 'block';
        
    } catch (error) {
        console.error('Error showing transactions:', error);
        addMessage('Sorry, there was an error loading transactions.', 'bot');
    }
}

// Function to update state panel with current context
function updateStatePanel(contextUpdates) {
    if (!contextUpdates) return;
    
    // Update intent
    if (contextUpdates.intent) {
        document.getElementById('currentIntent').textContent = contextUpdates.intent;
    }
    
    // Update transaction ID
    if (contextUpdates.transaction_id) {
        document.getElementById('currentTransactionId').textContent = contextUpdates.transaction_id;
    }
    
    // Update dispute type
    if (contextUpdates.dispute_type) {
        document.getElementById('currentDisputeType').textContent = contextUpdates.dispute_type;
    }
}

// Function to update BO panel with case details
function updateBOPanel(boStatus) {
    try {
        if (!boStatus || boStatus.status !== 'success' || !boStatus.case) {
            console.log('Invalid BO status data:', boStatus);
            return;
        }
        
        const case_data = boStatus.case;
        
        // Helper function to safely update element text content
        function safelyUpdateElement(id, value, formatter = (v) => v) {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value != null ? formatter(value) : 'N/A';
            } else {
                console.warn(`Element with id "${id}" not found`);
            }
        }
        
        // Update fraud metrics
        safelyUpdateElement('fraudBuyer', case_data.buyer_fraud_score, v => v.toFixed(2));
        safelyUpdateElement('fraudSeller', case_data.seller_fraud_score, v => v.toFixed(2));
        safelyUpdateElement('bpEligibility', case_data.bp_eligibility);
        safelyUpdateElement('payoutAmount', case_data.payout_amount, v => `$${v.toFixed(2)}`);
        safelyUpdateElement('fraudCollusion', case_data.dispute_collusion_score, v => v.toFixed(2));
        safelyUpdateElement('adjudicationOutcome', case_data.adjudication_outcome_score, v => v.toFixed(2));
        
        // Make the BO insights panel visible if it exists
        const insightsPanel = document.getElementById('boInsightsPanel');
        if (insightsPanel) {
            insightsPanel.style.display = 'block';
        } else {
            console.warn('BO Insights Panel element not found');
            return; // Exit if no panel exists
        }
        
        // Update progress if progress elements exist
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        
        if (!progressBar || !progressText) {
            console.warn('Progress bar or text elements not found');
            return;
        }
        
        // Function to safely add class to element
        function safelyAddClass(id, className) {
            const element = document.getElementById(id);
            if (element) {
                element.classList.add(className);
            }
        }
        
        // Function to safely remove all classes and add new ones
        function safelyResetAndAddClasses(element, ...classNames) {
            if (element) {
                element.className = ''; // Clear existing classes
                element.classList.add(...classNames);
            }
        }
        
        // Apply appropriate styling based on status type
        if (case_data.status_type === 'instant_payout') {
            // Instant Approval
            progressBar.style.width = '100%';
            safelyResetAndAddClasses(progressBar, 'progress-bar', 'bg-success');
            progressText.textContent = 'Instant Approval - 100%';
            
            // Highlight the key metrics that led to instant approval
            safelyAddClass('fraudBuyerLabel', 'text-success');
            safelyAddClass('fraudSellerLabel', 'text-success');
            safelyAddClass('bpEligibilityLabel', 'text-success');
            safelyAddClass('adjudicationOutcomeLabel', 'text-success');
            
        } else if (case_data.status_type === 'decline') {
            // Declined
            progressBar.style.width = '100%';
            safelyResetAndAddClasses(progressBar, 'progress-bar', 'bg-danger');
            progressText.textContent = 'Declined - 100%';
            
            // Highlight the metrics that led to decline
            if (case_data.bp_eligibility !== 'eligible') {
                safelyAddClass('bpEligibilityLabel', 'text-danger');
            }
            if (case_data.buyer_fraud_score > 0.7) {
                safelyAddClass('fraudBuyerLabel', 'text-danger');
            }
            
        } else {
            // Wait for Seller Response (default)
            progressBar.style.width = '50%';
            safelyResetAndAddClasses(progressBar, 'progress-bar', 'bg-info');
            progressText.textContent = 'Waiting for Seller Response - 50%';
        }
    } catch (error) {
        console.error('Error in updateBOPanel:', error);
        // Don't throw the error further to prevent it from affecting the chat flow
    }
}
