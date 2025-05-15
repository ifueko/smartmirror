function initializeChatUI({
    chatWindowId = 'chat-window',
    sendBackendRequestFn
}) {
    const chatWindow = document.getElementById(chatWindowId);
    let pendingConfirmationAction = null;

    if (!chatWindow) {
        console.error("Chat UI Handler: chat window not found.");
    }

    function addMessageToChat(messageText, className = 'bot', isRawHtml = false) {
        if (!chatWindow) return;
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${className}`;
        if (isRawHtml) {
            bubble.innerHTML = messageText;
        } else {
            bubble.textContent = messageText;
        }
        chatWindow.appendChild(bubble);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }
    return {addMessageToChat};
}

document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const micBtn = document.getElementById('btn-mic');
    const autosendCheckbox = document.getElementById('autosend-checkbox');

    function getCSRFToken() {
        const name = 'csrftoken';
        const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]+)'));
        return match ? match[2] : '';
    }

    // Function to send data to the backend
    async function sendHttpRequest(payload) {
        const resp = await fetch('chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify(payload)
        });
        return await resp.json();
    }
    
    const uiHandler = initializeChatUI({
        sendBackendRequestFn: sendHttpRequest
    });

    if (!uiHandler) {
        console.error("Failed to initialize Chat UI Handler in voice_chat_webspeech.js");
        return;
    }

    // Submit handler
    chatForm.addEventListener('submit', async e => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;

        uiHandler.addMessageToChat(text, 'user');
        chatInput.value = '';
        try {
            const data = await sendHttpRequest({ message: text });
            console.log(data)
            for (var i = 0; i < data.response.length; i++) {
                uiHandler.addMessageToChat(data.response[i], 'bot');
            }
        } catch (err) {
            console.error('Fetch error in voice_chat.js:', err);
           uiHandler.addMessageToChat(`Error: ${err}`, 'bot error');
        }
    });
});
