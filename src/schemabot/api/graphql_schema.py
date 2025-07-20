"""
GraphQL Schema for PM-KISAN Conversational AI System

This replaces the complex REST API with a clean, type-safe GraphQL interface.
Provides real-time subscriptions, precise data fetching, and unified conversation state.
"""

import strawberry
from typing import Optional, List, Dict, Any, AsyncGenerator
from enum import Enum
from datetime import datetime
import uuid
import json
import asyncio

# Import our existing LangGraph engine
from schemabot.core.conversation.langgraph_engine import SimpleLangGraphEngine, ConversationState, ConversationStage

# GraphQL Enums
@strawberry.enum
class Stage(Enum):
    BASIC_INFO = "basic_info"
    FAMILY_MEMBERS = "family_members" 
    EXCLUSION_CRITERIA = "exclusion_criteria"
    SPECIAL_PROVISIONS = "special_provisions"
    COMPLETED = "completed"

@strawberry.enum
class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

# GraphQL Types
@strawberry.type
class QuickOption:
    id: int
    text: str
    value: Optional[str] = None
    description: Optional[str] = None

@strawberry.type
class StageProgress:
    collected: int
    total: int
    
    @strawberry.field
    def percentage(self) -> float:
        return (self.collected / self.total * 100) if self.total > 0 else 0
    
    @strawberry.field
    def is_complete(self) -> bool:
        return self.collected >= self.total

@strawberry.type
class ConversationProgress:
    basicInfo: StageProgress
    familyMembers: StageProgress
    exclusionCriteria: StageProgress
    specialProvisions: StageProgress
    
    @strawberry.field
    def overall_percentage(self) -> float:
        total_collected = (
            self.basicInfo.collected + 
            self.familyMembers.collected + 
            self.exclusionCriteria.collected + 
            self.specialProvisions.collected
        )
        total_required = (
            self.basicInfo.total + 
            self.familyMembers.total + 
            self.exclusionCriteria.total + 
            self.specialProvisions.total
        )
        return (total_collected / total_required) * 100 if total_required > 0 else 0

@strawberry.type
class Message:
    id: str
    role: MessageRole
    content: str
    timestamp: datetime

@strawberry.type
class EligibilityResult:
    is_eligible: bool
    confidence_score: float
    explanation: str
    details: strawberry.scalars.JSON
    timestamp: datetime

@strawberry.type
class FarmerData:
    basicInfo: strawberry.scalars.JSON
    familyMembers: strawberry.scalars.JSON
    exclusionData: strawberry.scalars.JSON
    specialProvisions: strawberry.scalars.JSON
    schemeCode: str
    completedAt: datetime

@strawberry.type
class ConversationSession:
    id: str
    schemeCode: str
    stage: Stage
    createdAt: datetime
    updatedAt: datetime
    
    # Flexible data fetching - client chooses what to include
    @strawberry.field
    def messages(self, limit: Optional[int] = None) -> List[Message]:
        # Get messages from session storage
        if self.id in conversation_messages:
            msgs = conversation_messages[self.id]
            if limit:
                return msgs[-limit:]
            return msgs
        return []
    
    @strawberry.field
    def progress(self) -> ConversationProgress:
        # Get progress from session state
        if self.id in sessions:
            state = sessions[self.id]
            return ConversationProgress(
                basicInfo=StageProgress(collected=len(state.collected_data), total=17),
                familyMembers=StageProgress(collected=len(state.family_members), total=3),
                exclusionCriteria=StageProgress(collected=len(state.exclusion_data), total=7),
                specialProvisions=StageProgress(collected=len(state.special_provisions), total=3)
            )
        return ConversationProgress(
            basicInfo=StageProgress(collected=0, total=17),
            familyMembers=StageProgress(collected=0, total=3),
            exclusionCriteria=StageProgress(collected=0, total=7),
            specialProvisions=StageProgress(collected=0, total=3)
        )
    
    @strawberry.field
    def quick_options(self) -> Optional[List[QuickOption]]:
        # Return contextual quick options
        return [
            QuickOption(id=1, text="Continue", description="Proceed with conversation")
        ]
    
    @strawberry.field
    def farmer_data(self) -> Optional[FarmerData]:
        # Only return if conversation is complete
        if self.id in sessions:
            state = sessions[self.id]
            if state.stage == ConversationStage.COMPLETED:
                return FarmerData(
                    basicInfo=state.collected_data,
                    familyMembers=state.family_members,
                    exclusionData=state.exclusion_data,
                    specialProvisions=state.special_provisions,
                    schemeCode=self.schemeCode,
                    completedAt=datetime.now()
                )
        return None
    
    @strawberry.field
    def is_complete(self) -> bool:
        if self.id in sessions:
            return sessions[self.id].stage == ConversationStage.COMPLETED
        return False
    
    @strawberry.field
    def eligibility_result(self) -> Optional[EligibilityResult]:
        """Get eligibility result if conversation is complete"""
        if self.id in sessions:
            state = sessions[self.id]
            if state.stage == ConversationStage.COMPLETED:
                try:
                    import requests
                    
                    # Get farmer ID from collected data
                    farmer_id = None
                    for field_name, field_data in state.collected_data.items():
                        if field_name in ['aadhaar_number', 'farmer_id']:
                            farmer_id = field_data.value
                            break
                    
                    if not farmer_id:
                        return None
                    
                    # Call the scheme server eligibility endpoint
                    scheme_server_url = "http://localhost:8002/eligibility/check"
                    scheme_server_request = {
                        "scheme_id": self.schemeCode,
                        "farmer_id": farmer_id
                    }
                    
                    response = requests.post(scheme_server_url, json=scheme_server_request)
                    if response.status_code == 200:
                        result = response.json()
                        return EligibilityResult(
                            is_eligible=result.get("is_eligible", False),
                            confidence_score=result.get("confidence_score", 0.8),
                            explanation=result.get("explanation", "No explanation available"),
                            details=result.get("details", {}),
                            timestamp=datetime.now()
                        )
                except Exception as e:
                    print(f"Error getting eligibility result: {e}")
                    return None
        return None

# Input Types
@strawberry.input
class StartConversationInput:
    schemeCode: str
    language: Optional[str] = "en"

@strawberry.input
class SendMessageInput:
    sessionId: str
    content: str
    quickOptionId: Optional[int] = None

@strawberry.input
class CheckEligibilityInput:
    schemeCode: str
    farmerId: str

# In-memory storage (same as REST API for now)
sessions: Dict[str, ConversationState] = {}
engines: Dict[str, SimpleLangGraphEngine] = {}
conversation_messages: Dict[str, List[Message]] = {}
subscribers: Dict[str, List[Any]] = {}  # For real-time subscriptions

# Helper functions
def _stage_to_graphql(stage: ConversationStage) -> Stage:
    """Convert LangGraph stage to GraphQL enum"""
    mapping = {
        ConversationStage.BASIC_INFO: Stage.BASIC_INFO,
        ConversationStage.FAMILY_MEMBERS: Stage.FAMILY_MEMBERS,
        ConversationStage.EXCLUSION_CRITERIA: Stage.EXCLUSION_CRITERIA,
        ConversationStage.SPECIAL_PROVISIONS: Stage.SPECIAL_PROVISIONS,
        ConversationStage.COMPLETED: Stage.COMPLETED,
    }
    return mapping.get(stage, Stage.BASIC_INFO)

async def _notify_subscribers(session_id: str, message: Message):
    """Notify all subscribers of new message"""
    if session_id in subscribers:
        for subscriber in subscribers[session_id]:
            try:
                await subscriber.put(message)
            except:
                # Remove dead subscribers
                pass

# Mutations
@strawberry.type
class Mutation:
    
    @strawberry.mutation
    async def start_conversation(self, input: StartConversationInput) -> ConversationSession:
        """Start a new conversation for a specific scheme"""
        session_id = str(uuid.uuid4())
        
        try:
            # Initialize LangGraph engine
            engine = SimpleLangGraphEngine()
            engines[session_id] = engine
            
            # Initialize conversation
            response, updated_state = await engine.initialize_conversation(input.schemeCode)
            sessions[session_id] = updated_state
            
            # Create initial message
            initial_message = Message(
                id=str(uuid.uuid4()),
                role=MessageRole.ASSISTANT,
                content=response,
                timestamp=datetime.now()
            )
            
            # Store message
            conversation_messages[session_id] = [initial_message]
            
            # Create session object
            session = ConversationSession(
                id=session_id,
                schemeCode=input.schemeCode,
                stage=_stage_to_graphql(updated_state.stage),
                createdAt=datetime.now(),
                updatedAt=datetime.now()
            )
            
            # Notify subscribers
            await _notify_subscribers(session_id, initial_message)
            
            return session
            
        except Exception as e:
            print(f"Error starting conversation: {e}")
            # Return fallback session
            fallback_message = Message(
                id=str(uuid.uuid4()),
                role=MessageRole.ASSISTANT,
                content=f"Hello! I'm here to help you with your {input.schemeCode.upper()} application. Let's start with your basic information. What's your name?",
                timestamp=datetime.now()
            )
            conversation_messages[session_id] = [fallback_message]
            
            return ConversationSession(
                id=session_id,
                schemeCode=input.schemeCode,
                stage=Stage.BASIC_INFO,
                createdAt=datetime.now(),
                updatedAt=datetime.now()
            )
    
    @strawberry.mutation  
    async def send_message(self, input: SendMessageInput) -> Message:
        """Send message and get AI response"""
        session_id = input.sessionId
        
        # Check if session exists
        if session_id not in sessions or session_id not in engines:
            raise Exception("Session not found. Please start a new conversation.")
        
        try:
            # Store user message
            user_message = Message(
                id=str(uuid.uuid4()),
                role=MessageRole.USER,
                content=input.content,
                timestamp=datetime.now()
            )
            
            if session_id not in conversation_messages:
                conversation_messages[session_id] = []
            conversation_messages[session_id].append(user_message)
            
            # Process with LangGraph
            engine = engines[session_id]
            state = sessions[session_id]
            
            response, updated_state = await engine.process_user_input(input.content, state)
            sessions[session_id] = updated_state
            
            # Create assistant response
            assistant_message = Message(
                id=str(uuid.uuid4()),
                role=MessageRole.ASSISTANT,
                content=response,
                timestamp=datetime.now()
            )
            
            conversation_messages[session_id].append(assistant_message)
            
            # Notify subscribers
            await _notify_subscribers(session_id, user_message)
            await _notify_subscribers(session_id, assistant_message)
            
            return assistant_message
            
        except Exception as e:
            error_message = Message(
                id=str(uuid.uuid4()),
                role=MessageRole.ASSISTANT,
                content=f"I'm sorry, I encountered an error: {str(e)}. Could you please try again?",
                timestamp=datetime.now()
            )
            
            if session_id not in conversation_messages:
                conversation_messages[session_id] = []
            conversation_messages[session_id].append(error_message)
            
            return error_message
    
    @strawberry.mutation
    async def check_eligibility(self, input: CheckEligibilityInput) -> EligibilityResult:
        """Check eligibility for a farmer using the scheme server"""
        try:
            import requests
            
            # Call the scheme server eligibility endpoint
            scheme_server_url = "http://localhost:8002/eligibility/check"
            
            scheme_server_request = {
                "scheme_id": input.schemeCode,
                "farmer_id": input.farmerId
            }
            
            response = requests.post(scheme_server_url, json=scheme_server_request)
            response.raise_for_status()
            
            result = response.json()
            
            return EligibilityResult(
                is_eligible=result.get("is_eligible", False),
                confidence_score=result.get("confidence_score", 0.8),
                explanation=result.get("explanation", "No explanation available"),
                details=result.get("details", {}),
                timestamp=datetime.now()
            )
            
        except requests.exceptions.RequestException as e:
            print(f"Scheme server request error: {e}")
            return EligibilityResult(
                is_eligible=False,
                confidence_score=0.0,
                explanation="Scheme server unavailable",
                details={"error": str(e)},
                timestamp=datetime.now()
            )
        except Exception as e:
            print(f"Eligibility check error: {e}")
            return EligibilityResult(
                is_eligible=False,
                confidence_score=0.0,
                explanation=f"Error checking eligibility: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now()
            )

# Queries  
@strawberry.type
class Query:
    
    @strawberry.field
    async def conversation(self, session_id: str) -> Optional[ConversationSession]:
        """Get conversation by ID - client specifies what fields to include"""
        if session_id not in sessions:
            return None
            
        state = sessions[session_id]
        return ConversationSession(
            id=session_id,
            schemeCode="pm-kisan",  # TODO: store schemeCode in session
            stage=_stage_to_graphql(state.stage),
            createdAt=datetime.now(),  # TODO: store actual creation time
            updatedAt=datetime.now()
        )
    
    @strawberry.field
    async def available_schemes(self) -> List[strawberry.scalars.JSON]:
        """Get list of available schemes"""
        return [
            {"schemeCode": "pm-kisan", "name": "PM-KISAN", "description": "Farmer income support scheme"}
        ]

# Subscriptions for Real-time Chat
@strawberry.type
class Subscription:
    
    @strawberry.subscription
    async def message_stream(self, session_id: str) -> AsyncGenerator[Message, None]:
        """Real-time message stream for live chat"""
        # Create a queue for this subscriber
        queue = asyncio.Queue()
        
        # Add to subscribers
        if session_id not in subscribers:
            subscribers[session_id] = []
        subscribers[session_id].append(queue)
        
        try:
            while True:
                # Wait for new message
                message = await queue.get()
                yield message
        except asyncio.CancelledError:
            # Clean up subscriber
            if session_id in subscribers:
                try:
                    subscribers[session_id].remove(queue)
                except ValueError:
                    pass
            raise

# Schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation, 
    subscription=Subscription
) 