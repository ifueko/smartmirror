document.addEventListener('DOMContentLoaded', () => {
  const chatWindow = document.getElementById('chat-window');
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const micBtn = document.getElementById('btn-mic');
  const autosendCheckbox = document.getElementById('autosend-checkbox');

  function getCSRFToken() {
    const name = 'csrftoken';
    const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]+)'));
    return match ? match[2] : '';
  }

  // ———————— Submit handler ————————
  chatForm.addEventListener('submit', async e => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    // user bubble
    const userBubble = document.createElement('div');
    userBubble.className = 'chat-bubble user';
    userBubble.textContent = text;
    chatWindow.appendChild(userBubble);
    chatWindow.scrollTop = chatWindow.scrollHeight;
    chatInput.value = '';

    try {
      const resp = await fetch('chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
          message: text
        })
      });
      const data = await resp.json();
      console.log('Response:', data);

      // bot bubble
      if (data.error) {
        const errorBubble = document.createElement('div');
        errorBubble.className = 'chat-bubble bot error'; // You might want a specific class for error styling
        errorBubble.textContent = data.error;
        chatWindow.appendChild(errorBubble);
      } else if (data.response) {
        // Check if data.response is an array (for multi-line responses)
        if (Array.isArray(data.response)) {
          data.response.forEach(line => {
            console.log(line)
            console.log(data.response[line])
            // Optionally, you can skip adding a bubble for empty or whitespace-only lines
            if (line.trim() === '') {
              return;
            }
            const botBubble = document.createElement('div');
            botBubble.className = 'chat-bubble bot'; // Your existing class for bot messages
            botBubble.textContent = line; // Set the text content to the current line
            chatWindow.appendChild(botBubble);
          });
        } else if (typeof data.response === 'string') {
          // Fallback: If data.response is just a single string (not an array)
          // This handles cases where the backend might sometimes send a single string
          if (data.response.trim() === '') return; // Skip if the single response is empty

          const botBubble = document.createElement('div');
          botBubble.className = 'chat-bubble bot';
          botBubble.textContent = data.response;
          chatWindow.appendChild(botBubble);
        } else {
          // Handle cases where data.response is not an array or a string (unexpected format)
          console.warn("Received data.response in an unexpected format: ", data.response);
          const fallbackBubble = document.createElement('div');
          fallbackBubble.className = 'chat-bubble bot';
          fallbackBubble.textContent = 'Received an unusually formatted response.';
          chatWindow.appendChild(fallbackBubble);
        }
      } else {
        // Handle cases where there's neither a response nor an error (e.g., empty reply)
        const emptyBubble = document.createElement('div');
        emptyBubble.className = 'chat-bubble bot';
        emptyBubble.textContent = '[Bot provided no additional text]'; // Or any placeholder
        chatWindow.appendChild(emptyBubble);
      }

      chatWindow.scrollTop = chatWindow.scrollHeight;

    } catch (err) {
      console.error('Fetch error:', err);
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
