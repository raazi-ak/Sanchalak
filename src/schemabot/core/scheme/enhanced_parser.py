"""
Enhanced Scheme Parser for Canonical Enhanced Models
Handles the rich data model structure with validation rules and LLM extraction prompts
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, ValidationError
import yaml
import json
from pathlib import Path

from .models import GovernmentScheme, EligibilityRule, EligibilityLogic, Benefit, Metadata, Monitoring
from .canonical_models import CanonicalScheme, FieldDefinition, DataModelSection, ValidationType


class EnhancedSchemeParser:
    """Parser for enhanced scheme definitions with canonical data models"""
    
    def __init__(self):
        self.supported_validation_types = {
            "non_empty_string": self._validate_non_empty_string,
            "range": self._validate_range,
            "range(18, 120)": self._validate_age_range,
            "enum_values": self._validate_enum_values,
            "phone_format": self._validate_phone_format,
            "date_format": self._validate_date_format,
            "positive_float": self._validate_positive_float,
            "non_negative_float": self._validate_non_negative_float,
            "list_of_strings": self._validate_list_of_strings,
            "list_of_family_members": self._validate_family_members,
            "boolean": self._validate_boolean,
            "account_format": self._validate_account_format,
            "ifsc_format": self._validate_ifsc_format,
            "aadhaar_format": self._validate_aadhaar_format,
            "voter_id_format": self._validate_voter_id_format,
            "pincode_format": self._validate_pincode_format,
        }
    
    def parse_enhanced_scheme(self, file_path: str) -> CanonicalScheme:
        """Parse an enhanced scheme YAML file into a CanonicalScheme object"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data or 'schemes' not in data:
            raise ValueError("Invalid scheme file: missing 'schemes' key")
        
        scheme_data = data['schemes'][0]  # Take the first scheme
        
        # Parse the enhanced data model
        data_model = self._parse_data_model(scheme_data.get('data_model', {}))
        
        # Create the canonical scheme
        canonical_scheme = CanonicalScheme(
            id=scheme_data['id'],
            name=scheme_data['name'],
            code=scheme_data['code'],
            ministry=scheme_data['ministry'],
            launched_on=scheme_data['launched_on'],
            description=scheme_data['description'],
            data_model=data_model,
            validation_rules=scheme_data.get('validation_rules'),
            benefits=scheme_data.get('benefits'),
            documents=scheme_data.get('documents'),
            application_modes=scheme_data.get('application_modes'),
            notes=scheme_data.get('notes')
        )
        
        return canonical_scheme
    
    def _parse_data_model(self, data_model: Dict[str, Any]) -> Dict[str, DataModelSection]:
        """Parse the data model sections into FieldDefinition objects"""
        parsed_model = {}
        
        for section_name, section_fields in data_model.items():
            section_definitions = {}
            
            for field_name, field_data in section_fields.items():
                field_def = FieldDefinition(
                    type=field_data['type'],
                    required=field_data['required'],
                    description=field_data['description'],
                    prolog_fact=field_data.get('prolog_fact'),
                    validation=field_data.get('validation'),
                    values=field_data.get('values'),
                    structure=field_data.get('structure'),
                    prolog_facts=field_data.get('prolog_facts'),
                    computation=field_data.get('computation')
                )
                section_definitions[field_name] = field_def
            
            parsed_model[section_name] = DataModelSection(section_definitions)
        
        return parsed_model
    
    def validate_extracted_data(self, data: Dict[str, Any], scheme: CanonicalScheme) -> Dict[str, Any]:
        """Validate extracted data against the scheme's validation rules"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'validated_data': data.copy()
        }
        
        # Validate required fields
        required_fields = scheme.validation_rules.get('required_for_eligibility', [])
        for field in required_fields:
            if field not in data or data[field] is None:
                validation_result['errors'].append(f"Required field '{field}' is missing")
                validation_result['is_valid'] = False
        
        # Validate conditional requirements
        conditional_reqs = scheme.validation_rules.get('conditional_requirements', [])
        for req in conditional_reqs:
            condition = req['if']
            requirement = req['then']
            
            # Simple condition parsing (can be enhanced)
            if self._evaluate_condition(condition, data):
                required_field = requirement.split()[0]
                if required_field not in data or data[required_field] is None:
                    validation_result['errors'].append(f"Conditional field '{required_field}' is required when {condition}")
                    validation_result['is_valid'] = False
        
        # Validate individual fields
        for section_name, section in scheme.data_model.items():
            for field_name, field_def in section.items():
                if field_name in data:
                    field_value = data[field_name]
                    validation_result = self._validate_field(
                        field_value, field_def, field_name, validation_result
                    )
        
        return validation_result
    
    def _validate_field(self, value: Any, field_def: FieldDefinition, field_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single field against its definition"""
        if field_def.validation and field_def.validation in self.supported_validation_types:
            try:
                self.supported_validation_types[field_def.validation](value, field_def)
            except ValueError as e:
                result['errors'].append(f"Field '{field_name}': {str(e)}")
                result['is_valid'] = False
        
        return result
    
    def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        """Evaluate a simple condition string against data"""
        # Simple condition evaluation (can be enhanced with proper expression parsing)
        if '=' in condition:
            field, value = condition.split('=', 1)
            field = field.strip()
            value = value.strip().strip('"').strip("'")
            
            if field in data:
                return str(data[field]) == value
        
        return False
    
    # Validation functions
    def _validate_non_empty_string(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Must be a non-empty string")
    
    def _validate_range(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, (int, float)):
            raise ValueError("Must be a number")
        # Could add range validation if specified in field_def
    
    def _validate_age_range(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, int) or value < 18 or value > 120:
            raise ValueError("Age must be between 18 and 120")
    
    def _validate_enum_values(self, value: Any, field_def: FieldDefinition):
        if field_def.values and value not in field_def.values:
            raise ValueError(f"Must be one of: {', '.join(field_def.values)}")
    
    def _validate_phone_format(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, str) or not value.isdigit() or len(value) != 10:
            raise ValueError("Phone number must be 10 digits")
    
    def _validate_date_format(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, str):
            raise ValueError("Must be a date string")
        # Could add more sophisticated date validation
    
    def _validate_positive_float(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError("Must be a positive number")
    
    def _validate_non_negative_float(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError("Must be a non-negative number")
    
    def _validate_list_of_strings(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("Must be a list of strings")
    
    def _validate_family_members(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, list):
            raise ValueError("Must be a list of family members")
        # Could add more sophisticated family member validation
    
    def _validate_boolean(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, bool):
            raise ValueError("Must be a boolean value")
    
    def _validate_account_format(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, str) or not value.isdigit():
            raise ValueError("Account number must be numeric")
    
    def _validate_ifsc_format(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, str) or len(value) != 11:
            raise ValueError("IFSC code must be 11 characters")
    
    def _validate_aadhaar_format(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, str) or not value.isdigit() or len(value) != 12:
            raise ValueError("Aadhaar number must be 12 digits")
    
    def _validate_voter_id_format(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, str):
            raise ValueError("Must be a string")
    
    def _validate_pincode_format(self, value: Any, field_def: FieldDefinition):
        if not isinstance(value, str) or not value.isdigit() or len(value) != 6:
            raise ValueError("Pincode must be 6 digits")
    
    def generate_extraction_prompt(self, scheme: CanonicalScheme, transcript: str) -> str:
        """Generate LLM extraction prompt for the scheme"""
        if not hasattr(scheme, 'extraction_prompts') or not scheme.extraction_prompts:
            return f"Extract information from: {transcript}"
        
        main_prompt = scheme.extraction_prompts.get('main_extraction', {})
        prompt_template = main_prompt.get('prompt', 'Extract information from: {transcript}')
        
        return prompt_template.format(transcript=transcript)
    
    def get_clarification_prompts(self, scheme: CanonicalScheme) -> Dict[str, str]:
        """Get clarification prompts for the scheme"""
        if not hasattr(scheme, 'extraction_prompts'):
            return {}
        
        return scheme.extraction_prompts.get('clarification_prompts', {})
    
    def convert_to_legacy_format(self, canonical_scheme: CanonicalScheme) -> GovernmentScheme:
        """Convert canonical scheme to legacy GovernmentScheme format for backward compatibility"""
        # Extract basic eligibility rules from the canonical scheme
        eligibility_rules = []
        
        # Convert validation rules to eligibility rules
        if canonical_scheme.validation_rules:
            required_fields = canonical_scheme.validation_rules.get('required_for_eligibility', [])
            for i, field in enumerate(required_fields):
                rule = EligibilityRule(
                    rule_id=f"RULE_{i+1:03d}",
                    field=field,
                    operator="!=",
                    value=None,
                    data_type="string",
                    description=f"Field {field} is required"
                )
                eligibility_rules.append(rule)
        
        eligibility_logic = EligibilityLogic(
            rules=eligibility_rules,
            logic="ALL",
            required_criteria=canonical_scheme.validation_rules.get('required_for_eligibility', []) if canonical_scheme.validation_rules else [],
            exclusion_criteria=[]
        )
        
        # Convert benefits
        benefits = []
        if canonical_scheme.benefits:
            for benefit_data in canonical_scheme.benefits:
                benefit = Benefit(
                    type=benefit_data.get('type', ''),
                    description=benefit_data.get('description', ''),
                    amount=benefit_data.get('amount'),
                    frequency=benefit_data.get('frequency'),
                    coverage_details=benefit_data.get('coverage_details')
                )
                benefits.append(benefit)
        
        # Create metadata
        metadata = Metadata(
            category="agriculture",  # Default, could be extracted from scheme
            disbursement="direct_benefit_transfer",
            version="5.0.0",
            status="active"
        )
        
        # Create monitoring
        monitoring = Monitoring(
            claim_settlement_target="Within 45 days",
            participating_entities=["State Agriculture Departments", "District Collectors"]
        )
        
        # Create legacy scheme
        legacy_scheme = GovernmentScheme(
            id=canonical_scheme.id,
            name=canonical_scheme.name,
            code=canonical_scheme.code,
            ministry=canonical_scheme.ministry,
            launched_on=canonical_scheme.launched_on,
            description=canonical_scheme.description,
            metadata=metadata,
            eligibility=eligibility_logic,
            benefits=benefits,
            documents=canonical_scheme.documents or [],
            application_modes=canonical_scheme.application_modes or [],
            monitoring=monitoring,
            notes=canonical_scheme.notes
        )
        
        return legacy_scheme


# Convenience functions
def load_enhanced_scheme(file_path: str) -> CanonicalScheme:
    """Load an enhanced scheme from file"""
    parser = EnhancedSchemeParser()
    return parser.parse_enhanced_scheme(file_path)


def validate_extracted_data(data: Dict[str, Any], scheme: CanonicalScheme) -> Dict[str, Any]:
    """Validate extracted data against a scheme"""
    parser = EnhancedSchemeParser()
    return parser.validate_extracted_data(data, scheme)


def generate_extraction_prompt(scheme: CanonicalScheme, transcript: str) -> str:
    """Generate extraction prompt for a scheme"""
    parser = EnhancedSchemeParser()
    return parser.generate_extraction_prompt(scheme, transcript) 