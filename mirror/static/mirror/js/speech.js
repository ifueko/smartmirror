// mirror/static/mirror/js/speech.js

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const micBtn      = document.getElementById('btn-mic');      // 🎙️ button
  const inputField  = document.getElementById('chat-input');   // your chat <input>
  const sendBtn     = document.getElementById('send-btn');     // your “Send” button
  const chatForm    = document.getElementById('chat-form');    // your chat <form>
  const autosendChk = document.getElementById('autosend');     // optional auto-send <input type="checkbox">

  // State
  let audioContext, processor, sourceNode, socket;
  let listening = false;

  micBtn.addEventListener('click', async () => {
    if (!listening) {
      // —— START RECORDING ——
      // 1) get mic
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContext = new AudioContext();
      processor    = audioContext.createScriptProcessor(4096, 1, 1);
      sourceNode   = audioContext.createMediaStreamSource(stream);
      sourceNode.connect(processor);
      processor.connect(audioContext.destination);

      // 2) open websocket
      socket = new WebSocket(
        (location.protocol === 'https:' ? 'wss://' : 'ws://') +
        location.host +
        '/ws/asr/'
      );
      socket.binaryType = 'arraybuffer';
      socket.onopen = () => {
        console.log('WebSocket open');
        // send sample rate config
        socket.send(JSON.stringify({
          type:       'audio_config',
          sampleRate: audioContext.sampleRate
        }));
      };
      socket.onmessage = ev => {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'transcript') {
          const t = msg.transcript.trim();
          // append instead of overwrite:
          if (inputField.value) {
            inputField.value = inputField.value.trim() + ' ' + t;
          } else {
            inputField.value = t;
          }
          inputField.dispatchEvent(new Event('input', { bubbles: true }));
          // auto-send if checked
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

      // 3) stream audio chunks
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

      // signal end of stream
      socket.send(JSON.stringify({ type: 'end_stream' }));
      listening = false;
      micBtn.classList.remove('recording');
    }
  });
});
