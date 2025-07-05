"""
Data Extractor Module

Extracts structured farmer data from transcript text using LM Studio API directly.
"""

import json
import logging
import requests
import yaml
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class DataExtractor:
    """Extracts structured farmer data from transcript text using LM Studio."""
    
    def __init__(self, lm_studio_url: str = "http://localhost:1234/v1"):
        """
        Initialize the data extractor with LM Studio.
        
        Args:
            lm_studio_url: URL for LM Studio API (default: localhost:1234)
        """
        self.api_url = lm_studio_url.rstrip('/')
        self.session = requests.Session()
        
    def load_canonical_exclusions(self, canonical_yaml_path: str) -> Dict[str, Any]:
        """
        Load exclusions from canonical YAML file.
        
        Args:
            canonical_yaml_path: Path to canonical YAML file
            
        Returns:
            Dictionary containing exclusions configuration
        """
        try:
            with open(canonical_yaml_path, 'r', encoding='utf-8') as f:
                canonical_data = yaml.safe_load(f)
            
            # Extract exclusions section
            exclusions = canonical_data.get('exclusions', {})
            logger.info(f"✅ Loaded {len(exclusions.get('rules', []))} exclusions from canonical YAML")
            return exclusions
            
        except Exception as e:
            logger.error(f"❌ Failed to load canonical exclusions: {str(e)}")
            return {"rules": []}
    
    def check_exclusions(self, farmer_data: Dict[str, Any], exclusions: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Check if farmer is excluded from scheme eligibility.
        
        Args:
            farmer_data: Farmer data dictionary
            exclusions: Exclusions configuration from canonical YAML
            
        Returns:
            Tuple of (is_eligible, list_of_exclusion_reasons)
        """
        exclusion_reasons = []
        rules = exclusions.get('rules', [])
        
        for rule in rules:
            rule_name = rule.get('name', 'Unknown')
            rule_description = rule.get('description', 'No description')
            required = rule.get('required', True)
            conditions = rule.get('conditions', [])
            
            # Check each condition in the rule
            rule_triggered = False
            for condition in conditions:
                field = condition.get('field')
                operator = condition.get('operator', 'equals')
                value = condition.get('value')
                
                if field not in farmer_data:
                    if required:
                        exclusion_reasons.append(f"Missing required field '{field}' for rule '{rule_name}': {rule_description}")
                        rule_triggered = True
                    continue
                
                farmer_value = farmer_data[field]
                
                # Apply operator
                if operator == 'equals':
                    if farmer_value == value:
                        exclusion_reasons.append(f"Rule '{rule_name}' triggered: {rule_description}")
                        rule_triggered = True
                elif operator == 'not_equals':
                    if farmer_value != value:
                        exclusion_reasons.append(f"Rule '{rule_name}' triggered: {rule_description}")
                        rule_triggered = True
                elif operator == 'greater_than':
                    if isinstance(farmer_value, (int, float)) and farmer_value > value:
                        exclusion_reasons.append(f"Rule '{rule_name}' triggered: {rule_description}")
                        rule_triggered = True
                elif operator == 'less_than':
                    if isinstance(farmer_value, (int, float)) and farmer_value < value:
                        exclusion_reasons.append(f"Rule '{rule_name}' triggered: {rule_description}")
                        rule_triggered = True
                elif operator == 'in':
                    if farmer_value in value:
                        exclusion_reasons.append(f"Rule '{rule_name}' triggered: {rule_description}")
                        rule_triggered = True
                elif operator == 'not_in':
                    if farmer_value not in value:
                        exclusion_reasons.append(f"Rule '{rule_name}' triggered: {rule_description}")
                        rule_triggered = True
            
            # If any condition in a required rule is triggered, farmer is excluded
            if rule_triggered and required:
                return False, exclusion_reasons
        
        return True, exclusion_reasons

    def _call_lm_studio(self, prompt: str, max_tokens: int = 1000) -> str:
        """
        Call LM Studio API to get response.
        
        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens for response
            
        Returns:
            LLM response text
        """
        try:
            payload = {
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": max_tokens,
                "stream": False
            }
            
            response = self.session.post(
                f"{self.api_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"❌ LM Studio API error: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Failed to call LM Studio: {str(e)}")
            return ""
        
    def extract_from_transcript(self, transcript_text: str, farmer_id: str) -> Dict[str, Any]:
        """
        Extract structured farmer data from transcript text using LM Studio.
        
        Args:
            transcript_text: Raw transcript text
            farmer_id: Unique identifier for the farmer
            
        Returns:
            Dictionary containing extracted farmer data
        """
        try:
            logger.info(f"Extracting data for farmer {farmer_id}")
            
            # Create extraction prompt
            prompt = f"""
Extract structured farmer information from the following transcript. Return ONLY a valid JSON object with the following fields:

{{
    "name": "farmer's name",
    "age": "age in years (number)",
    "gender": "male/female/other",
    "phone_number": "phone number",
    "family_members": [
        {{
            "relation": "wife/husband/son/daughter/father/mother/brother/sister",
            "name": "family member name",
            "age": "age in years (number)"
        }}
    ],
    "state": "state name",
    "district": "district name", 
    "village": "village name",
    "pincode": "pincode",
    "land_size_acres": "land size in acres (number)",
    "land_ownership": "owned/leased/sharecropping/joint/unknown",
    "crops": ["list", "of", "crops"],
    "farming_equipment": ["list", "of", "equipment"],
    "irrigation_type": "rain_fed/canal/borewell/well/drip/sprinkler/tube_well/surface/flood/unknown",
    "annual_income": "annual income in rupees (number)",
    "bank_account": "true/false",
    "has_kisan_credit_card": "true/false"
}}

For family_members, extract each family member mentioned with their relation, name, and age.
If a field is not mentioned in the transcript, use null for that field.

Transcript: {transcript_text}

JSON Response:
"""
            
            # Call LM Studio
            response_text = self._call_lm_studio(prompt, max_tokens=1500)
            
            # Parse JSON response
            try:
                extracted_data = json.loads(response_text.strip())
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse JSON response: {str(e)}")
                logger.error(f"Response text: {response_text}")
                extracted_data = {}
            
            # Add metadata
            extraction_metadata = {
                "method": "lm_studio_llm",
                "confidence_scores": {},  # Could be enhanced with confidence scoring
                "entities_extracted": list(extracted_data.keys()) if extracted_data else [],
                "processing_time": None,
                "extracted_at": datetime.utcnow().isoformat(),
                "raw_response": response_text
            }
            
            # Create the farmer data structure
            farmer_data = {
                "farmer_id": farmer_id,
                "name": extracted_data.get("name", "Unknown"),
                "extraction_metadata": extraction_metadata,
                "pipeline_metadata": {
                    "task_id": f"extraction_{farmer_id}_{int(datetime.utcnow().timestamp())}",
                    "processed_at": datetime.utcnow().isoformat(),
                    "transcribed_text": transcript_text
                },
                "status": "completed"
            }
            
            # Add extracted fields if they exist
            if "age" in extracted_data:
                farmer_data["age"] = extracted_data["age"]
            if "gender" in extracted_data:
                farmer_data["gender"] = extracted_data["gender"]
            if "phone_number" in extracted_data:
                farmer_data["phone_number"] = extracted_data["phone_number"]
                farmer_data["contact"] = extracted_data["phone_number"]
            if "family_size" in extracted_data:
                farmer_data["family_size"] = extracted_data["family_size"]
            if "family_members" in extracted_data:
                farmer_data["family_members"] = extracted_data["family_members"]
            if "state" in extracted_data:
                farmer_data["state"] = extracted_data["state"]
            if "district" in extracted_data:
                farmer_data["district"] = extracted_data["district"]
            if "village" in extracted_data:
                farmer_data["village"] = extracted_data["village"]
            if "pincode" in extracted_data:
                farmer_data["pincode"] = extracted_data["pincode"]
            if "land_size_acres" in extracted_data:
                farmer_data["land_size_acres"] = extracted_data["land_size_acres"]
                farmer_data["land_size"] = extracted_data["land_size_acres"]
            if "land_ownership" in extracted_data:
                farmer_data["land_ownership"] = extracted_data["land_ownership"]
            if "crops" in extracted_data:
                farmer_data["crops"] = extracted_data["crops"]
            if "farming_equipment" in extracted_data:
                farmer_data["farming_equipment"] = extracted_data["farming_equipment"]
            if "irrigation_type" in extracted_data:
                farmer_data["irrigation_type"] = extracted_data["irrigation_type"]
            if "annual_income" in extracted_data:
                farmer_data["annual_income"] = extracted_data["annual_income"]
            if "bank_account" in extracted_data:
                farmer_data["bank_account"] = extracted_data["bank_account"]
            if "has_kisan_credit_card" in extracted_data:
                farmer_data["has_kisan_credit_card"] = extracted_data["has_kisan_credit_card"]
            
            # Build location string
            location_parts = []
            if farmer_data.get("village"):
                location_parts.append(farmer_data["village"])
            if farmer_data.get("district"):
                location_parts.append(farmer_data["district"])
            if farmer_data.get("state"):
                location_parts.append(farmer_data["state"])
            
            farmer_data["location"] = ", ".join(location_parts) if location_parts else "Not provided"
            
            logger.info(f"✅ Successfully extracted data for farmer {farmer_id}")
            return farmer_data
            
        except Exception as e:
            logger.error(f"❌ Failed to extract data for farmer {farmer_id}: {str(e)}")
            return {
                "farmer_id": farmer_id,
                "name": "Unknown",
                "status": "failed",
                "error": str(e),
                "extraction_metadata": {
                    "method": "ollama_llm",
                    "error": str(e),
                    "extracted_at": datetime.utcnow().isoformat()
                },
                "pipeline_metadata": {
                    "task_id": f"extraction_{farmer_id}_{int(datetime.utcnow().timestamp())}",
                    "processed_at": datetime.utcnow().isoformat(),
                    "transcribed_text": transcript_text
                }
            }
    
    def extract_from_file(self, file_path: str, farmer_id: str) -> Dict[str, Any]:
        """
        Extract data from a transcript file.
        
        Args:
            file_path: Path to the transcript text file
            farmer_id: Unique identifier for the farmer
            
        Returns:
            Dictionary containing extracted farmer data
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                transcript_text = f.read().strip()
            
            return self.extract_from_transcript(transcript_text, farmer_id)
            
        except Exception as e:
            logger.error(f"❌ Failed to read file {file_path}: {str(e)}")
            return {
                "farmer_id": farmer_id,
                "name": "Unknown",
                "status": "failed",
                "error": f"File read error: {str(e)}"
            }