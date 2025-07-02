from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.transcribe_routes import router as transcribe_router
from api.tts_routes import router as tts_router
from fastapi.responses import FileResponse
from fastapi import HTTPException
import os
app = FastAPI(
    title="Sanchalak API",
    description="Backend for Sanchalak — audio-based interaction system for government schemes",
    version="1.0.0"
)

# Enable CORS for frontend development/testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve TTS-generated audio files
@app.get("/tts/audio/{filename}", tags=["Text-to-Speech"])
async def get_audio(filename: str):
    file_path = os.path.join("tts_outputs", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Audio file not found")

# Register API routers
app.include_router(transcribe_router, tags=["Transcription"])
app.include_router(tts_router, prefix="/tts", tags=["Text-to-Speech"])

# Root endpoint
@app.get("/", tags=["Info"])
async def root():
    return {
        "message": "Sanchalak Agricultural Voice Assistant API",
        "version": "1.0.0",
        "description": "Transcribes, translates, and responds to farmer queries"
    }

# Health check endpoint
@app.get("/health", tags=["Health Check"])
async def health_check():
    return {"status": "healthy", "service": "Sanchalak API"}
