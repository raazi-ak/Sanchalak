"""
Canonical Integration for Schemabot

This module integrates our canonical YAML system with schemabot's conversation engine.
It provides the bridge between schemabot's LLM infrastructure and our canonical data.
"""

import sys
import os
from typing import Dict, Any, List, Optional, Tuple
import logging

# Add path to our canonical modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'core', 'schemes'))

try:
    from canonical_parser import CanonicalSchemeParser
    from canonical_models import CanonicalScheme, FieldDefinition
except ImportError:
    # Fallback to absolute imports
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from core.schemes.canonical_parser import CanonicalSchemeParser
    from core.schemes.canonical_models import CanonicalScheme, FieldDefinition

logger = logging.getLogger(__name__)

class CanonicalIntegration:
    """Integrates canonical YAML with schemabot's conversation system"""
    
    def __init__(self, canonical_schemes_directory: str = "src/schemes/outputs"):
        self.canonical_parser = CanonicalSchemeParser(canonical_schemes_directory)
        self.loaded = False
        
    async def initialize(self):
        """Initialize by loading canonical schemes"""
        if not self.loaded:
            success = await self.canonical_parser.load_canonical_schemes()
            self.loaded = success
            if not success:
                logger.error("Failed to load canonical schemes")
    
    def get_canonical_scheme(self, scheme_code: str) -> Optional[CanonicalScheme]:
        """Get canonical scheme by code"""
        return self.canonical_parser.get_canonical_scheme(scheme_code)
    
    def get_required_fields(self, scheme_code: str) -> List[str]:
        """Get required fields in flat format for schemabot compatibility"""
        required_fields = self.canonical_parser.get_required_fields(scheme_code)
        # Convert from "section.field" format to flat field names
        flat_fields = []
        for field_path in required_fields:
            if '.' in field_path:
                section, field = field_path.split('.', 1)
                # Use field name as key for schemabot compatibility
                flat_fields.append(field)
            else:
                flat_fields.append(field_path)
        return flat_fields
    
    def get_field_metadata(self, scheme_code: str, field_name: str) -> Optional[Dict[str, Any]]:
        """Get field metadata in schemabot-compatible format"""
        # Try to find field in any section
        all_metadata = self.canonical_parser.get_all_field_metadata(scheme_code)
        
        for field_path, field_def in all_metadata.items():
            if '.' in field_path:
                section, field = field_path.split('.', 1)
                if field == field_name:
                    return {
                        "field_name": field_name,
                        "description": field_def.description,
                        "data_type": field_def.type.value,
                        "required": field_def.required,
                        "validation": field_def.validation.value if field_def.validation else None,
                        "values": field_def.values if field_def.type.value == "enum" else None
                    }
            elif field_path == field_name:
                return {
                    "field_name": field_name,
                    "description": field_def.description,
                    "data_type": field_def.type.value,
                    "required": field_def.required,
                    "validation": field_def.validation.value if field_def.validation else None,
                    "values": field_def.values if field_def.type.value == "enum" else None
                }
        
        return None
    
    def validate_collected_data(self, scheme_code: str, collected_data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Validate collected data using canonical Pydantic models"""
        return self.canonical_parser.validate_collected_data(scheme_code, collected_data)
    
    def map_canonical_to_schemabot_format(self, scheme_code: str, canonical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map canonical nested data to schemabot's flat format"""
        # This would flatten nested canonical data to schemabot's flat structure
        # For now, return as-is since schemabot expects flat data
        return canonical_data
    
    def map_schemabot_to_canonical_format(self, scheme_code: str, schemabot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map schemabot's flat data to canonical nested format"""
        # This would convert flat schemabot data to canonical nested structure
        # For now, return as-is since we're working with flat data
        return schemabot_data
    
    def get_field_prompt_examples(self, scheme_code: str, field_name: str) -> List[str]:
        """Get prompt examples for a field based on canonical definitions"""
        field_metadata = self.get_field_metadata(scheme_code, field_name)
        if not field_metadata:
            return []
        
        examples = []
        data_type = field_metadata.get("data_type")
        description = field_metadata.get("description", "")
        
        if data_type == "integer":
            if "age" in field_name.lower():
                examples.extend([
                    "I am 35 years old",
                    "My age is 45",
                    "35"
                ])
            elif "income" in field_name.lower():
                examples.extend([
                    "My annual income is Rs. 50,000",
                    "I earn 50000 rupees per year",
                    "Rs. 50,000"
                ])
        elif data_type == "float":
            if "land" in field_name.lower():
                examples.extend([
                    "I have 2.5 acres of land",
                    "My land size is 1 hectare",
                    "2.5 acres"
                ])
        elif data_type == "enum":
            values = field_metadata.get("values", [])
            for value in values[:3]:  # Show first 3 examples
                examples.append(f"I am {value}")
        
        # Add generic examples
        examples.append(f"Please provide your {description.lower()}")
        
        return examples
    
    def get_scheme_info_for_prompts(self, scheme_code: str) -> Dict[str, Any]:
        """Get scheme information formatted for schemabot prompts"""
        scheme = self.get_canonical_scheme(scheme_code)
        if not scheme:
            return {}
        
        return {
            "scheme_name": scheme.name,
            "ministry": scheme.ministry,
            "description": scheme.description,
            "launched_on": scheme.launched_on,
            "total_fields": sum(len(section.root) for section in scheme.data_model.values()) if scheme.data_model else 0,
            "required_fields_count": len(self.get_required_fields(scheme_code))
        } 