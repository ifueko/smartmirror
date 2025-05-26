// === Chat UI Handler ===
function initializeChatUI({
    chatWindowId = 'chat-window',
}) {
    const chatWindow = document.getElementById(chatWindowId);
    if (!chatWindow) {
        console.error("Chat UI Handler: chat window not found.");
    }

    function addMessageToChat(messageText, className = 'bot', isRawHtml = false) {
        if (!chatWindow) return;
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${className}`;
        bubble[isRawHtml ? 'innerHTML' : 'textContent'] = messageText;
        chatWindow.appendChild(bubble);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    return { addMessageToChat };
}

// === Confirmation Modal Handler ===
let currentActiveConfirmationActionId = null;
let confirmationModalInstance = null;
let pollingInterval = null;
let thoughtPollingInterval = null;

function showUiConfirmationModal(confirmation) {
    if (currentActiveConfirmationActionId) return;
    currentActiveConfirmationActionId = confirmation.action_id;

    document.getElementById('confirmationDescription').textContent = confirmation.description;
    const detailsContainer = document.getElementById('confirmationDetailsContainer');
    const detailsPre = document.getElementById('confirmationDetails');

    if (confirmation.details && Object.keys(confirmation.details).length > 0) {
        detailsPre.textContent = JSON.stringify(confirmation.details, null, 2);
        detailsContainer.style.display = 'block';
    } else {
        detailsContainer.style.display = 'none';
    }

    const modalElement = document.getElementById('confirmationActionModal');
    confirmationModalInstance = new bootstrap.Modal(modalElement);
    document.getElementById('confirmConfirmationBtn').onclick = () => handleUiDecision(confirmation.action_id, true);
    document.getElementById('denyConfirmationBtn').onclick = () => handleUiDecision(confirmation.action_id, false);
    confirmationModalInstance.show();
}

function hideUiConfirmationModal() {
    if (confirmationModalInstance) {
        confirmationModalInstance.hide();
        const confirmBtn = document.getElementById('confirmConfirmationBtn');
        const denyBtn = document.getElementById('denyConfirmationBtn');
        if (confirmBtn) confirmBtn.onclick = null;
        if (denyBtn) denyBtn.onclick = null;
    }
    confirmationModalInstance = null;
    currentActiveConfirmationActionId = null;
}

async function handleUiDecision(actionId, wasConfirmed) {
    hideUiConfirmationModal();
    try {
        await fetch(`/api/submit_ui_confirmation/${actionId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ confirmed: wasConfirmed }),
        });
    } catch (error) {
        console.error(`Failed to submit UI decision:`, error);
    }
}

async function pollForUiConfirmations(addMessageToChat) {
    if (currentActiveConfirmationActionId) return;

    try {
        const response = await fetch(`/api/get_pending_ui_confirmations`);
        if (!response.ok) return;

        const confirmations = await response.json();
        if (confirmations && confirmations.length > 0) {
            showUiConfirmationModal(confirmations[0]);
        }
    } catch (error) {
        console.error("Error polling UI confirmations:", error);
    }
}

function startPolling(addMessageToChat) {
    if (!pollingInterval) {
        pollingInterval = setInterval(() => pollForUiConfirmations(addMessageToChat), 500);
        console.log("Polling started");
    }
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
        console.log("Polling stopped");
    }
}

function showThoughtBubble(text) {
    const box = document.getElementById("thought-bubble");
    const textEl = document.getElementById("thought-text");
    if (box && textEl) {
        textEl.textContent = text;
        box.classList.remove("d-none");
    }
}

function hideThoughtBubble() {
    const box = document.getElementById("thought-bubble");
    if (box) {
        box.classList.add("d-none");
    }
}

async function pollForThoughts() {
    let data = null;
    try {
        const response = await fetch(`/api/get_pending_thoughts`);
        data = await response.json();
        console.log(data)
        if (data && data.thoughts) {
            for (var i = 0; i < data.thoughts.length; i++) {
                const thought = data.thoughts[i];
                showThoughtBubble(thought);
            }
        }
    } catch (err) {
        console.warn("Thought poll error:", err);
    }
}

function startThoughtPolling() {
    if (!thoughtPollingInterval) {
        thoughtPollingInterval = setInterval(pollForThoughts, 250);
    }
}

function stopThoughtPolling() {
    if (thoughtPollingInterval) {
        clearInterval(thoughtPollingInterval);
        thoughtPollingInterval = null;
        hideThoughtBubble();
    }
}

function getCsrfToken() {
    const csrfTokenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return csrfTokenInput?.value || '';
}

// === Event Binding on DOM Load ===
document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const uiHandler = initializeChatUI({ chatWindowId: 'chat-window' });

    async function sendHttpRequest(payload) {
        const resp = await fetch('chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify(payload)
        });
        return await resp.json();
    }


    chatForm.addEventListener('submit', async e => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;

        uiHandler.addMessageToChat(text, 'user');
        chatInput.value = '';

        try {
            startPolling(uiHandler.addMessageToChat);
            startThoughtPolling();
            const data = await sendHttpRequest({ message: text });
            if (data.response && Array.isArray(data.response)) {
                data.response.forEach(r => uiHandler.addMessageToChat(r, 'bot'));
            }
            stopPolling();
            stopThoughtPolling();
        } catch (err) {
            console.error('Chat error:', err);
            uiHandler.addMessageToChat(`Error: ${err}`, 'bot error');
            stopPolling();
            stopThoughtPolling();
        }
    });
});
