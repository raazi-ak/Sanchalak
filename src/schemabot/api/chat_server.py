from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
import uuid
from datetime import datetime
import asyncio

from schemabot.core.conversation.langgraph_engine import SimpleLangGraphEngine, ConversationState, ConversationStage

app = FastAPI(
    title="PM-KISAN Chat Data Extraction API",
    description="""
    ## Conversational AI Data Collection System for PM-KISAN Applications
    
    This API provides intelligent conversational data collection for government scheme applications.
    The system uses LangGraph-powered conversation flows to collect farmer information in a natural,
    user-friendly manner.
    
    ### Features
    - 🤖 **AI-Powered Conversations**: Natural language processing for data extraction
    - 📊 **Progress Tracking**: Real-time progress monitoring across conversation stages
    - 🔄 **Session Management**: Multi-user support with session-based conversations
    - 🚜 **Complete Farmer Objects**: EFR-ready data structures for seamless integration
    - 🛠️ **Developer Mode**: Advanced features for testing and debugging
    
    ### Conversation Stages
    1. **Basic Info**: Personal and contact information (17 fields)
    2. **Family Members**: Family composition with PM-KISAN eligibility rules
    3. **Exclusion Criteria**: 7 eligibility questions with conditional logic
    4. **Special Provisions**: Additional scheme-specific requirements
    
    ### Developer Mode
    Enable developer mode by including the header: `X-Developer-Mode: true`
    
    This unlocks additional features:
    - Stage skipping capabilities
    - Debug information in responses
    - Advanced conversation control
    - Detailed logging and metrics
    """,
    version="1.0.0",
    contact={
        "name": "PM-KISAN Development Team",
        "email": "support@pmkisan-ai.gov.in"
    },
    license_info={
        "name": "Government of India License",
        "url": "https://www.gov.in/license"
    }
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage (use Redis in production)
sessions: Dict[str, ConversationState] = {}
engines: Dict[str, SimpleLangGraphEngine] = {}

# Define models first
class QuickOption(BaseModel):
    id: int = Field(..., description="Option ID for selection")
    text: str = Field(..., description="Display text for the option")
    description: Optional[str] = Field(None, description="Additional description for the option")

# Quick options storage for interactive responses
quick_options_storage: Dict[str, List[QuickOption]] = {}

# Request/Response Models
class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Session ID for continuing conversation. If not provided, a new session will be created.")
    user_input: str = Field(..., description="User's message or input", example="My name is Rajesh Kumar")
    quick_option_id: Optional[int] = Field(None, description="ID of selected quick option instead of text input")
    scheme_code: str = Field("pm-kisan", description="Government scheme code", example="pm-kisan")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_input": "My name is Rajesh Kumar",
                "quick_option_id": None,
                "scheme_code": "pm-kisan"
            }
        }

class DeveloperAction(BaseModel):
    action: Literal["skip_stage", "skip_question", "restart", "debug"] = Field(..., description="Developer action to perform")
    target: Optional[str] = Field(None, description="Target stage or field for the action")
    
    class Config:
        json_schema_extra = {
            "example": {
                "action": "skip_stage",
                "target": "basic_info"
            }
        }

class NextStep(BaseModel):
    instruction: str = Field(..., description="What the user should do next")
    endpoint: str = Field(..., description="Which endpoint to call")
    method: str = Field(..., description="HTTP method to use")
    example_payload: Dict[str, Any] = Field(..., description="Example request payload")

class ChatResponse(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    assistant_response: str = Field(..., description="AI assistant's response message")
    stage: str = Field(..., description="Current conversation stage", example="basic_info")
    progress: Dict[str, Any] = Field(..., description="Detailed progress information")
    is_complete: bool = Field(..., description="Whether data collection is complete")
    farmer_data: Optional[Dict[str, Any]] = Field(None, description="Complete farmer data object (only when is_complete=true)")
    debug_info: Optional[Dict[str, Any]] = Field(None, description="Debug information (only in developer mode)")
    
    # Interactive guidance
    quick_options: Optional[List[QuickOption]] = Field(None, description="Quick response options with integer IDs")
    next_step: NextStep = Field(..., description="Detailed guidance for next API call")
    expected_input_type: str = Field(..., description="Type of input expected", example="text|choice|yes_no")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "assistant_response": "What is your age?",
                "stage": "basic_info",
                "progress": {"basic_info": {"collected": 1, "total": 17}},
                "is_complete": False,
                "quick_options": [
                    {"id": 1, "text": "I'm 25 years old", "value": "25"},
                    {"id": 2, "text": "I'm 45 years old", "value": "45"},
                    {"id": 3, "text": "I'm 65 years old", "value": "65"}
                ],
                "next_step": {
                    "instruction": "Send your age or select a quick option",
                    "endpoint": "/chat",
                    "method": "POST",
                    "example_payload": {
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "user_input": "45",
                        "quick_option_id": 2
                    }
                },
                "expected_input_type": "text"
            }
        }

class SessionStatus(BaseModel):
    session_id: str
    stage: str
    progress: Dict[str, Any]
    is_complete: bool
    created_at: datetime
    last_updated: datetime

class FarmerData(BaseModel):
    # Basic Info
    basic_info: Dict[str, Any]
    # Exclusion criteria
    exclusion_data: Dict[str, Any]
    # Family members
    family_members: List[Dict[str, Any]]
    # Special provisions
    special_provisions: Dict[str, Any]
    # Metadata
    scheme_code: str
    collection_completed_at: datetime
    session_id: str

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_endpoint(
    request: ChatRequest,
    x_developer_mode: Optional[str] = Header(None, alias="X-Developer-Mode", description="Enable developer mode (set to 'true')")
):
    """
    ## Main Chat Endpoint for Conversational Data Collection
    
    This endpoint handles the core conversation flow for PM-KISAN data collection.
    
    ### Usage
    1. **Start Conversation**: Send empty `user_input` to get welcome message
    2. **Continue Conversation**: Include `session_id` and user's response
    3. **Complete Collection**: When `is_complete=true`, extract `farmer_data`
    
    ### Developer Mode
    Include header `X-Developer-Mode: true` to enable:
    - Debug information in responses
    - Detailed conversation state
    - Performance metrics
    
    ### Response States
    - **is_complete=false**: Continue conversation
    - **is_complete=true**: Data collection finished, `farmer_data` available
    
    ### Example Conversation Flow
    ```
    1. POST /chat {"user_input": ""} → Welcome message
    2. POST /chat {"session_id": "...", "user_input": "Rajesh Kumar"} → Next question
    3. Continue until is_complete=true
    4. Extract farmer_data for EFR upload
    ```
    """
    try:
        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        
        # Initialize engine if not exists
        if session_id not in engines:
            engine = SimpleLangGraphEngine()
            await engine.initialize(request.scheme_code)
            engines[session_id] = engine
            
            # Initialize conversation state
            if session_id not in sessions:
                welcome_msg, state = await engine.initialize_conversation(request.scheme_code)
                sessions[session_id] = state
                
                return ChatResponse(
                    session_id=session_id,
                    assistant_response=welcome_msg,
                    stage=state.stage.value,
                    progress=_get_progress(engine, state),
                    is_complete=False
                )
        
        # Get existing session and engine
        engine = engines[session_id]
        state = sessions[session_id]
        
        # Check for developer mode
        is_dev_mode = x_developer_mode and x_developer_mode.lower() == "true"
        
        # Process user input
        response, updated_state = await engine.process_user_input(request.user_input, state)
        sessions[session_id] = updated_state
        
        # Check if data collection is complete
        is_complete = updated_state.stage == ConversationStage.COMPLETED
        farmer_data = None
        debug_info = None
        
        if is_complete:
            farmer_data = _build_farmer_object(engine, updated_state, request.scheme_code, session_id)
        
        # Add debug info if developer mode is enabled
        if is_dev_mode:
            debug_info = {
                "conversation_turns": updated_state.turn_count,
                "current_stage": updated_state.stage.value,
                "debug_log": updated_state.debug_log[-5:] if updated_state.debug_log else [],
                "available_actions": _get_available_dev_actions(updated_state),
                "stage_completion": {
                    "basic_info_complete": len(state.collected_data) >= len(engine.required_fields),
                    "exclusions_complete": len(state.exclusion_data) >= len(engine.exclusion_fields),
                    "family_complete": len(state.family_members) > 0 or "no family" in response.lower(),
                    "special_complete": len(state.special_provisions) >= len(engine.special_provision_fields)
                }
            }
        
        return ChatResponse(
            session_id=session_id,
            assistant_response=response,
            stage=updated_state.stage.value,
            progress=_get_progress(engine, updated_state),
            is_complete=is_complete,
            farmer_data=farmer_data,
            debug_info=debug_info
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@app.post("/chat/{session_id}/dev-action", response_model=ChatResponse, tags=["Developer"])
async def developer_action(
    session_id: str,
    action: DeveloperAction,
    x_developer_mode: Optional[str] = Header(None, alias="X-Developer-Mode", description="Must be 'true' to access developer features")
):
    """
    ## Developer Actions for Advanced Conversation Control
    
    **🚨 Developer Mode Required**: Include header `X-Developer-Mode: true`
    
    ### Available Actions
    
    #### Skip Stage
    ```json
    {"action": "skip_stage", "target": "basic_info"}
    ```
    Skip entire conversation stage and move to next.
    
    #### Skip Question  
    ```json
    {"action": "skip_question", "target": "current"}
    ```
    Skip current question and move to next in same stage.
    
    #### Restart Conversation
    ```json
    {"action": "restart"}
    ```
    Reset conversation to beginning.
    
    #### Debug Information
    ```json
    {"action": "debug"}
    ```
    Get detailed debug information without processing input.
    
    ### Supported Stages
    - `basic_info`: Personal information collection
    - `family_members`: Family composition 
    - `exclusion_criteria`: Eligibility questions
    - `special_provisions`: Additional requirements
    """
    # Verify developer mode
    if not x_developer_mode or x_developer_mode.lower() != "true":
        raise HTTPException(status_code=403, detail="Developer mode required. Include header X-Developer-Mode: true")
    
    if session_id not in sessions or session_id not in engines:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        engine = engines[session_id]
        state = sessions[session_id]
        
        if action.action == "skip_stage":
            response, updated_state = await _skip_stage(engine, state, action.target)
        elif action.action == "skip_question":
            response, updated_state = await _skip_question(engine, state)
        elif action.action == "restart":
            response, updated_state = await _restart_conversation(engine, state)
        elif action.action == "debug":
            response, updated_state = await _get_debug_info(engine, state)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action.action}")
        
        sessions[session_id] = updated_state
        
        # Check completion
        is_complete = updated_state.stage == ConversationStage.COMPLETED
        farmer_data = None
        if is_complete:
            farmer_data = _build_farmer_object(engine, updated_state, "pm-kisan", session_id)
        
        return ChatResponse(
            session_id=session_id,
            assistant_response=response,
            stage=updated_state.stage.value,
            progress=_get_progress(engine, updated_state),
            is_complete=is_complete,
            farmer_data=farmer_data,
            debug_info={
                "action_performed": action.action,
                "target": action.target,
                "available_actions": _get_available_dev_actions(updated_state)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Developer action failed: {str(e)}")

@app.get("/sessions/{session_id}/status", response_model=SessionStatus, tags=["Session Management"])
async def get_session_status(session_id: str):
    """
    Get current status of a chat session
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = sessions[session_id]
    engine = engines[session_id]
    
    return SessionStatus(
        session_id=session_id,
        stage=state.stage.value,
        progress=_get_progress(engine, state),
        is_complete=state.stage == ConversationStage.COMPLETED,
        created_at=datetime.now(),  # TODO: Store actual creation time
        last_updated=datetime.now()
    )

@app.get("/sessions/{session_id}/farmer-data", response_model=FarmerData, tags=["Data Export"])
async def get_farmer_data(session_id: str):
    """
    ## Get Complete Farmer Data Object
    
    **⚠️ Only available when data collection is complete** (`is_complete=true`)
    
    Returns a complete farmer data object ready for EFR database upload.
    
    ### Farmer Data Structure
    - **basic_info**: All personal and contact information
    - **exclusion_data**: Eligibility criteria responses  
    - **family_members**: Family composition with PM-KISAN rules
    - **special_provisions**: Additional scheme requirements
    - **metadata**: Collection timestamps and session info
    
    ### Usage
    ```python
    # After conversation completion
    farmer_data = get_farmer_data(session_id)
    
    # Upload to EFR database
    efr_client.upload_farmer(farmer_data)
    ```
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = sessions[session_id]
    engine = engines[session_id]
    
    if state.stage != ConversationStage.COMPLETED:
        raise HTTPException(status_code=400, detail="Data collection not yet complete")
    
    farmer_data = _build_farmer_object(engine, state, "pm-kisan", session_id)
    return farmer_data

@app.delete("/sessions/{session_id}", tags=["Session Management"])
async def delete_session(session_id: str):
    """
    ## Delete Chat Session
    
    Permanently deletes a conversation session and frees up server resources.
    
    **⚠️ Warning**: This action cannot be undone. All conversation data will be lost.
    
    ### When to Use
    - After successfully uploading farmer data to EFR
    - When abandoning incomplete conversations
    - For cleanup and resource management
    """
    if session_id in sessions:
        del sessions[session_id]
    if session_id in engines:
        del engines[session_id]
    
    return {"message": f"Session {session_id} deleted successfully"}

@app.get("/sessions", tags=["Session Management"])
async def list_sessions():
    """
    ## List All Active Sessions
    
    Returns a summary of all currently active conversation sessions.
    
    ### Response Information
    - **session_id**: Unique session identifier
    - **stage**: Current conversation stage
    - **is_complete**: Whether data collection is finished
    - **progress**: Detailed progress breakdown
    
    ### Use Cases
    - Monitor active conversations
    - Session management and cleanup
    - System administration and monitoring
    """
    session_list = []
    for session_id, state in sessions.items():
        engine = engines.get(session_id)
        if engine:
            session_list.append({
                "session_id": session_id,
                "stage": state.stage.value,
                "is_complete": state.stage == ConversationStage.COMPLETED,
                "progress": _get_progress(engine, state)
            })
    
    return {"sessions": session_list}

@app.get("/api-docs/json", tags=["Documentation"])
async def get_openapi_json():
    """
    ## Get OpenAPI JSON Schema
    
    Returns the complete OpenAPI 3.0 specification as JSON.
    Useful for generating client SDKs or importing into API testing tools.
    """
    return app.openapi()

@app.get("/health", tags=["System"])
async def health_check():
    """
    ## System Health Check
    
    Returns system status and basic metrics.
    """
    return {
        "status": "healthy", 
        "timestamp": datetime.now(),
        "active_sessions": len(sessions),
        "version": "1.0.0",
        "features": {
            "developer_mode": True,
            "session_management": True,
            "multi_stage_conversations": True,
            "farmer_data_extraction": True
        }
    }

def _get_progress(engine: SimpleLangGraphEngine, state: ConversationState) -> Dict[str, Any]:
    """
    Generate progress summary
    """
    return {
        "basic_info": {
            "collected": len(state.collected_data),
            "total": len(engine.required_fields),
            "fields": list(state.collected_data.keys())
        },
        "exclusions": {
            "answered": len(state.exclusion_data),
            "total": len(engine.exclusion_fields),
            "answers": state.exclusion_data
        },
        "family": {
            "members": len(state.family_members),
            "details": state.family_members
        },
        "special_provisions": {
            "collected": len(state.special_provisions),
            "total": len(engine.special_provision_fields),
            "provisions": state.special_provisions
        },
        "stage": state.stage.value
    }

def _build_farmer_object(engine: SimpleLangGraphEngine, state: ConversationState, scheme_code: str, session_id: str) -> Dict[str, Any]:
    """
    Build complete farmer object ready for EFR upload
    """
    return {
        "basic_info": {field.field_name: field.value for field_name, field in state.collected_data.items()},
        "exclusion_data": state.exclusion_data,
        "family_members": state.family_members,
        "special_provisions": state.special_provisions,
        "scheme_code": scheme_code,
        "collection_completed_at": datetime.now().isoformat(),
        "session_id": session_id,
        "metadata": {
            "total_turns": state.turn_count,
            "debug_log": state.debug_log[-10:] if state.debug_log else [],  # Last 10 debug entries
            "collection_method": "conversational_ai"
        }
    }

def _get_available_dev_actions(state: ConversationState) -> List[str]:
    """Get available developer actions for current state"""
    actions = ["debug", "restart"]
    
    if state.stage != ConversationStage.COMPLETED:
        actions.extend(["skip_question", "skip_stage"])
    
    return actions

async def _skip_stage(engine: SimpleLangGraphEngine, state: ConversationState, target_stage: Optional[str] = None) -> tuple:
    """Skip current or target stage"""
    if target_stage:
        # Skip specific stage
        if target_stage == "basic_info":
            # Fill basic info with dummy data
            for field in engine.required_fields:
                if field not in state.collected_data:
                    from ..core.conversation.langgraph_engine import ExtractedField
                    state.collected_data[field] = ExtractedField(
                        value="[SKIPPED]",
                        confidence=1.0,
                        source="developer_skip",
                        timestamp=datetime.now(),
                        raw_input="[SKIPPED]"
                    )
            state.stage = ConversationStage.FAMILY_MEMBERS
            return "✅ [DEV] Skipped basic info stage. Moving to family members.", state
        
        elif target_stage == "family_members":
            state.stage = ConversationStage.EXCLUSION_CRITERIA
            return "✅ [DEV] Skipped family members stage. Moving to exclusions.", state
        
        elif target_stage == "exclusion_criteria":
            # Fill exclusions with dummy data
            for field in engine.exclusion_fields:
                state.exclusion_data[field] = False
            state.stage = ConversationStage.SPECIAL_PROVISIONS
            return "✅ [DEV] Skipped exclusion criteria stage. Moving to special provisions.", state
        
        elif target_stage == "special_provisions":
            state.stage = ConversationStage.COMPLETED
            return "✅ [DEV] Skipped special provisions. Application complete!", state
    
    else:
        # Skip current stage
        if state.stage == ConversationStage.BASIC_INFO:
            return await _skip_stage(engine, state, "basic_info")
        elif state.stage == ConversationStage.FAMILY_MEMBERS:
            return await _skip_stage(engine, state, "family_members")
        elif state.stage == ConversationStage.EXCLUSION_CRITERIA:
            return await _skip_stage(engine, state, "exclusion_criteria")
        elif state.stage == ConversationStage.SPECIAL_PROVISIONS:
            return await _skip_stage(engine, state, "special_provisions")
    
    return "✅ [DEV] Stage skip completed.", state

async def _skip_question(engine: SimpleLangGraphEngine, state: ConversationState) -> tuple:
    """Skip current question in current stage"""
    response = f"✅ [DEV] Skipped current question in {state.stage.value} stage."
    return response, state

async def _restart_conversation(engine: SimpleLangGraphEngine, state: ConversationState) -> tuple:
    """Restart conversation from beginning"""
    # Reset state
    state.collected_data.clear()
    state.exclusion_data.clear()
    state.family_members.clear()
    state.special_provisions.clear()
    state.stage = ConversationStage.BASIC_INFO
    state.turn_count = 0
    state.debug_log.clear()
    
    welcome_msg, new_state = await engine.initialize_conversation("pm-kisan")
    return f"✅ [DEV] Conversation restarted.\n\n{welcome_msg}", new_state

async def _get_debug_info(engine: SimpleLangGraphEngine, state: ConversationState) -> tuple:
    """Get detailed debug information"""
    debug_response = f"""
🔍 **Debug Information**

**Current Stage**: {state.stage.value}
**Turn Count**: {state.turn_count}

**Progress Summary**:
- Basic Info: {len(state.collected_data)}/{len(engine.required_fields)} fields
- Exclusions: {len(state.exclusion_data)}/{len(engine.exclusion_fields)} answered  
- Family: {len(state.family_members)} members
- Special: {len(state.special_provisions)}/{len(engine.special_provision_fields)} provisions

**Recent Debug Log**:
{chr(10).join(state.debug_log[-5:]) if state.debug_log else "No debug entries"}

**Available Actions**: {', '.join(_get_available_dev_actions(state))}
    """
    
    return debug_response.strip(), state

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003) 