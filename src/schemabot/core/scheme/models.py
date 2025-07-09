from pydantic import BaseModel, Field, validator, ConfigDict
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

class Operator(str, Enum):
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    BETWEEN = "between"
    IN = "in"
    NOT_IN = "not_in"

class EligibilityRule(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    rule_id: str
    field: str
    operator: Operator
    value: Union[str, int, float, bool, List[Any]]
    data_type: DataType
    description: str
    
    @validator('value')
    def validate_value_type(cls, v, values):
        data_type = values.get('data_type')
        operator = values.get('operator')
        
        if operator == Operator.BETWEEN and not isinstance(v, list):
            raise ValueError("BETWEEN operator requires list value with 2 elements")
        
        if operator in [Operator.IN, Operator.NOT_IN] and not isinstance(v, list):
            raise ValueError(f"{operator} operator requires list value")
        
        return v

class EligibilityLogic(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    rules: List[EligibilityRule]
    logic: str = Field(default="ALL", pattern="^(ALL|ANY)$")
    required_criteria: List[str] = []
    exclusion_criteria: List[str] = []

class Benefit(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    type: str
    description: str
    amount: Optional[float] = None
    frequency: Optional[str] = None
    coverage_details: Optional[str] = None

class Metadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    category: str
    disbursement: str
    version: str = "1.0.0"
    status: str

class Monitoring(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    claim_settlement_target: str
    participating_entities: List[str]

class GovernmentScheme(BaseModel):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    id: str
    name: str
    code: str
    ministry: str
    launched_on: str
    description: str
    metadata: Metadata
    eligibility: EligibilityLogic
    benefits: List[Benefit]
    documents: List[str]
    application_modes: List[str]
    monitoring: Monitoring
    notes: Optional[str] = None

class SchemeMetadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    last_updated: datetime
    version: str
    source_file: str

class SchemeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    ARCHIVED = "archived"

class SchemeInfo(BaseModel):
    """Basic scheme information for listings"""
    model_config = ConfigDict(protected_namespaces=())
    
    file: str
    status: SchemeStatus
    category: str
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[str] = None

class SchemeRegistry(BaseModel):
    """Registry containing all scheme information"""
    model_config = ConfigDict(protected_namespaces=())
    
    schemes: Dict[str, SchemeInfo]
    last_updated: Optional[datetime] = None
    version: str = "1.0.0"

class SchemeValidationResult(BaseModel):
    """Result of scheme validation"""
    model_config = ConfigDict(protected_namespaces=())
    
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    scheme_code: Optional[str] = None

class SchemeParsingResult(BaseModel):
    """Result of scheme parsing operation"""
    model_config = ConfigDict(protected_namespaces=())
    
    success: bool
    scheme: Optional[GovernmentScheme] = None
    errors: List[str] = []
    warnings: List[str] = []

class SchemeBulkOperation(BaseModel):
    """Bulk operation result"""
    model_config = ConfigDict(protected_namespaces=())
    
    success_count: int
    error_count: int
    errors: List[str] = []
    processed_schemes: List[str] = []

# Aliases for backward compatibility
Scheme = GovernmentScheme

# Export all models for easy importing
__all__ = [
    'DataType',
    'Operator', 
    'EligibilityRule',
    'EligibilityLogic',
    'Benefit',
    'Metadata',
    'Monitoring',
    'GovernmentScheme',
    'SchemeMetadata',
    'SchemeStatus',
    'SchemeInfo',
    'SchemeRegistry',
    'SchemeValidationResult',
    'SchemeParsingResult',
    'SchemeBulkOperation',
    'Scheme'
]
