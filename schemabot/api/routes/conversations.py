"""
Conversation Endpoints
Manage user conversations with the Sanchalak bot including message exchange and eligibility results.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict

# Import models and dependencies
from core.prompts.context import ConversationContext
from core.eligibility.checker import EligibilityChecker
from api.dependencies import get_current_user, get_metrics_collector

# Define missing request/response models
class StartConversationRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    scheme_code: str
    language: str = "en"

class SendMessageRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    message: str

class EndConversationRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    run_eligibility_check: bool = True

class ConversationResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    conversation: ConversationContext

class MessageResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    conversation_id: str
    role: MessageRole
    message: str
    timestamp: datetime

class ConversationListResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    conversations: List[ConversationContext]
    total_count: int
    limit: int
    offset: int
    has_more: bool

class EndConversationResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    conversation_id: str
    ended: bool
    eligibility_result: Optional[Dict[str, Any]] = None

# Initialize core services
context_manager = ConversationContext()
eligibility_checker = EligibilityChecker()

# Initialize router
router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def start_conversation(
    request: StartConversationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    cache_manager = Depends(get_cache_manager),
    metrics_collector = Depends(get_metrics_collector)
):
    """
    Start a new conversation for a specific scheme and language.
    """
    try:
        # Create conversation context
        conversation = ConversationContext(
            scheme_code=request.scheme_code,
            language=request.language,
            user_id=current_user.user_id if hasattr(current_user, 'user_id') else 'anonymous',
            created_at=datetime.now(timezone.utc)
        )

        # Persist conversation to cache (or DB)
        await cache_manager.set(f"conversation:{conversation.id}", conversation, ttl=86400)

        # Record metrics
        await metrics_collector.record_api_call("start_conversation", 1)

        return ConversationResponse(conversation=conversation)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start conversation: {str(e)}"
        )


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    background_tasks: BackgroundTasks,
    cache_manager = Depends(get_cache_manager),
    metrics_collector = Depends(get_metrics_collector)
):
    """
    Send a user message to an existing conversation and get the assistant response.
    """
    try:
        # Retrieve conversation
        conversation: ConversationContext = await cache_manager.get(f"conversation:{conversation_id}")
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        # Add user message
        conversation.add_message(MessageRole.USER, request.message)

        # Generate assistant response using LLM via context manager
        assistant_reply = await context_manager.generate_reply(conversation)

        # Add assistant message
        conversation.add_message(MessageRole.ASSISTANT, assistant_reply)

        # Update conversation in cache
        await cache_manager.set(f"conversation:{conversation_id}", conversation, ttl=86400)

        # Background eligibility evaluation if data collection is complete
        if conversation.is_data_collection_complete():
            background_tasks.add_task(run_eligibility_check, conversation_id)

        # Record metrics
        await metrics_collector.record_api_call("send_message", 1)

        return MessageResponse(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            message=assistant_reply,
            timestamp=datetime.now(timezone.utc)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    cache_manager = Depends(get_cache_manager),
    metrics_collector = Depends(get_metrics_collector)
):
    """
    Retrieve the full conversation by ID.
    """
    try:
        conversation: ConversationContext = await cache_manager.get(f"conversation:{conversation_id}")
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        await metrics_collector.record_api_call("get_conversation", 1)
        return ConversationResponse(conversation=conversation)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation: {str(e)}"
        )


@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    user_id: Optional[str] = Query(None, description="Filter conversations by user ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    cache_manager = Depends(get_cache_manager),
    metrics_collector = Depends(get_metrics_collector)
):
    """
    List conversations for the current user or all users (admin).
    """
    try:
        # Mock implementation - replace with actual cache pattern matching
        conversations = []
        total_count = 0
        
        # In a real implementation, you would:
        # pattern = "conversation:*"
        # keys = await cache_manager.keys(pattern)
        # for key in keys:
        #     conv: ConversationContext = await cache_manager.get(key)
        #     if user_id and conv.user_id != user_id:
        #         continue
        #     conversations.append(conv)

        total_count = len(conversations)
        conversations = conversations[offset:offset+limit]

        await metrics_collector.record_api_call("list_conversations", len(conversations))

        return ConversationListResponse(
            conversations=conversations,
            total_count=total_count,
            limit=limit,
            offset=offset,
            has_more=offset+limit < total_count
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.post("/{conversation_id}/end", response_model=EndConversationResponse)
async def end_conversation(
    conversation_id: str,
    request: EndConversationRequest,
    cache_manager = Depends(get_cache_manager),
    metrics_collector = Depends(get_metrics_collector)
):
    """
    End a conversation and optionally trigger eligibility computation.
    """
    try:
        conversation: ConversationContext = await cache_manager.get(f"conversation:{conversation_id}")
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        conversation.ended = True
        conversation.ended_at = datetime.now(timezone.utc)

        # Eligibility check if requested
        eligibility_result = None
        if request.run_eligibility_check and conversation.is_data_collection_complete():
            eligibility_result = await eligibility_checker.check_eligibility(
                conversation.scheme_code,
                conversation.collected_data
            )
            conversation.eligibility_result = eligibility_result

        await cache_manager.set(f"conversation:{conversation_id}", conversation, ttl=604800)  # 1 week retention

        await metrics_collector.record_api_call("end_conversation", 1)

        return EndConversationResponse(
            conversation_id=conversation_id,
            ended=True,
            eligibility_result=eligibility_result
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to end conversation: {str(e)}"
        )


async def run_eligibility_check(conversation_id: str):
    """
    Background task to compute eligibility.
    """
    try:
        cache_manager = await get_cache_manager()
        conversation: ConversationContext = await cache_manager.get(f"conversation:{conversation_id}")
        if not conversation:
            return

        eligibility_result = await eligibility_checker.check_eligibility(
            conversation.scheme_code,
            conversation.collected_data
        )

        conversation.eligibility_result = eligibility_result
        await cache_manager.set(f"conversation:{conversation_id}", conversation, ttl=86400)

    except Exception:
        # Silently fail for background tasks
        pass