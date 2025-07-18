"""
Enhanced Data Extractor Module

Extracts structured farmer data from transcript text using EFR scheme service
and enhanced YAML prompts for better accuracy and validation.
"""

import json
import logging
import requests
import yaml
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class EnhancedDataExtractor:
    """Extracts structured farmer data using EFR scheme service and enhanced prompts."""
    
    def __init__(self, lm_studio_url: str = "http://localhost:1234/v1", efr_api_url: str = "http://localhost:8001"):
        """
        Initialize the enhanced data extractor.
        
        Args:
            lm_studio_url: URL for LM Studio API (default: localhost:1234)
            efr_api_url: URL for EFR API (default: localhost:8001)
        """
        self.api_url = lm_studio_url.rstrip('/')
        self.efr_api_url = efr_api_url.rstrip('/')
        self.session = requests.Session()
        
    def get_extraction_prompt(self, scheme_name: str = "pm-kisan") -> str:
        """
        Get extraction prompt from EFR scheme service.
        
        Args:
            scheme_name: Name of the scheme
            
        Returns:
            Enhanced extraction prompt from EFR
        """
        try:
            response = self.session.get(f"{self.efr_api_url}/scheme/{scheme_name}/llm_prompts")
            if response.status_code == 200:
                data = response.json()
                return data.get("extraction_prompt", "")
            else:
                logger.error(f"❌ Failed to get extraction prompt: {response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"❌ Failed to get extraction prompt: {str(e)}")
            return ""
    
    def get_scheme_data_model(self, scheme_name: str = "pm-kisan") -> Dict[str, Any]:
        """
        Get scheme data model from EFR service.
        
        Args:
            scheme_name: Name of the scheme
            
        Returns:
            Data model definition from EFR
        """
        try:
            response = self.session.get(f"{self.efr_api_url}/scheme/{scheme_name}/data_model")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Failed to get data model: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"❌ Failed to get data model: {str(e)}")
            return {}
    
    def validate_extracted_data(self, farmer_data: Dict[str, Any], scheme_name: str = "pm-kisan") -> Tuple[bool, List[str]]:
        """
        Validate extracted data using EFR validation service.
        
        Args:
            farmer_data: Extracted farmer data
            scheme_name: Name of the scheme
            
        Returns:
            Tuple of (is_valid, validation_errors)
        """
        try:
            response = self.session.post(
                f"{self.efr_api_url}/scheme/{scheme_name}/validate",
                json=farmer_data
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("valid", False), result.get("errors", [])
            else:
                logger.error(f"❌ Validation failed: {response.status_code}")
                return False, ["Validation service unavailable"]
        except Exception as e:
            logger.error(f"❌ Validation error: {str(e)}")
            return False, [f"Validation error: {str(e)}"]
    
    def check_exclusions(self, farmer_data: Dict[str, Any], scheme_name: str = "pm-kisan") -> Tuple[bool, List[str]]:
        """
        Check exclusions using EFR exclusion service.
        
        Args:
            farmer_data: Farmer data to check
            scheme_name: Name of the scheme
            
        Returns:
            Tuple of (is_eligible, exclusion_reasons)
        """
        try:
            response = self.session.post(
                f"{self.efr_api_url}/scheme/{scheme_name}/check_exclusions",
                json=farmer_data
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("eligible", True), result.get("exclusions", [])
            else:
                logger.error(f"❌ Exclusion check failed: {response.status_code}")
                return True, []
        except Exception as e:
            logger.error(f"❌ Exclusion check error: {str(e)}")
            return True, []

    def _call_lm_studio(self, prompt: str, max_tokens: int = 1500) -> str:
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
        
    def extract_from_transcript(self, transcript_text: str, farmer_id: str, scheme_name: str = "pm-kisan") -> Dict[str, Any]:
        """
        Extract structured farmer data from transcript text using enhanced prompts.
        
        Args:
            transcript_text: Raw transcript text
            farmer_id: Unique identifier for the farmer
            scheme_name: Name of the scheme for extraction
            
        Returns:
            Dictionary containing extracted farmer data with validation
        """
        try:
            logger.info(f"Extracting data for farmer {farmer_id} using scheme {scheme_name}")
            
            # Get enhanced extraction prompt from EFR
            extraction_prompt = self.get_extraction_prompt(scheme_name)
            if not extraction_prompt:
                logger.warning("Using fallback extraction prompt")
                extraction_prompt = self._get_fallback_prompt()
            
            # Create full prompt with transcript
            full_prompt = f"{extraction_prompt}\n\nTranscript: {transcript_text}\n\nJSON Response:"
            
            # Call LM Studio with enhanced prompt
            response_text = self._call_lm_studio(full_prompt, max_tokens=2000)
            
            # Parse JSON response
            try:
                extracted_data = json.loads(response_text.strip())
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse JSON response: {str(e)}")
                logger.error(f"Response text: {response_text}")
                extracted_data = {}
            
            # Validate extracted data using EFR
            is_valid, validation_errors = self.validate_extracted_data(extracted_data, scheme_name)
            
            # Check exclusions
            is_eligible, exclusion_reasons = self.check_exclusions(extracted_data, scheme_name)
            
            # Add metadata
            extraction_metadata = {
                "method": "enhanced_lm_studio_efr",
                "scheme_name": scheme_name,
                "validation_status": "valid" if is_valid else "invalid",
                "validation_errors": validation_errors,
                "eligibility_status": "eligible" if is_eligible else "excluded",
                "exclusion_reasons": exclusion_reasons,
                "entities_extracted": list(extracted_data.keys()) if extracted_data else [],
                "processing_time": None,
                "extracted_at": datetime.utcnow().isoformat(),
                "raw_response": response_text,
                "prompt_source": "efr_enhanced_yaml"
            }
            
            # Create the farmer data structure
            farmer_data = {
                "farmer_id": farmer_id,
                "name": extracted_data.get("name", "Unknown"),
                "extraction_metadata": extraction_metadata,
                "pipeline_metadata": {
                    "task_id": f"enhanced_extraction_{farmer_id}_{int(datetime.utcnow().timestamp())}",
                    "processed_at": datetime.utcnow().isoformat(),
                    "transcribed_text": transcript_text,
                    "scheme_name": scheme_name
                },
                "status": "completed" if is_valid else "validation_failed"
            }
            
            # Add all extracted fields
            for field, value in extracted_data.items():
                if field != "name":  # Already set above
                    farmer_data[field] = value
            
            # Build location string if available
            location_parts = []
            for loc_field in ["village", "district", "state"]:
                if farmer_data.get(loc_field):
                    location_parts.append(farmer_data[loc_field])
            
            farmer_data["location"] = ", ".join(location_parts) if location_parts else "Not provided"
            
            # Add validation summary
            farmer_data["validation_summary"] = {
                "valid": is_valid,
                "errors": validation_errors,
                "eligible": is_eligible,
                "exclusions": exclusion_reasons
            }
            
            logger.info(f"✅ Successfully extracted data for farmer {farmer_id} (valid: {is_valid}, eligible: {is_eligible})")
            return farmer_data
            
        except Exception as e:
            logger.error(f"❌ Failed to extract data for farmer {farmer_id}: {str(e)}")
            return {
                "farmer_id": farmer_id,
                "name": "Unknown",
                "status": "failed",
                "error": str(e),
                "extraction_metadata": {
                    "method": "enhanced_lm_studio_efr",
                    "scheme_name": scheme_name,
                    "error": str(e),
                    "extracted_at": datetime.utcnow().isoformat()
                },
                "pipeline_metadata": {
                    "task_id": f"enhanced_extraction_{farmer_id}_{int(datetime.utcnow().timestamp())}",
                    "processed_at": datetime.utcnow().isoformat(),
                    "transcribed_text": transcript_text,
                    "scheme_name": scheme_name
                }
            }
    
    def _get_fallback_prompt(self) -> str:
        """Get fallback extraction prompt if EFR is unavailable."""
        return """
Extract structured farmer information from the following transcript. Return ONLY a valid JSON object with the following fields:

{
    "name": "farmer's name",
    "age": "age in years (number)",
    "gender": "male/female/other",
    "phone_number": "phone number",
    "family_members": [
        {
            "relation": "wife/husband/son/daughter/father/mother/brother/sister",
            "name": "family member name",
            "age": "age in years (number)"
        }
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
    "has_kisan_credit_card": "true/false",
    "aadhaar_linked": "true/false",
    "category": "general/sc/st/obc/unknown",
    "is_constitutional_post_holder": "true/false",
    "is_political_office_holder": "true/false",
    "is_government_employee": "true/false",
    "government_post": "post name or null",
    "monthly_pension": "pension amount or null",
    "is_income_tax_payer": "true/false",
    "is_professional": "true/false",
    "is_nri": "true/false"
}

For family_members, extract each family member mentioned with their relation, name, and age.
If a field is not mentioned in the transcript, use null for that field.
"""
    
    def extract_from_file(self, file_path: str, farmer_id: str, scheme_name: str = "pm-kisan") -> Dict[str, Any]:
        """
        Extract data from a transcript file using enhanced prompts.
        
        Args:
            file_path: Path to the transcript text file
            farmer_id: Unique identifier for the farmer
            scheme_name: Name of the scheme for extraction
            
        Returns:
            Dictionary containing extracted farmer data
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                transcript_text = f.read().strip()
            
            return self.extract_from_transcript(transcript_text, farmer_id, scheme_name)
            
        except Exception as e:
            logger.error(f"❌ Failed to read file {file_path}: {str(e)}")
            return {
                "farmer_id": farmer_id,
                "name": "Unknown",
                "status": "failed",
                "error": f"File read error: {str(e)}"
            }
    
    def batch_extract(self, transcripts: List[Tuple[str, str]], scheme_name: str = "pm-kisan") -> List[Dict[str, Any]]:
        """
        Extract data from multiple transcripts in batch.
        
        Args:
            transcripts: List of (transcript_text, farmer_id) tuples
            scheme_name: Name of the scheme for extraction
            
        Returns:
            List of extraction results
        """
        results = []
        
        logger.info(f"Starting batch extraction for {len(transcripts)} transcripts")
        
        for i, (transcript_text, farmer_id) in enumerate(transcripts, 1):
            logger.info(f"Processing transcript {i}/{len(transcripts)} for farmer {farmer_id}")
            result = self.extract_from_transcript(transcript_text, farmer_id, scheme_name)
            results.append(result)
        
        # Generate batch summary
        total = len(results)
        successful = len([r for r in results if r.get("status") == "completed"])
        valid = len([r for r in results if r.get("validation_summary", {}).get("valid", False)])
        eligible = len([r for r in results if r.get("validation_summary", {}).get("eligible", False)])
        
        logger.info(f"✅ Batch extraction completed:")
        logger.info(f"   Total: {total}")
        logger.info(f"   Successful: {successful}")
        logger.info(f"   Valid: {valid}")
        logger.info(f"   Eligible: {eligible}")
        
        return results

# Backward compatibility alias
DataExtractor = EnhancedDataExtractor