document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const optionsContainer = document.getElementById('optionsContainer');

    // Initial bot message
    addMessage("Hello! I'm your PayPal Dispute Assistant. How can I help you today?", 'bot');

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
            const response = await fetch('http://localhost:3000/api/chat', {
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
            
            // Add bot response
            if (data.message) {
                addMessage(data.message, 'bot');
            }

            // Show options if available
            if (data.options) {
                showOptions(data.options);
            }

        } catch (error) {
            console.error('Error:', error);
            addMessage('Sorry, I encountered an error. Please try again later.', 'bot');
        } finally {
            // Reset loading state
            sendButton.disabled = false;
            userInput.disabled = false;
        }
    }
});
