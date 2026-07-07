const API_URL = 'http://localhost:8000/advice';
const messagesDiv = document.getElementById('messages');
const routeDisplay = document.getElementById('route-display');
const routeText = document.getElementById('route-text');
const queryInput = document.getElementById('query-input');
const voiceBtn = document.getElementById('voice-btn');
const sendBtn = document.getElementById('send-btn');
const statusDiv = document.getElementById('status');
const langSelect = document.getElementById('lang-select');

let recognition;
let synthesis = window.speechSynthesis;

// Map our dropdown to speech synthesis language codes
const speechLangMap = {
    'en': 'en-US',
    'es': 'es-ES',
    'fr': 'fr-FR',
    'de': 'de-DE',
    'zh': 'zh-CN',
    'ar': 'ar-SA',
    'ru': 'ru-RU'
};

// Initialize speech recognition if available
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        queryInput.value = transcript;
        statusDiv.textContent = 'Ready';
        statusDiv.className = 'status ready';
    };

    recognition.onend = () => {
        statusDiv.textContent = 'Ready';
        statusDiv.className = 'status ready';
    };

    recognition.onerror = (event) => {
        statusDiv.textContent = 'Speech recognition error: ' + event.error;
        statusDiv.className = 'status listening';
        console.error('Speech recognition error:', event);
    };
} else {
    voiceBtn.disabled = true;
    voiceBtn.title = 'Speech recognition not supported in this browser';
    voiceBtn.setAttribute('aria-disabled', 'true');
}

function speakText(text) {
    if (!('speechSynthesis' in window)) {
        console.warn('Speech synthesis not supported');
        return;
    }
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const selectedLang = langSelect.value;
    utterance.lang = speechLangMap[selectedLang] || 'en-US';
    utterance.rate = 0.9; 
    utterance.volume = 0.9;
    utterance.onend = () => {
        statusDiv.textContent = 'Ready';
        statusDiv.className = 'status ready';
    };
    utterance.onerror = (event) => {
        console.error('Speech synthesis error:', event);
        statusDiv.textContent = 'Speech error';
        statusDiv.className = 'status listening';
        setTimeout(() => {
            statusDiv.textContent = 'Ready';
            statusDiv.className = 'status ready';
        }, 2000);
    };
    speechSynthesis.speak(utterance);
}

function addMessage(text, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + (isUser ? 'user-message' : 'bot-message');

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;

    if (!isUser) {
        const speakerBtn = document.createElement('button');
        speakerBtn.className = 'speaker-btn';
        speakerBtn.innerHTML = '🔊';
        speakerBtn.title = 'Listen';
        speakerBtn.setAttribute('aria-label', 'Listen to message');
        speakerBtn.onclick = () => speakText(text);
        messageDiv.appendChild(speakerBtn);
    }

    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    if (!isUser && speechSynthesis) {
        setTimeout(() => speakText(text), 300);
    }
}

function showRoute(route) {
    if (route && route.length > 0) {
        routeText.textContent = route.join(' → ');
        routeDisplay.style.display = 'block';
        routeDisplay.setAttribute('aria-live', 'polite');
    } else {
        routeDisplay.style.display = 'none';
        routeDisplay.removeAttribute('aria-live');
    }
}

async function sendQuery() {
    const query = queryInput.value.trim();
    const selectedLang = langSelect.value;
    if (!query) return;

    queryInput.disabled = true;
    sendBtn.disabled = true;
    voiceBtn.disabled = true;
    statusDiv.textContent = 'Thinking...';
    statusDiv.className = 'status thinking';

    addMessage(query, true);
    queryInput.value = '';

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                language: selectedLang,
                location: 'Gate_A' 
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        addMessage(data.advice);
        showRoute(data.route);

    } catch (error) {
        console.error('Error:', error);
        addMessage('Sorry, I encountered an error. Please try again.');
    } finally {
        queryInput.disabled = false;
        sendBtn.disabled = false;
        voiceBtn.disabled = false;
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

voiceBtn.addEventListener('click', () => {
    if (!recognition) {
        alert('Speech recognition not available in this browser');
        return;
    }
    const selectedLang = langSelect.value;
    recognition.lang = speechLangMap[selectedLang] || 'en-US';
    statusDiv.textContent = 'Listening...';
    statusDiv.className = 'status listening';
    recognition.start();
});

queryInput.focus();

document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        speechSynthesis.cancel();
    }
});
