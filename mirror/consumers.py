import asyncio
import json
import logging
import torch
import torchaudio
import numpy as np
import whisper

from channels.generic.websocket import AsyncWebsocketConsumer
WHISPER_MODEL_NAME = "turbo" 
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
TARGET_SAMPLE_RATE = 16000

MAX_CHUNK_DURATION_S = 3.0
MAX_SESSION_DURATION_S = 30.0
SILENCE_THRESHOLD_CHUNKS = 2

logger = logging.getLogger(__name__)

try:
    logger.info(f"Loading Whisper ASR model \"{WHISPER_MODEL_NAME}\" onto device \"{DEVICE}\"...")
    WHISPER_MODEL = whisper.load_model(WHISPER_MODEL_NAME, device=DEVICE)
    logger.info(f"Whisper model \"{WHISPER_MODEL_NAME}\" loaded successfully.")
except Exception as e:
    logger.error(f"Fatal error loading Whisper model: {e}", exc_info=True)
    WHISPER_MODEL = None

class ASRConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not WHISPER_MODEL:
            logger.warning("Whisper ASR model not loaded. Closing WebSocket connection.")
            await self.close(code=1011)
            return

        await self.accept()
        self.client_sample_rate = None
        self.resampler_to_16k = None
        
        self.audio_segment_buffer = bytearray()
        self.current_segment_duration_s = 0.0
        self.total_session_duration_s = 0.0
        self.consecutive_empty_transcripts = 0

        logger.info("ASRConsumer (Whisper) connected.")

    async def disconnect(self, close_code):
        logger.info(f"ASRConsumer (Whisper) disconnected. Code: {close_code}")
        if self.audio_segment_buffer:
            logger.info("Transcribing remaining audio on disconnect.")
            await self.transcribe_and_send(self.audio_segment_buffer, reason="disconnect_flush")
        
        # Clean up attributes
        attributes_to_delete = ['client_sample_rate', 'resampler_to_16k', 
                                'audio_segment_buffer', 'current_segment_duration_s', 
                                'total_session_duration_s', 'consecutive_empty_transcripts']
        for attr in attributes_to_delete:
            if hasattr(self, attr):
                delattr(self, attr)

    async def transcribe_and_send(self, pcm_audio_buffer, reason=""):
        if not pcm_audio_buffer:
            logger.info(f"Transcription requested ({reason}), but audio buffer is empty.")
            return True
        logger.info(f"Transcribing segment ({len(pcm_audio_buffer)} bytes) due to: {reason}")
        audio_np = np.frombuffer(pcm_audio_buffer, dtype=np.int16).astype(np.float32) / 32768.0
        if audio_np.size == 0:
            logger.info("Converted audio_np for transcription is empty.")
            return True
        transcript_text = ""
        try:
            if WHISPER_MODEL:
                # fp16=False if using CPU, can be True if on CUDA and model supports it
                result = WHISPER_MODEL.transcribe(audio_np, language="en", fp16=(DEVICE=="cuda"))
                transcript_text = result["text"].strip()
                logger.info(f"Whisper transcription ({reason}): {transcript_text}")
                # Send the full transcript of this segment
                await self.send(text_data=json.dumps({"full_transcript": transcript_text, "reason": reason}))
            else:
                logger.error("WHISPER_MODEL not loaded during transcribe_and_send!")
                await self.send_error("ASR model (Whisper) not available.")
                return False # Indicate transcription failed

        except Exception as e:
            logger.error(f"Error during Whisper transcription: {e}", exc_info=True)
            await self.send_error(f"Transcription error: {str(e)}")
            return False # Indicate transcription failed
        
        if not transcript_text: # If transcript is empty
            self.consecutive_empty_transcripts += 1
            logger.info(f"Empty transcript, consecutive empty: {self.consecutive_empty_transcripts}")
            if self.consecutive_empty_transcripts >= SILENCE_THRESHOLD_CHUNKS:
                logger.info("Silence threshold reached. Ending session.")
                await self.close_session("silence_timeout")
                return False # Indicate session should end
        else:
            self.consecutive_empty_transcripts = 0 # Reset on non-empty transcript
        
        return True # Indicate successful processing of this buffer


    async def close_session(self, reason_text):
        logger.info(f"Closing WebSocket session due to: {reason_text}")
        await self.send(text_data=json.dumps({"status": "asr_session_ended", "reason": reason_text}))
        await self.close(code=1000, reason=f"ASR session ended: {reason_text}")


    async def receive(self, text_data=None, bytes_data=None):
        if not WHISPER_MODEL:
            await self.send_error("ASR service not available (model not loaded).")
            await self.close(code=1011)
            return

        if text_data:
            try:
                message = json.loads(text_data)
                if message.get("type") == "audio_config":
                    self.client_sample_rate = int(message.get("sampleRate"))
                    if not self.client_sample_rate:
                        await self.send_error("Invalid sampleRate received.")
                        return
                    
                    # Initialize resampler if client SR is different from Whisper's target
                    if self.client_sample_rate != TARGET_SAMPLE_RATE:
                        self.resampler_to_16k = torchaudio.transforms.Resample(
                            orig_freq=self.client_sample_rate, new_freq=TARGET_SAMPLE_RATE
                        )
                        logger.info(f"Client SR: {self.client_sample_rate}Hz. Resampler to {TARGET_SAMPLE_RATE}kHz configured.")
                    else:
                        self.resampler_to_16k = None # No resampling needed
                        logger.info(f"Client SR: {self.client_sample_rate}Hz. Matches target, no resampling needed.")
                    await self.send(text_data=json.dumps({"status": "config_received"}))
                # Handle other text messages if needed
            except Exception as e:
                logger.error(f"Error processing text message: {e}", exc_info=True)
                await self.send_error(f"Error processing config: {str(e)}")
            return

        if bytes_data:
            if not self.client_sample_rate:
                await self.send_error("Audio config not received. Please send sample rate first.")
                return

            # 1. Convert received Float32 bytes to NumPy array
            audio_f32_np = np.frombuffer(bytes_data, dtype=np.float32)
            
            # Calculate duration of this incoming chunk (at client's sample rate)
            # This specific chunk's duration isn't directly used for accumulation logic below,
            # as accumulation duration is based on resampled audio.

            # 2. Resample to Whisper's target sample rate (16kHz)
            resampled_audio_f32_np = audio_f32_np
            if self.resampler_to_16k:
                audio_f32_tensor = torch.from_numpy(audio_f32_np)
                resampled_audio_tensor = self.resampler_to_16k(audio_f32_tensor)
                resampled_audio_f32_np = resampled_audio_tensor.numpy()

            # Calculate duration of the resampled audio chunk
            duration_of_this_resampled_chunk_s = len(resampled_audio_f32_np) / TARGET_SAMPLE_RATE

            # 3. Convert Float32 to Int16 PCM for accumulation (can also accumulate Float32)
            # Whisper can take float32, so let's accumulate float32 to avoid quality loss
            # and convert to 16-bit only if a VAD needed it. Since Whisper takes float32,
            # we can keep it as float32.
            # The self.audio_segment_buffer will store resampled float32 audio directly.
            # For direct concatenation, it's easier if it's a list of numpy arrays, or one growing array.
            # Let's use a bytearray of float32 bytes for easier extension.
            
            # For simplicity in buffer management, let's convert to 16-bit PCM bytes here.
            # Whisper can handle float32 numpy array directly, which is better quality-wise.
            # Let's refine: accumulate float32 numpy arrays.
            
            # If self.audio_segment_buffer is a list of NumPy arrays:
            if not hasattr(self, 'audio_segment_parts'): # Initialize if first chunk
                self.audio_segment_parts = []
            self.audio_segment_parts.append(resampled_audio_f32_np)
            self.current_segment_duration_s += duration_of_this_resampled_chunk_s
            self.total_session_duration_s += duration_of_this_resampled_chunk_s

            # 4. Check max session duration
            if self.total_session_duration_s >= MAX_SESSION_DURATION_S:
                logger.info("Max session duration reached.")
                combined_segment = np.concatenate(self.audio_segment_parts) if self.audio_segment_parts else np.array([], dtype=np.float32)
                self.audio_segment_parts = [] # Clear parts
                await self.transcribe_and_send(combined_segment.tobytes(), reason="max_duration_final_chunk") # Convert to bytes for consistency or pass np array
                await self.close_session("max_duration")
                return

            if self.current_segment_duration_s >= MAX_CHUNK_DURATION_S:
                logger.info(f"Segment duration {self.current_segment_duration_s:.2f}s reached threshold {MAX_CHUNK_DURATION_S}s.")
                combined_segment_np = np.concatenate(self.audio_segment_parts)
                combined_segment_np_clipped = np.clip(combined_segment_np, -1.0, 1.0)
                pcm_buffer_for_transcription = (combined_segment_np_clipped * 32767).astype(np.int16).tobytes()

                if not await self.transcribe_and_send(pcm_buffer_for_transcription, reason="chunk_processed"):
                    self.audio_segment_parts = []
                    self.current_segment_duration_s = 0.0
                    return 
                
                self.audio_segment_parts = []
                self.current_segment_duration_s = 0.0
            
    async def send_error(self, message):
        logger.warning(f"Sending error to client: {message}")
        await self.send(text_data=json.dumps({"error": message}))
