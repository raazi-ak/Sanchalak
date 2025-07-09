"""
Data Processing MCP Tools

Provides tools for LLMs to process and validate data.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import sys
import os

logger = logging.getLogger(__name__)

class DataTools:
    """MCP tools for data processing and validation."""
    
    def __init__(self, lm_studio_url: str = "http://localhost:1234/v1"):
        """Initialize data tools."""
        self.lm_studio_url = lm_studio_url
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of MCP tools for data processing."""
        return [
            {
                "name": "validate_farmer_data",
                "description": "Validate farmer data completeness and quality",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "farmer_data": {
                            "type": "object",
                            "description": "Farmer data to validate"
                        },
                        "scheme": {
                            "type": "string",
                            "description": "Scheme name for validation",
                            "default": "pm_kisan"
                        }
                    },
                    "required": ["farmer_data"]
                }
            },
            {
                "name": "create_prolog_facts",
                "description": "Create Prolog facts from normalized farmer data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "normalized_data": {
                            "type": "object",
                            "description": "Normalized farmer data"
                        }
                    },
                    "required": ["normalized_data"]
                }
            }
        ]
    

    
    def validate_farmer_data(self, farmer_data: Dict[str, Any], scheme: str = "pm_kisan") -> Dict[str, Any]:
        """Validate farmer data completeness and quality."""
        try:
            # Normalize data first
            normalized_data = self.data_normalizer.normalize_farmer_data(farmer_data)
            
            # Get required fields for the scheme
            required_fields = self.data_normalizer.general_required_fields
            
            # Validate required fields
            is_valid, missing_fields = self.data_normalizer.validate_required_fields(
                normalized_data, required_fields
            )
            
            # Check data quality
            quality_issues = []
            
            # Check for null values in important fields
            for field in ["name", "land_size_acres", "state"]:
                if normalized_data.get(field) is None:
                    quality_issues.append(f"Missing {field}")
            
            # Check for invalid values
            if normalized_data.get("land_size_acres") is not None and normalized_data["land_size_acres"] <= 0:
                quality_issues.append("Land size must be greater than 0")
            
            if normalized_data.get("age") is not None and (normalized_data["age"] < 18 or normalized_data["age"] > 120):
                quality_issues.append("Age must be between 18 and 120")
            
            return {
                "success": True,
                "farmer_id": normalized_data.get("farmer_id"),
                "is_valid": is_valid,
                "missing_fields": missing_fields,
                "quality_issues": quality_issues,
                "normalized_data": normalized_data,
                "required_fields": required_fields,
                "message": f"Data validation {'passed' if is_valid else 'failed'}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to validate farmer data"
            }
    
    def create_prolog_facts(self, normalized_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Prolog facts from normalized farmer data."""
        try:
            prolog_facts = self.data_normalizer.create_prolog_facts(normalized_data)
            
            return {
                "success": True,
                "farmer_id": normalized_data.get("farmer_id"),
                "prolog_facts": prolog_facts,
                "fact_count": len(prolog_facts),
                "message": f"Generated {len(prolog_facts)} Prolog facts"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create Prolog facts"
            } 