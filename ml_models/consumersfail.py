import asyncio
import json
import logging
import torch
import torchaudio
import numpy as np

from channels.generic.websocket import AsyncWebsocketConsumer
import whisper

WHISPER_MODEL_NAME = "turbo"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
TARGET_SAMPLE_RATE = 16000

logger = logging.getLogger(__name__)

try:
    logger.info(
        f'Loading Whisper ASR model "{WHISPER_MODEL_NAME}" onto device "{DEVICE}"...'
    )
    WHISPER_MODEL = whisper.load_model(WHISPER_MODEL_NAME, device=DEVICE)
    logger.info(f'Whisper model "{WHISPER_MODEL_NAME}" loaded successfully.')
except Exception as e:
    logger.error(f"Fatal error loading Whisper model: {e}", exc_info=True)
    WHISPER_MODEL = None


class ASRConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not WHISPER_MODEL:
            logger.warning(
                "Whisper ASR model not loaded. Closing WebSocket connection."
            )
            await self.close(code=1011)
            return

        await self.accept()
        self.client_sample_rate = None
        self.resampler_to_16k = None
        self.full_audio_buffer = bytearray()
        self.transcription_started = False

        logger.info("ASRConsumer (Whisper) connected.")

    async def disconnect(self, close_code):
        logger.info(f"ASRConsumer (Whisper) disconnected. Code: {close_code}")
        if self.full_audio_buffer and not self.transcription_started:
            logger.info("Transcribing remaining audio on disconnect.")
            await self.transcribe_and_send(
                bytes(self.full_audio_buffer), reason="disconnect_flush"
            )

        attributes_to_delete = [
            "client_sample_rate",
            "resampler_to_16k",
            "full_audio_buffer",
            "transcription_started",
        ]
        for attr in attributes_to_delete:
            if hasattr(self, attr):
                delattr(self, attr)

    async def transcribe_and_send(self, pcm_audio_bytes, reason=""):
        if not pcm_audio_bytes:
            logger.info(
                f"Transcription requested ({reason}), but audio buffer is empty."
            )
            return True
        logger.info(
            f"Transcribing full audio ({len(pcm_audio_bytes)} bytes) due to: {reason}"
        )
        audio_np = np.frombuffer(pcm_audio_bytes, dtype=np.float16)
        if audio_np.size == 0:
            logger.info("Converted audio_np for transcription is empty.")
            return True
        transcript_text = ""
        try:
            if WHISPER_MODEL:
                result = WHISPER_MODEL.transcribe(
                    audio_np, language="en", fp16=(DEVICE == "cuda")
                )
                transcript_text = result["text"].strip()
                logger.info(f"Whisper transcription ({reason}): {transcript_text}")
                await self.send(
                    text_data=json.dumps(
                        {"full_transcript": transcript_text, "reason": reason}
                    )
                )
            else:
                logger.error("WHISPER_MODEL not loaded during transcribe_and_send!")
                await self.send_error("ASR model (Whisper) not available.")
                return False  # Indicate transcription failed

        except Exception as e:
            logger.error(f"Error during Whisper transcription: {e}", exc_info=True)
            await self.send_error(f"Transcription error: {str(e)}")
            return False  # Indicate transcription failed

        return True  # Indicate successful processing

    async def send_error(self, message):
        logger.warning(f"Sending error to client: {message}")
        await self.send(text_data=json.dumps({"error": message}))

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
                            orig_freq=self.client_sample_rate,
                            new_freq=TARGET_SAMPLE_RATE,
                        )
                        logger.info(
                            f"Client SR: {self.client_sample_rate}Hz. Resampler to {TARGET_SAMPLE_RATE}kHz configured."
                        )
                    else:
                        self.resampler_to_16k = None  # No resampling needed
                        logger.info(
                            f"Client SR: {self.client_sample_rate}Hz. Matches target, no resampling needed."
                        )
                    await self.send(text_data=json.dumps({"status": "config_received"}))
                elif message.get("type") == "end_stream":
                    logger.info(
                        "Received end_stream signal from client. Starting transcription."
                    )
                    self.transcription_started = True
                    await self.transcribe_and_send(
                        bytes(self.full_audio_buffer), reason="end_of_stream"
                    )
                    await self.close(code=1000, reason="Transcription complete.")
                # Handle other text messages if needed
            except Exception as e:
                logger.error(f"Error processing text message: {e}", exc_info=True)
                await self.send_error(f"Error processing config/command: {str(e)}")
            return

        if bytes_data:
            if not self.client_sample_rate:
                await self.send_error(
                    "Audio config not received. Please send sample rate first."
                )
                return

            # Append the received audio data to the buffer
            self.full_audio_buffer.extend(bytes_data)
            logger.info(
                f"Received audio chunk ({len(bytes_data)} bytes), total buffer size: {len(self.full_audio_buffer)} bytes."
            )
