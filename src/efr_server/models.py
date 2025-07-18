from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import uuid4

# Farmer Profile with comprehensive data
class AudioMetadata(BaseModel):
    """Metadata from audio processing"""
    detected_language: Optional[str] = None
    transcription_confidence: Optional[float] = Field(None, ge=0, le=1)
    processing_time: Optional[float] = None

class ExtractionMetadata(BaseModel):
    """Metadata from information extraction"""
    method: Optional[str] = None  # spacy, ollama, rule-based
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    entities_extracted: List[str] = Field(default_factory=list)
    processing_time: Optional[float] = None

class PipelineMetadata(BaseModel):
    """Metadata from the processing pipeline"""
    task_id: str
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    transcribed_text: Optional[str] = None

class LandOwnershipType(str, Enum):
    """Types of land ownership"""
    OWNED = "owned"
    LEASED = "leased"
    SHARECROPPING = "sharecropping"
    JOINT = "joint"
    INSTITUTIONAL = "institutional"
    UNKNOWN = "unknown"

class IrrigationType(str, Enum):
    """Types of irrigation"""
    RAIN_FED = "rain_fed"
    CANAL = "canal"
    BOREWELL = "borewell"
    WELL = "well"
    DRIP = "drip_irrigation"
    SPRINKLER = "sprinkler_irrigation"
    TUBE_WELL = "tube_well"
    SURFACE = "surface_irrigation"
    FLOOD = "flood_irrigation"
    UNKNOWN = "unknown"

class ProcessingStatus(str, Enum):
    """Processing status for farmer records"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

class Farmer(BaseModel):
    """Comprehensive farmer profile with all available information"""
    
    # Required fields
    aadhaar_number: str
    farmer_id: str
    name: str
    
    # Personal Information
    age: int = Field(ge=18, le=120)
    gender: str
    phone_number: str
    family_size: int = Field(ge=1)
    dependents: int = Field(ge=0)
    
    # Location Information
    state: str
    district: str
    sub_district_block: str
    village: str
    pincode: str
    
    # Agricultural Information
    land_size_acres: float = Field(ge=0)
    land_ownership: LandOwnershipType
    crops: List[str] = Field(default_factory=list)
    farming_equipment: List[str] = Field(default_factory=list)
    irrigation_type: IrrigationType
    
    # Financial Information
    annual_income: float = Field(ge=0)
    bank_account: bool
    account_number: str
    ifsc_code: str
    has_kisan_credit_card: bool
    
    # PM-KISAN Specific Fields
    aadhaar_linked: bool
    category: str
    family_definition: str
    region: str
    land_owner: bool
    date_of_land_ownership: str
    
    # Professional Information
    profession: Optional[str] = None
    
    # Processing Metadata
    audio_metadata: Optional[AudioMetadata] = None
    extraction_metadata: Optional[ExtractionMetadata] = None
    pipeline_metadata: Optional[PipelineMetadata] = None
    
    # Processing status
    status: ProcessingStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Family members
    family_members: List[Dict[str, Any]] = Field(default_factory=list)
    
    # PM-KISAN Exclusion Fields
    is_constitutional_post_holder: bool
    is_political_office_holder: bool
    is_government_employee: bool
    government_post: Optional[str] = None
    monthly_pension: Optional[float] = None
    is_income_tax_payer: bool
    is_professional: bool
    is_nri: bool
    is_pensioner: bool
    
   
    
    # Generic special provisions for scheme-specific data
    special_provisions: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('government_post')
    def validate_government_post(cls, v, values):
        if values.get('is_government_employee') and not v:
            raise ValueError('government_post is required when is_government_employee is True')
        return v

    @validator('monthly_pension')
    def validate_monthly_pension(cls, v, values):
        if values.get('is_pensioner') and v is None:
            raise ValueError('monthly_pension is required when is_pensioner is True')
        return v

    @validator('profession')
    def validate_profession(cls, v, values):
        if values.get('is_professional') and not v:
            raise ValueError('profession is required when is_professional is True')
        return v

    def __init__(self, **data):
        aadhaar_number = data.get('aadhaar_number')
        # Always use Aadhaar number as farmer_id for consistency
        if aadhaar_number:
            data['farmer_id'] = aadhaar_number
        elif 'farmer_id' not in data or not data.get('farmer_id'):
            data['farmer_id'] = str(uuid4())
        super().__init__(**data)

class FarmerSearchQuery(BaseModel):
    """Query model for searching farmers"""
    name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    crops: Optional[List[str]] = None
    land_size_min: Optional[float] = None
    land_size_max: Optional[float] = None
    status: Optional[ProcessingStatus] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)

class FarmerSummary(BaseModel):
    """Summary statistics for farmers"""
    total_farmers: int
    by_state: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_crops: Dict[str, int] = Field(default_factory=dict)
    average_land_size: float
    total_land_size: float
    processing_stats: Dict[str, Any] = Field(default_factory=dict)

class DatabaseResponse(BaseModel):
    """Standard database response"""
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class BulkFarmerResponse(BaseModel):
    """Response for bulk farmer operations"""
    success: bool
    processed_count: int
    failed_count: int
    farmers: List[Farmer] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
