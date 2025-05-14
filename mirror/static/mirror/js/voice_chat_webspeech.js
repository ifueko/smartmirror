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
            uiHandler.displayServerResponse(data);
        } catch (err) {
            console.error('Fetch error in voice_chat_webspeech.js:', err);
            uiHandler.addMessageToChat('Error connecting to chat service.', 'bot error');
        }
    });
  // ———————— Speech Recognition setup ————————
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.error('SpeechRecognition API not supported');
    micBtn.style.display = 'none';
    return;
  }

  const recognizer = new SpeechRecognition();
  recognizer.lang = 'en-US';
  recognizer.interimResults = false;
  recognizer.maxAlternatives = 1;

  let listening = false;

  // toggle recording
  micBtn.addEventListener('click', () => {
    if (!listening) recognizer.start();
    else recognizer.stop();
  });

  recognizer.onstart = () => {
    listening = true;
    micBtn.classList.add('recording');
  };

  recognizer.onspeechend = () => {
    recognizer.stop();
  };

  recognizer.onend = () => {
    listening = false;
    micBtn.classList.remove('recording');
    micBtn.blur();
  };

  recognizer.onresult = ev => {
    const transcript = ev.results[0][0].transcript;
    console.log('🎙️ Recognized:', transcript);
    chatInput.value = transcript;

    if (autosendCheckbox && autosendCheckbox.checked) {
      // submit programmatically
      if (chatForm.requestSubmit) chatForm.requestSubmit();
      else chatForm.dispatchEvent(new Event('submit', {
        cancelable: true
      }));
    }
  };

  recognizer.onerror = e => {
    console.error('SpeechRecognition error:', e.error);
    recognizer.stop();
  };
});
