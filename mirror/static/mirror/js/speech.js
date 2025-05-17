document.addEventListener('DOMContentLoaded', () => {
  // UI elements
  const micBtn      = document.getElementById('btn-mic');
  const inputField  = document.getElementById('chat-input');
  const sendBtn     = document.getElementById('send-btn');
  const chatForm    = document.getElementById('chat-form');
  const autosendChk = document.getElementById('autosend');

  // State holders
  let audioContext, processor, sourceNode, mediaStream, socket;
  let listening = false;

  micBtn.addEventListener('click', async () => {
    if (!listening) {
      // —— START RECORDING ——
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContext = new AudioContext();
      processor    = audioContext.createScriptProcessor(4096, 1, 1);
      sourceNode   = audioContext.createMediaStreamSource(mediaStream);
      sourceNode.connect(processor);
      processor.connect(audioContext.destination);

      // Open ASR WebSocket
      socket = new WebSocket(
        (location.protocol === 'https:' ? 'wss://' : 'ws://') +
        location.host +
        '/ws/asr/'
      );
      socket.binaryType = 'arraybuffer';
      socket.onopen = () => {
        socket.send(JSON.stringify({
          type:       'audio_config',
          sampleRate: audioContext.sampleRate
        }));
      };
      socket.onmessage = ev => {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'transcript') {
          const t = msg.transcript.trim();
          // append or set
          inputField.value = inputField.value
            ? inputField.value.trim() + ' ' + t
            : t;
          inputField.dispatchEvent(new Event('input', { bubbles: true }));
          if (autosendChk?.checked) {
            if (sendBtn) sendBtn.click();
            else if (chatForm) chatForm.submit();
          }
        } else if (msg.error) {
          console.error('ASR error:', msg.error);
        }
      };
      socket.onerror = e => console.error('WebSocket error', e);
      socket.onclose = e => console.log('WebSocket closed', e.code);

      // Stream PCM chunks
      processor.onaudioprocess = e => {
        const floatData = e.inputBuffer.getChannelData(0);
        const int16     = new Int16Array(floatData.length);
        for (let i = 0; i < floatData.length; i++) {
          let s = Math.max(-1, Math.min(1, floatData[i]));
          int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        socket.send(int16.buffer);
      };

      listening = true;
      micBtn.classList.add('recording');

    } else {
      // —— STOP RECORDING ——
      processor.disconnect();
      sourceNode.disconnect();
      await audioContext.close();

      // **Stop all mic tracks** so the browser releases the mic
      mediaStream.getTracks().forEach(track => track.stop());

      // Tell server we're done
      socket.send(JSON.stringify({ type: 'end_stream' }));

      listening = false;
      micBtn.classList.remove('recording');
    }
  });
});
