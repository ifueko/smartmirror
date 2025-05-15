const UI_CONFIRM_POLL_INTERVAL_MS = 3500;
const CONFIRMATION_API_APP_BASE_URL = "";
let currentActiveConfirmationActionId = null;
let confirmationModalInstance = null;

function showUiConfirmationModal(confirmation) {
    if (currentActiveConfirmationActionId) {
        console.warn("Confirmation modal already active for:", currentActiveConfirmationActionId);
        return;
    }
    currentActiveConfirmationActionId = confirmation.action_id;
    // Populate modal content
    document.getElementById('confirmationDescription').textContent = confirmation.description;
    const detailsContainer = document.getElementById('confirmationDetailsContainer');
    const detailsPre = document.getElementById('confirmationDetails');

    if (confirmation.details && Object.keys(confirmation.details).length > 0) {
        detailsPre.textContent = JSON.stringify(confirmation.details, null, 2);
        detailsContainer.style.display = 'block';
    } else {
        detailsContainer.style.display = 'none';
    }

    // Get Bootstrap modal instance and show it
    const modalElement = document.getElementById('confirmationActionModal');
    confirmationModalInstance = new bootstrap.Modal(modalElement);

    // Add event listeners for buttons
    document.getElementById('confirmConfirmationBtn').onclick = () => handleUiDecision(confirmation.action_id, true);
    document.getElementById('denyConfirmationBtn').onclick = () => handleUiDecision(confirmation.action_id, false);
    
    confirmationModalInstance.show();
}

function hideUiConfirmationModal() {
    if (confirmationModalInstance) {
        confirmationModalInstance.hide();
        // Bootstrap's hide method might not immediately remove from DOM or nullify instance.
        // For robust cleanup if re-showing immediately:
        const modalElement = document.getElementById('confirmationActionModal');
        if (modalElement) {
             // Remove event listeners to prevent multiple bindings if modal is reused
            const confirmBtn = document.getElementById('confirmConfirmationBtn');
            if (confirmBtn) confirmBtn.onclick = null;
            const denyBtn = document.getElementById('denyConfirmationBtn');
            if (denyBtn) denyBtn.onclick = null;
        }
    }
    confirmationModalInstance = null; // Clear instance
    currentActiveConfirmationActionId = null; // Allow next poll to show a modal
}

async function handleUiDecision(actionId, wasConfirmed) {
    hideUiConfirmationModal(); // Hide modal immediately
    console.log(`User decision for ${actionId}: ${wasConfirmed ? 'CONFIRMED' : 'DENIED'}`);

    try {
        const response = await fetch(`${CONFIRMATION_API_APP_BASE_URL}/api/submit_ui_confirmation/${actionId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(), // Important for Django POST requests
            },
            body: JSON.stringify({ confirmed: wasConfirmed }),
        });
        
        if (!response.ok) {
            const errorData = await response.text();
            console.error(`Error submitting UI decision for ${actionId}:`, response.statusText, errorData);
            // Optionally, notify user via an alert or a less intrusive UI element
        } else {
            const result = await response.json();
            console.log(`UI Decision for ${actionId} submitted to server:`, result);
        }
    } catch (error) {
        console.error(`Failed to submit UI decision for ${actionId}:`, error);
    }
}

async function pollForUiConfirmations() {
    if (currentActiveConfirmationActionId) {
        return;
    }

    try {
        const response = await fetch(`${CONFIRMATION_API_APP_BASE_URL}/api/get_pending_ui_confirmations`);
        if (!response.ok) {
            console.error("Error fetching pending UI confirmations:", response.statusText);
            return;
        }
        console.log(response);
        const confirmations = await response.json();

        if (confirmations && confirmations.length > 0) {
            showUiConfirmationModal(confirmations[0]);
        }
    } catch (error) {
        console.error("Failed to fetch or process pending UI confirmations:", error);
    }
}

function getCsrfToken() {
    const csrfTokenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return csrfTokenInput.value;
}

// Start polling when the script loads
console.log("UI Confirmation Handler script loaded and polling started.");
setInterval(pollForUiConfirmations, UI_CONFIRM_POLL_INTERVAL_MS);
