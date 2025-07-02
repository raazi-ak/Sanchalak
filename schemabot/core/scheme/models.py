from pydantic import BaseModel, Field, validator
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
    rules: List[EligibilityRule]
    logic: str = Field(default="ALL", regex="^(ALL|ANY)$")
    required_criteria: List[str] = []
    exclusion_criteria: List[str] = []

class Benefit(BaseModel):
    type: str
    description: str
    amount: Optional[float] = None
    frequency: Optional[str] = None
    coverage_details: Optional[str] = None

class Metadata(BaseModel):
    category: str
    disbursement: str
    version: str = "1.0.0"
    status: str

class Monitoring(BaseModel):
    claim_settlement_target: str
    participating_entities: List[str]

class GovernmentScheme(BaseModel):
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
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
