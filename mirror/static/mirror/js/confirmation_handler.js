const UI_CONFIRM_POLL_INTERVAL_MS = 3500; // Poll a bit less frequently than MCP server polls this
const CONFIRMATION_API_APP_BASE_URL = ""; // Relative URL if JS is served by same Django app

let currentActiveConfirmationActionId = null;
let confirmationModalInstance = null; // To store Bootstrap modal instance

// Function to create and show the Bootstrap modal
function showUiConfirmationModal(confirmation) {
    if (currentActiveConfirmationActionId) {
        console.warn("Confirmation modal already active for:", currentActiveConfirmationActionId);
        return; // Prevent multiple modals if polling is too fast or UI is slow
    }
    currentActiveConfirmationActionId = confirmation.action_id;

    // Remove any existing modal first (simple cleanup)
    const existingModal = document.getElementById('confirmationActionModal');
    if (existingModal) {
        existingModal.remove();
    }

    // Create modal HTML structure (Bootstrap 5)
    const modalHtml = `
        <div class="modal fade" id="confirmationActionModal" tabindex="-1" aria-labelledby="confirmationModalLabel" aria-hidden="true" data-bs-backdrop="static" data-bs-keyboard="false">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="confirmationModalLabel">Action Confirmation</h5>
                        </div>
                    <div class="modal-body">
                        <p id="confirmationDescription"></p>
                        <div id="confirmationDetailsContainer" style="max-height: 200px; overflow-y: auto; background-color: #333; padding: 10px; border-radius: 5px; margin-top:10px; display:none;">
                            <h6>Details:</h6>
                            <pre id="confirmationDetails" style="white-space: pre-wrap; word-break: break-all;"></pre>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-danger" id="denyConfirmationBtn">Deny</button>
                        <button type="button" class="btn btn-success" id="confirmConfirmationBtn">Confirm</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);

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
            // modalElement.remove(); // Or just ensure it's properly disposed by Bootstrap
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
    // currentActiveConfirmationActionId is already nulled by hideUiConfirmationModal
}

async function pollForUiConfirmations() {
    if (currentActiveConfirmationActionId) {
        // console.log("UI confirmation modal is already active. Skipping UI poll.");
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
            // Process the first pending confirmation. A more complex UI could queue them.
            showUiConfirmationModal(confirmations[0]);
        }
    } catch (error) {
        console.error("Failed to fetch or process pending UI confirmations:", error);
    }
}

function getCsrfToken() {
    // Standard Django way to get CSRF token from cookie for AJAX POST
    const csrfTokenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (csrfTokenInput) {
        return csrfTokenInput.value;
    }
    // Fallback for cookies if input field is not present (less common for AJAX now)
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.split('=').map(c => c.trim());
        if (name === 'csrftoken') {
            return value;
        }
    }
    console.warn('CSRF token not found.');
    return null; 
}


// Start polling when the script loads
console.log("UI Confirmation Handler script loaded and polling started.");
setInterval(pollForUiConfirmations, UI_CONFIRM_POLL_INTERVAL_MS);
