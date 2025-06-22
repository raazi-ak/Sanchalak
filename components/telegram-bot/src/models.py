from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class EKYCStatus(str, Enum):
    NOT_STARTED = "not_started"
    AADHAAR_VERIFIED = "aadhaar_verified"
    PHOTO_VERIFIED = "photo_verified"
    SKIPPED = "skipped"

class SessionStatus(str, Enum):
    ACTIVE = "active"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

class MessageType(str, Enum):
    TEXT = "text"
    VOICE = "voice"

class FarmerVerification(BaseModel):
    """Model for farmer verification collection"""
    farmer_id: str = Field(default_factory=lambda: f"farmer_{str(uuid.uuid4())[:8]}")
    phone: Optional[str] = None
    name: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.PENDING
    telegram_user_id: int
    username: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    language_preference: str = "hi"
    
    # eKYC fields
    ekyc_status: EKYCStatus = EKYCStatus.NOT_STARTED
    aadhaar_number: Optional[str] = None  # Encrypted/hashed
    aadhaar_last_digits: Optional[str] = None  # Last 4 digits for display
    photo_verification_status: Optional[bool] = None
    ekyc_completed_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True

class LogMessage(BaseModel):
    """Individual message within a session"""
    message_id: str = Field(default_factory=lambda: f"msg_{str(uuid.uuid4())[:8]}")
    type: MessageType
    content: Optional[str] = None  # For text messages
    file_path: Optional[str] = None  # For voice messages
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True

class SessionLog(BaseModel):
    """Model for session logs collection"""
    session_id: str = Field(default_factory=lambda: f"session_{str(uuid.uuid4())[:8]}")
    farmer_id: str
    telegram_user_id: int
    status: SessionStatus = SessionStatus.ACTIVE
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    messages: List[LogMessage] = []
    processing_result: Optional[Dict[str, Any]] = None
    orchestrator_response: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    class Config:
        use_enum_values = True

class MockAIResponse(BaseModel):
    """Mock response structure for testing"""
    eligibility_status: str
    eligible_schemes: List[str]
    recommendations: List[str]
    confidence_score: float
    processing_time: float
    
class BotResponse(BaseModel):
    """Structured bot response"""
    text: str
    is_session_active: bool = False
    session_id: Optional[str] = None
    response_type: str = "info"  # info, success, error, processing

# Telegram Update Models (for type hints)
class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None

class TelegramMessage(BaseModel):
    message_id: int
    text: Optional[str] = None
    voice: Optional[Dict[str, Any]] = None
    from_user: TelegramUser
    chat_id: int
    date: datetime 