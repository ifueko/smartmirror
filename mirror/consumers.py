# mirror/consumers.py
import asyncio
import json
import logging
import torch
import torchaudio
import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer
from speechbrain.inference.ASR import StreamingASR, ASRStreamingContext # Corrected import from previous full code
from speechbrain.utils.dynamic_chunk_training import DynChunkTrainConfig # Corrected import

# --- Global ASR Model Setup (as you had it) ---
MODEL_SOURCE = "speechbrain/asr-streaming-conformer-librispeech"
DEVICE = "cpu"
CHUNK_SIZE_CONFIG = 24
LEFT_CONTEXT_CHUNKS_CONFIG = 4
NUM_THREADS = None

if NUM_THREADS is not None:
    torch.set_num_threads(NUM_THREADS)

# Ensure basicConfig is called only once, preferably at a higher level if possible,
# or guard it. For now, this is fine if consumers.py is imported once.
# logging.basicConfig(level=logging.INFO) # This might be getting called multiple times if reloader is active.
                                        # Consider configuring logging in settings.py or asgi.py for the project.
logger = logging.getLogger(__name__) # Get a logger specific to this module

try:
    logger.info(f"Loading SpeechBrain ASR model from \"{MODEL_SOURCE}\" onto device {DEVICE}")
    asr_model = StreamingASR.from_hparams(MODEL_SOURCE, run_opts={"device": DEVICE})
    asr_config = DynChunkTrainConfig(CHUNK_SIZE_CONFIG, LEFT_CONTEXT_CHUNKS_CONFIG)
    TARGET_SAMPLE_RATE = asr_model.audio_normalizer.sample_rate
    CHUNK_SIZE_FRAMES = asr_model.get_chunk_size_frames(asr_config)
    logger.info(f"ASR model loaded. Target SR: {TARGET_SAMPLE_RATE}, Expected chunk frames: {CHUNK_SIZE_FRAMES}")
except Exception as e:
    logger.error(f"Fatal error loading SpeechBrain ASR model: {e}", exc_info=True)
    asr_model = None

class ASRConsumer(AsyncWebsocketConsumer):
    # NO custom __init__ here - let it use the default from parent classes

    async def connect(self):
        logger.info("ASRConsumer.connect method entered.")
        
        # --- BEGIN CRITICAL DEBUG LOGS ---
        logger.info(f"  (connect) self.scope type: {type(self.scope)}")
        logger.info(f"  (connect) self.scope content: {self.scope}") # Log the entire scope
        
        if isinstance(self.scope, dict):
            logger.info(f"  (connect) 'channel' in self.scope: {'channel' in self.scope}")
            if 'channel' in self.scope:
                logger.info(f"  (connect) self.scope['channel'] value: {self.scope['channel']}")
            else:
                logger.error("  (connect) CRITICAL: 'channel' key NOT FOUND in self.scope!")
        else:
            logger.error("  (connect) CRITICAL: self.scope is not a dictionary or not set!")
        
        # Check if channel_name was set by the base Consumer.__call__
        logger.info(f"  (connect) hasattr(self, 'channel_name') BEFORE accept/problem line: {hasattr(self, 'channel_name')}")
        if hasattr(self, 'channel_name'):
            logger.info(f"  (connect) self.channel_name value if it exists: {self.channel_name}")
        # --- END CRITICAL DEBUG LOGS ---

        if not asr_model:
            logger.warning("ASR model not loaded. Closing WebSocket connection.")
            await self.close(code=1011)
            return

        await self.accept()
        logger.info("Connection accepted by calling self.accept().")

        self.asr_context = asr_model.make_streaming_context(asr_config)
        self.waveform_buffer = torch.tensor([], dtype=torch.float32, device=DEVICE)
        self.client_sample_rate = None
        self.resampler = None
        self.decoded_text_accumulator = ""
        
        # This is the line that previously failed (e.g., line 49 or 71 in your file)
        logger.info(f"Attempting to log WebSocket connected with channel_name...")
        if hasattr(self, 'channel_name'): # Guarding the access for this debug run
            logger.info(f"WebSocket connected: {self.channel_name}")
        else:
            logger.error("WebSocket connected: BUT self.channel_name IS MISSING! This will cause AttributeError if accessed directly.")
            # To reproduce the error if it's still missing:
            # logger.info(f"WebSocket connected (forcing error if missing): {self.channel_name}")


    async def disconnect(self, close_code):
        logger.info(f"ASRConsumer.disconnect method entered. Code: {close_code}")
        if hasattr(self, 'channel_name'): # Guard access
            logger.info(f"WebSocket disconnected: {self.channel_name} (Code: {close_code})")
        else:
            logger.warning(f"WebSocket disconnected (channel_name was missing at disconnect). Code: {close_code}")

        if hasattr(self, 'asr_context'):
            del self.asr_context
        if hasattr(self, 'waveform_buffer'):
            del self.waveform_buffer
        if hasattr(self, 'resampler') and self.resampler is not None:
            del self.resampler
            
    async def receive(self, text_data=None, bytes_data=None):
        # Using your full receive logic from the file you provided
        if not asr_model:
            await self.send_error("ASR service not available.")
            return

        if text_data:
            try:
                message = json.loads(text_data)
                if message.get("type") == "audio_config":
                    self.client_sample_rate = int(message.get("sampleRate"))
                    if self.client_sample_rate and self.client_sample_rate != TARGET_SAMPLE_RATE:
                        self.resampler = torchaudio.transforms.Resample(
                            orig_freq=self.client_sample_rate, new_freq=TARGET_SAMPLE_RATE
                        ).to(DEVICE)
                        logger.info(f"Client sample rate: {self.client_sample_rate}Hz. Resampler configured.")
                    else:
                        self.resampler = None
                        logger.info(f"Client sample rate: {self.client_sample_rate}Hz. No resampling needed.")
                    await self.send(text_data=json.dumps({"status": "config_received"}))
            except json.JSONDecodeError:
                logger.warning(f"Received non-JSON text message: {text_data}")
            except Exception as e:
                logger.error(f"Error processing text message: {e}", exc_info=True)
                await self.send_error(f"Error processing config: {str(e)}")

        elif bytes_data:
            if self.client_sample_rate is None:
                await self.send_error("Audio config not received. Please send sample rate first.")
                return
            try:
                y = np.frombuffer(bytes_data, dtype=np.float32)
                y = torch.tensor(y, dtype=torch.float32, device=DEVICE)
                y_max_abs = torch.max(torch.abs(y))
                if y_max_abs > 0:
                    y /= y_max_abs
                else:
                    y = torch.zeros_like(y)
                if len(y.shape) > 1:
                    y = torch.mean(y, dim=1)
                if self.resampler:
                    y = self.resampler(y)
                self.waveform_buffer = torch.concat((self.waveform_buffer, y))
                transcribed_for_this_pass = ""
                while self.waveform_buffer.size(0) >= CHUNK_SIZE_FRAMES:
                    chunk_to_process = self.waveform_buffer[:CHUNK_SIZE_FRAMES]
                    self.waveform_buffer = self.waveform_buffer[CHUNK_SIZE_FRAMES:]
                    chunk_to_process = chunk_to_process.unsqueeze(0)
                    with torch.no_grad():
                        transcribed_segments = asr_model.transcribe_chunk(self.asr_context, chunk_to_process)
                    if transcribed_segments and transcribed_segments[0] is not None:
                        transcribed_for_this_pass += transcribed_segments[0]
                if transcribed_for_this_pass:
                    self.decoded_text_accumulator += transcribed_for_this_pass
                    await self.send(text_data=json.dumps({"transcript_update": transcribed_for_this_pass, "full_transcript": self.decoded_text_accumulator}))
            except Exception as e:
                logger.error(f"Error processing audio_chunk: {e}", exc_info=True)
                await self.send_error(f"Error processing audio: {str(e)}")

    async def send_error(self, message):
        await self.send(text_data=json.dumps({"error": message}))
