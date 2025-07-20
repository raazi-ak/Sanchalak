#trans\transcribe.py

import os
import tempfile
import time
import asyncio
import uuid
from typing import Optional, BinaryIO

import whisper
import numpy as np
import torch
import httpx
from pydub import AudioSegment
from dotenv import load_dotenv

from config import get_settings
from models import AudioProcessingResponse, LanguageCode, ProcessingStatus
from utils.logger import get_logger

load_dotenv()
settings = get_settings()
logger = get_logger(__name__)

# Azure Translator Config
AZURE_TRANSLATOR_ENDPOINT = os.getenv("AZURE_TRANSLATOR_ENDPOINT")
AZURE_TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY")
AZURE_REGION = os.getenv("AZURE_TRANSLATOR_REGION")

# Translate given text to English using Azure Translator
async def translate_text_to_english(text: str) -> str:
    url = f"{AZURE_TRANSLATOR_ENDPOINT}/translate?api-version=3.0&to=en"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_REGION,
        "Content-Type": "application/json"
    }
    body = [{"Text": text}]

    retries = 3
    for _ in range(retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=body)
                logger.info("Azure Raw Response: %s", response.text)
                response.raise_for_status()
                return response.json()[0]["translations"][0]["text"]
        except (httpx.HTTPError, KeyError) as e:
            logger.error("Azure Translation Error: %s", str(e))
            await asyncio.sleep(1)
    raise Exception("Azure translation failed")


class AudioIngestionAgent:
    def __init__(self):
        self.whisper_model = None
        self.supported_formats = settings.SUPPORTED_AUDIO_FORMATS.split(",")
        self.max_duration = 300
        self.sample_rate = 16000
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Audio agent will use device: {self.device}")

    async def initialize(self):
        try:
            logger.info(f"Loading Whisper model: {settings.WHISPER_MODEL}")
            loop = asyncio.get_event_loop()
            self.whisper_model = await loop.run_in_executor(
                None, whisper.load_model, settings.WHISPER_MODEL, self.device
            )
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to initialize audio agent: {str(e)}")
            raise

    async def process_audio(self, audio_file: BinaryIO, language_hint: Optional[LanguageCode] = None) -> AudioProcessingResponse:
        start_time = time.time()
        task_id = f"audio_{int(time.time() * 1000)}"
        try:
            logger.info("🔍 Starting audio processing")
            processed_audio = await self._preprocess_audio(audio_file)
            logger.info("✅ Audio preprocessing done")

            if processed_audio.shape[0] == 0:
                raise ValueError("Audio input was empty after preprocessing.")

            transcription_result = await self._transcribe_audio(processed_audio, language_hint)
            detected_language = await self._detect_language(transcription_result)
            translated_text = await translate_text_to_english(transcription_result["text"])
            confidence_score = self._calculate_confidence(transcription_result)
            processing_time = time.time() - start_time

            return AudioProcessingResponse(
                task_id=task_id,
                status=ProcessingStatus.COMPLETED,
                transcribed_text=transcription_result["text"],
                translated_text=translated_text,
                detected_language=detected_language,
                confidence_score=confidence_score,
                processing_time=processing_time
            )
        except Exception as e:
            logger.error(f"Audio processing failed: {str(e)}", exc_info=True)
            return AudioProcessingResponse(
                task_id=task_id,
                status=ProcessingStatus.FAILED,
                processing_time=time.time() - start_time,
                error_details=str(e)
            )

    async def _preprocess_audio(self, audio_file: BinaryIO) -> np.ndarray:
        input_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.mp3")
        output_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.wav")
        try:
            # Save to disk
            with open(input_path, "wb") as f:
                content = audio_file.read()
                f.write(content)
                logger.info(f"📦 Audio file saved ({len(content)} bytes)")

            # Convert to wav
            audio = AudioSegment.from_file(input_path)
            logger.info(f"🧪 Duration: {len(audio)} ms | Channels: {audio.channels} | Sample rate: {audio.frame_rate}")

            audio = audio.set_channels(1).set_frame_rate(self.sample_rate)
            audio.export(output_path, format="wav")

            # Load into Whisper
            audio_array = whisper.load_audio(output_path)
            logger.info(f"📈 Audio array shape: {audio_array.shape}")
            return audio_array
        finally:
            for path in [input_path, output_path]:
                if os.path.exists(path):
                    os.remove(path)

    async def _transcribe_audio(self, audio_array: np.ndarray, language_hint: Optional[LanguageCode] = None) -> dict:
        try:
            options = {
                "language": language_hint.value if language_hint else None,
                "task": "transcribe",
                "fp16": False
            }
            logger.info("🔠 Starting Whisper transcription")

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: self.whisper_model.transcribe(audio_array, **options)
            )
            logger.info("🔤 Transcribed text: %s", result.get("text", "[no text]"))
            return result
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise

    async def _detect_language(self, transcription_result: dict) -> Optional[LanguageCode]:
        lang_code = transcription_result.get("language")
        logger.info("🌐 Detected language: %s", lang_code)

        lang_mapping = {
            'hi': LanguageCode.HINDI,
            'en': LanguageCode.ENGLISH,
            'gu': LanguageCode.GUJARATI,
            'pa': LanguageCode.PUNJABI,
            'bn': LanguageCode.BENGALI,
            'te': LanguageCode.TELUGU,
            'ta': LanguageCode.TAMIL,
            'ml': LanguageCode.MALAYALAM,
            'kn': LanguageCode.KANNADA,
            'or': LanguageCode.ODIA
        }
        return lang_mapping.get(lang_code, LanguageCode.HINDI)

    def _calculate_confidence(self, transcription_result: dict) -> float:
        segments = transcription_result.get("segments", [])
        if not segments:
            return 0.0
        confidences = [1 - seg.get("no_speech_prob", 0.5) for seg in segments]
        return sum(confidences) / len(confidences)
