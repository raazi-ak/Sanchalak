from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum
import uuid

class ConversationStage(str, Enum):
    """Conversation stages"""
    GREETING = "greeting"
    DATA_COLLECTION = "data_collection"
    CLARIFICATION = "clarification"
    ELIGIBILITY_CHECK = "eligibility_check"
    RESULT_DELIVERY = "result_delivery"
    FOLLOWUP = "followup"
    ENDED = "ended"

class MessageRole(str, Enum):
    """Message roles in conversation"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ConversationStatus(str, Enum):
    """Overall conversation status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class Message(BaseModel):
    """Individual message in conversation"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class DataCollectionStatus(BaseModel):
    """Status of data collection for each field"""
    field_name: str
    is_collected: bool = False
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    collected_value: Optional[Any] = None
    validation_errors: List[str] = Field(default_factory=list)

class EligibilityCheckResult(BaseModel):
    """Eligibility check result stored in conversation"""
    is_eligible: bool
    score: float = Field(ge=0, le=100)
    passed_rules: List[str] = Field(default_factory=list)
    failed_rules: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=datetime.utcnow)

class ConversationContext(BaseModel):
    """Complete conversation context and state management"""
    
    # Basic conversation info
    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    
    # Scheme information
    scheme_code: str
    scheme_name: Optional[str] = None
    
    # Conversation state
    status: ConversationStatus = ConversationStatus.ACTIVE
    stage: ConversationStage = ConversationStage.GREETING
    current_field: Optional[str] = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Data collection
    collected_data: Dict[str, Any] = Field(default_factory=dict)
    data_collection_status: List[DataCollectionStatus] = Field(default_factory=list)
    required_fields: List[str] = Field(default_factory=list)
    
    # Conversation history
    messages: List[Message] = Field(default_factory=list)
    
    # Results
    eligibility_result: Optional[EligibilityCheckResult] = None
    
    # Metadata and tracking
    attempts_count: Dict[str, int] = Field(default_factory=dict)
    error_count: int = 0
    llm_interactions: int = 0
    total_processing_time: float = 0.0
    
    # Configuration
    max_attempts_per_field: int = 3
    conversation_timeout_minutes: int = 30
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator('updated_at', always=True)
    def set_updated_at(cls, v):
        return datetime.utcnow()
    
    def add_message(
        self, 
        role: MessageRole, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Add a new message to the conversation"""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        return message
    
    def update_data_collection_status(self, field_name: str, value: Any = None, error: str = None):
        """Update the status of data collection for a specific field"""
        # Find existing status or create new one
        status = None
        for item in self.data_collection_status:
            if item.field_name == field_name:
                status = item
                break
        
        if not status:
            status = DataCollectionStatus(field_name=field_name)
            self.data_collection_status.append(status)
        
        status.attempts += 1
        status.last_attempt = datetime.utcnow()
        
        if value is not None:
            status.is_collected = True
            status.collected_value = value
            self.collected_data[field_name] = value
        
        if error:
            status.validation_errors.append(error)
        
        self.updated_at = datetime.utcnow()
    
    def get_missing_fields(self) -> List[str]:
        """Get list of fields that still need to be collected"""
        return [field for field in self.required_fields if field not in self.collected_data]
    
    def get_next_field_to_collect(self) -> Optional[str]:
        """Get the next field that needs to be collected"""
        missing = self.get_missing_fields()
        
        # Filter out fields that have exceeded max attempts
        available_fields = []
        for field in missing:
            attempts = self.attempts_count.get(field, 0)
            if attempts < self.max_attempts_per_field:
                available_fields.append(field)
        
        return available_fields[0] if available_fields else None
    
    def is_data_collection_complete(self) -> bool:
        """Check if all required data has been collected"""
        return len(self.get_missing_fields()) == 0
    
    def can_proceed_to_eligibility_check(self) -> bool:
        """Check if conversation can proceed to eligibility check"""
        return (
            self.is_data_collection_complete() or 
            len(self.collected_data) >= len(self.required_fields) * 0.8  # 80% completion threshold
        )
    
    def is_conversation_expired(self) -> bool:
        """Check if conversation has expired"""
        time_diff = datetime.utcnow() - self.created_at
        return time_diff.total_seconds() > (self.conversation_timeout_minutes * 60)
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get a summary of the conversation state"""
        return {
            "conversation_id": self.conversation_id,
            "scheme_code": self.scheme_code,
            "status": self.status,
            "stage": self.stage,
            "progress": {
                "collected_fields": len(self.collected_data),
                "required_fields": len(self.required_fields),
                "completion_percentage": (len(self.collected_data) / len(self.required_fields) * 100) if self.required_fields else 0
            },
            "timing": {
                "duration_minutes": (datetime.utcnow() - self.created_at).total_seconds() / 60,
                "last_activity": self.updated_at
            },
            "interactions": {
                "total_messages": len(self.messages),
                "llm_interactions": self.llm_interactions,
                "error_count": self.error_count
            },
            "eligibility": {
                "checked": self.eligibility_result is not None,
                "eligible": self.eligibility_result.is_eligible if self.eligibility_result else None,
                "score": self.eligibility_result.score if self.eligibility_result else None
            }
        }

class ConversationHistory(BaseModel):
    """Historical conversation data for analytics"""
    conversation_id: str
    user_id: Optional[str] = None
    scheme_code: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Outcomes
    was_eligible: Optional[bool] = None
    eligibility_score: Optional[float] = None
    completion_status: ConversationStatus
    
    # Metrics
    total_messages: int = 0
    data_fields_collected: int = 0
    errors_encountered: int = 0
    llm_tokens_used: Optional[int] = None
    
    # User behavior
    user_engagement_score: Optional[float] = None  # Based on response quality and speed
    most_difficult_field: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ConversationMetrics(BaseModel):
    """Aggregated metrics for monitoring and analytics"""
    
    # Time-based metrics
    total_conversations: int = 0
    active_conversations: int = 0
    completed_conversations: int = 0
    failed_conversations: int = 0
    
    # Success metrics
    average_completion_rate: float = 0.0
    average_eligibility_score: float = 0.0
    average_conversation_duration: float = 0.0
    
    # Performance metrics
    average_messages_per_conversation: float = 0.0
    average_llm_interactions: float = 0.0
    most_common_failure_reasons: List[str] = Field(default_factory=list)
    
    # Scheme-specific metrics
    scheme_popularity: Dict[str, int] = Field(default_factory=dict)
    scheme_success_rates: Dict[str, float] = Field(default_factory=dict)
    
    # Data collection metrics
    most_difficult_fields: List[str] = Field(default_factory=list)
    average_attempts_per_field: Dict[str, float] = Field(default_factory=dict)
    
    # Timestamp
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

class ConversationHealthCheck(BaseModel):
    """Health check information for conversation service"""
    
    service_status: str = "healthy"
    active_conversations_count: int = 0
    processing_queue_size: int = 0
    average_response_time_ms: float = 0.0
    error_rate_percentage: float = 0.0
    
    # Resource usage
    memory_usage_mb: Optional[float] = None
    cpu_usage_percentage: Optional[float] = None
    
    # External dependencies
    llm_service_status: str = "unknown"
    database_status: str = "unknown"
    cache_status: str = "unknown"
    
    last_checked: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def is_healthy(self) -> bool:
        """Check if the service is in a healthy state"""
        return (
            self.service_status == "healthy" and
            self.error_rate_percentage < 5.0 and
            self.average_response_time_ms < 2000
        )