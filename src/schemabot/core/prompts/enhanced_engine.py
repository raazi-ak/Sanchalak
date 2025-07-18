"""
Enhanced Prompt Engine for Schemabot

This module provides an enhanced dynamic prompt engine that uses LLM directives
and extraction prompts from the enhanced canonical YAML files via EFR API.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import asyncio
import json
import re
import httpx

from src.schemabot.api.models.conversation import ConversationContext, MessageRole, ConversationStage
from .templates import PromptBuilder
from ..eligibility.checker import EligibilityChecker

logger = logging.getLogger(__name__)

class EnhancedPromptEngine:
    """
    Enhanced dynamic prompt engine that uses the scheme server as source of truth.
    """
    
    def __init__(self, scheme_server_url: str = "http://localhost:8002"):
        """
        Initialize enhanced prompt engine.
        Args:
            scheme_server_url: Base URL for scheme server API
        """
        self.scheme_server_url = scheme_server_url.rstrip('/')
        self.prompt_builder = PromptBuilder()
        self.eligibility_checker = EligibilityChecker()
        self.scheme_cache: Dict[str, Dict[str, Any]] = {}
        self.data_model_cache: Dict[str, Dict[str, Any]] = {}
        self.prompts_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_expiry = 3600  # 1 hour
        self.cache_timestamps: Dict[str, float] = {}

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self.cache_timestamps:
            return False
        
        import time
        return (time.time() - self.cache_timestamps[cache_key]) < self.cache_expiry
        
    async def _get_cached_scheme_data(self, scheme_code: str) -> Optional[Dict[str, Any]]:
        """Get scheme data from cache or API."""
        cache_key = f"scheme_{scheme_code}"
        
        if self._is_cache_valid(cache_key) and cache_key in self.scheme_cache:
            logger.info(f"Using cached scheme data for {scheme_code}")
            return self.scheme_cache[cache_key]
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.scheme_server_url}/schemes/{scheme_code}")
                if resp.status_code == 200:
                    scheme_data = resp.json().get("data", {})
                    import time
                    self.scheme_cache[cache_key] = scheme_data
                    self.cache_timestamps[cache_key] = time.time()
                    logger.info(f"Cached scheme data for {scheme_code}")
                    return scheme_data
                else:
                    logger.error(f"Failed to fetch scheme data: {resp.status_code} {resp.text}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching scheme data for {scheme_code}: {e}")
            return None
            
    async def _get_cached_data_model(self, scheme_code: str) -> Optional[Dict[str, Any]]:
        """Get data model from cache or API."""
        cache_key = f"data_model_{scheme_code}"
        
        if self._is_cache_valid(cache_key) and cache_key in self.data_model_cache:
            logger.info(f"Using cached data model for {scheme_code}")
            return self.data_model_cache[cache_key]
        
        try:
            scheme_data = await self._get_cached_scheme_data(scheme_code)
            if scheme_data and "data_model" in scheme_data:
                import time
                self.data_model_cache[cache_key] = scheme_data["data_model"]
                self.cache_timestamps[cache_key] = time.time()
                logger.info(f"Cached data model for {scheme_code}")
                return scheme_data["data_model"]
            else:
                logger.error(f"No data_model found in scheme data for {scheme_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching data model for {scheme_code}: {e}")
            return None
        
    async def generate_initial_prompt(self, scheme_code: str) -> Tuple[str, ConversationContext]:
        """Generate the initial greeting prompt using EFR scheme data."""
        try:
            # Get scheme data from cache or EFR
            scheme_data = await self._get_cached_scheme_data(scheme_code)
            if not scheme_data:
                error_msg = f"I'm sorry, I couldn't find information about the {scheme_code} scheme."
                return error_msg, None
            
            # Get data model to understand required fields
            data_model = await self._get_cached_data_model(scheme_code)
            if not data_model:
                error_msg = f"I'm sorry, I couldn't load the data requirements for {scheme_code}."
                return error_msg, None
                
            # Create conversation context
            context = ConversationContext(
                scheme_code=scheme_code,
                scheme_name=scheme_data.get("name", scheme_code)
            )
            
            # Store scheme data in collected_data for reference
            context.collected_data["_scheme_data"] = scheme_data
            context.collected_data["_data_model"] = data_model
            
            # Get required fields from data model
            validation_rules = scheme_data.get("validation_rules", {})
            required_fields = validation_rules.get("required_for_eligibility", [])
            context.required_fields = required_fields[:10]  # Limit to first 10 for testing
            
            if required_fields:
                context.current_field = required_fields[0]
            
            context.stage = ConversationStage.GREETING
            
            # Generate initial prompt
            initial_prompt = await self._generate_greeting_prompt(scheme_data, data_model)
            
            logger.info(f"Generated initial prompt for scheme: {scheme_code}")
            return initial_prompt, context
                
        except Exception as e:
            logger.error(f"Error generating initial prompt for {scheme_code}: {e}")
            error_msg = f"I'm sorry, there was an error accessing the {scheme_code} scheme information."
            return error_msg, None
            
    async def _generate_greeting_prompt(self, scheme_data: Dict[str, Any], data_model: Dict[str, Any]) -> str:
        """Generate greeting prompt based on scheme data."""
        scheme_name = scheme_data.get("name", "Government Scheme")
        description = scheme_data.get("description", "")
        ministry = scheme_data.get("ministry", "")
        
        # Get first required field to ask about
        validation_rules = scheme_data.get("validation_rules", {})
        required_fields = validation_rules.get("required_for_eligibility", [])
        first_field = required_fields[0] if required_fields else None
        
        # Find the field in data model sections to get its description
        first_field_description = ""
        if first_field:
            for section in scheme_data.get("data_model", []):
                fields = section.get("fields", {})
                if first_field in fields:
                    first_field_description = fields[first_field].get("description", first_field)
                    break
        
        prompt = f"""Hello! I'm your assistant for the {scheme_name} scheme.

{description}

This scheme is operated by {ministry}.

I need to collect some information from you. Let's get started.

{f"First, please provide: {first_field_description}" if first_field_description else "Please share your information."}

You can respond in English, and if you need assistance in another language, just let me know.

Important: I am currently only collecting information. Once all required information is gathered, I will let you know."""

        return prompt
        
    async def generate_llm_context(
        self, 
        context: ConversationContext, 
        user_input: str
    ) -> str:
        """Generate context and guidance for the LLM to use in conversation."""
        try:
            # Check if we already have all required data
            missing_fields = context.get_missing_fields()
            if not missing_fields:
                context.stage = ConversationStage.RESULT_DELIVERY
                return "All required data collected. Thank the user and inform them that data collection is complete."
            
            # Extract data from user input for current field
            extracted_data = await self._extract_data_from_input(
                user_input, 
                context.current_field, 
                context.scheme_code
            )
            
            # Update collected data if extraction was successful
            if extracted_data:
                context.collected_data.update(extracted_data)
                logger.info(f"Successfully collected data for {context.current_field}: {extracted_data}")
                
                # Move to next field
                current_index = context.required_fields.index(context.current_field)
                if current_index + 1 < len(context.required_fields):
                    context.current_field = context.required_fields[current_index + 1]
                else:
                    context.current_field = None
                    context.stage = ConversationStage.RESULT_DELIVERY
                    return "All required data collected. Thank the user and inform them that data collection is complete."
            
            # Generate context for next question
            if context.current_field:
                # Get the specific question template from canonical YAML
                question_template = await self._get_field_question_template(context.current_field, context.scheme_code)
                progress = f"{len(context.collected_data)}/{len(context.required_fields)} fields collected"
                
                if question_template:
                    guidance = f"FIELD: {context.current_field}\n"
                    guidance += f"QUESTION: {question_template.get('question', 'Please provide the information.')}\n"
                    guidance += f"HELP_TEXT: {question_template.get('help_text', '')}\n"
                    guidance += f"PROGRESS: {progress}\n"
                    guidance += f"INSTRUCTION: Ask EXACTLY the question specified above. Do not modify or add to it."
                    
                    return guidance
                else:
                    # Fallback to old method if no template found
                    field_info = await self._get_field_info(context.current_field, context.scheme_code)
                    guidance = f"FIELD: {context.current_field}\n"
                    guidance += f"DESCRIPTION: {field_info.get('description', context.current_field)}\n"
                    guidance += f"PROGRESS: {progress}\n"
                    guidance += f"INSTRUCTION: Ask for this field only."
                    
                    return guidance
            else:
                return "All required data collected. Thank the user and inform them that data collection is complete."
                
        except Exception as e:
            logger.error(f"Error generating LLM context: {e}")
            return f"Continue collecting information. Ask for the next required field."
            
    async def _get_field_info(self, field_name: str, scheme_code: str) -> Dict[str, Any]:
        """Get information about a specific field from the scheme data."""
        try:
            scheme_data = await self._get_cached_scheme_data(scheme_code)
            if not scheme_data:
                return {"description": field_name}
            
            # Search for field in data model sections
            for section in scheme_data.get("data_model", []):
                fields = section.get("fields", {})
                if field_name in fields:
                    return fields[field_name]
            
            return {"description": field_name}
        except Exception as e:
            logger.error(f"Error getting field info for {field_name}: {e}")
            return {"description": field_name}
            
    async def _get_field_question_template(self, field_name: str, scheme_code: str) -> Optional[Dict[str, str]]:
        """Get the specific question template for a field from the canonical YAML."""
        try:
            scheme_data = await self._get_cached_scheme_data(scheme_code)
            if not scheme_data:
                return None
            
            # Look for LLM directives -> field_questions
            llm_directives = scheme_data.get("llm_directives", {})
            field_questions = llm_directives.get("field_questions", {})
            
            if field_name in field_questions:
                return field_questions[field_name]
            
            return None
        except Exception as e:
            logger.error(f"Error getting question template for {field_name}: {e}")
            return None
            
    async def cleanup(self):
        """Cleanup resources and close sessions to prevent memory leaks."""
        try:
            # Clear all caches
            self.scheme_cache.clear()
            self.data_model_cache.clear()
            self.prompts_cache.clear()
            self.cache_timestamps.clear()
            
            # Close EFR client session if it exists
            # The httpx client does not have a direct session attribute to close here
            # as it's a lightweight client.
            # If httpx was used for other API calls, you might need to manage sessions.
            
            logger.info("Enhanced prompt engine cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during enhanced prompt engine cleanup: {e}")

    async def generate_followup_prompt(
        self, 
        context: ConversationContext, 
        user_input: str
    ) -> str:
        """Generate follow-up prompt based on conversation context and user input."""
        try:
            # Extract data from user input
            extracted_data = await self._extract_data_from_input(
                user_input, 
                context.current_field, 
                context.scheme_code
            )
            
            # Update collected data if extraction was successful
            if extracted_data:
                context.collected_data.update(extracted_data)
                # Reset attempts for this field
                context.attempts_count[context.current_field] = 0
                
                # Move to next field
                missing_fields = context.get_missing_fields()
                if missing_fields:
                    context.current_field = missing_fields[0]
                    context.stage = ConversationStage.DATA_COLLECTION
                else:
                    # All data collected, perform eligibility check
                    context.stage = ConversationStage.RESULT_DELIVERY
                    return await self._generate_eligibility_result(context)
            else:
                # Increment attempts for current field
                context.attempts_count[context.current_field] = context.attempts_count.get(context.current_field, 0) + 1
                
                if context.attempts_count[context.current_field] >= 3:
                    # Too many attempts, move to next field or end
                    missing_fields = context.get_missing_fields()
                    remaining_fields = [f for f in missing_fields if f != context.current_field]
                    if remaining_fields:
                        context.current_field = remaining_fields[0]
                        context.stage = ConversationStage.DATA_COLLECTION
                    else:
                        context.stage = ConversationStage.RESULT_DELIVERY
                        return await self._generate_partial_eligibility_result(context)
                else:
                    # Ask for clarification
                    context.stage = ConversationStage.CLARIFICATION
                    return await self._generate_clarification_prompt(context, user_input)
            
            # Generate next question
            return await self._generate_next_question(context)
            
        except Exception as e:
            logger.error(f"Error generating followup prompt: {e}")
            return "मुझे खुशी होगी अगर आप अपनी जानकारी फिर से साझा कर सकें। कृपया कोशिश करें।"
            
    async def _extract_data_from_input(
        self, 
        user_input: str, 
        field_name: str, 
        scheme_code: str
    ) -> Optional[Dict[str, Any]]:
        """Extract data from user input using EFR scheme-specific prompts."""
        try:
            # Get scheme data and extraction prompts
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.scheme_server_url}/schemes/{scheme_code}")
                if resp.status_code == 200:
                    scheme_data = resp.json().get("data", {})
                    if not scheme_data:
                        return None
                    
                    # Check if scheme has extraction prompts
                    extraction_prompts = scheme_data.get("extraction_prompts", {})
                    main_extraction = extraction_prompts.get("main_extraction", {})
                    
                    if main_extraction:
                        # Use the main extraction prompt from enhanced YAML
                        prompt_template = main_extraction.get("prompt", "")
                        if prompt_template:
                            # Format the prompt with the transcript
                            extraction_prompt = prompt_template.format(transcript=user_input)
                            
                            # Here you would call your LLM with the extraction prompt
                            # For now, we'll use a simplified extraction
                            return await self._simple_field_extraction(user_input, field_name)
                    
                    # Fallback to simple extraction
                    return await self._simple_field_extraction(user_input, field_name)
                
        except Exception as e:
            logger.error(f"Error extracting data from input: {e}")
            return None
            
    async def _simple_field_extraction(self, user_input: str, field_name: str) -> Optional[Dict[str, Any]]:
        """Simple field extraction for basic fields."""
        # This is a simplified extraction - in production you'd use your LLM
        user_input_lower = user_input.lower().strip()
        
        if field_name == "farmer_id":
            # Extract farmer ID - accept any non-empty string
            if len(user_input.strip()) > 0:
                return {"farmer_id": user_input.strip()}
                
        elif field_name == "name":
            # Extract name
            if len(user_input.strip()) > 0:
                return {"name": user_input.strip()}
                
        elif field_name == "age":
            # Extract age
            numbers = re.findall(r'\b(\d{1,3})\b', user_input)
            for num in numbers:
                age = int(num)
                if 18 <= age <= 120:
                    return {"age": age}
                    
        elif field_name == "gender":
            # Extract gender
            if any(word in user_input_lower for word in ["male", "पुरुष", "मर्द", "आदमी"]):
                return {"gender": "male"}
            elif any(word in user_input_lower for word in ["female", "महिला", "औरत", "स्त्री"]):
                return {"gender": "female"}
                
        elif field_name == "phone_number":
            # Extract phone number
            phone_match = re.search(r'(\d{10})', user_input)
            if phone_match:
                return {"phone_number": phone_match.group(1)}
                
        elif field_name == "state":
            # Extract state name
            if len(user_input.strip()) > 0:
                return {"state": user_input.strip()}
                
        # Add more field-specific extraction logic
        
        return None
        
    async def _generate_next_question(self, context: ConversationContext) -> str:
        """Generate the next question based on current field."""
        try:
            if not context.current_field:
                return await self._generate_eligibility_result(context)
                
            # Get clarification prompts from EFR
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.scheme_server_url}/schemes/{context.scheme_code}")
                if resp.status_code == 200:
                    scheme_data = resp.json().get("data", {})
                    if scheme_data:
                        extraction_prompts = scheme_data.get("extraction_prompts", {})
                        clarification_prompts = extraction_prompts.get("clarification_prompts", {})
                        
                        # Check for field-specific clarification prompt
                        if context.current_field in clarification_prompts:
                            return clarification_prompts[context.current_field]
                            
                        # Check for special region prompts
                        collected_state = context.collected_data.get("state", "").lower()
                        if any(ne_state in collected_state for ne_state in ["manipur", "nagaland", "arunachal", "assam", "meghalaya", "mizoram", "sikkim", "tripura"]):
                            if "manipur" in collected_state and "special_region_manipur" in clarification_prompts:
                                return clarification_prompts["special_region_manipur"]
                            elif "nagaland" in collected_state and "special_region_nagaland" in clarification_prompts:
                                return clarification_prompts["special_region_nagaland"]
                            elif "special_region_northeast" in clarification_prompts:
                                return clarification_prompts["special_region_northeast"]
                                
                        elif "jharkhand" in collected_state and "special_region_jharkhand" in clarification_prompts:
                            return clarification_prompts["special_region_jharkhand"]
                
                # Get field metadata for generic question
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{self.scheme_server_url}/schemes/{context.scheme_code}/data_model")
                    if resp.status_code == 200:
                        data_model = resp.json().get("data", {})
                        if data_model:
                            for section in data_model.get("data_model", []):
                                fields = section.get("fields", {})
                                if context.current_field in fields:
                                    field_info = fields[context.current_field]
                                    description = field_info.get("description", context.current_field)
                                    
                                    # Add constraint to prevent eligibility assessment
                                    question = f"कृपया बताएं: {description}\n\n"
                                    question += "नोट: मैं अभी केवल जानकारी एकत्रित कर रहा हूं। पात्रता की जांच सभी जानकारी मिलने के बाद ही की जाएगी।"
                                    return question
                                    
                # Fallback generic question with constraint
                question = f"कृपया {context.current_field} की जानकारी दें।\n\n"
                question += "नोट: मैं अभी केवल जानकारी एकत्रित कर रहा हूं। पात्रता की जांच सभी जानकारी मिलने के बाद ही की जाएगी।"
                return question
                
        except Exception as e:
            logger.error(f"Error generating next question: {e}")
            return "कृपया अगली जानकारी साझा करें।"
            
    async def _generate_clarification_prompt(
        self, 
        context: ConversationContext, 
        user_input: str
    ) -> str:
        """Generate clarification prompt for unclear input."""
        try:
            # Get field metadata
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.scheme_server_url}/schemes/{context.scheme_code}/data_model")
                if resp.status_code == 200:
                    data_model = resp.json().get("data", {})
                    if data_model:
                        for section in data_model.get("data_model", []):
                            fields = section.get("fields", {})
                            if context.current_field in fields:
                                field_info = fields[context.current_field]
                                description = field_info.get("description", context.current_field)
                                field_type = field_info.get("type", "string")
                                values = field_info.get("values", [])
                                
                                clarification = f"मुझे {description} के बारे में स्पष्ट जानकारी नहीं मिली।"
                                
                                if field_type == "enum" and values:
                                    options = ", ".join(values)
                                    clarification += f" कृपया इनमें से चुनें: {options}"
                                elif field_type == "integer":
                                    clarification += " कृपया एक संख्या दें।"
                                elif field_type == "boolean":
                                    clarification += " कृपया हां या नहीं में जवाब दें।"
                                else:
                                    clarification += f" कृपया {description} की सही जानकारी दें।"
                                    
                                return clarification
                                
            return f"मुझे {context.current_field} की जानकारी स्पष्ट नहीं मिली। कृपया फिर से बताएं।"
            
        except Exception as e:
            logger.error(f"Error generating clarification prompt: {e}")
            return "कृपया अपनी जानकारी स्पष्ट रूप से बताएं।"
            
    async def _generate_eligibility_result(self, context: ConversationContext) -> str:
        """Generate final eligibility result."""
        try:
            # Validate data using EFR
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.scheme_server_url}/validate_data", json={
                    "scheme_code": context.scheme_code,
                    "collected_data": context.collected_data
                })
                if resp.status_code == 200:
                    validation_result = resp.json()
                    
                    if validation_result and validation_result.get("is_valid", False):
                        # Get scheme benefits
                        resp = await client.get(f"{self.scheme_server_url}/schemes/{context.scheme_code}")
                        if resp.status_code == 200:
                            scheme_data = resp.json().get("data", {})
                            benefits = scheme_data.get("benefits", []) if scheme_data else []
                            
                            result = "🎉 बधाई हो! आप इस योजना के लिए पात्र हैं।\n\n"
                            
                            if benefits:
                                result += "योजना के लाभ:\n"
                                for benefit in benefits:
                                    if isinstance(benefit, dict):
                                        benefit_desc = benefit.get("description", "")
                                        amount = benefit.get("amount", "")
                                        if amount:
                                            result += f"• {benefit_desc} - ₹{amount}\n"
                                        else:
                                            result += f"• {benefit_desc}\n"
                            
                            result += "\nआगे की प्रक्रिया के लिए अपने नजदीकी कार्यालय से संपर्क करें।"
                            return result
                    else:
                        errors = validation_result.get("errors", []) if validation_result else ["अज्ञात त्रुटि"]
                        result = "खेद है, आप इस योजना के लिए पात्र नहीं हैं।\n\n"
                        result += "कारण:\n"
                        for error in errors:
                            result += f"• {error}\n"
                        return result
                
        except Exception as e:
            logger.error(f"Error generating eligibility result: {e}")
            return "पात्रता जांच में त्रुटि हुई। कृपया बाद में कोशिश करें।"
            
    async def _generate_partial_eligibility_result(self, context: ConversationContext) -> str:
        """Generate result when some data is missing."""
        return """आपकी कुछ जानकारी अधूरी है, इसलिए मैं पूर्ण पात्रता जांच नहीं कर सका।

कृपया निम्नलिखित जानकारी के साथ दोबारा कोशिश करें:
• पूरा नाम
• उम्र  
• लिंग
• फोन नंबर
• राज्य का नाम
• जमीन की जानकारी

या अपने नजदीकी कार्यालय से संपर्क करें।"""

    async def get_extraction_prompt(self, scheme_code: str) -> Optional[str]:
        """Get the main extraction prompt for a scheme."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.scheme_server_url}/schemes/{scheme_code}")
                if resp.status_code == 200:
                    scheme_data = resp.json().get("data", {})
                    if scheme_data:
                        extraction_prompts = scheme_data.get("extraction_prompts", {})
                        main_extraction = extraction_prompts.get("main_extraction", {})
                        return main_extraction.get("prompt", "")
        except Exception as e:
            logger.error(f"Error getting extraction prompt for {scheme_code}: {e}")
        return None
        
    async def get_clarification_prompts(self, scheme_code: str) -> Dict[str, str]:
        """Get all clarification prompts for a scheme."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.scheme_server_url}/schemes/{scheme_code}")
                if resp.status_code == 200:
                    scheme_data = resp.json().get("data", {})
                    if scheme_data:
                        extraction_prompts = scheme_data.get("extraction_prompts", {})
                        return extraction_prompts.get("clarification_prompts", {})
        except Exception as e:
            logger.error(f"Error getting clarification prompts for {scheme_code}: {e}")
        return {}
        
    async def get_llm_directives(self, scheme_code: str) -> Dict[str, Any]:
        """Get LLM directives for a scheme."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.scheme_server_url}/schemes/{scheme_code}")
                if resp.status_code == 200:
                    scheme_data = resp.json().get("data", {})
                    if scheme_data:
                        return scheme_data.get("llm_directives", {})
        except Exception as e:
            logger.error(f"Error getting LLM directives for {scheme_code}: {e}")
        return {} 