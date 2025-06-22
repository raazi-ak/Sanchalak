"""
AI Agent Service for Sanchalak System
Handles audio transcription, information extraction, and data processing
Called by the Orchestrator to process farmer data
"""

import time
import uuid
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import the existing agent components
from audio_injestion import AudioIngestionAgent
from info_extraction import EnhancedInfoExtractionAgent
from eligibility_checker import EligibilityCheckerAgent
from vector_db import VectorDBAgent
from config import get_settings
from models import FarmerInfo, LanguageCode, ProcessingStatus
from utils.logger import get_logger

# Initialize settings and logger
settings = get_settings()
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Sanchalak AI Agent",
    description="AI processing service for farmer data extraction and analysis",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instances
agents: Dict[str, Any] = {}

# Request/Response models for orchestrator integration
class ProcessRequest(BaseModel):
    session_id: str
    farmer_id: str
    text_content: Optional[str] = None
    voice_file_paths: Optional[list] = None
    language: str = "hi"

class ProcessResponse(BaseModel):
    status: str
    session_id: str
    farmer_data: Optional[Dict[str, Any]] = None
    processing_time: float
    extracted_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    """Initialize AI agents on startup"""
    try:
        logger.info("Initializing AI Agent service...")
        
        # Initialize core agents
        agents["audio"] = AudioIngestionAgent()
        await agents["audio"].initialize()
        
        agents["nlp"] = EnhancedInfoExtractionAgent()
        await agents["nlp"].initialize()
        
        agents["eligibility"] = EligibilityCheckerAgent()  
        await agents["eligibility"].initialize()
        
        agents["vector_db"] = VectorDBAgent()
        await agents["vector_db"].initialize()
        
        logger.info("AI Agent service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize AI Agent service: {str(e)}")
        raise

@app.post("/api/v1/process", response_model=ProcessResponse)
async def process_farmer_data(request: ProcessRequest):
    """
    Main processing endpoint called by Orchestrator
    Processes farmer data and extracts structured information for EFR storage
    """
    start_time = time.time()
    
    try:
        logger.info(f"Processing request for session {request.session_id}")
        
        combined_text = ""
        
        # Step 1: Process voice files if provided
        if request.voice_file_paths:
            logger.info(f"Processing {len(request.voice_file_paths)} voice files")
            for voice_file_path in request.voice_file_paths:
                try:
                    # Use the audio agent to transcribe
                    with open(voice_file_path, "rb") as audio_file:
                        audio_result = await agents["audio"].process_audio(
                            audio_file=audio_file,
                            language_hint=request.language
                        )
                        if audio_result.transcribed_text:
                            combined_text += " " + audio_result.transcribed_text
                except Exception as e:
                    logger.warning(f"Failed to process voice file {voice_file_path}: {str(e)}")
        
        # Step 2: Add text content if provided
        if request.text_content:
            combined_text += " " + request.text_content
        
        if not combined_text.strip():
            raise HTTPException(status_code=400, detail="No content to process")
        
        logger.info(f"Total content length: {len(combined_text)} characters")
        
        # Step 3: Extract farmer information using NLP agent
        logger.info("Extracting farmer information...")
        language_code = LanguageCode(request.language) if request.language in [e.value for e in LanguageCode] else LanguageCode.HINDI
        
        extraction_result = await agents["nlp"].extract_information(
            text=combined_text.strip(),
            language=language_code
        )
        
        # Step 4: Build structured farmer data for EFR database
        farmer_data = {
            "farmer_id": request.farmer_id,
            "session_id": request.session_id,
            "name": extraction_result.farmer_info.name,
            "contact": extraction_result.farmer_info.phone_number,
            "land_size": extraction_result.farmer_info.land_size_acres,
            "crops": extraction_result.farmer_info.crops,
            "location": {
                "state": extraction_result.farmer_info.state,
                "district": extraction_result.farmer_info.district,
                "village": extraction_result.farmer_info.village,
                "pincode": extraction_result.farmer_info.pincode
            },
            "annual_income": extraction_result.farmer_info.annual_income,
            "irrigation_type": extraction_result.farmer_info.irrigation_type,
            "land_ownership": extraction_result.farmer_info.land_ownership,
            "age": extraction_result.farmer_info.age,
            "family_size": extraction_result.farmer_info.family_size,
            "extracted_text": combined_text,
            "language_detected": request.language,
            "processed_at": time.time()
        }
        
        # Remove None values
        farmer_data = {k: v for k, v in farmer_data.items() if v is not None}
        
        processing_time = time.time() - start_time
        
        logger.info(f"Successfully processed farmer data in {processing_time:.2f}s")
        
        return ProcessResponse(
            status="completed",
            session_id=request.session_id,
            farmer_data=farmer_data,
            processing_time=processing_time,
            extracted_info={
                "entities_found": len(extraction_result.entities),
                "confidence_scores": extraction_result.confidence_scores,
                "extraction_method": extraction_result.extraction_method
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Processing failed for session {request.session_id}: {str(e)}")
        
        return ProcessResponse(
            status="error",
            session_id=request.session_id,
            processing_time=processing_time,
            error=str(e)
        )

@app.post("/api/v1/check_eligibility")
async def check_eligibility(farmer_data: Dict[str, Any]):
    """
    Check scheme eligibility for a farmer (called when user uses /status)
    """
    try:
        logger.info(f"Checking eligibility for farmer: {farmer_data.get('farmer_id')}")
        
        # Convert farmer_data to FarmerInfo object
        farmer_info = FarmerInfo(**farmer_data)
        
        # Check eligibility using eligibility agent
        eligibility_response = await agents["eligibility"].check_eligibility(
            farmer_info=farmer_info,
            explain_decisions=True
        )
        
        return {
            "status": "completed",
            "farmer_id": farmer_data.get('farmer_id'),
            "eligibility_response": eligibility_response.dict()
        }
        
    except Exception as e:
        logger.error(f"Eligibility check failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AI Agent",
        "agents_loaded": list(agents.keys()),
        "version": "1.0.0"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=True if settings.environment == "development" else False
    )