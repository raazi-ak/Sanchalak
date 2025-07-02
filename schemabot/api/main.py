from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import asyncio
import json
import time
from typing import Dict, Any, List, Optional
import structlog
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import uvicorn

# Import core components
from core.scheme.parser import SchemeParser
from core.eligibility.checker import EligibilityChecker
from core.prompts.dynamic_engine import DynamicPromptEngine, ConversationContext
from core.llm.gemma_client import get_gemma_client, gemma_client_lifespan
from api.models import *

# Configure structured logging

# Prometheus metrics
REQUEST_COUNT = Counter('sanchalak_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('sanchalak_request_duration_seconds', 'Request duration')
GENERATION_DURATION = Histogram('sanchalak_generation_duration_seconds', 'LLM generation duration')

# Global components
scheme_parser = None
eligibility_checker = None
prompt_engine = None
conversation_contexts: Dict[str, ConversationContext] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global scheme_parser, eligibility_checker, prompt_engine
    
    logger.info("Starting Sanchalak Backend...")
    
    try:
        # Initialize components
        settings = get_settings()
        
        # Load scheme parser
        scheme_parser = SchemeParser(settings.scheme_yaml_path)
        logger.info(f"Loaded {len(scheme_parser.schemes)} schemes")
        
        # Initialize eligibility checker
        eligibility_checker = EligibilityChecker()
        
        # Initialize prompt engine
        prompt_engine = DynamicPromptEngine(scheme_parser, eligibility_checker)
        
        # Initialize Gemma client
        gemma_client = get_gemma_client()
        health = gemma_client.health_check()
        
        if health["status"] != "healthy":
            raise RuntimeError(f"Gemma client unhealthy: {health}")
        
        logger.info("All components initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        logger.info("Shutting down Sanchalak Backend...")
        # Cleanup
        conversation_contexts.clear()

# Create FastAPI app
app = FastAPI(
    title="Sanchalak - Government Scheme Assistant",
    description="Backend API for checking government scheme eligibility",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging and monitoring
setup_logging(app)
setup_monitoring(app)

# Dependency injection
def get_scheme_parser() -> SchemeParser:
    return scheme_parser

def get_eligibility_checker() -> EligibilityChecker:
    return eligibility_checker

def get_prompt_engine() -> DynamicPromptEngine:
    return prompt_engine

# Health and monitoring endpoints
@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    try:
        # Check all components
        gemma_client = get_gemma_client()
        gemma_health = gemma_client.health_check()
        
        scheme_count = len(scheme_parser.schemes) if scheme_parser else 0
        
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "components": {
                "scheme_parser": {"status": "healthy", "schemes_loaded": scheme_count},
                "eligibility_checker": {"status": "healthy"},
                "prompt_engine": {"status": "healthy"},
                "gemma_client": gemma_health
            },
            "active_conversations": len(conversation_contexts)
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/performance")
async def performance_stats():
    """Get performance statistics"""
    try:
        gemma_client = get_gemma_client()
        stats = gemma_client.get_performance_stats()
        
        return {
            "gemma_performance": stats,
            "active_conversations": len(conversation_contexts),
            "total_schemes": len(scheme_parser.schemes) if scheme_parser else 0
        }
        
    except Exception as e:
        logger.error(f"Performance stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance stats")

# Scheme management endpoints
@app.get("/schemes", response_model=List[SchemeInfo])
async def list_schemes(
    category: Optional[str] = None,
    ministry: Optional[str] = None,
    parser: SchemeParser = Depends(get_scheme_parser)
):
    """List available government schemes"""
    try:
        schemes = parser.list_schemes()
        
        # Apply filters
        if category:
            schemes = [s for s in schemes if s.get('category', '').lower() == category.lower()]
        
        if ministry:
            schemes = [s for s in schemes if ministry.lower() in s.get('ministry', '').lower()]
        
        return [SchemeInfo(**scheme) for scheme in schemes]
        
    except Exception as e:
        logger.error(f"List schemes error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list schemes")

@app.get("/schemes/{scheme_code}", response_model=SchemeDetail)
async def get_scheme_details(
    scheme_code: str,
    parser: SchemeParser = Depends(get_scheme_parser)
):
    """Get detailed information about a specific scheme"""
    try:
        scheme = parser.get_scheme(scheme_code)
        if not scheme:
            raise HTTPException(status_code=404, detail="Scheme not found")
        
        required_fields = parser.get_required_fields(scheme_code)
        
        return SchemeDetail(
            **scheme.dict(),
            required_fields=required_fields
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get scheme details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scheme details")

# Conversation endpoints
@app.post("/conversations/start", response_model=ConversationStartResponse)
async def start_conversation(
    request: ConversationStartRequest,
    prompt_engine: DynamicPromptEngine = Depends(get_prompt_engine)
):
    """Start a new conversation for scheme eligibility checking"""
    try:
        # Generate initial prompt and context
        initial_prompt, context = prompt_engine.generate_initial_prompt(request.scheme_code)
        
        if not context:
            raise HTTPException(status_code=404, detail="Scheme not found")
        
        # Generate initial response
        gemma_client = get_gemma_client()
        
        generation_start = time.time()
        initial_response = await gemma_client.generate_response_async(initial_prompt)
        generation_time = time.time() - generation_start
        
        GENERATION_DURATION.observe(generation_time)
        
        if not initial_response:
            raise HTTPException(status_code=500, detail="Failed to generate initial response")
        
        # Store conversation context
        conversation_contexts[request.session_id] = context
        
        # Add to conversation history
        context.conversation_history.append({
            "role": "assistant",
            "content": initial_response
        })
        
        logger.info(
            f"Started conversation",
            session_id=request.session_id,
            scheme_code=request.scheme_code,
            generation_time=generation_time
        )
        
        return ConversationStartResponse(
            session_id=request.session_id,
            scheme_code=request.scheme_code,
            initial_response=initial_response,
            required_fields=scheme_parser.get_required_fields(request.scheme_code),
            conversation_stage=context.stage
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Start conversation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to start conversation")

@app.post("/conversations/continue", response_model=ConversationResponse)
async def continue_conversation(
    request: ConversationContinueRequest,
    background_tasks: BackgroundTasks,
    prompt_engine: DynamicPromptEngine = Depends(get_prompt_engine)
):
    """Continue an existing conversation"""
    try:
        # Get conversation context
        context = conversation_contexts.get(request.session_id)
        if not context:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Generate follow-up prompt
        followup_prompt = prompt_engine.generate_followup_prompt(context, request.user_input)
        
        # Generate response
        gemma_client = get_gemma_client()
        
        generation_start = time.time()
        response = await gemma_client.generate_response_async(followup_prompt)
        generation_time = time.time() - generation_start
        
        GENERATION_DURATION.observe(generation_time)
        
        if not response:
            raise HTTPException(status_code=500, detail="Failed to generate response")
        
        # Validate response
        scheme = scheme_parser.get_scheme(context.scheme_code)
        is_valid, issues = gemma_client.validate_response(response, {"scheme_name": scheme.name})
        
        if not is_valid:
            logger.warning(f"Response validation issues: {issues}")
        
        # Add to conversation history
        context.conversation_history.extend([
            {"role": "user", "content": request.user_input},
            {"role": "assistant", "content": response}
        ])
        
        # Check if eligibility check is complete
        eligibility_result = None
        if context.eligibility_result:
            eligibility_result = EligibilityResultResponse(
                is_eligible=context.eligibility_result.is_eligible,
                score=context.eligibility_result.score,
                passed_rules=context.eligibility_result.passed_rules,
                failed_rules=context.eligibility_result.failed_rules,
                missing_fields=context.eligibility_result.missing_fields,
                recommendations=context.eligibility_result.recommendations
            )
        
        # Log conversation metrics
        background_tasks.add_task(
            log_conversation_metrics,
            request.session_id,
            context.scheme_code,
            len(context.conversation_history),
            generation_time,
            is_valid
        )
        
        return ConversationResponse(
            session_id=request.session_id,
            response=response,
            conversation_stage=context.stage,
            collected_data=context.collected_data,
            eligibility_result=eligibility_result,
            is_complete=context.stage.value == "result_delivery"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Continue conversation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to continue conversation")

@app.post("/conversations/stream")
async def stream_conversation(
    request: ConversationContinueRequest,
    prompt_engine: DynamicPromptEngine = Depends(get_prompt_engine)
):
    """Stream conversation response for real-time interaction"""
    try:
        # Get conversation context
        context = conversation_contexts.get(request.session_id)
        if not context:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Generate follow-up prompt
        followup_prompt = prompt_engine.generate_followup_prompt(context, request.user_input)
        
        # Stream response
        async def generate_stream():
            try:
                gemma_client = get_gemma_client()
                
                async for token in gemma_client.generate_streaming_response(followup_prompt):
                    yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                
                yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream conversation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to stream conversation")

# Direct eligibility check endpoint
@app.post("/eligibility/check", response_model=EligibilityCheckResponse)
async def check_eligibility(
    request: EligibilityCheckRequest,
    checker: EligibilityChecker = Depends(get_eligibility_checker),
    parser: SchemeParser = Depends(get_scheme_parser)
):
    """Direct eligibility check with complete farmer data"""
    try:
        scheme = parser.get_scheme(request.scheme_code)
        if not scheme:
            raise HTTPException(status_code=404, detail="Scheme not found")
        
        # Perform eligibility check
        result = checker.check_eligibility(request.farmer_data, scheme)
        
        return EligibilityCheckResponse(
            scheme_code=request.scheme_code,
            scheme_name=scheme.name,
            is_eligible=result.is_eligible,
            eligibility_score=result.score,
            passed_rules=result.passed_rules,
            failed_rules=result.failed_rules,
            missing_fields=result.missing_fields,
            recommendations=result.recommendations,
            benefits=scheme.benefits if result.is_eligible else [],
            required_documents=scheme.documents if result.is_eligible else []
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eligibility check error: {e}")
        raise HTTPException(status_code=500, detail="Failed to check eligibility")

# Utility functions
async def log_conversation_metrics(
    session_id: str,
    scheme_code: str,
    message_count: int,
    generation_time: float,
    response_valid: bool
):
    """Log conversation metrics for monitoring"""
    logger.info(
        "Conversation metrics",
        session_id=session_id,
        scheme_code=scheme_code,
        message_count=message_count,
        generation_time=generation_time,
        response_valid=response_valid
    )

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status="500"
    ).inc()
    
    return HTTPException(
        status_code=500,
        detail="An unexpected error occurred"
    )

if __name__ == "__main__":
    settings = get_settings()
    
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,  # Use structlog instead
        access_log=False  # Use custom middleware
    )
