"""
Pydantic models for the Farmer AI Pipeline
Defines data structures for API requests/responses and internal data handling
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


# Enums
class LanguageCode(str, Enum):
    HINDI = "hi"
    ENGLISH = "en"
    GUJARATI = "gu"
    PUNJABI = "pa"
    BENGALI = "bn"
    TELUGU = "te"
    TAMIL = "ta"
    MALAYALAM = "ml"
    KANNADA = "kn"
    ODIA = "or"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    PARTIALLY_ELIGIBLE = "partially_eligible"
    INSUFFICIENT_DATA = "insufficient_data"


# Audio Processing Models
class AudioUploadRequest(BaseModel):
    """Request model for audio upload"""
    language_hint: Optional[LanguageCode] = LanguageCode.HINDI
    farmer_id: Optional[str] = None
    session_id: Optional[str] = None


class AudioProcessingResponse(BaseModel):
    """Response model for audio processing"""
    task_id: str
    status: ProcessingStatus
    transcribed_text: Optional[str] = None
    detected_language: Optional[LanguageCode] = None
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Farmer Information Models
class FarmerInfo(BaseModel):
    """Farmer personal and agricultural information"""
    farmer_id: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = Field(None, ge=18, le=100)
    gender: Optional[str] = None
    phone_number: Optional[str] = None
    
    # Location
    state: Optional[str] = None
    district: Optional[str] = None
    village: Optional[str] = None
    pincode: Optional[str] = None
    
    # Agricultural details
    land_size_acres: Optional[float] = Field(None, ge=0)
    land_ownership: Optional[str] = None  # owned, leased, shared
    crops: List[str] = Field(default_factory=list)
    irrigation_type: Optional[str] = None  # rain-fed, canal, borewell, drip
    
    # Financial
    annual_income: Optional[float] = Field(None, ge=0)
    bank_account: Optional[str] = None
    has_kisan_credit_card: Optional[bool] = None
    
    # Family
    family_size: Optional[int] = Field(None, ge=1)
    dependents: Optional[int] = Field(None, ge=0)
    
    @validator('phone_number')
    def validate_phone(cls, v):
        if v and not v.startswith('+91'):
            v = '+91' + v.lstrip('0')
        return v


class ExtractedInfo(BaseModel):
    """Information extracted from farmer's audio/text"""
    raw_text: str
    farmer_info: FarmerInfo
    entities: Dict[str, Any] = Field(default_factory=dict)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    extraction_method: str  # spacy, rasa, rule-based
    processed_at: datetime = Field(default_factory=datetime.utcnow)


# Government Scheme Models
class EligibilityRule(BaseModel):
    """Eligibility rule for a government scheme"""
    field: str
    operator: str  # >=, <=, ==, !=, in, not_in
    value: Union[str, int, float, List[str]]
    weight: float = 1.0


class GovernmentScheme(BaseModel):
    """Government scheme information"""
    scheme_id: str
    name: str
    name_hindi: Optional[str] = None
    description: str
    description_hindi: Optional[str] = None
    
    # Benefits
    benefit_amount: Optional[float] = None
    benefit_type: str  # subsidy, loan, insurance, direct_transfer
    
    # Eligibility
    eligibility_rules: List[EligibilityRule] = Field(default_factory=list)
    target_beneficiaries: List[str] = Field(default_factory=list)
    
    # Administrative
    implementing_agency: str
    application_process: str
    required_documents: List[str] = Field(default_factory=list)
    
    # URLs and contact
    official_website: Optional[str] = None
    helpline_number: Optional[str] = None
    
    # Metadata
    launch_date: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    
    # Vector embedding
    embedding: Optional[List[float]] = None


class EligibilityCheck(BaseModel):
    """Result of eligibility check for a scheme"""
    scheme_id: str
    scheme_name: str
    status: EligibilityStatus
    score: float = Field(ge=0, le=1)  # 0-1 eligibility score
    
    # Detailed results
    passed_rules: List[str] = Field(default_factory=list)
    failed_rules: List[str] = Field(default_factory=list)
    missing_info: List[str] = Field(default_factory=list)
    
    # Explanation
    explanation: str
    explanation_hindi: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)


class EligibilityResponse(BaseModel):
    """Complete eligibility response"""
    farmer_info: FarmerInfo
    eligible_schemes: List[EligibilityCheck] = Field(default_factory=list)
    ineligible_schemes: List[EligibilityCheck] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    
    total_schemes_checked: int
    eligible_count: int
    processing_time: float
    checked_at: datetime = Field(default_factory=datetime.utcnow)


# Vector Database Models
class DocumentChunk(BaseModel):
    """Document chunk for vector database"""
    chunk_id: str
    content: str
    content_hindi: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    source_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VectorSearchResult(BaseModel):
    """Vector database search result"""
    chunk_id: str
    content: str
    similarity_score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_url: Optional[str] = None


class VectorSearchRequest(BaseModel):
    """Vector database search request"""
    query: str
    top_k: int = 5
    similarity_threshold: float = 0.5
    filters: Optional[Dict[str, Any]] = None


# API Response Models
class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    uptime: float
    models_loaded: Dict[str, bool] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


class ProcessingTask(BaseModel):
    """Background task model"""
    task_id: str
    task_type: str
    status: ProcessingStatus
    progress: float = Field(ge=0, le=100, default=0)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_completion: Optional[datetime] = None


# Complete Pipeline Models
class FarmerPipelineRequest(BaseModel):
    """Complete pipeline request"""
    audio_file: Optional[str] = None  # File path or base64
    text_input: Optional[str] = None
    farmer_id: Optional[str] = None
    language_hint: LanguageCode = LanguageCode.HINDI
    include_scheme_recommendations: bool = True
    explain_decisions: bool = True


class FarmerPipelineResponse(BaseModel):
    """Complete pipeline response"""
    task_id: str
    farmer_info: Optional[FarmerInfo] = None
    eligibility_response: Optional[EligibilityResponse] = None
    processing_steps: List[Dict[str, Any]] = Field(default_factory=list)
    total_processing_time: float
    
    # Audio processing results
    transcription: Optional[str] = None
    detected_language: Optional[LanguageCode] = None
    
    # Vector search results
    relevant_schemes: List[VectorSearchResult] = Field(default_factory=list)
    
    status: ProcessingStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Metrics and Analytics
class UsageMetrics(BaseModel):
    """Usage metrics for monitoring"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_processing_time: float = 0.0
    languages_processed: Dict[str, int] = Field(default_factory=dict)
    schemes_queried: Dict[str, int] = Field(default_factory=dict)
    error_types: Dict[str, int] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Webhooks and Notifications
class WebhookPayload(BaseModel):
    """Webhook payload for external integrations"""
    event_type: str
    farmer_id: Optional[str] = None
    task_id: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class NotificationRequest(BaseModel):
    """Notification request for farmers"""
    farmer_id: str
    message: str
    message_hindi: Optional[str] = None
    notification_type: str  # sms, email, push
    priority: str = "normal"  # low, normal, high, urgent
    schedule_at: Optional[datetime] = None