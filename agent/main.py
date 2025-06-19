"""
Main FastAPI application for the Farmer AI Pipeline
Handles HTTP requests and orchestrates the entire AI/NLP pipeline
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any
from info_extraction import EnhancedInfoExtractionAgent
from eligibility_checker import EligibilityCheckerAgent
from vector_db import VectorDBAgent
from web_scraper import WebScraperAgent

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Response, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
import uvicorn

from config import get_settings
from models import *
from utils_logger import get_logger, configure_uvicorn_logger
from errorhandler import setup_error_handlers
from router_audio import router as audio_router
from router_schemes import router as schemes_router
from OllamaAgent import OllamaAgent
from audio_ingestion import AudioIngestionAgent
from app.agents.info_extraction import InfoExtractionAgent
from app.agents.eligibility_checker import EligibilityCheckerAgent
from app.agents.vector_db import VectorDBAgent
from app.agents.web_scraper import WebScraperAgent

# Initialize settings and logger
settings = get_settings()
logger = get_logger(__name__)

# Global agent instances
agents: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting Farmer AI Pipeline...")
    
    try:
        # Initialize agents
        logger.info("Initializing AI agents...")
        
        agents["audio"] = AudioIngestionAgent()
        await agents["audio"].initialize()
        
        # Replace the nlp agent initialization
        agents["nlp"] = EnhancedInfoExtractionAgent()  # Use the enhanced version
        await agents["nlp"].initialize()

        
        agents["eligibility"] = EligibilityCheckerAgent()
        await agents["eligibility"].initialize()
        
        agents["vector_db"] = VectorDBAgent()
        await agents["vector_db"].initialize()
        
        agents["scraper"] = WebScraperAgent()
        await agents["scraper"].initialize()
        
        logger.info("All agents initialized successfully")
        
        # Start background tasks
        if settings.environment == "production":
            # Schedule periodic scheme updates
            pass
            
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down Farmer AI Pipeline...")
        for agent_name, agent in agents.items():
            try:
                if hasattr(agent, 'cleanup'):
                    await agent.cleanup()
                logger.info(f"Cleaned up {agent_name} agent")
            except Exception as e:
                logger.error(f"Error cleaning up {agent_name}: {str(e)}")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-powered scheme matching for Indian farmers using voice processing and NLP",
    version=settings.version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

if settings.environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.farmrai.com", "localhost"]
    )

# Security
security = HTTPBearer(auto_error=False)


@app.middleware("http")
async def process_time_middleware(request: Request, call_next):
    """Add processing time to response headers"""
    start_time = time.time()
    
    # Generate request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 3))
    response.headers["X-Request-ID"] = request_id
    
    # Log request
    logger.info(
        f"Request processed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time": process_time,
            "user_agent": request.headers.get("user-agent"),
            "ip": request.client.host if request.client else None
        }
    )
    
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple rate limiting middleware"""
    # In production, use Redis-based rate limiting
    # For now, this is a placeholder
    response = await call_next(request)
    return response


# Setup error handlers
setup_error_handlers(app)

# Include routers
app.include_router(
    audio.router,
    prefix="/api/v1/audio",
    tags=["audio"],
    dependencies=[]
)

app.include_router(
    schemes.router,
    prefix="/api/v1/schemes",
    tags=["schemes"],
    dependencies=[]
)


# Health check endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    uptime = time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0
    
    models_loaded = {}
    for agent_name, agent in agents.items():
        if hasattr(agent, 'is_ready'):
            models_loaded[agent_name] = await agent.is_ready()
        else:
            models_loaded[agent_name] = True
    
    return HealthResponse(
        version=settings.version,
        uptime=uptime,
        models_loaded=models_loaded
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to the Farmer AI Pipeline",
        "version": settings.version,
        "docs_url": "/docs" if settings.debug else "Contact administrator for API documentation",
        "status": "operational"
    }


# Complete pipeline endpoint
@app.post("/api/v1/process", response_model=FarmerPipelineResponse)
async def process_farmer_request(
    background_tasks: BackgroundTasks,
    request: FarmerPipelineRequest,
    audio_file: Optional[UploadFile] = File(None)
):
    """
    Complete farmer request processing pipeline
    Handles audio transcription, information extraction, and scheme matching
    """
    task_id = str(uuid.uuid4())
    
    try:
        logger.info(f"Starting pipeline processing for task {task_id}")
        start_time = time.time()
        
        processing_steps = []
        farmer_info = None
        transcribed_text = None
        detected_language = None
        
        # Step 1: Audio Processing (if audio file provided)
        if audio_file:
            logger.info(f"Processing audio file for task {task_id}")
            
            # Validate audio file
            if audio_file.content_type not in ["audio/wav", "audio/mpeg", "audio/mp4", "audio/ogg"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported audio format: {audio_file.content_type}"
                )
            
            contents = await audio_file.read()
            audio_file.seek(0)
            if len(contents) > settings.max_audio_size_mb * 1024 * 1024:
                raise HTTPException(
                status_code=400,
                detail=f"Audio file too large. Max size is {settings.max_audio_size_mb}MB"
            )

            
            # Process audio
            audio_result = await agents["audio"].process_audio(
                audio_file=audio_file,
                language_hint=request.language_hint
            )
            
            transcribed_text = audio_result.transcribed_text
            detected_language = audio_result.detected_language
            
            processing_steps.append({
                "step": "audio_transcription",
                "status": "completed",
                "processing_time": audio_result.processing_time,
                "confidence": audio_result.confidence_score
            })
            
        elif request.text_input:
            transcribed_text = request.text_input
            detected_language = request.language_hint
            
            processing_steps.append({
                "step": "text_input",
                "status": "completed",
                "processing_time": 0.0
            })
        else:
            raise HTTPException(
                status_code=400,
                detail="Either audio file or text input is required"
            )
        
        # Step 2: Information Extraction
        if transcribed_text:
            logger.info(f"Extracting information for task {task_id}")
            
            extraction_result = await agents["nlp"].extract_information(
                text=transcribed_text,
                language=detected_language or request.language_hint
            )
            
            farmer_info = extraction_result.farmer_info
            
            processing_steps.append({
                "step": "information_extraction",
                "status": "completed",
                "processing_time": (time.time() - start_time),
                "entities_found": len(extraction_result.entities),
                "confidence_scores": extraction_result.confidence_scores
            })
        
        # Step 3: Scheme Matching (if requested)
        eligibility_response = None
        relevant_schemes = []
        
        if request.include_scheme_recommendations and farmer_info:
            logger.info(f"Checking scheme eligibility for task {task_id}")
            
            # Vector search for relevant schemes
            if transcribed_text:
                search_results = await agents["vector_db"].search_schemes(
                    query=transcribed_text,
                    top_k=settings.top_k_results
                )
                relevant_schemes = search_results
            
            # Eligibility check
            eligibility_response = await agents["eligibility"].check_eligibility(
                farmer_info=farmer_info,
                explain_decisions=request.explain_decisions
            )
            
            processing_steps.append({
                "step": "scheme_matching",
                "status": "completed",
                "processing_time": (time.time() - start_time),
                "schemes_found": len(relevant_schemes),
                "eligible_schemes": eligibility_response.eligible_count if eligibility_response else 0
            })
        
        total_processing_time = time.time() - start_time
        
        # Prepare response
        response = FarmerPipelineResponse(
            task_id=task_id,
            farmer_info=farmer_info,
            eligibility_response=eligibility_response,
            processing_steps=processing_steps,
            total_processing_time=total_processing_time,
            transcription=transcribed_text,
            detected_language=detected_language,
            relevant_schemes=relevant_schemes,
            status=ProcessingStatus.COMPLETED
        )
        
        # Log successful completion
        logger.info(f"Pipeline processing completed for task {task_id} in {total_processing_time:.2f}s")
        
        # Schedule background tasks for analytics
        background_tasks.add_task(log_usage_metrics, task_id, response)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pipeline processing failed for task {task_id}: {str(e)}")
        
        return FarmerPipelineResponse(
            task_id=task_id,
            processing_steps=processing_steps,
            total_processing_time=time.time() - start_time,
            status=ProcessingStatus.FAILED
        )


async def log_usage_metrics(task_id: str, response: FarmerPipelineResponse):
    """Log usage metrics for analytics"""
    try:
        # In production, store in database or send to analytics service
        logger.info(f"Logging metrics for task {task_id}")
    except Exception as e:
        logger.error(f"Failed to log metrics: {str(e)}")


# Task status endpoint
@app.get("/api/v1/tasks/{task_id}", response_model=ProcessingTask)
async def get_task_status(task_id: str):
    """Get status of a background task"""
    # In production, implement with Celery or similar
    return ProcessingTask(
        task_id=task_id,
        task_type="farmer_pipeline",
        status=ProcessingStatus.COMPLETED,
        progress=100.0
    )


# Metrics endpoint (for monitoring)
@app.get("/api/v1/metrics")
async def get_metrics():
    """Get application metrics"""
    if not settings.enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    
    return {
        "uptime": time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0,
        "agents_status": {
            agent_name: await agent.is_ready() if hasattr(agent, 'is_ready') else True
            for agent_name, agent in agents.items()
        },
        "memory_usage": "Not implemented",  # Implement with psutil
        "request_count": "Not implemented"   # Implement with Redis counter
    }


# Admin endpoints (protected in production)
@app.post("/api/v1/admin/reload-schemes")
async def reload_schemes():
    """Reload government schemes from external sources"""
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Admin endpoint disabled in production")
    
    try:
        await agents["scraper"].update_schemes()
        await agents["vector_db"].rebuild_index()
        return {"message": "Schemes reloaded successfully"}
    except Exception as e:
        logger.error(f"Failed to reload schemes: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reload schemes")


@app.post("/api/v1/admin/update-models")
async def update_models():
    """Update ML models"""
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Admin endpoint disabled in production")
    
    try:
        # Reinitialize agents with latest models
        for agent_name, agent in agents.items():
            await agent.update_models()
        return {"message": "Models updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update models")


if __name__ == "__main__":
    # Store start time
    app.state.start_time = time.time()
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
        access_log=True,
        use_colors=True
    )