function initializeChatUI({
    chatWindowId = 'chat-window',
    confirmationModalId = 'confirmationModal',
    confirmationMessageId = 'confirmationDetails',
    btnConfirmActionId = 'confirmConfirmationBtn',
    btnConfirmCancelId = 'denyConfirmationBtn',
    sendBackendRequestFn 
}) {

    const chatWindow = document.getElementById(chatWindowId);
    const confirmationModalElement = document.getElementById(confirmationModalId);
    const confirmationModal = confirmationModalElement ? new bootstrap.Modal(confirmationModalElement) : null;
    const confirmationMessageP = document.getElementById(confirmationMessageId);
    const btnConfirmAction = document.getElementById(btnConfirmActionId);
    const btnConfirmCancel = document.getElementById(btnConfirmCancelId);

    let pendingConfirmationAction = null;

    if (!chatWindow || !confirmationModal || !confirmationMessageP || !btnConfirmAction || !btnConfirmCancel) {
        console.error("Chat UI Handler: One or more essential DOM elements are missing. Confirmation modal might not work.");
        // return null; // Or throw an error
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

    function displayServerResponse(data) {
        if (!chatWindow) { // Basic check
            console.error("Chat window not found for displaying server response.");
            return;
        }
        console.log('Chat Response Data (UI Handler):', data);

        if (data.error) {
            addMessageToChat(data.error, 'bot error');
        } else if (data.needs_confirmation && data.action_details) {
            pendingConfirmationAction = data.action_details;
            if (confirmationMessageP) confirmationMessageP.textContent = data.action_details.description || "Please confirm this action.";
            if (confirmationModal) confirmationModal.show();
            addMessageToChat(data.response && data.response.length > 0 ? data.response.join('\n') : (data.action_details.description || "I need you to confirm an action. Please see the popup."), 'bot');
        } else if (data.action_confirmed_executed) {
            if (confirmationModal && confirmationModal._isShown) {
                confirmationModal.hide();
            }
            const message = data.response && data.response.length > 0 ? data.response.join('\n') : "Action completed successfully.";
            addMessageToChat(message, 'bot');

            if (data.updated_data) {
                let updatedDataText = "<strong>Updated Information:</strong><br>";
                let hasData = false;
                // (Same updated_data rendering logic as in previous voice_chat.js example)
                if (data.updated_data.tasks && data.updated_data.tasks.length > 0) { /* ... */ hasData = true; }
                if (data.updated_data.habits) {  /* ... */ hasData = true; }
                if (data.updated_data.events && data.updated_data.events.length > 0) { /* ... */ hasData = true; }
                if (hasData) addMessageToChat(updatedDataText, 'bot', true);
            }
            pendingConfirmationAction = null;
        } else if (data.response) {
            const responseText = Array.isArray(data.response) ? data.response.join('\n') : (typeof data.response === 'string' ? data.response : "[Bot provided no clear response]");
            addMessageToChat(responseText.trim() || "[Bot provided no additional text]", 'bot');
            
            if (data.updated_data) { // For non-confirmation flows
                 // (Same updated_data rendering logic)
                 let updatedDataText = "<strong>Current Information:</strong><br>";
                 // ...
                 addMessageToChat(updatedDataText, 'bot', true);
            }
        } else {
            addMessageToChat("[Bot provided no clear response]", 'bot');
        }
    }

    if (btnConfirmAction && sendBackendRequestFn) {
        btnConfirmAction.addEventListener('click', async () => {
            if (pendingConfirmationAction) {
                addMessageToChat(`Yes, confirm: ${pendingConfirmationAction.description.substring(0, 50)}...`, 'user');
                try {
                    const responseData = await sendBackendRequestFn({
                        confirmed_action_details: pendingConfirmationAction
                    });
                    displayServerResponse(responseData);
                } catch (err) {
                    console.error('Confirmation Fetch error (UI Handler):', err);
                    addMessageToChat('Error sending confirmation.', 'bot error');
                    if (confirmationModal && confirmationModal._isShown) {
                        confirmationModal.hide();
                    }
                }
                pendingConfirmationAction = null;
            }
        });
    }

    if (btnConfirmCancel) {
        btnConfirmCancel.addEventListener('click', () => {
            if (pendingConfirmationAction) {
                addMessageToChat("Okay, I won't do that.", 'bot');
                pendingConfirmationAction = null;
            }
            // Modal hides via data-bs-dismiss
        });
    }
    
    // Return an object containing functions that the specific ASR scripts can call
    return {
        addMessageToChat,
        displayServerResponse
        // You might not need to expose pendingConfirmationAction if all modal logic is internal
    };
}
