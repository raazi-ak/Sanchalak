from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from tts import translate_to_target_language, synthesize_speech
from models import ProcessingStatus, TextToSpeechResponse
import asyncio
import os
from fastapi.responses import FileResponse

router = APIRouter(prefix="/tts", tags=["Text-to-Speech"])

class TTSRequest(BaseModel):
    text: str
    target_language: str

@router.post("/", response_model=TextToSpeechResponse)
async def handle_tts(request: TTSRequest):
    try:
        # Translate the input text to the target language
        translated = await translate_to_target_language(request.text, request.target_language)

        # Synthesize speech for the translated text
        tts_result = await synthesize_speech(translated, request.target_language)

        # Inject translated text into response
        tts_result.translated_text = translated
        return tts_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")

# Optional: Serve audio file through API
@router.get("/audio/{filename}")
async def get_audio(filename: str):
    file_path = os.path.join("tts_outputs", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Audio file not found")
