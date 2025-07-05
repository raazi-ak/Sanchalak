"""
MCP Tools for Canonical Scheme Handling

Provides tools for LLMs to:
- List available schemes
- Get scheme field definitions from canonical YAML
- Request consent for data collection
- Validate collected data using Pydantic models
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import sys
import os

# Import canonical modules from their current location in schemabot
from schemabot.core.scheme.canonical_parser import CanonicalSchemeParser
from schemabot.core.scheme.canonical_models import CanonicalScheme, FieldDefinition, ConsentRequest

logger = logging.getLogger(__name__)

class CanonicalSchemeTools:
    """MCP Tools for canonical scheme operations"""
    
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
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools"""
        return [
            {
                "name": "get_schemes_registry",
                "description": "Get the complete schemes registry showing all supported schemes, their locations, and file structure",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "list_available_schemes",
                "description": "List all available government schemes with basic information",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_scheme_details",
                "description": "Get detailed information about a specific scheme including field definitions",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scheme_code": {
                            "type": "string",
                            "description": "Code of the scheme (e.g., 'PM-KISAN')"
                        }
                    },
                    "required": ["scheme_code"]
                }
            },
            {
                "name": "get_field_definitions",
                "description": "Get field definitions for a scheme to understand what data to collect",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scheme_code": {
                            "type": "string",
                            "description": "Code of the scheme"
                        }
                    },
                    "required": ["scheme_code"]
                }
            },
            {
                "name": "generate_consent_request",
                "description": "Generate a consent request for data collection for a specific scheme",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scheme_code": {
                            "type": "string",
                            "description": "Code of the scheme"
                        }
                    },
                    "required": ["scheme_code"]
                }
            },
            {
                "name": "validate_collected_data",
                "description": "Validate collected data against the scheme's Pydantic model",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scheme_code": {
                            "type": "string",
                            "description": "Code of the scheme"
                        },
                        "collected_data": {
                            "type": "object",
                            "description": "Data collected from the user"
                        }
                    },
                    "required": ["scheme_code", "collected_data"]
                }
            },
            {
                "name": "get_field_prompt_examples",
                "description": "Get examples of how to ask for specific fields based on their definitions",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scheme_code": {
                            "type": "string",
                            "description": "Code of the scheme"
                        },
                        "field_path": {
                            "type": "string",
                            "description": "Field path (e.g., 'basic_info.name')"
                        }
                    },
                    "required": ["scheme_code", "field_path"]
                }
            }
        ]
    
    async def list_available_schemes(self) -> Dict[str, Any]:
        """List all available schemes"""
        await self.initialize()
        
        if not self.loaded:
            return {
                "success": False,
                "error": "Failed to load canonical schemes"
            }
        
        schemes = self.canonical_parser.list_canonical_schemes()
        
        return {
            "success": True,
            "schemes": schemes,
            "count": len(schemes),
            "message": f"Found {len(schemes)} available schemes"
        }
    
    async def get_scheme_details(self, scheme_code: str) -> Dict[str, Any]:
        """Get detailed information about a specific scheme"""
        await self.initialize()
        
        if not self.loaded:
            return {
                "success": False,
                "error": "Failed to load canonical schemes"
            }
        
        scheme = self.canonical_parser.get_canonical_scheme(scheme_code)
        if not scheme:
            return {
                "success": False,
                "error": f"Scheme '{scheme_code}' not found"
            }
        
        # Get field definitions
        field_metadata = self.canonical_parser.get_all_field_metadata(scheme_code)
        required_fields = self.canonical_parser.get_required_fields(scheme_code)
        
        # Convert FieldDefinition objects to dictionaries for JSON serialization
        field_metadata_dict = {}
        for field_path, field_def in field_metadata.items():
            field_metadata_dict[field_path] = {
                "type": field_def.type.value,
                "required": field_def.required,
                "description": field_def.description,
                "validation": field_def.validation.value if field_def.validation else None,
                "values": field_def.values if field_def.type.value == "enum" else None,
                "prolog_fact": field_def.prolog_fact,
                "structure": field_def.structure,
                "prolog_facts": field_def.prolog_facts,
                "computation": field_def.computation
            }
        
        return {
            "success": True,
            "scheme": {
                "code": scheme.code,
                "name": scheme.name,
                "ministry": scheme.ministry,
                "description": scheme.description,
                "launched_on": scheme.launched_on
            },
            "field_metadata": field_metadata_dict,
            "required_fields": required_fields,
            "total_fields": len(field_metadata),
            "required_count": len(required_fields)
        }
    
    async def get_field_definitions(self, scheme_code: str) -> Dict[str, Any]:
        """Get field definitions for data collection"""
        await self.initialize()
        
        if not self.loaded:
            return {
                "success": False,
                "error": "Failed to load canonical schemes"
            }
        
        scheme = self.canonical_parser.get_canonical_scheme(scheme_code)
        if not scheme:
            return {
                "success": False,
                "error": f"Scheme '{scheme_code}' not found"
            }
        
        field_metadata = self.canonical_parser.get_all_field_metadata(scheme_code)
        required_fields = self.canonical_parser.get_required_fields(scheme_code)
        
        # Organize fields by section
        fields_by_section = {}
        for field_path, field_def in field_metadata.items():
            if '.' in field_path:
                section, field_name = field_path.split('.', 1)
            else:
                section = "general"
                field_name = field_path
            
            if section not in fields_by_section:
                fields_by_section[section] = []
            
            fields_by_section[section].append({
                "field_name": field_name,
                "field_path": field_path,
                "type": field_def.type.value,
                "required": field_def.required,
                "description": field_def.description,
                "validation": field_def.validation.value if field_def.validation else None,
                "values": field_def.values if field_def.type.value == "enum" else None
            })
        
        return {
            "success": True,
            "scheme_name": scheme.name,
            "fields_by_section": fields_by_section,
            "required_fields": required_fields,
            "total_fields": len(field_metadata),
            "required_count": len(required_fields)
        }
    
    async def generate_consent_request(self, scheme_code: str) -> Dict[str, Any]:
        """Generate consent request for data collection"""
        await self.initialize()
        
        if not self.loaded:
            return {
                "success": False,
                "error": "Failed to load canonical schemes"
            }
        
        scheme = self.canonical_parser.get_canonical_scheme(scheme_code)
        if not scheme:
            return {
                "success": False,
                "error": f"Scheme '{scheme_code}' not found"
            }
        
        consent_data = self.canonical_parser.get_consent_request_data(scheme_code)
        
        # Generate consent request text
        consent_text = f"""
CONSENT REQUEST FOR {scheme.name.upper()}

Dear User,

I need to collect some information from you to check your eligibility for the {scheme.name} scheme.

PURPOSE: {consent_data['data_purpose']}

INFORMATION I WILL COLLECT:
{chr(10).join([f"• {desc}" for desc in consent_data['data_fields']])}

DATA RETENTION: {consent_data['data_retention']}

YOUR RIGHTS:
{chr(10).join([f"• {right}" for right in consent_data['user_rights']])}

Do you consent to provide this information for eligibility checking?

Please respond with "Yes" or "No".
"""
        
        return {
            "success": True,
            "scheme_name": scheme.name,
            "consent_text": consent_text.strip(),
            "consent_data": consent_data,
            "required_fields_count": len(consent_data['data_fields'])
        }
    
    async def validate_collected_data(self, scheme_code: str, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate collected data against scheme requirements"""
        await self.initialize()
        
        if not self.loaded:
            return {
                "success": False,
                "error": "Failed to load canonical schemes"
            }
        
        # Validate the data
        is_valid, errors, validated_data = self.canonical_parser.validate_collected_data(scheme_code, collected_data)
        
        return {
            "success": True,
            "is_valid": is_valid,
            "errors": errors,
            "validated_data": validated_data,
            "validation_timestamp": datetime.utcnow().isoformat(),
            "field_count": len(collected_data),
            "validated_count": len(validated_data)
        }
    
    async def get_field_prompt_examples(self, scheme_code: str, field_path: str) -> Dict[str, Any]:
        """Get examples of how to ask for a specific field"""
        await self.initialize()
        
        if not self.loaded:
            return {
                "success": False,
                "error": "Failed to load canonical schemes"
            }
        
        field_metadata = self.canonical_parser.get_field_metadata(scheme_code, field_path)
        if not field_metadata:
            return {
                "success": False,
                "error": f"Field '{field_path}' not found in scheme '{scheme_code}'"
            }
        
        # Generate prompt examples based on field type and description
        examples = self._generate_field_prompt_examples(field_path, field_metadata)
        
        return {
            "success": True,
            "field_path": field_path,
            "field_metadata": {
                "type": field_metadata.type.value,
                "required": field_metadata.required,
                "description": field_metadata.description,
                "validation": field_metadata.validation.value if field_metadata.validation else None,
                "values": field_metadata.values if field_metadata.type.value == "enum" else None
            },
            "prompt_examples": examples,
            "suggested_prompt": examples[0] if examples else f"Please provide your {field_path.replace('_', ' ')}"
        }
    
    def _generate_field_prompt_examples(self, field_path: str, field_def: FieldDefinition) -> List[str]:
        """Generate prompt examples for a field"""
        field_name = field_path.split('.')[-1].replace('_', ' ')
        
        examples = []
        
        if field_def.type.value == "string":
            if "name" in field_name.lower():
                examples.append(f"What is your full name?")
                examples.append(f"Please tell me your name.")
            elif "phone" in field_name.lower():
                examples.append(f"What is your mobile number?")
                examples.append(f"Please provide your phone number.")
            elif "address" in field_name.lower():
                examples.append(f"What is your address?")
                examples.append(f"Please provide your residential address.")
            else:
                examples.append(f"Please provide your {field_name}.")
        
        elif field_def.type.value == "integer":
            if "age" in field_name.lower():
                examples.append(f"What is your age?")
                examples.append(f"How old are you?")
            else:
                examples.append(f"Please provide your {field_name} (number only).")
        
        elif field_def.type.value == "float":
            if "land" in field_name.lower() and "size" in field_name.lower():
                examples.append(f"What is the size of your land in acres?")
                examples.append(f"How much land do you own (in acres)?")
            elif "income" in field_name.lower():
                examples.append(f"What is your annual income in rupees?")
                examples.append(f"How much do you earn per year?")
            else:
                examples.append(f"Please provide your {field_name} (number only).")
        
        elif field_def.type.value == "boolean":
            examples.append(f"Do you have {field_name.replace('_', ' ')}? (Yes/No)")
            examples.append(f"Please confirm if you have {field_name.replace('_', ' ')}.")
        
        elif field_def.type.value == "enum":
            if field_def.values:
                options = ", ".join(field_def.values)
                examples.append(f"What is your {field_name}? Options: {options}")
                examples.append(f"Please select your {field_name} from: {options}")
        
        # Add description-based example
        if field_def.description:
            examples.append(f"{field_def.description}")
        
        return examples[:3]  # Return top 3 examples
    
    async def get_schemes_registry(self) -> Dict[str, Any]:
        """Get the complete schemes registry from supported_schemes.yaml"""
        try:
            import yaml
            from pathlib import Path
            
            registry_path = Path("src/schemes/outputs/supported_schemes.yaml")
            
            if not registry_path.exists():
                return {
                    "success": False,
                    "error": f"Schemes registry file not found: {registry_path}"
                }
            
            with open(registry_path, 'r', encoding='utf-8') as file:
                registry_data = yaml.safe_load(file)
            
            if not registry_data:
                return {
                    "success": False,
                    "error": "Empty or invalid schemes registry file"
                }
            
            return {
                "success": True,
                "registry": registry_data,
                "schemes_count": len(registry_data.get("schemes", [])),
                "active_schemes": [
                    scheme["code"] for scheme in registry_data.get("schemes", []) 
                    if scheme.get("status") == "active"
                ],
                "legacy_schemes": [
                    scheme["code"] for scheme in registry_data.get("schemes", []) 
                    if scheme.get("status") == "legacy"
                ],
                "message": "Schemes registry loaded successfully"
            }
            
        except yaml.YAMLError as e:
            return {
                "success": False,
                "error": f"YAML parsing error in schemes registry: {e}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error loading schemes registry: {e}"
            } 