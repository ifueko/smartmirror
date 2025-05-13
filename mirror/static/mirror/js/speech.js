document.addEventListener('DOMContentLoaded', () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.error('🔥 SpeechRecognition API not supported in this browser.');
    document.getElementById('btn-mic').style.display = 'none';
    return;
  }

  const recognizer = new SpeechRecognition();
  recognizer.lang = 'en-US';
  recognizer.interimResults = false;
  recognizer.maxAlternatives = 1;

  recognizer.onerror = (e) => {
    console.error('🎙️ SpeechRecognition error:', e.error, e);
  };
  recognizer.onnomatch = () => {
    console.warn('🎙️ SpeechRecognition no match');
  };

  const micBtn = document.getElementById('btn-mic');
  let listening = false;

  micBtn.addEventListener('click', () => {
    if (!listening) {
      try {
        recognizer.start();
      } catch (err) {
        console.error('⚠️ Failed to start recognition:', err);
      }
    } else {
      recognizer.stop();
    }
  });

  recognizer.addEventListener('start', () => {
    listening = true;
    micBtn.classList.add('text-danger');
    micBtn.title = "Listening… click again to stop";
  });

  recognizer.addEventListener('end', () => {
    listening = false;
    micBtn.classList.remove('text-danger');
    micBtn.title = "Speak your message";
  });

  recognizer.addEventListener('result', (ev) => {
    const transcript = ev.results[0][0].transcript;
    console.log('🎙️ Recognized:', transcript);
    const input = document.getElementById('chat-input');
    input.value = transcript;
    // auto-submit:
    //document.getElementById('chat-form').dispatchEvent(new Event('submit', { cancelable: true }));
  });
});
