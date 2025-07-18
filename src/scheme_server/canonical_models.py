from pydantic import BaseModel, Field, validator, ConfigDict, RootModel
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum

class DataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    LIST = "list"
    ENUM = "enum"
    LIST_OF_OBJECTS = "list_of_objects"

class ValidationType(str, Enum):
    NON_EMPTY_STRING = "non_empty_string"
    RANGE = "range"
    RANGE_18_120 = "range(18, 120)"  # Specific age range
    ENUM_VALUES = "enum_values"
    PHONE_FORMAT = "phone_format"
    DATE_FORMAT = "date_format"
    POSITIVE_FLOAT = "positive_float"
    NON_NEGATIVE_FLOAT = "non_negative_float"
    LIST_OF_STRINGS = "list_of_strings"
    LIST_OF_FAMILY_MEMBERS = "list_of_family_members"
    BOOLEAN = "boolean"
    ACCOUNT_FORMAT = "account_format"
    IFSC_FORMAT = "ifsc_format"
    AADHAAR_FORMAT = "aadhaar_format"
    VOTER_ID_FORMAT = "voter_id_format"
    PINCODE_FORMAT = "pincode_format"

class FieldDefinition(BaseModel):
    """Definition for a single field in the canonical YAML"""
    model_config = ConfigDict(protected_namespaces=())
    
    type: DataType
    required: bool
    description: str
    prolog_fact: Optional[str] = None
    validation: Optional[ValidationType] = None
    values: Optional[List[str]] = None  # For enum types
    structure: Optional[Dict[str, Any]] = None  # For list_of_objects
    prolog_facts: Optional[List[str]] = None  # For complex objects
    computation: Optional[str] = None  # For derived fields

class DataModelSection(RootModel[Dict[str, 'FieldDefinition']]):
    """A section of the data model (e.g., basic_info, location, land)"""
    model_config = ConfigDict(protected_namespaces=())

class CanonicalScheme(BaseModel):
    """Complete canonical scheme structure"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: str
    name: str
    code: str
    ministry: str
    launched_on: str
    description: str
    
    # Enhanced data model
    data_model: Dict[str, DataModelSection]
    
    # Validation rules
    validation_rules: Optional[Dict[str, Any]] = None
    
    # Benefits and other scheme details
    benefits: Optional[List[Dict[str, Any]]] = None
    documents: Optional[List[str]] = None
    application_modes: Optional[List[str]] = None
    notes: Optional[str] = None

class CanonicalSchemeRegistry(BaseModel):
    """Registry of canonical schemes"""
    model_config = ConfigDict(protected_namespaces=())
    
    schemes: List[CanonicalScheme]

class ConsentStage(str, Enum):
    NOT_STARTED = "not_started"
    CONSENT_REQUESTED = "consent_requested"
    CONSENT_GRANTED = "consent_granted"
    CONSENT_DENIED = "consent_denied"
    DATA_COLLECTION = "data_collection"
    VALIDATION = "validation"
    COMPLETE = "complete"

class ConversationContext(BaseModel):
    """Enhanced conversation context with consent and canonical data support"""
    model_config = ConfigDict(protected_namespaces=())
    
    scheme_code: str
    stage: ConsentStage
    collected_data: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    current_field: Optional[str] = None
    attempts_count: Dict[str, int] = Field(default_factory=dict)
    consent_granted: bool = False
    consent_requested: bool = False
    session_id: Optional[str] = None
    
    # Canonical data structure
    canonical_scheme: Optional[CanonicalScheme] = None
    required_fields: List[str] = Field(default_factory=list)
    field_metadata: Dict[str, FieldDefinition] = Field(default_factory=dict)

class ConsentRequest(BaseModel):
    """Request for user consent to collect data"""
    model_config = ConfigDict(protected_namespaces=())
    
    scheme_name: str
    scheme_description: str
    data_purpose: str
    data_fields: List[str]
    data_retention: str
    user_rights: List[str]

class ConsentResponse(BaseModel):
    """User response to consent request"""
    model_config = ConfigDict(protected_namespaces=())
    
    granted: bool
    timestamp: datetime
    session_id: str
    user_acknowledgment: Optional[str] = None

class DataValidationResult(BaseModel):
    """Result of data validation against Pydantic model"""
    model_config = ConfigDict(protected_namespaces=())
    
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validated_data: Optional[Dict[str, Any]] = None

# Export all models
__all__ = [
    'DataType',
    'ValidationType',
    'FieldDefinition',
    'DataModelSection',
    'CanonicalScheme',
    'CanonicalSchemeRegistry',
    'ConsentStage',
    'ConversationContext',
    'ConsentRequest',
    'ConsentResponse',
    'DataValidationResult'
] 