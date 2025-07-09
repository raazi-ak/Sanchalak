import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging
import structlog
from datetime import datetime

from .canonical_models import (
    CanonicalScheme, 
    CanonicalSchemeRegistry, 
    FieldDefinition, 
    DataModelSection,
    DataType,
    ValidationType
)

logger = structlog.get_logger(__name__)

class CanonicalSchemeParsingError(Exception):
    """Custom exception for canonical scheme parsing errors"""
    pass

class CanonicalSchemeParser:
    """Parser for canonical YAML scheme files"""
    
    def __init__(self, canonical_schemes_directory: str = "src/schemes/outputs"):
        self.canonical_schemes_directory = Path(canonical_schemes_directory)
        self.schemes: Dict[str, CanonicalScheme] = {}
        self.validation_errors: Dict[str, List[str]] = {}
        self.parsing_errors: List[str] = []
        
    async def load_canonical_schemes(self) -> bool:
        """Load canonical schemes from YAML files"""
        try:
            if not self.canonical_schemes_directory.exists():
                logger.warning(f"Canonical schemes directory not found: {self.canonical_schemes_directory}")
                return False
            
            schemes_loaded = 0
            
            # Look for canonical YAML files in subdirectories
            for scheme_dir in self.canonical_schemes_directory.iterdir():
                if scheme_dir.is_dir():
                    # Look for enhanced canonical files
                    canonical_files = list(scheme_dir.glob("*canonical*ENHANCED*.yaml"))
                    if not canonical_files:
                        # Fallback to any canonical file
                        canonical_files = list(scheme_dir.glob("*canonical*.yaml"))
                    
                    for canonical_file in canonical_files:
                        try:
                            scheme = await self.parse_canonical_scheme(str(canonical_file))
                            if scheme:
                                self.schemes[scheme.code] = scheme
                                schemes_loaded += 1
                                logger.debug(f"Successfully loaded canonical scheme: {scheme.code}")
                        except Exception as e:
                            error_msg = f"Failed to load canonical scheme {canonical_file}: {e}"
                            logger.error(error_msg)
                            self.parsing_errors.append(error_msg)
            
            logger.info(f"Successfully loaded {schemes_loaded} canonical schemes")
            return schemes_loaded > 0
            
        except Exception as e:
            error_msg = f"Unexpected error loading canonical schemes: {e}"
            self.parsing_errors.append(error_msg)
            logger.error(error_msg)
            return False
    
    async def parse_canonical_scheme(self, file_path: str) -> Optional[CanonicalScheme]:
        """Parse a single canonical scheme file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                scheme_data = yaml.safe_load(file)
            
            if not scheme_data:
                raise CanonicalSchemeParsingError(f"Empty scheme file: {file_path}")
            
            # If the YAML contains a 'schemes' array, take the first one
            if 'schemes' in scheme_data and isinstance(scheme_data['schemes'], list):
                if len(scheme_data['schemes']) > 0:
                    scheme_data = scheme_data['schemes'][0]
                else:
                    raise CanonicalSchemeParsingError(f"No schemes found in file: {file_path}")
            
            # Convert the data_model structure to proper format
            if 'data_model' in scheme_data:
                data_model = {}
                
                # List of sections that are NOT field definitions (metadata sections)
                non_field_sections = ['validation_rules', 'extraction_prompts', 'derived_fields']
                
                for section_name, section_fields in scheme_data['data_model'].items():
                    if isinstance(section_fields, dict):
                        # Skip metadata sections that aren't field definitions
                        if section_name in non_field_sections:
                            # Move these to top level of scheme_data
                            scheme_data[section_name] = section_fields
                            continue
                        
                        # Convert each field to FieldDefinition
                        field_definitions = {}
                        for field_name, field_data in section_fields.items():
                            if isinstance(field_data, dict):
                                # Check if this looks like a field definition (has required fields)
                                if 'type' in field_data and 'description' in field_data:
                                    # Create a copy of field_data to avoid modifying original
                                    field_data_copy = field_data.copy()
                                    # If this field has a 'structure' key, preserve it as-is (don't convert to FieldDefinition)
                                    if 'structure' in field_data_copy:
                                        # Keep structure as raw dict for list_of_objects type
                                        pass  # structure stays as dict
                                    field_definitions[field_name] = FieldDefinition(**field_data_copy)
                                else:
                                    # This might be metadata or non-field data, skip it
                                    logger.warning(f"Skipping non-field data in section {section_name}: {field_name}")
                        
                        if field_definitions:  # Only create section if it has valid fields
                            data_model[section_name] = DataModelSection(field_definitions)
                
                scheme_data['data_model'] = data_model
            
            # Create the canonical scheme object
            scheme = CanonicalScheme(**scheme_data)
            return scheme
            
        except yaml.YAMLError as e:
            raise CanonicalSchemeParsingError(f"YAML parsing error in {file_path}: {e}")
        except Exception as e:
            raise CanonicalSchemeParsingError(f"Error parsing canonical scheme {file_path}: {e}")
    
    def get_canonical_scheme(self, code: str) -> Optional[CanonicalScheme]:
        """Get canonical scheme by code"""
        return self.schemes.get(code)
    
    def list_canonical_schemes(self) -> List[Dict[str, Any]]:
        """List all available canonical schemes with basic info"""
        return [
            {
                "code": scheme.code,
                "name": scheme.name,
                "ministry": scheme.ministry,
                "description": scheme.description,
                "data_model_sections": list(scheme.data_model.keys()) if scheme.data_model else []
            }
            for scheme in self.schemes.values()
        ]
    
    def get_required_fields(self, scheme_code: str) -> List[str]:
        """Get all required fields from canonical scheme"""
        scheme = self.get_canonical_scheme(scheme_code)
        if not scheme or not scheme.data_model:
            return []
        
        required_fields = []
        for section_name, section in scheme.data_model.items():
            for field_name, field_def in section.root.items():
                if field_def.required:
                    required_fields.append(f"{section_name}.{field_name}")
        
        return required_fields
    
    def get_field_metadata(self, scheme_code: str, field_path: str) -> Optional[FieldDefinition]:
        """Get metadata for a specific field using dot notation (e.g., 'basic_info.name')"""
        scheme = self.get_canonical_scheme(scheme_code)
        if not scheme or not scheme.data_model:
            return None
        
        # Parse field path (e.g., "basic_info.name" -> section="basic_info", field="name")
        if '.' in field_path:
            section_name, field_name = field_path.split('.', 1)
        else:
            # Fallback: search all sections
            for section_name, section in scheme.data_model.items():
                if field_path in section.root:
                    return section.root[field_path]
            return None
        
        if section_name in scheme.data_model and field_name in scheme.data_model[section_name].root:
            return scheme.data_model[section_name].root[field_name]
        
        return None
    
    def get_all_field_metadata(self, scheme_code: str) -> Dict[str, FieldDefinition]:
        """Get metadata for all fields in a scheme"""
        scheme = self.get_canonical_scheme(scheme_code)
        if not scheme or not scheme.data_model:
            return {}
        
        all_fields = {}
        for section_name, section in scheme.data_model.items():
            for field_name, field_def in section.root.items():
                field_path = f"{section_name}.{field_name}"
                all_fields[field_path] = field_def
        
        return all_fields
    
    def validate_collected_data(self, scheme_code: str, collected_data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Validate collected data against canonical scheme structure"""
        scheme = self.get_canonical_scheme(scheme_code)
        if not scheme:
            return False, ["Scheme not found"], {}
        
        errors = []
        validated_data = {}
        
        # Validate each collected field
        for field_path, value in collected_data.items():
            field_metadata = self.get_field_metadata(scheme_code, field_path)
            if not field_metadata:
                errors.append(f"Unknown field: {field_path}")
                continue
            
            # Validate field value
            validation_result = self._validate_field_value(field_path, value, field_metadata)
            if not validation_result[0]:
                errors.extend(validation_result[1])
            else:
                validated_data[field_path] = validation_result[2]
        
        # Check for missing required fields
        required_fields = self.get_required_fields(scheme_code)
        missing_fields = [field for field in required_fields if field not in collected_data]
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
        
        return len(errors) == 0, errors, validated_data
    
    def _validate_field_value(self, field_path: str, value: Any, field_def: FieldDefinition) -> Tuple[bool, List[str], Any]:
        """Validate a single field value"""
        errors = []
        
        # Type validation
        if field_def.type == DataType.INTEGER:
            try:
                validated_value = int(value)
            except (ValueError, TypeError):
                errors.append(f"{field_path}: Expected integer, got {type(value).__name__}")
                return False, errors, None
        elif field_def.type == DataType.FLOAT:
            try:
                validated_value = float(value)
            except (ValueError, TypeError):
                errors.append(f"{field_path}: Expected float, got {type(value).__name__}")
                return False, errors, None
        elif field_def.type == DataType.BOOLEAN:
            if not isinstance(value, bool):
                errors.append(f"{field_path}: Expected boolean, got {type(value).__name__}")
                return False, errors, None
            validated_value = value
        elif field_def.type == DataType.ENUM:
            if field_def.values and value not in field_def.values:
                errors.append(f"{field_path}: Expected one of {field_def.values}, got {value}")
                return False, errors, None
            validated_value = value
        else:
            validated_value = value
        
        # Additional validation based on validation type
        if field_def.validation:
            validation_result = self._apply_validation_rules(field_path, validated_value, field_def)
            if not validation_result[0]:
                errors.extend(validation_result[1])
        
        return len(errors) == 0, errors, validated_value
    
    def _apply_validation_rules(self, field_path: str, value: Any, field_def: FieldDefinition) -> Tuple[bool, List[str]]:
        """Apply specific validation rules"""
        errors = []
        
        if field_def.validation == ValidationType.NON_EMPTY_STRING:
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{field_path}: Must be a non-empty string")
        
        elif field_def.validation == ValidationType.POSITIVE_FLOAT:
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"{field_path}: Must be a positive number")
        
        elif field_def.validation == ValidationType.NON_NEGATIVE_FLOAT:
            if not isinstance(value, (int, float)) or value < 0:
                errors.append(f"{field_path}: Must be a non-negative number")
        
        elif field_def.validation == ValidationType.PHONE_FORMAT:
            if not isinstance(value, str) or not self._is_valid_phone(value):
                errors.append(f"{field_path}: Must be a valid phone number")
        
        elif field_def.validation == ValidationType.AADHAAR_FORMAT:
            if not isinstance(value, str) or not self._is_valid_aadhaar(value):
                errors.append(f"{field_path}: Must be a valid Aadhaar number")
        
        elif field_def.validation == ValidationType.IFSC_FORMAT:
            if not isinstance(value, str) or not self._is_valid_ifsc(value):
                errors.append(f"{field_path}: Must be a valid IFSC code")
        
        return len(errors) == 0, errors
    
    def _is_valid_phone(self, phone: str) -> bool:
        """Validate phone number format"""
        import re
        # Basic Indian phone number validation
        pattern = r'^(\+91|91)?[6-9]\d{9}$'
        return bool(re.match(pattern, phone.replace(' ', '')))
    
    def _is_valid_aadhaar(self, aadhaar: str) -> bool:
        """Validate Aadhaar number format"""
        import re
        # Aadhaar is 12 digits
        pattern = r'^\d{12}$'
        return bool(re.match(pattern, aadhaar.replace(' ', '')))
    
    def _is_valid_ifsc(self, ifsc: str) -> bool:
        """Validate IFSC code format"""
        import re
        # IFSC is 11 characters: 4 letters + 7 alphanumeric
        pattern = r'^[A-Z]{4}0[A-Z0-9]{6}$'
        return bool(re.match(pattern, ifsc.upper()))
    
    def build_pydantic_model(self, scheme_code: str) -> Optional[type]:
        """Dynamically build a Pydantic model from canonical scheme"""
        scheme = self.get_canonical_scheme(scheme_code)
        if not scheme or not scheme.data_model:
            return None
        
        # This would require dynamic model creation
        # For now, return None - we'll implement this later
        return None
    
    def get_consent_request_data(self, scheme_code: str) -> Dict[str, Any]:
        """Get data needed for consent request"""
        scheme = self.get_canonical_scheme(scheme_code)
        if not scheme:
            return {}
        
        required_fields = self.get_required_fields(scheme_code)
        
        return {
            "scheme_name": scheme.name,
            "scheme_description": scheme.description,
            "data_purpose": f"To check eligibility for {scheme.name} scheme",
            "data_fields": [self.get_field_metadata(scheme_code, field).description 
                           for field in required_fields 
                           if self.get_field_metadata(scheme_code, field)],
            "data_retention": "Data will be used only for eligibility checking and will not be stored permanently",
            "user_rights": [
                "Right to withdraw consent at any time",
                "Right to know what data is being collected",
                "Right to request deletion of collected data"
            ]
        }
    
    def get_parsing_errors(self) -> List[str]:
        """Get all parsing errors"""
        return self.parsing_errors
    
    def has_errors(self) -> bool:
        """Check if there are any parsing errors"""
        return len(self.parsing_errors) > 0
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get parser health status"""
        return {
            "schemes_loaded": len(self.schemes),
            "has_errors": self.has_errors(),
            "error_count": len(self.parsing_errors),
            "available_schemes": list(self.schemes.keys())
        } 