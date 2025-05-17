# ml_models/consumers.py
import io
import json
import logging
import wave
import datetime
import asyncio

import numpy as np
import torch
import whisper
from channels.generic.websocket import AsyncWebsocketConsumer
from whisper import DecodingOptions, log_mel_spectrogram

logger = logging.getLogger(__name__)

WHISPER_MODEL_NAME = "tiny.en"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
WHISPER_MODEL = whisper.load_model(WHISPER_MODEL_NAME, device=DEVICE)

class ASRConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.audio_buffer = bytearray()
        self.client_sample_rate = None
        logger.info("ASRConsumer connected.")

    async def disconnect(self, close_code):
        logger.info(f"ASRConsumer disconnected ({close_code}); flushing.")
        if self.audio_buffer:
            await self._finish_stream("disconnect_flush")

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            msg = json.loads(text_data)
            t = msg.get("type")
            if t == "audio_config":
                self.client_sample_rate = int(msg.get("sampleRate", 0))
                if not self.client_sample_rate:
                    return await self._send_error("Invalid sampleRate")
                return await self.send(text_data=json.dumps({"status":"config_received"}))
            if t == "end_stream":
                return await self._finish_stream("end_of_stream")

        if bytes_data:
            if not self.client_sample_rate:
                return await self._send_error("Audio config not received.")
            self.audio_buffer.extend(bytes_data)
            logger.debug(f"Buffered {len(bytes_data)} bytes (total {len(self.audio_buffer)})")

    async def _finish_stream(self, reason: str):
        # 1) pull out the raw PCM bytes & clear buffer
        pcm = bytes(self.audio_buffer)
        self.audio_buffer.clear()

        # 2) convert to numpy float32 in [-1,1]
        audio_int16 = np.frombuffer(pcm, dtype=np.int16)
        audio = audio_int16.astype(np.float32) / 32768.0

        # 3) if your incoming sample rate != 16000, resample:
        if self.client_sample_rate != 16000:
            # this uses torch + torchaudio; if you don't have torchaudio you can swap in librosa.resample
            audio_t = torch.from_numpy(audio)
            audio_t = torch.nn.functional.interpolate(
                audio_t.unsqueeze(0).unsqueeze(0),
                scale_factor=16000/self.client_sample_rate,
                mode="linear",
                align_corners=False
            ).squeeze()
            audio = audio_t.cpu().numpy()

        # 4) pad/trim & compute log-mel
        audio = whisper.pad_or_trim(audio)
        mel   = log_mel_spectrogram(audio).to(DEVICE)

        # 5) decode
        opts   = DecodingOptions(fp16=False, language="en")
        result = whisper.decode(WHISPER_MODEL, mel, opts)
        transcript = result.text.strip()

        # 6) send it back
        await self.send(text_data=json.dumps({
            "type":       "transcript",
            "transcript": transcript,
            "reason":     reason,
            "timestamp":  datetime.datetime.utcnow().isoformat() + "Z"
        }))

        # 7) close the WS
        await self.close(code=1000, reason="transcription_complete")

    async def _send_error(self, msg: str):
        logger.warning(msg)
        await self.send(text_data=json.dumps({"error": msg}))
