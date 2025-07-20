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
    basic_info: StageProgress
    family_members: StageProgress
    exclusion_criteria: StageProgress
    special_provisions: StageProgress
    
    @strawberry.field
    def overall_percentage(self) -> float:
        total_collected = (
            self.basic_info.collected + 
            self.family_members.collected + 
            self.exclusion_criteria.collected + 
            self.special_provisions.collected
        )
        total_required = (
            self.basic_info.total + 
            self.family_members.total + 
            self.exclusion_criteria.total + 
            self.special_provisions.total
        )
        return (total_collected / total_required) * 100 if total_required > 0 else 0

@strawberry.type
class Message:
    id: str
    role: MessageRole
    content: str
    timestamp: datetime

@strawberry.type
class FarmerData:
    basic_info: strawberry.scalars.JSON
    family_members: strawberry.scalars.JSON
    exclusion_data: strawberry.scalars.JSON
    special_provisions: strawberry.scalars.JSON
    scheme_code: str
    completed_at: datetime

@strawberry.type
class ConversationSession:
    id: str
    scheme_code: str
    stage: Stage
    created_at: datetime
    updated_at: datetime
    
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
                basic_info=StageProgress(collected=len(state.collected_data), total=17),
                family_members=StageProgress(collected=len(state.family_members), total=3),
                exclusion_criteria=StageProgress(collected=len(state.exclusion_data), total=7),
                special_provisions=StageProgress(collected=len(state.special_provisions), total=3)
            )
        return ConversationProgress(
            basic_info=StageProgress(collected=0, total=17),
            family_members=StageProgress(collected=0, total=3),
            exclusion_criteria=StageProgress(collected=0, total=7),
            special_provisions=StageProgress(collected=0, total=3)
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
                    basic_info=state.collected_data,
                    family_members=state.family_members,
                    exclusion_data=state.exclusion_data,
                    special_provisions=state.special_provisions,
                    scheme_code=self.scheme_code,
                    completed_at=datetime.now()
                )
        return None
    
    @strawberry.field
    def is_complete(self) -> bool:
        if self.id in sessions:
            return sessions[self.id].stage == ConversationStage.COMPLETED
        return False

# Input Types
@strawberry.input
class StartConversationInput:
    scheme_code: str
    language: Optional[str] = "en"

@strawberry.input
class SendMessageInput:
    session_id: str
    content: str
    quick_option_id: Optional[int] = None

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
            response, updated_state = await engine.initialize_conversation(input.scheme_code)
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
                scheme_code=input.scheme_code,
                stage=_stage_to_graphql(updated_state.stage),
                created_at=datetime.now(),
                updated_at=datetime.now()
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
                content=f"Hello! I'm here to help you with your {input.scheme_code.upper()} application. Let's start with your basic information. What's your name?",
                timestamp=datetime.now()
            )
            conversation_messages[session_id] = [fallback_message]
            
            return ConversationSession(
                id=session_id,
                scheme_code=input.scheme_code,
                stage=Stage.BASIC_INFO,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
    
    @strawberry.mutation  
    async def send_message(self, input: SendMessageInput) -> Message:
        """Send message and get AI response"""
        session_id = input.session_id
        
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
            scheme_code="pm-kisan",  # TODO: store scheme_code in session
            stage=_stage_to_graphql(state.stage),
            created_at=datetime.now(),  # TODO: store actual creation time
            updated_at=datetime.now()
        )
    
    @strawberry.field
    async def available_schemes(self) -> List[strawberry.scalars.JSON]:
        """Get list of available schemes"""
        return [
            {"scheme_code": "pm-kisan", "name": "PM-KISAN", "description": "Farmer income support scheme"}
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