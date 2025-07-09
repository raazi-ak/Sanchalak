#schemabot\api\main.py

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from contextlib import asynccontextmanager
import asyncio
import json
import time
from typing import Dict, Any, List, Optional
import structlog
import yaml
from pathlib import Path
import sys
import os

# Add src to path to import our modules
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import our actual components
from efr_database.models import Farmer, DatabaseResponse
from pipeline.pm_kisan_checker import PMKisanChecker
import requests

# Configure structured logging
logger = structlog.get_logger()

# Global components
scheme_registry = None
pm_kisan_checker = None
conversation_contexts: Dict[str, Dict] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global scheme_registry, pm_kisan_checker
    
    logger.info("Starting Sanchalak Backend...")
    
    try:
        # Load scheme registry
        scheme_yaml_path = Path(__file__).parent.parent.parent / "schemes" / "outputs" / "supported_schemes.yaml"
        with open(scheme_yaml_path, 'r') as f:
            scheme_registry = yaml.safe_load(f)
        
        # Initialize PM-KISAN checker
        pm_kisan_checker = PMKisanChecker()
        
        logger.info(f"Loaded {len(scheme_registry.get('schemes', []))} schemes")
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Scheme management endpoints
@app.get("/schemes")
async def list_schemes():
    """List available government schemes"""
    try:
        schemes = scheme_registry.get('schemes', [])
        return {
            "schemes": schemes,
            "total": len(schemes)
        }
    except Exception as e:
        logger.error(f"List schemes error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list schemes")

@app.get("/schemes/{scheme_code}")
async def get_scheme_details(scheme_code: str):
    """Get detailed information about a specific scheme"""
    try:
        schemes = scheme_registry.get('schemes', [])
        scheme = next((s for s in schemes if s.get('code') == scheme_code), None)
        
        if not scheme:
            raise HTTPException(status_code=404, detail="Scheme not found")
        
        # Load the actual canonical YAML for detailed info
        if scheme_code == "PM-KISAN":
            canonical_path = Path(__file__).parent.parent.parent / "schemes" / "outputs" / "pm-kisan" / "rules_canonical_ENHANCED.yaml"
            if canonical_path.exists():
                with open(canonical_path, 'r') as f:
                    canonical_data = yaml.safe_load(f)
                scheme['canonical_data'] = canonical_data
        
        return scheme
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get scheme details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scheme details")

# EFR Database integration
@app.get("/farmer/{farmer_id}")
async def get_farmer(farmer_id: str):
    """Get farmer data from EFR database"""
    try:
        response = requests.get(f"http://localhost:8001/farmer/{farmer_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=404, detail=f"Farmer not found: {e}")

@app.post("/farmer")
async def create_farmer(farmer_data: Dict[str, Any]):
    """Create farmer in EFR database"""
    try:
        response = requests.post("http://localhost:8001/farmer", json=farmer_data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to create farmer: {e}")

# Eligibility checking
@app.post("/eligibility/check/{scheme_code}")
async def check_eligibility(scheme_code: str, farmer_id: str):
    """Check eligibility for a specific scheme"""
    try:
        if scheme_code == "PM-KISAN":
            # Get farmer data from EFR
            farmer_response = requests.get(f"http://localhost:8001/farmer/{farmer_id}")
            farmer_response.raise_for_status()
            farmer_data = farmer_response.json()
            
            # Check eligibility using Prolog
            is_eligible, explanation = pm_kisan_checker.check_eligibility(farmer_id, farmer_data)
            
            return {
                "scheme_code": scheme_code,
                "farmer_id": farmer_id,
                "is_eligible": is_eligible,
                "explanation": explanation,
                "farmer_data": farmer_data
            }
        else:
            raise HTTPException(status_code=400, detail=f"Scheme {scheme_code} not yet supported")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eligibility check error: {e}")
        raise HTTPException(status_code=500, detail="Failed to check eligibility")

# Simple conversation endpoints
@app.post("/conversations/")
async def start_conversation(request: dict):
    """Start a new conversation"""
    try:
        session_id = request.get("session_id")
        scheme_code = request.get("scheme_code")
        
        if not session_id or not scheme_code:
            raise HTTPException(status_code=400, detail="session_id and scheme_code are required")
        
        # Get scheme details
        schemes = scheme_registry.get('schemes', [])
        scheme = next((s for s in schemes if s.get('code') == scheme_code), None)
        
        if not scheme:
            raise HTTPException(status_code=404, detail="Scheme not found")
        
        # Initialize conversation context
        conversation_contexts[session_id] = {
            "scheme_code": scheme_code,
            "scheme_name": scheme.get('name', ''),
            "messages": [],
            "stage": "initial",
            "collected_data": {}
        }
        
        # Generate initial response
        initial_response = f"Welcome! I can help you with the {scheme.get('name', '')} scheme. What would you like to know?"
        
        # Add to conversation history
        conversation_contexts[session_id]["messages"].append({
            "role": "assistant",
            "content": initial_response
        })
        
        return {
            "session_id": session_id,
            "scheme_code": scheme_code,
            "initial_response": initial_response,
            "required_fields": scheme.get('canonical', {}).get('required_fields', []),
            "conversation_stage": "initial"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Start conversation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to start conversation")

@app.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, request: dict):
    """Send a message to an existing conversation"""
    try:
        # Get conversation context
        context = conversation_contexts.get(conversation_id)
        if not context:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        user_input = request.get("content", "")
        if not user_input:
            raise HTTPException(status_code=400, detail="Message content is required")
        
        # Add user message to history
        context["messages"].append({
            "role": "user",
            "content": user_input
        })
        
        # Generate response based on conversation stage
        response = generate_conversation_response(context, user_input)
        
        # Add assistant response to history
        context["messages"].append({
            "role": "assistant",
            "content": response
        })
        
        return {
            "conversation_id": conversation_id,
            "response": response,
            "conversation_stage": context["stage"],
            "collected_data": context.get("collected_data", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")

def generate_conversation_response(context: Dict, user_input: str) -> str:
    """Generate appropriate response based on conversation context"""
    scheme_code = context["scheme_code"]
    stage = context["stage"]
    
    if scheme_code == "PM-KISAN":
        if stage == "initial":
            return f"I can help you with PM-KISAN eligibility. I'll need to collect some information about you. Let's start with basic details like your name, age, and location."
        else:
            return f"I understand you're asking about {user_input}. For PM-KISAN, I can help you check eligibility and guide you through the application process."
    else:
        return f"I understand you're asking about {user_input}. For the {context['scheme_name']} scheme, I can help you with eligibility requirements and application process."

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return Response(
        content=json.dumps({"detail": "Internal server error"}),
        status_code=500,
        media_type="application/json"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
