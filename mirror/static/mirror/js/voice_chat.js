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

    // ———————— Submit handler (existing code, no changes needed here) ————————
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
            const resp = await fetch('chat', { // Assuming 'chat' is your HTTP endpoint for chat logic
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
            console.log('Chat Response:', data);

            // bot bubble (your existing logic for displaying bot response)
            if (data.error) {
                const errorBubble = document.createElement('div');
                errorBubble.className = 'chat-bubble bot error';
                errorBubble.textContent = data.error;
                chatWindow.appendChild(errorBubble);
            } else if (data.response) {
                if (Array.isArray(data.response)) {
                    data.response.forEach(line => {
                        if (line.trim() === '') return;
                        const botBubble = document.createElement('div');
                        botBubble.className = 'chat-bubble bot';
                        botBubble.textContent = line;
                        chatWindow.appendChild(botBubble);
                    });
                } else if (typeof data.response === 'string') {
                    if (data.response.trim() === '') return;
                    const botBubble = document.createElement('div');
                    botBubble.className = 'chat-bubble bot';
                    botBubble.textContent = data.response;
                    chatWindow.appendChild(botBubble);
                } else {
                    console.warn("Received data.response in an unexpected format: ", data.response);
                    // ... (your existing fallback)
                }
            } else {
                 // ... (your existing handling for no response)
            }
            chatWindow.scrollTop = chatWindow.scrollHeight;
        } catch (err) {
            console.error('Fetch error:', err);
            const errorBubble = document.createElement('div');
            errorBubble.className = 'chat-bubble bot error';
            errorBubble.textContent = 'Error connecting to chat service.';
            chatWindow.appendChild(errorBubble);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }
    });

    // ———————— NEW WebSocket ASR Service Logic ————————
    let socket;
    let audioContext;
    let scriptProcessor;
    let mediaStreamSource;
    let localStream;
    let isRecording = false;

    const ASR_WEBSOCKET_URL = `ws://${window.location.host}/ws/asr/`;
    const BUFFER_SIZE = 4096; // Audio buffer size for ScriptProcessorNode

    function updateMicButtonUI(recording) {
        if (recording) {
            micBtn.classList.add('text-danger', 'recording'); // 'recording' class from your old CSS might make it blink
            micBtn.title = "Listening… click again to stop";
        } else {
            micBtn.classList.remove('text-danger', 'recording');
            micBtn.title = "Speak your message";
            micBtn.blur(); // Remove focus
        }
    }

    async function startASR() {
        if (isRecording) return;
        console.log('Starting ASR...');
        var content = "";

        try {
            localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            isRecording = true;
            updateMicButtonUI(true);
            chatInput.value = ""; // Clear input field when starting new recording

            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            mediaStreamSource = audioContext.createMediaStreamSource(localStream);
            scriptProcessor = audioContext.createScriptProcessor(BUFFER_SIZE, 1, 1); // 1 input channel, 1 output channel

            scriptProcessor.onaudioprocess = (e) => {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    const inputData = e.inputBuffer.getChannelData(0); // Float32Array
                    socket.send(inputData.buffer); // Send ArrayBuffer
                }
            };

            mediaStreamSource.connect(scriptProcessor);
            scriptProcessor.connect(audioContext.destination); // Necessary for onaudioprocess to fire

            socket = new WebSocket(ASR_WEBSOCKET_URL);

            socket.onopen = () => {
                console.log('ASR WebSocket connected.');
                // Send audio configuration
                socket.send(JSON.stringify({
                    type: "audio_config",
                    sampleRate: audioContext.sampleRate
                }));
                console.log(`Sent audio_config with sampleRate: ${audioContext.sampleRate}`);
            };

            socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                console.log('ASR Message:', data);

                if (data.full_transcript) { 
                    content = content + data.full_transcript;
                    chatInput.value = content;
                } else if (data.transcript_update) { // Fallback if only updates are sent
                    content = content + data.transcript_update;
                    chatInput.value = content;
                }
                
                if (data.error) {
                    console.error('ASR Error from server:', data.error);
                    // Optionally display this error to the user
                    stopASR(); // Stop on error
                }
            };

            socket.onclose = (event) => {
                console.log('ASR WebSocket closed:', event.reason, `Code: ${event.code}`);
                if (isRecording) { // Only call stopASR if it wasn't manually stopped
                    stopASRCleanup();
                }
            };

            socket.onerror = (error) => {
                console.error('ASR WebSocket error:', error);
                // Optionally display error to user
                if (isRecording) {
                     stopASRCleanup(); // Clean up if an error occurs during recording
                }
            };

        } catch (err) {
            console.error('Error starting ASR:', err);
            alert(`Could not start recording: ${err.message}`); // User feedback
            isRecording = false;
            updateMicButtonUI(false);
        }
    }
    
    function stopASRCleanup() {
        console.log('Cleaning up ASR resources...');
        if (scriptProcessor) {
            scriptProcessor.disconnect();
            scriptProcessor.onaudioprocess = null; // Remove handler
            scriptProcessor = null;
        }
        if (mediaStreamSource) {
            mediaStreamSource.disconnect();
            mediaStreamSource = null;
        }
        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
            localStream = null;
        }
        if (audioContext && audioContext.state !== 'closed') {
            audioContext.close().catch(e => console.warn("Error closing audio context:", e));
            audioContext = null;
        }
        isRecording = false;
        updateMicButtonUI(false);

        // Auto-send if enabled and there's text
        if (autosendCheckbox && autosendCheckbox.checked && chatInput.value.trim()) {
            console.log("Autosending transcript...");
            if (chatForm.requestSubmit) chatForm.requestSubmit();
            else chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
        }
    }

    function stopASR() {
        if (!isRecording) return;
        console.log('Stopping ASR...');
        if (socket && socket.readyState === WebSocket.OPEN) {
            // Optionally send an "end_of_stream" message if your backend expects it
            // socket.send(JSON.stringify({ type: "end_stream" }));
            socket.close(1000, "Client stopped recording"); // Graceful close
        }
        // stopASRCleanup will be called by socket.onclose or directly if socket never opened/errored
        // However, if the socket is already closed or never opened, we need to ensure cleanup happens.
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            stopASRCleanup();
        }
        // If socket was open, socket.onclose will trigger stopASRCleanup.
    }

    micBtn.addEventListener('click', () => {
        if (!isRecording) {
            startASR();
        } else {
            stopASR();
        }
    });
});
