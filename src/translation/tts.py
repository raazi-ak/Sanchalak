#trans\tts.py

import os
import uuid
import httpx
import asyncio

from config import get_settings
from models import AZURE_LANGUAGE_VOICE_MAPPING, ProcessingStatus, TextToSpeechResponse
from common.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Load from env or fallback to settings
AZURE_TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY", settings.AZURE_TRANSLATOR_KEY)
AZURE_TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION", settings.AZURE_TRANSLATOR_REGION)
AZURE_TRANSLATOR_ENDPOINT = os.getenv("AZURE_TRANSLATOR_ENDPOINT", settings.AZURE_TRANSLATOR_ENDPOINT)
AZURE_SPEECH_KEY = os.getenv("AZURE_TTS_KEY", settings.AZURE_TTS_KEY)
AZURE_SPEECH_REGION = os.getenv("AZURE_TTS_REGION", settings.AZURE_TTS_REGION)

# -------------------------
# Translate text
# -------------------------
async def translate_to_target_language(text: str, target_lang: str) -> str:
    url = f"{AZURE_TRANSLATOR_ENDPOINT}/translate?api-version=3.0&to={target_lang}"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_TRANSLATOR_REGION,
        "Content-Type": "application/json"
    }
    body = [{"Text": text}]

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            translated = response.json()[0]["translations"][0]["text"]
            logger.info(f"Translated to {target_lang}: {translated}")
            return translated
        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            raise

# -------------------------
# Convert text to speech
# -------------------------
async def synthesize_speech(text: str, lang_code: str, output_path: str = None) -> TextToSpeechResponse:
    voice = AZURE_LANGUAGE_VOICE_MAPPING.get(lang_code)
    if not voice:
        error = f"No Azure voice available for language code: {lang_code}"
        logger.error(error)
        return TextToSpeechResponse(status=ProcessingStatus.FAILED, error_message=error)

    xml_lang = "-".join(voice.split("-")[:2])  # e.g., 'hi-IN'
    # Ensure the directory exists
    os.makedirs("tts_outputs", exist_ok=True)

    # Generate path in tts_outputs/
    output_path = output_path or os.path.join("tts_outputs", f"tts_output_{uuid.uuid4().hex[:8]}.mp3")
    logger.info(f"Saving TTS output to: {output_path}")

    url = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3"
    }

    ssml = f"""
    <speak version='1.0' xml:lang='{xml_lang}'>
        <voice name='{voice}'>{text}</voice>
    </speak>
    """

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, content=ssml.encode("utf-8"))
            response.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(response.content)
            logger.info(f"TTS audio saved to {output_path}")
            return TextToSpeechResponse(status=ProcessingStatus.COMPLETED, audio_path=output_path)
        except Exception as e:
            logger.error(f"TTS synthesis failed: {str(e)}")
            logger.error(f"Azure response: {response.status_code} - {response.text}")
            return TextToSpeechResponse(status=ProcessingStatus.FAILED, error_message=str(e))
