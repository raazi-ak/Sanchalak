from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime
import json
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from schemabot.core.conversation.langgraph_engine import SimpleLangGraphEngine, ConversationState, ConversationStage

app = FastAPI(
    title="Simple PM-KISAN Chat API",
    description="Simple chat interface for PM-KISAN data collection",
    version="1.0.0"
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple models
class ChatMessage(BaseModel):
    session_id: str
    user_input: str
    scheme_code: str = "pm-kisan"
    quick_option_id: Optional[int] = None

class ChatResponse(BaseModel):
    session_id: str
    assistant_response: str
    stage: str
    progress: Dict[str, Dict[str, int]]
    is_complete: bool
    quick_options: Optional[List[Dict[str, Any]]] = None
    farmer_data: Optional[Dict[str, Any]] = None

# In-memory storage for MVP
sessions: Dict[str, ConversationState] = {}
engines: Dict[str, SimpleLangGraphEngine] = {}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}



@app.get("/start/{scheme_code}")
async def start_conversation(scheme_code: str):
    """Start a new conversation for a specific scheme using LangGraph"""
    session_id = str(uuid.uuid4())
    
    try:
        # Initialize LangGraph engine
        engine = SimpleLangGraphEngine()
        engines[session_id] = engine
        
        # Initialize conversation
        response, updated_state = await engine.initialize_conversation(scheme_code)
        sessions[session_id] = updated_state
        
        return ChatResponse(
            session_id=session_id,
            assistant_response=response,
            stage=updated_state.stage.value,
            progress={
                "basic_info": {"collected": len(updated_state.collected_data), "total": 17},
                "family_members": {"collected": len(updated_state.family_members), "total": 3},
                "exclusion_criteria": {"collected": len(updated_state.exclusion_data), "total": 7},
                "special_provisions": {"collected": len(updated_state.special_provisions), "total": 3}
            },
            is_complete=updated_state.stage == ConversationStage.COMPLETED,
            quick_options=[{"id": 1, "text": "Continue", "description": "Proceed"}]
        )
        
    except Exception as e:
        print(f"Error starting conversation: {e}")
        return ChatResponse(
            session_id=session_id,
            assistant_response=f"Hello! I'm here to help you with your {scheme_code.upper()} application. Let's start with your basic information. What's your name?",
            stage="basic_info",
            progress={
                "basic_info": {"collected": 0, "total": 5},
                "family_members": {"collected": 0, "total": 3},
                "exclusion_criteria": {"collected": 0, "total": 2},
                "special_provisions": {"collected": 0, "total": 2}
            },
            is_complete=False,
            quick_options=[{"id": 1, "text": "Continue", "description": "Proceed"}]
        )

@app.post("/chat")
async def chat(message: ChatMessage):
    """Process chat message using LangGraph engine"""
    session_id = message.session_id
    user_message = message.user_input
    
    # Get session and engine
    if session_id not in sessions or session_id not in engines:
        raise HTTPException(status_code=404, detail="Session not found. Please start a new conversation.")
    
    try:
        engine = engines[session_id]
        state = sessions[session_id]
        
        # Process user input with LangGraph
        response, updated_state = await engine.process_user_input(user_message, state)
        
        # Update session state
        sessions[session_id] = updated_state
        
        return ChatResponse(
            session_id=session_id,
            assistant_response=response,
            stage=updated_state.stage.value,
            progress={
                "basic_info": {"collected": len(updated_state.collected_data), "total": 17},
                "family_members": {"collected": len(updated_state.family_members), "total": 3},
                "exclusion_criteria": {"collected": len(updated_state.exclusion_data), "total": 7},
                "special_provisions": {"collected": len(updated_state.special_provisions), "total": 3}
            },
            is_complete=updated_state.stage == ConversationStage.COMPLETED,
            farmer_data=updated_state.collected_data if updated_state.stage == ConversationStage.COMPLETED else None,
            quick_options=[{"id": 1, "text": "Continue", "description": "Proceed"}] if updated_state.stage != ConversationStage.COMPLETED else None
        )
        
    except Exception as e:
        print(f"Error processing message: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback response
        return ChatResponse(
            session_id=session_id,
            assistant_response="I'm sorry, I encountered an error processing your message. Could you please try again?",
            stage="error",
            progress={},
            is_complete=False,
            quick_options=[{"id": 1, "text": "Try again", "description": "Retry your message"}]
        )

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session data"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return sessions[session_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003) 