
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from enum import Enum
import json

class DataType(Enum):
    """Enumeration for supported data types in eligibility rules."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    ARRAY = "array"

class Operator(Enum):
    """Enumeration for supported operators in eligibility rules."""
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    GREATER_THAN_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_EQUAL = "<="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    BETWEEN = "between"
    SIZE = "size"
    SIZE_GT = "size_gt"
    SIZE_LT = "size_lt"

class RuleLogic(Enum):
    """Enumeration for rule combination logic."""
    ALL = "ALL"
    ANY = "ANY"

@dataclass
class EligibilityRule:
    """Data model for individual eligibility rules."""
    rule_id: str
    field: str
    operator: str
    value: Any
    data_type: str
    description: Optional[str] = None
    error_message: Optional[str] = None
    weight: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert rule to dictionary format."""
        return {
            "rule_id": self.rule_id,
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
            "data_type": self.data_type,
            "description": self.description,
            "error_message": self.error_message,
            "weight": self.weight
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "EligibilityRule":
        """Create rule from dictionary data."""
        return cls(
            rule_id=data["rule_id"],
            field=data["field"],
            operator=data["operator"],
            value=data["value"],
            data_type=data["data_type"],
            description=data.get("description"),
            error_message=data.get("error_message"),
            weight=data.get("weight")
        )

@dataclass
class SchemeMetadata:
    """Data model for scheme metadata."""
    scheme_id: str
    name: str
    code: str
    ministry: str
    launched_on: str
    description: str
    category: Optional[str] = None
    disbursement: Optional[str] = None
    version: str = "1.0.0"
    created_date: Optional[str] = None
    modified_date: Optional[str] = None
    status: str = "active"

    def to_dict(self) -> Dict:
        """Convert metadata to dictionary format."""
        return {
            "scheme_id": self.scheme_id,
            "name": self.name,
            "code": self.code,
            "ministry": self.ministry,
            "launched_on": self.launched_on,
            "description": self.description,
            "category": self.category,
            "disbursement": self.disbursement,
            "version": self.version,
            "created_date": self.created_date,
            "modified_date": self.modified_date,
            "status": self.status
        }

@dataclass
class SchemeBenefit:
    """Data model for scheme benefits."""
    type: str
    description: str
    amount: Optional[float] = None
    frequency: Optional[str] = None
    coverage_details: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert benefit to dictionary format."""
        return {
            "type": self.type,
            "description": self.description,
            "amount": self.amount,
            "frequency": self.frequency,
            "coverage_details": self.coverage_details
        }

@dataclass
class SchemeEligibility:
    """Data model for scheme eligibility criteria."""
    rules: List[EligibilityRule]
    logic: str = "ALL"
    required_criteria: Optional[List[str]] = None
    exclusion_criteria: Optional[List[str]] = None

    def to_dict(self) -> Dict:
        """Convert eligibility to dictionary format."""
        return {
            "rules": [rule.to_dict() for rule in self.rules],
            "logic": self.logic,
            "required_criteria": self.required_criteria,
            "exclusion_criteria": self.exclusion_criteria
        }

@dataclass
class SchemeDefinition:
    """Complete scheme definition model."""
    metadata: SchemeMetadata
    eligibility: SchemeEligibility
    benefits: List[SchemeBenefit]
    documents: List[str]
    application_modes: List[str]
    monitoring: Optional[Dict] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert scheme definition to dictionary format."""
        return {
            "metadata": self.metadata.to_dict(),
            "eligibility": self.eligibility.to_dict(),
            "benefits": [benefit.to_dict() for benefit in self.benefits],
            "documents": self.documents,
            "application_modes": self.application_modes,
            "monitoring": self.monitoring,
            "notes": self.notes
        }

    def to_json(self) -> str:
        """Convert scheme definition to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

@dataclass
class RuleResult:
    """Data model for individual rule evaluation results."""
    rule_id: str
    field: str
    operator: str
    expected_value: Any
    actual_value: Any
    passed: bool
    description: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert rule result to dictionary format."""
        return {
            "rule_id": self.rule_id,
            "field": self.field,
            "operator": self.operator,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "passed": self.passed,
            "description": self.description,
            "error_message": self.error_message
        }

@dataclass
class EligibilityResult:
    """Data model for complete eligibility check results."""
    is_eligible: bool
    scheme_info: Dict
    rule_results: List[RuleResult]
    explanations: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    checked_at: Optional[str] = None
    processing_time_ms: Optional[float] = None

    def __post_init__(self):
        """Set checked_at timestamp if not provided."""
        if self.checked_at is None:
            self.checked_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Convert eligibility result to dictionary format."""
        return {
            "is_eligible": self.is_eligible,
            "scheme_info": self.scheme_info,
            "rule_results": [result.to_dict() for result in self.rule_results],
            "explanations": self.explanations,
            "recommendations": self.recommendations,
            "checked_at": self.checked_at,
            "processing_time_ms": self.processing_time_ms,
            "summary": {
                "total_rules": len(self.rule_results),
                "passed_rules": len([r for r in self.rule_results if r.passed]),
                "failed_rules": len([r for r in self.rule_results if not r.passed])
            }
        }

    def to_json(self) -> str:
        """Convert eligibility result to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)
