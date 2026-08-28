const API_URL = '/log_complaint';
const messagesDiv = document.getElementById('messages');
const urgencyDisplay = document.getElementById('urgency-display');
const urgencyText = document.getElementById('urgency-text');
const categorySelect = document.getElementById('category-select');
const locationInput = document.getElementById('location-input');
const contactInput = document.getElementById('contact-input');
const queryInput = document.getElementById('query-input');
const sendBtn = document.getElementById('send-btn');
const statusDiv = document.getElementById('status');

function addMessage(text, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + (isUser ? 'user-message' : 'bot-message');

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;

    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showUrgency(level) {
    if (level && level !== 'none') {
        urgencyText.textContent = level;
        urgencyDisplay.style.display = 'block';
        urgencyDisplay.setAttribute('aria-live', 'polite');
    } else {
        urgencyText.textContent = '';
        urgencyDisplay.style.display = 'none';
        urgencyDisplay.removeAttribute('aria-live');
    }
}

async function sendQuery() {
    const query = queryInput.value.trim();
    const selectedCat = categorySelect.value;
    const selectedLocation = locationInput.value.trim();
    const selectedContact = contactInput.value.trim();
    if (!query || !selectedCat) return;

    queryInput.disabled = true;
    sendBtn.disabled = true;
    statusDiv.textContent = 'Thinking...';
    statusDiv.className = 'status thinking';

    addMessage(query, true);
    queryInput.value = '';

    try {
        const body = {
            query: query,
            category: selectedCat,
            location: selectedLocation,
            contact: selectedContact
        };
        console.debug('Sending complaint request', body);
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        });

        console.debug('Complaint response status:', response.status);
        if (!response.ok) {
            const text = await response.text();
            console.error('Complaint request failed body:', text);
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.debug('Complaint response data:', data);
        addMessage(data.advice || data.status);
        showUrgency(data.urgency);
        queryInput.value = '';

    } catch (error) {
        console.error('Error:', error);
        addMessage('Sorry, I encountered an error. Please try again.');
    } finally {
        queryInput.disabled = false;
        sendBtn.disabled = false;
        statusDiv.textContent = 'Ready';
        statusDiv.className = 'status ready';
        queryInput.focus();
    }
}

sendBtn.addEventListener('click', sendQuery);

queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendQuery();
    }
});

document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
    }
});

window.addEventListener('error', (event) => {
    console.error('Global runtime error:', event.error || event.message, event);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
});