"""
Audio processing router for the Farmer AI Pipeline
Handles audio upload, transcription, and related endpoints
"""

import time
from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse

from models import (
    AudioUploadRequest,
    AudioProcessingResponse,
    LanguageCode,
    ProcessingStatus
)
from errorhandler import (
    raise_audio_processing_error,
    raise_transcription_error,
    AudioProcessingError,
    TranscriptionError
)
from utils.logger import get_logger

logger = get_logger(__name__)

# Create router instance
router = APIRouter(
    prefix="/audio",
    tags=["audio"],
    responses={
        400: {"description": "Audio processing error"},
        413: {"description": "Audio file too large"},
        415: {"description": "Unsupported audio format"}
    }
)

# Dependency to get audio agent
async def get_audio_agent():
    """Dependency to get the audio processing agent"""
    from main import agents
    if "audio" not in agents:
        raise HTTPException(status_code=503, detail="Audio processing service unavailable")
    return agents["audio"]

@router.post("/upload", response_model=AudioProcessingResponse)
async def upload_audio(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    language_hint: Optional[LanguageCode] = LanguageCode.HINDI,
    audio_agent = Depends(get_audio_agent)
):
    """
    Upload and process an audio file for transcription
    
    - **audio_file**: Audio file to transcribe (WAV, MP3, M4A, OGG, FLAC)
    - **language_hint**: Expected language of the audio (optional)
    
    Returns transcribed text with language detection and confidence score
    """
    logger.info(f"Received audio upload: {audio_file.filename}")
    
    try:
        # Validate file type
        allowed_content_types = [
            "audio/wav", "audio/mpeg", "audio/mp4", "audio/ogg", 
            "audio/flac", "audio/x-flac", "audio/webm"
        ]
        
        if audio_file.content_type not in allowed_content_types:
            raise_audio_processing_error(
                f"Unsupported audio format: {audio_file.content_type}",
                {"supported_formats": allowed_content_types}
            )
        
        # Check file size (50MB limit)
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
        if audio_file.size and audio_file.size > MAX_FILE_SIZE:
            raise_audio_processing_error(
                f"Audio file too large: {audio_file.size / (1024*1024):.1f}MB (max: 50MB)",
                {"file_size_mb": audio_file.size / (1024*1024), "max_size_mb": 50}
            )
        
        # Process audio
        result = await audio_agent.process_audio(
            audio_file=audio_file.file,
            language_hint=language_hint
        )
        
        logger.info(f"Audio processing completed: {result.task_id}")
        
        # Schedule cleanup in background
        background_tasks.add_task(cleanup_audio_processing, result.task_id)
        
        return result
        
    except AudioProcessingError:
        raise
    except TranscriptionError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in audio upload: {str(e)}")
        raise_audio_processing_error(
            "Failed to process audio file",
            {"error": str(e)}
        )

@router.post("/transcribe", response_model=AudioProcessingResponse)
async def transcribe_audio(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    language_hint: Optional[LanguageCode] = LanguageCode.HINDI,
    audio_agent = Depends(get_audio_agent)
):
    """
    Transcribe an audio file without full pipeline processing
    
    Similar to upload but focused only on transcription
    """
    return await upload_audio(background_tasks, audio_file, language_hint, audio_agent)

@router.get("/formats")
async def get_supported_formats(audio_agent = Depends(get_audio_agent)):
    """
    Get list of supported audio formats
    """
    try:
        formats = await audio_agent.get_supported_formats()
        return {
            "supported_formats": formats,
            "max_file_size_mb": 50,
            "max_duration_seconds": 300
        }
    except Exception as e:
        logger.error(f"Error getting supported formats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get supported formats")

@router.get("/estimate-time/{duration}")
async def estimate_processing_time(
    duration: float,
    audio_agent = Depends(get_audio_agent)
):
    """
    Estimate processing time for given audio duration
    
    - **duration**: Audio duration in seconds
    """
    try:
        if duration <= 0 or duration > 300:
            raise HTTPException(
                status_code=400, 
                detail="Duration must be between 0 and 300 seconds"
            )
        
        estimated_time = await audio_agent.estimate_processing_time(duration)
        
        return {
            "audio_duration_seconds": duration,
            "estimated_processing_time_seconds": estimated_time,
            "note": "Actual processing time may vary based on server load and audio complexity"
        }
    except Exception as e:
        logger.error(f"Error estimating processing time: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to estimate processing time")

@router.get("/health")
async def audio_service_health(audio_agent = Depends(get_audio_agent)):
    """
    Check health status of audio processing service
    """
    try:
        health_status = await audio_agent.get_health_status()
        is_ready = await audio_agent.is_ready()
        
        return {
            "status": "healthy" if is_ready else "unhealthy",
            "ready": is_ready,
            **health_status,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error checking audio service health: {str(e)}")
        return {
            "status": "unhealthy",
            "ready": False,
            "error": str(e),
            "timestamp": time.time()
        }

# Background Tasks

async def cleanup_audio_processing(task_id: str):
    """Clean up resources after audio processing"""
    try:
        logger.info(f"Cleaning up audio processing task: {task_id}")
        # Add any cleanup logic here (e.g., temp file deletion)
    except Exception as e:
        logger.error(f"Error during audio cleanup: {str(e)}")

# Export router
__all__ = ["router"]