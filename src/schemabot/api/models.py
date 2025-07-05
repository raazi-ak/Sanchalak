#schemabot\api\models.py

from pydantic import BaseModel, Field, validator
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime

class ConversationStage(str, Enum):
    GREETING = "greeting"
    DATA_COLLECTION = "data_collection"
    CLARIFICATION = "clarification"
    ELIGIBILITY_CHECK = "eligibility_check"
    RESULT_DELIVERY = "result_delivery"

class SchemeInfo(BaseModel):
    code: str
    name: str
    ministry: str
    category: str
    status: str
    description: str = Field(..., max_length=500)

class SchemeDetail(BaseModel):
    id: str
    name: str
    code: str
    ministry: str
    launched_on: str
    description: str
    category: str
    disbursement: str
    version: str
    status: str
    benefits: List[Dict[str, Any]]
    documents: List[str]
    application_modes: List[str]
    required_fields: List[str]

class ConversationStartRequest(BaseModel):
    scheme_code: str = Field(..., min_length=1, max_length=50)
    session_id: str = Field(..., min_length=1, max_length=100)
    
    @validator('session_id')
    def validate_session_id(cls, v):
        # Basic session ID validation
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Session ID must be alphanumeric with hyphens/underscores')
        return v

class ConversationStartResponse(BaseModel):
    session_id: str
    scheme_code: str
    initial_response: str
    required_fields: List[str]
    conversation_stage: ConversationStage

class ConversationContinueRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    user_input: str = Field(..., min_length=1, max_length=1000)

class EligibilityResultResponse(BaseModel):
    is_eligible: bool
    score: float = Field(..., ge=0, le=100)
    passed_rules: List[str]
    failed_rules: List[str]
    missing_fields: List[str]
    recommendations: List[str]

class ConversationResponse(BaseModel):
    session_id: str
    response: str
    conversation_stage: ConversationStage
    collected_data: Dict[str, Any]
    eligibility_result: Optional[EligibilityResultResponse] = None
    is_complete: bool

class EligibilityCheckRequest(BaseModel):
    scheme_code: str = Field(..., min_length=1, max_length=50)
    farmer_data: Dict[str, Any] = Field(..., min_items=1)
    
    @validator('farmer_data')
    def validate_farmer_data(cls, v):
        # Basic validation for farmer data
        if not isinstance(v, dict):
            raise ValueError('Farmer data must be a dictionary')
        return v

class EligibilityCheckResponse(BaseModel):
    scheme_code: str
    scheme_name: str
    is_eligible: bool
    eligibility_score: float
    passed_rules: List[str]
    failed_rules: List[str]
    missing_fields: List[str]
    recommendations: List[str]
    benefits: List[Dict[str, Any]]
    required_documents: List[str]
