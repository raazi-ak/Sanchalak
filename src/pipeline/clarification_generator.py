"""
Clarification Generator for MCP Tools

Provides functionality to generate clarification questions for missing farmer data.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ClarificationGenerator:
    """Generate clarification questions for missing farmer data."""
    
    def __init__(self, lm_studio_url: str = "http://localhost:1234/v1"):
        """Initialize clarification generator."""
        self.lm_studio_url = lm_studio_url
        
    def identify_missing_data(self, farmer_data: Dict[str, Any], required_fields: List[str]) -> List[str]:
        """Identify missing required fields in farmer data."""
        missing_fields = []
        for field in required_fields:
            if field not in farmer_data or farmer_data[field] is None or farmer_data[field] == "":
                missing_fields.append(field)
        return missing_fields
    
    def generate_clarification_question(self, field: str, context: Dict[str, Any] = None) -> str:
        """Generate a clarification question for a specific field."""
        questions = {
            "name": "What is your full name?",
            "age": "What is your age?",
            "land_owner": "Do you own agricultural land?",
            "land_size_acres": "What is the size of your agricultural land in acres?",
            "aadhaar_linked": "Is your Aadhaar number linked to your bank account?",
            "bank_account": "Do you have a bank account?",
            "state": "Which state do you live in?",
            "district": "Which district do you live in?",
            "village": "Which village do you live in?",
            "phone_number": "What is your phone number?",
            "aadhaar_number": "What is your Aadhaar number?",
            "account_number": "What is your bank account number?",
            "ifsc_code": "What is your bank's IFSC code?"
        }
        
        return questions.get(field, f"Please provide information about {field}")
    
    def validate_answer(self, field: str, answer: str) -> Dict[str, Any]:
        """Validate an answer for a specific field."""
        # Simple validation logic
        is_valid = True
        error_message = None
        
        if field == "age":
            try:
                age = int(answer)
                if age < 18 or age > 120:
                    is_valid = False
                    error_message = "Age must be between 18 and 120"
            except ValueError:
                is_valid = False
                error_message = "Age must be a number"
        
        elif field == "land_size_acres":
            try:
                size = float(answer)
                if size < 0:
                    is_valid = False
                    error_message = "Land size cannot be negative"
            except ValueError:
                is_valid = False
                error_message = "Land size must be a number"
        
        elif field == "phone_number":
            if not answer.isdigit() or len(answer) != 10:
                is_valid = False
                error_message = "Phone number must be 10 digits"
        
        elif field == "aadhaar_number":
            if not answer.isdigit() or len(answer) != 12:
                is_valid = False
                error_message = "Aadhaar number must be 12 digits"
        
        return {
            "is_valid": is_valid,
            "error_message": error_message,
            "normalized_value": answer.strip() if is_valid else None
        } 