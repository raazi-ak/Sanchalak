import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import structlog
from datetime import datetime

from src.schemabot.core.scheme.models import Scheme, SchemeRegistry, GovernmentScheme

logger = structlog.get_logger(__name__)

class SchemeParsingError(Exception):
    """Custom exception for scheme parsing errors"""
    pass

class SchemeParser:
    def __init__(self, schemes_directory: str = "schemas", registry_file: str = "schemas/schemes_registry.yaml"):
        self.schemes_directory = Path(schemes_directory)
        self.registry_file = Path(registry_file)
        self.schemes: Dict[str, GovernmentScheme] = {}
        self.validation_errors: Dict[str, List[str]] = {}
        self.parsing_errors: List[str] = []
        
    async def load_schemes(self) -> bool:
        """Load and validate schemes from YAML files"""
        try:
            # Check if registry file exists
            if not self.registry_file.exists():
                logger.warning(f"Registry file not found: {self.registry_file}")
                return False
            
            # Load registry
            with open(self.registry_file, 'r', encoding='utf-8') as file:
                registry_data = yaml.safe_load(file)
            
            if not registry_data or 'schemes' not in registry_data:
                logger.error("Invalid registry structure: 'schemes' key not found")
                return False
            
            schemes_loaded = 0
            for scheme_code, scheme_info in registry_data['schemes'].items():
                try:
                    scheme_file = self.schemes_directory / scheme_info.get('file', f'{scheme_code}.yaml')
                    
                    if scheme_file.exists():
                        scheme = await self.parse_scheme(str(scheme_file))
                        self.schemes[scheme.code] = scheme
                        schemes_loaded += 1
                        logger.debug(f"Successfully loaded scheme: {scheme.code}")
                    else:
                        logger.warning(f"Scheme file not found: {scheme_file}")
                        
                except Exception as e:
                    error_msg = f"Failed to load scheme {scheme_code}: {e}"
                    logger.error(error_msg)
                    self.parsing_errors.append(error_msg)
            
            logger.info(f"Successfully loaded {schemes_loaded} schemes")
            return schemes_loaded > 0
            
        except yaml.YAMLError as e:
            error_msg = f"YAML parsing error in registry: {e}"
            self.parsing_errors.append(error_msg)
            logger.error(error_msg)
            return False
            
        except Exception as e:
            error_msg = f"Unexpected error loading schemes: {e}"
            self.parsing_errors.append(error_msg)
            logger.error(error_msg)
            return False
    
    async def parse_scheme(self, file_path: str) -> GovernmentScheme:
        """Parse a single scheme file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                scheme_data = yaml.safe_load(file)
            
            if not scheme_data:
                raise SchemeParsingError(f"Empty scheme file: {file_path}")
            
            # If the YAML contains a 'schemes' array, take the first one
            if 'schemes' in scheme_data and isinstance(scheme_data['schemes'], list):
                if len(scheme_data['schemes']) > 0:
                    scheme_data = scheme_data['schemes'][0]
                else:
                    raise SchemeParsingError(f"No schemes found in file: {file_path}")
            
            # Validate and create scheme object
            scheme = GovernmentScheme(**scheme_data)
            return scheme
            
        except yaml.YAMLError as e:
            raise SchemeParsingError(f"YAML parsing error in {file_path}: {e}")
        except Exception as e:
            raise SchemeParsingError(f"Error parsing scheme {file_path}: {e}")
    
    async def parse_scheme_data(self, data: Dict[str, Any]) -> GovernmentScheme:
        """Parse scheme from data dictionary"""
        try:
            return GovernmentScheme(**data)
        except Exception as e:
            raise SchemeParsingError(f"Error parsing scheme data: {e}")
    
    def get_scheme(self, code: str) -> Optional[GovernmentScheme]:
        """Get scheme by code"""
        return self.schemes.get(code)
    
    def list_schemes(self) -> List[Dict[str, Any]]:
        """List all available schemes with basic info"""
        return [
            {
                "code": scheme.code,
                "name": scheme.name,
                "ministry": scheme.ministry,
                "category": scheme.metadata.category,
                "status": scheme.metadata.status,
                "description": scheme.description
            }
            for scheme in self.schemes.values()
        ]
    
    def get_required_fields(self, code: str) -> List[str]:
        """Get all fields required for eligibility check"""
        scheme = self.get_scheme(code)
        if not scheme:
            return []
        
        return scheme.eligibility.required_criteria
    
    def get_field_metadata(self, scheme_code: str, field_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific field"""
        scheme = self.get_scheme(scheme_code)
        if not scheme:
            return None
        
        for rule in scheme.eligibility.rules:
            if rule.field == field_name:
                return {
                    "field": rule.field,
                    "data_type": rule.data_type.value,
                    "description": rule.description,
                    "operator": rule.operator.value,
                    "expected_value": rule.value
                }
        
        return None
    
    def validate_scheme_data(self, scheme_code: str) -> Dict[str, Any]:
        """Validate scheme data integrity"""
        scheme = self.get_scheme(scheme_code)
        if not scheme:
            return {"valid": False, "errors": ["Scheme not found"]}
        
        errors = []
        warnings = []
        
        # Check for duplicate rule IDs
        rule_ids = [rule.rule_id for rule in scheme.eligibility.rules]
        if len(rule_ids) != len(set(rule_ids)):
            errors.append("Duplicate rule IDs found")
        
        # Check for missing required fields in rules
        required_fields = set(scheme.eligibility.required_criteria)
        rule_fields = set(rule.field for rule in scheme.eligibility.rules)
        missing_rules = required_fields - rule_fields
        
        if missing_rules:
            warnings.append(f"Required criteria without rules: {missing_rules}")
        
        # Validate benefit amounts
        for benefit in scheme.benefits:
            if benefit.amount is not None and benefit.amount < 0:
                errors.append(f"Negative benefit amount: {benefit.type}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def reload_schemes(self) -> bool:
        """Reload schemes from files"""
        try:
            old_count = len(self.schemes)
            self.schemes.clear()
            self.validation_errors.clear()
            self.parsing_errors.clear()
            
            success = await self.load_schemes()
            
            logger.info(f"Reloaded schemes: {old_count} -> {len(self.schemes)}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to reload schemes: {e}")
            return False
    
    def get_parsing_errors(self) -> List[str]:
        """Get list of parsing errors"""
        return self.parsing_errors.copy()
    
    def has_errors(self) -> bool:
        """Check if there were any parsing errors"""
        return len(self.parsing_errors) > 0 or len(self.validation_errors) > 0
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the parser"""
        return {
            "schemes_loaded": len(self.schemes),
            "parsing_errors": len(self.parsing_errors),
            "validation_errors": len(self.validation_errors),
            "is_healthy": not self.has_errors(),
            "registry_file_exists": self.registry_file.exists()
        }