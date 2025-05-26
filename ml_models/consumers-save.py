import asyncio
import wave
import json
import logging
import os
import datetime
import whisper
import torch

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

WHISPER_MODEL_NAME = "tiny.en"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
try:
    logger.info(f"Loading Whisper model `{WHISPER_MODEL_NAME}` on `{DEVICE}`…")
    WHISPER_MODEL = whisper.load_model(WHISPER_MODEL_NAME, device=DEVICE)
    logger.info("Whisper loaded.")
except Exception:
    logger.exception("Failed to load Whisper model.")
    WHISPER_MODEL = None


class ASRConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.audio_buffer = bytearray()
        self.client_sample_rate = None
        logger.info("ASRConsumer connected.")

    async def disconnect(self, close_code):
        logger.info(f"Disconnected ({close_code}), flushing buffer.")
        if self.audio_buffer:
            await self._finalize_stream(reason="disconnect_flush")

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            msg = json.loads(text_data)
            t = msg.get("type")
            if t == "audio_config":
                self.client_sample_rate = int(msg.get("sampleRate", 0))
                if not self.client_sample_rate:
                    return await self.send_error("Invalid sampleRate")
                return await self.send(
                    text_data=json.dumps({"status": "config_received"})
                )

            if t == "end_stream":
                logger.info("End stream, starting transcription.")
                await self._finalize_stream(reason="end_of_stream")
                return

        if bytes_data:
            if not self.client_sample_rate:
                return await self.send_error("Audio config not received")
            self.audio_buffer.extend(bytes_data)
            logger.debug(
                f"Buffered {len(bytes_data)} bytes, total {len(self.audio_buffer)}"
            )
            return

    async def _finalize_stream(self, reason=""):
        # 1) save to WAV
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"received_{timestamp}.wav"
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.client_sample_rate or 44100)
            wf.writeframes(bytes(self.audio_buffer))

        # clear buffer
        self.audio_buffer = bytearray()

        # 2) transcribe in thread
        if WHISPER_MODEL:
            result = await asyncio.to_thread(WHISPER_MODEL.transcribe, filename)
            text = result.get("text", "").strip()
        else:
            text = "[no model loaded]"

        # 3) send back to client
        await self.send(
            text_data=json.dumps(
                {
                    "type": "transcript",
                    "filename": filename,
                    "transcript": text,
                    "reason": reason,
                }
            )
        )

        # 4) close WebSocket
        await self.close(code=1000, reason="done")

    async def send_error(self, msg):
        logger.warning(msg)
        await self.send(text_data=json.dumps({"error": msg}))
