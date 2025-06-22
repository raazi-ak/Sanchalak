from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import shutil
import time
import httpx
import logging
from agent import transcribe_and_parse, send_to_efr_db, send_to_form_filler, update_status

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  

app = FastAPI(title="Sanchalak Orchestrator", version="1.0.0")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Configuration from environment variables  
USE_AI_AGENT = os.getenv("USE_AI_AGENT", "true").lower() == "true"  # Enable AI agent by default
AI_AGENT_URL = os.getenv("AI_AGENT_URL", "http://ai-agent:8004")

# Pydantic models for session processing
class SessionMessage(BaseModel):
    type: str  # "text" or "voice"
    content: Optional[str] = None
    file_path: Optional[str] = None
    timestamp: str

class SessionData(BaseModel):
    session_id: str
    farmer_id: str
    start_time: str
    messages: List[SessionMessage]
    user_language: Optional[str] = "hi"

class ProcessingResponse(BaseModel):
    status: str
    session_id: str
    eligibility_status: Optional[str] = None
    eligible_schemes: Optional[List[str]] = None
    recommendations: Optional[List[str]] = None
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None
    analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    # New fields for better error handling
    service_status: Optional[Dict[str, str]] = None  # Track each service status
    fallback_used: Optional[str] = None  # Which fallback was used
    error_code: Optional[str] = None  # Specific error code for debugging

@app.post("/upload")
async def upload_voice(farmer_id: str = Form(...), file: UploadFile = File(...)):
    """Legacy endpoint for single file upload"""
    file_location = os.path.join(UPLOAD_DIR, f"{farmer_id}_{file.filename}")
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Step 1: Parse (mock)
    parsed_farmer = transcribe_and_parse(file_location)

    # Step 2: Send to EFR_DB
    send_to_efr_db(parsed_farmer)

    # Step 3: Send to form_filler
    form_response = send_to_form_filler(parsed_farmer) 
    if not form_response:
        return JSONResponse(status_code=500, content={"error": "Form filling failed"}) 
    scheme_name = form_response.get("scheme_name")     

    # Step 4: Update status
    update_status(farmer_id, scheme_name)  

    return JSONResponse(content={
        "message": "Voice uploaded and processed",
        "path": file_location,
        "parsed_data": parsed_farmer,
        "scheme": scheme_name,
        "status": "submitted"
    })

@app.post("/process_session", response_model=ProcessingResponse)
async def process_session(session_data: SessionData):
    """Process a complete session from Telegram bot"""
    
    try:
        start_time = time.time()
        
        # Extract and process messages
        text_messages = []
        voice_files = []
        
        for message in session_data.messages:
            if message.type == "text" and message.content:
                text_messages.append(message.content)
            elif message.type == "voice" and message.file_path:
                voice_files.append(message.file_path)
        
        # Combine all text content
        combined_text = " ".join(text_messages)
        
        # Process voice files (mock transcription for now)
        transcribed_voice_content = []
        for voice_file in voice_files:
            # Mock transcription - in reality, this would use speech-to-text
            mock_transcription = _mock_voice_transcription(voice_file)
            transcribed_voice_content.append(mock_transcription)
        
        # Combine all content
        all_content = combined_text + " " + " ".join(transcribed_voice_content)
        
        # Send to AI Agent for processing - fail if AI agent is required but unavailable
        if USE_AI_AGENT:
            # Call real AI Agent - raise error if it fails
            analysis_result = await _call_ai_agent(
                content=all_content,
                voice_files=voice_files,
                farmer_id=session_data.farmer_id,
                session_id=session_data.session_id,
                language=session_data.user_language or "hi"
            )
            
            # Check if AI agent failed and we should not fallback
            if analysis_result.get("error_code") and analysis_result["error_code"].startswith("AI_AGENT_"):
                # AI Agent failed - return proper error instead of mock data
                error_msg = analysis_result.get("error_details", {})
                service_status = analysis_result.get("service_status", {})
                
                return ProcessingResponse(
                    status="service_unavailable",
                    session_id=session_data.session_id,
                    error="One or more services are currently not operational, but worry not, your log is safe.",
                    error_code=analysis_result["error_code"],
                    service_status=service_status,
                    fallback_used=None,
                    processing_time=None
                )
        else:
            # Use mock analysis for development (when AI agent is explicitly disabled)
            analysis_result = _analyze_farmer_content(
                content=all_content,
                farmer_id=session_data.farmer_id,
                language=session_data.user_language or "hi"
            )
        
        # Build response with detailed service status
        response = ProcessingResponse(
            status="completed",
            session_id=session_data.session_id,
            eligibility_status=analysis_result.get("eligibility_status"),
            eligible_schemes=analysis_result.get("eligible_schemes"),
            recommendations=analysis_result.get("recommendations"),
            confidence_score=analysis_result.get("confidence_score"),
            processing_time=None,
            analysis={
                "text_messages_analyzed": len(text_messages),
                "voice_messages_processed": len(voice_files),
                "total_messages": len(session_data.messages),
                "content_length": len(all_content),
                "detected_topics": analysis_result.get("detected_topics", [])
            },
            # Include service status and error details
            service_status=analysis_result.get("service_status", {}),
            fallback_used=analysis_result.get("fallback_used"),
            error_code=analysis_result.get("error_code"),
            error=analysis_result.get("error_details", {}).get("connection_error") or 
                  analysis_result.get("error_details", {}).get("timeout_error") or
                  analysis_result.get("error_details", {}).get("http_error") or
                  analysis_result.get("error_details", {}).get("unexpected_error")
        )
        
        # Send to downstream services
        if analysis_result.get("farmer_data"):
            send_to_efr_db(analysis_result["farmer_data"])
            
            # Send to form filler for scheme applications
            if analysis_result.get("eligible_schemes"):
                form_response = send_to_form_filler(analysis_result["farmer_data"])
                if form_response and form_response.get("scheme_name"):
                    update_status(session_data.farmer_id, form_response["scheme_name"])
        
        return response
        
    except Exception as e:
        return ProcessingResponse(
            status="error",
            session_id=session_data.session_id,
            error="One or more services are currently not operational, but worry not, your log is safe.",
            processing_time=None
        )

async def _call_ai_agent(content: str, voice_files: List[str], farmer_id: str, session_id: str, language: str) -> Dict[str, Any]:
    """Call the AI Agent for real processing with detailed error tracking"""
    import httpx
    
    ai_agent_status = "unknown"
    error_details = {}
    
    try:
        # First check if AI agent is available
        logger.info(f"🔍 Checking AI Agent health at {AI_AGENT_URL}/health")
        async with httpx.AsyncClient() as client:
            health_response = await client.get(
                f"{AI_AGENT_URL}/health",
                timeout=5.0
            )
            health_response.raise_for_status()
            ai_agent_status = "healthy"
            health_data = health_response.json()
            logger.info(f"✅ AI Agent is healthy: {health_data}")
            logger.info(f"📊 AI Agent services: {health_data.get('services', {})}")
        
        # Prepare data for AI Agent (matching ProcessRequest model)
        ai_payload = {
            "session_id": session_id,
            "farmer_id": farmer_id,
            "text_content": content,
            "voice_file_paths": voice_files,
            "language": language
        }
        
        logger.info(f"📤 Sending session data to AI Agent: {AI_AGENT_URL}/api/v1/process")
        logger.info(f"📋 Payload summary: session_id={ai_payload['session_id']}, text_length={len(ai_payload['text_content'])}, voice_files={len(ai_payload['voice_file_paths'])}")
        
        # Call AI Agent
        async with httpx.AsyncClient() as client:
            logger.info("🔄 Making API call to AI Agent...")
            response = await client.post(
                f"{AI_AGENT_URL}/api/v1/process",
                json=ai_payload,
                timeout=60.0
            )
            response.raise_for_status()
            ai_result = response.json()
            
            logger.info(f"✅ AI Agent response received: status={ai_result.get('status')}")
            logger.info(f"📊 Processing results: farmer_data={bool(ai_result.get('farmer_data'))}, extraction_time={ai_result.get('processing_time', 'N/A')}s")
            ai_agent_status = "processing_completed"
            
            # Convert AI agent response to expected orchestrator format
            if ai_result.get("status") == "completed" and ai_result.get("farmer_data"):
                farmer_data = ai_result["farmer_data"]
                
                return {
                    "farmer_data": farmer_data,
                    "eligibility_status": "processed_by_ai_agent",
                    "eligible_schemes": [],
                    "recommendations": [
                        "Your farming data has been successfully processed by AI",
                        "Use /status command to check scheme eligibility"
                    ],
                    "confidence_score": 0.9,
                    "detected_topics": ["ai_processed_farming_data"],
                    "service_status": {"ai_agent": ai_agent_status},
                    "fallback_used": None,
                    "error_code": None
                }
            else:
                ai_agent_status = "processing_failed"
                error_details["ai_processing_error"] = ai_result.get('error', 'Unknown processing error')
                raise Exception(f"AI Agent processing failed: {ai_result.get('error', 'Unknown error')}")
            
    except httpx.ConnectError as e:
        ai_agent_status = "connection_failed"
        error_details["connection_error"] = f"Cannot connect to AI Agent at {AI_AGENT_URL}"
        error_details["technical_details"] = str(e)
        logger.error(f"🔌 AI Agent connection failed: {e}")
        logger.error(f"🌐 Target URL: {AI_AGENT_URL}")
    except httpx.TimeoutException as e:
        ai_agent_status = "timeout"
        error_details["timeout_error"] = "AI Agent took too long to respond"
        error_details["technical_details"] = str(e)
        logger.error(f"⏱️ AI Agent timeout after 60s: {e}")
    except httpx.HTTPStatusError as e:
        ai_agent_status = "http_error"
        error_details["http_error"] = f"AI Agent returned HTTP {e.response.status_code}"
        error_details["technical_details"] = str(e)
        logger.error(f"🚫 AI Agent HTTP error {e.response.status_code}: {e}")
        try:
            error_body = e.response.text
            logger.error(f"📄 Error response body: {error_body}")
        except:
            pass
    except Exception as e:
        ai_agent_status = "unexpected_error"
        error_details["unexpected_error"] = str(e)
        logger.error(f"💥 AI Agent unexpected error: {e}")
        import traceback
        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
    
    # Return error details instead of falling back to mock analysis
    return {
        "error_code": f"AI_AGENT_{ai_agent_status.upper()}",
        "service_status": {"ai_agent": ai_agent_status},
        "error_details": error_details,
        "fallback_used": None,
        # Don't include farmer_data or other fields that would indicate success
    }

def _mock_voice_transcription(file_path: str) -> str:
    """Mock voice transcription - replace with actual speech-to-text"""
    # Simulate different types of farmer speech based on filename
    mock_transcriptions = [
        "मेरे पास 2 एकड़ जमीन है और मैं धान की खेती करता हूं। मुझे कृषि लोन चाहिए।",
        "I have small farm with wheat and need help with government schemes for farmers.",
        "എനിക്ക് ഒരു ഏക്കർ സ്ഥലമുണ്ട്, നെല്ലുകൃഷി ചെയ്യുന്നു. സർക്കാർ സഹായം വേണം।",
        "मला शेतीसाठी कर्ज हवे आहे. माझ्याकडे 3 एकर जमीन आहे.",
        "నాకు వ్యవసాయ రుణం కావాలి. నేను వరి, మిరపకాయ పండిస్తాను."
    ]
    
    # Simple hash-based selection for consistency
    import hashlib
    hash_value = int(hashlib.md5(file_path.encode()).hexdigest(), 16)
    return mock_transcriptions[hash_value % len(mock_transcriptions)]

def _analyze_farmer_content(content: str, farmer_id: str, language: str) -> Dict[str, Any]:
    """Analyze farmer content and determine eligibility"""
    
    content_lower = content.lower()
    
    # Detect topics and keywords
    detected_topics = []
    eligible_schemes = []
    
    # Crop-related keywords
    crop_keywords = {
        "rice": ["rice", "धान", "चावल", "നെല്ല്", "तांदूळ", "వరి"],
        "wheat": ["wheat", "गेहूं", "ഗോതമ്പ്", "गहू", "గోధుమ"],
        "cotton": ["cotton", "कपास", "പരുത്തി", "कापूस", "పత్తి"],
        "sugarcane": ["sugarcane", "गन्ना", "കരിമ്പ്", "ऊस", "చెరకు"]
    }
    
    detected_crops = []
    for crop, keywords in crop_keywords.items():
        if any(keyword in content_lower for keyword in keywords):
            detected_crops.append(crop)
            detected_topics.append(f"crops_{crop}")
    
    # Land size detection
    land_size = None
    if any(word in content_lower for word in ["एकड़", "acre", "ഏക്കർ", "एकर", "ఎకరం"]):
        detected_topics.append("land_ownership")
        # Mock land size detection
        land_size = 2.5  # Default assumption
    
    # Financial needs
    financial_needs = []
    if any(word in content_lower for word in ["loan", "लोन", "कर्ज", "വായ്പ", "कर्ज", "రుణం"]):
        financial_needs.append("credit")
        detected_topics.append("financial_assistance")
    
    # Determine eligible schemes based on analysis
    if detected_crops:
        eligible_schemes.append("PM-KISAN")
        if "rice" in detected_crops or "wheat" in detected_crops:
            eligible_schemes.append("PMFBY")  # Crop Insurance
    
    if financial_needs:
        eligible_schemes.append("Kisan Credit Card")
    
    if land_size and land_size <= 2:
        eligible_schemes.append("PM-KISAN")  # Small farmers
    
    # Generate recommendations
    recommendations = []
    if "PM-KISAN" in eligible_schemes:
        recommendations.append("Apply for PM-KISAN scheme for direct income support")
    if "PMFBY" in eligible_schemes:
        recommendations.append("Consider crop insurance under PMFBY scheme")
    if "Kisan Credit Card" in eligible_schemes:
        recommendations.append("Apply for Kisan Credit Card for flexible agricultural credit")
    
    # Add general recommendations
    recommendations.extend([
        "Get soil health card for better crop planning",
        "Explore organic farming certification programs",
        "Join farmer producer organizations for better market access"
    ])
    
    # Mock farmer data for downstream services (matching EFR database schema)
    farmer_data = {
        "farmer_id": farmer_id,  # Required by EFR database
        "name": f"Farmer_{farmer_id}",
        "contact": "9876543210",  # Mock
        "land_size": land_size or 2.0,
        "crops": detected_crops or ["rice"],
        "location": "India",  # Mock
        "language_detected": language,
        "extracted_text": content,
        "processed_at": time.time()
    }
    
    return {
        "eligibility_status": "eligible" if eligible_schemes else "needs_more_info",
        "eligible_schemes": eligible_schemes,
        "recommendations": recommendations[:3],  # Limit to top 3
        "confidence_score": 0.85 if len(detected_topics) >= 2 else 0.60,
        "detected_topics": detected_topics,
        "farmer_data": farmer_data,
        # Default service status when not using AI agent
        "service_status": {"orchestrator": "mock_analysis_used"},
        "fallback_used": None,
        "error_code": None
    }

def _extract_basic_farmer_data(content: str, farmer_id: str, session_id: str, language: str) -> Dict[str, Any]:
    """Extract basic farmer data for storage without eligibility analysis"""
    
    content_lower = content.lower()
    
    # Basic extraction without deep analysis
    detected_crops = []
    crop_keywords = {
        "rice": ["rice", "धान", "चावल", "നെല്ല്", "तांदूळ", "వరి"],
        "wheat": ["wheat", "गेहूं", "ഗോതമ്പ്", "गहू", "గోధుమ"],
        "cotton": ["cotton", "कपास", "പരുത്തി", "कापूस", "పత్తి"],
        "sugarcane": ["sugarcane", "गन्ना", "കരിമ്പ്", "ऊस", "చెరకు"]
    }
    
    for crop, keywords in crop_keywords.items():
        if any(keyword in content_lower for keyword in keywords):
            detected_crops.append(crop)
    
    # Simple land size detection
    land_size = None
    if any(word in content_lower for word in ["एकड़", "acre", "ഏക്കർ", "एकर", "ఎకరం"]):
        land_size = 2.0  # Default assumption
    
    # Basic farmer data for storage
    farmer_data = {
        "session_id": session_id,
        "farmer_id": farmer_id,
        "name": f"Farmer_{farmer_id}",
        "content": content,
        "detected_crops": detected_crops,
        "estimated_land_size": land_size,
        "language": language,
        "stored_at": time.time(),
        "data_type": "session_data"
    }
    
    return farmer_data

# Removed duplicate /api/process_session endpoint - main flow uses /process_session

@app.post("/api/check_eligibility")
async def api_check_eligibility(request: Dict[str, Any]):
    """Check scheme eligibility via AI Agent - called by Telegram bot"""
    try:
        farmer_data = request.get("farmer_data", {})
        scheme_code = request.get("scheme_code", "")
        
        if not farmer_data.get("farmer_id"):
            raise HTTPException(status_code=400, detail="farmer_id is required")
        
        # Check if AI Agent is available and use it for eligibility check
        if USE_AI_AGENT:
            try:
                async with httpx.AsyncClient() as client:
                    # Call AI Agent's eligibility endpoint
                    response = await client.post(
                        f"{AI_AGENT_URL}/api/v1/check_eligibility",
                        json=farmer_data,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    ai_result = response.json()
                    
                    if ai_result.get("status") == "completed":
                        eligibility_response = ai_result.get("eligibility_response", {})
                        return {
                            "eligible": True,
                            "schemes": eligibility_response.get("eligible_schemes", []),
                            "details": eligibility_response.get("explanations", {}),
                            "confidence": eligibility_response.get("confidence_score", 0.8),
                            "source": "ai_agent"
                        }
                    else:
                        # Fallback to mock
                        return _mock_eligibility_check(farmer_data, scheme_code)
                        
            except Exception as e:
                print(f"AI Agent eligibility check failed: {e}")
                return _mock_eligibility_check(farmer_data, scheme_code)
        else:
            return _mock_eligibility_check(farmer_data, scheme_code)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eligibility check failed: {str(e)}")

@app.post("/api/generate_form")
async def api_generate_form(request: Dict[str, Any]):
    """Generate form via form filler - called by Telegram bot"""
    try:
        farmer_id = request.get("farmer_id")
        scheme_code = request.get("scheme_code", "PM-KISAN")
        
        if not farmer_id:
            raise HTTPException(status_code=400, detail="farmer_id is required")
        
        # Get farmer data from EFR database
        efr_db_url = os.getenv("EFR_DB_URL", "http://efr-db:8000")
        async with httpx.AsyncClient() as client:
            farmer_response = await client.get(f"{efr_db_url}/farmer/{farmer_id}")
            
            if farmer_response.status_code == 404:
                raise HTTPException(status_code=404, detail="Farmer not found")
            
            farmer_response.raise_for_status()
            farmer_data = farmer_response.json()
        
        # Send to form filler
        form_result = send_to_form_filler(farmer_data)
        
        if form_result and form_result.get("scheme_name"):
            # Update status tracker
            update_status(farmer_id, form_result["scheme_name"])
            
            return {
                "success": True,
                "form_data": form_result.get("filled_form", {}),
                "scheme_name": form_result.get("scheme_name"),
                "file_path": form_result.get("saved_to"),
                "status": "generated"
            }
        else:
            raise HTTPException(status_code=500, detail="Form generation failed")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Form generation failed: {str(e)}")

def _mock_eligibility_check(farmer_data: Dict[str, Any], scheme_code: str) -> Dict[str, Any]:
    """Mock eligibility check when AI Agent is not available"""
    land_size = farmer_data.get("land_size", 0)
    crops = farmer_data.get("crops", [])
    location = farmer_data.get("location", {})
    
    eligible_schemes = []
    
    # Basic eligibility logic
    if land_size <= 5:  # Small farmer
        eligible_schemes.append("PM-KISAN")
    
    if any(crop in ["rice", "wheat", "cotton"] for crop in crops):
        eligible_schemes.append("PMFBY")  # Crop insurance
    
    if land_size > 0:
        eligible_schemes.append("Kisan Credit Card")
    
    return {
        "eligible": len(eligible_schemes) > 0,
        "schemes": eligible_schemes,
        "details": {
            "land_size_category": "small" if land_size <= 2 else "medium" if land_size <= 5 else "large",
            "crop_eligibility": "eligible" if crops else "needs_crops_info"
        },
        "confidence": 0.7,
        "source": "mock_orchestrator"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "orchestrator",
        "timestamp": time.time()
    }
