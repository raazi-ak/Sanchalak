# api/transcribe_routes.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from transcribe import AudioIngestionAgent
from models import AudioProcessingResponse, ProcessingStatus
import time
import uuid
import logging
import os
import tempfile

router = APIRouter(prefix="/transcribe", tags=["Transcription"])
logger = logging.getLogger(__name__)

@router.post("/", response_model=AudioProcessingResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    task_id = f"audio_{uuid.uuid4().hex[:8]}"
    try:

        logger.info(f"🔁 Received file: {file.filename}")
        logger.info(f"📏 File size: {file.file.seek(0, 2)} bytes")
        file.file.seek(0)
        start = time.time()
        agent = AudioIngestionAgent()
        await agent.initialize()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            content = await file.read()
            temp_audio.write(content)
            temp_audio_path = temp_audio.name

        with open(temp_audio_path, "rb") as f:
            result = await agent.process_audio(f)

        os.remove(temp_audio_path)
        result.task_id = task_id
        result.processing_time = time.time() - start
        if result.status != ProcessingStatus.COMPLETED:
            logger.warning("Agent returned failed status")

        return result

    except Exception as e:
        logger.exception("Transcription failed.")
        return AudioProcessingResponse(
            task_id=task_id,
            status=ProcessingStatus.FAILED,
            transcribed_text=None,
            translated_text=None,
            detected_language=None,
            confidence_score=None,
            processing_time=0.0,
            error_details=str(e)
        )
