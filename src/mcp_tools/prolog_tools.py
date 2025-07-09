"""
MCP Tools for Prolog Eligibility System

Provides tools for LLMs to interact with the Prolog-based eligibility checking system.
"""

import json
import logging
import sys
import os
from typing import Dict, Any, List

# Add pipeline path for PM-KISAN checker
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

logger = logging.getLogger(__name__)

class PrologTools:
    """MCP Tools for Prolog eligibility operations"""
    
    def __init__(self, prolog_file_path: str = None):
        self.prolog_file_path = prolog_file_path
        if prolog_file_path is None:
            # Get the absolute path to the prolog file from project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.join(current_dir, "..", "..")
            self.prolog_file_path = os.path.join(project_root, "src", "schemes", "outputs", "pm-kisan", "REFERENCE_prolog_system.pl")
        
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools"""
        return [
            {
                "name": "prolog_check_eligibility",
                "description": "Check PM-KISAN eligibility using Prolog rules for a farmer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "farmer_id": {
                            "type": "string",
                            "description": "Farmer ID to check eligibility for"
                        }
                    },
                    "required": ["farmer_id"]
                }
            },
            {
                "name": "prolog_check_eligibility_with_data",
                "description": "Check PM-KISAN eligibility using Prolog rules with provided farmer data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "farmer_data": {
                            "type": "object",
                            "description": "Complete farmer data to check eligibility"
                        }
                    },
                    "required": ["farmer_data"]
                }
            }
        ]
    
    def prolog_check_eligibility(self, farmer_id: str) -> Dict[str, Any]:
        """Check PM-KISAN eligibility for a farmer by ID"""
        try:
            from pm_kisan_checker import PMKisanChecker
            
            checker = PMKisanChecker(self.prolog_file_path)
            result = checker.check_farmer(farmer_id)
            
            return {
                "success": True,
                "farmer_id": farmer_id,
                "is_eligible": result.get("eligible", False),
                "farmer_name": result.get("farmer_name", "Unknown"),
                "explanation": result.get("explanation", "No explanation available"),
                "facts_generated": result.get("facts_generated", 0),
                "error": result.get("error")
            }
            
        except Exception as e:
            logger.error(f"Error checking eligibility for farmer {farmer_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "farmer_id": farmer_id,
                "message": f"Failed to check eligibility for farmer {farmer_id}"
            }
    
    def prolog_check_eligibility_with_data(self, farmer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check PM-KISAN eligibility using provided farmer data"""
        try:
            from pm_kisan_checker import PMKisanChecker
            
            checker = PMKisanChecker(self.prolog_file_path)
            
            # Extract farmer_id from data or generate one
            farmer_id = farmer_data.get("farmer_id", farmer_data.get("aadhaar_number", "unknown"))
            
            # Check eligibility with the provided data
            is_eligible, explanation = checker.check_eligibility(farmer_id, farmer_data)
            
            return {
                "success": True,
                "farmer_id": farmer_id,
                "is_eligible": is_eligible,
                "explanation": explanation,
                "farmer_name": farmer_data.get("name", "Unknown"),
                "data_provided": True
            }
            
        except Exception as e:
            logger.error(f"Error checking eligibility with data: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to check eligibility with provided data"
            } 