from enum import Enum
from typing import Optional, Dict
from pydantic import BaseModel


# -------------------------
# Language Codes
# -------------------------
class LanguageCode(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    GUJARATI = "gu"
    PUNJABI = "pa"
    BENGALI = "bn"
    TELUGU = "te"
    TAMIL = "ta"
    MALAYALAM = "ml"
    KANNADA = "kn"
    ODIA = "or"


# -------------------------
# Status Enums
# -------------------------
class ProcessingStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# -------------------------
# Transcription Response
# -------------------------
class AudioProcessingResponse(BaseModel):
    task_id: str
    status: ProcessingStatus
    transcribed_text: Optional[str] = None
    translated_text: Optional[str] = None
    detected_language: Optional[LanguageCode] = None
    confidence_score: Optional[float] = None
    processing_time: float
    error_details: Optional[str] = None

    def __str__(self):
        confidence = (
            f"{self.confidence_score:.2f}" if self.confidence_score is not None else "N/A"
        )
        return (
            f"[{self.status}] "
            f"Language: {self.detected_language or 'Unknown'} | "
            f"Confidence: {confidence} | "
            f"Text: {self.transcribed_text or 'N/A'}"
        )

    class Config:
        use_enum_values = True


# -------------------------
# TTS Response
# -------------------------
class TextToSpeechResponse(BaseModel):
    status: ProcessingStatus
    translated_text: Optional[str] = None
    audio_path: Optional[str] = None
    error_message: Optional[str] = None


# -------------------------
# Azure TTS Voice Mapping
# -------------------------
AZURE_LANGUAGE_VOICE_MAPPING: Dict[str, str] = {
    "hi": "hi-IN-SwaraNeural",
    "gu": "gu-IN-DhwaniNeural",
    "pa": "pa-IN-AmarNeural",
    "bn": "bn-IN-TanishaaNeural",
    "te": "te-IN-MohanNeural",
    "ta": "ta-IN-PallaviNeural",
    "ml": "ml-IN-SobhanaNeural",
    "kn": "kn-IN-SapnaNeural",
    "or": "or-IN-PrabhatNeural",
    "en": "en-IN-NeerjaNeural",
}
