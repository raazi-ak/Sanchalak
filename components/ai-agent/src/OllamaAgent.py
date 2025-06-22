"""
Ollama Agent for LLM Integration in Farmer AI Pipeline
Handles communication with Ollama for local LLM processing
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, AsyncGenerator
import aiohttp
import logging

try:
    from ollama import AsyncClient, Client
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from config import get_settings
from utils.error_handeller import raise_ollama_error, OllamaError
from utils.logger import get_logger, log_async_execution_time

settings = get_settings()
logger = get_logger(__name__)

class OllamaAgent:
    """
    Agent for interacting with Ollama LLM models
    Provides both synchronous and asynchronous interfaces
    """
    
    def __init__(self, host: Optional[str] = None, timeout: int = 60):
        self.host = host or settings.ollama_host
        self.timeout = timeout
        self.async_client: Optional[AsyncClient] = None
        self.sync_client: Optional[Client] = None
        self.available_models: List[str] = []
        self.current_model: str = settings.ollama_model
        self.fallback_model: str = settings.ollama_fallback_model
        self.is_available = OLLAMA_AVAILABLE
        
        logger.info(f"Initializing Ollama agent with host: {self.host}")

    async def initialize(self):
        """Initialize the Ollama client and check connectivity"""
        if not self.is_available:
            logger.warning("Ollama library not available - LLM features will be disabled")
            return
        
        try:
            # Initialize async client
            self.async_client = AsyncClient(
                host=self.host,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            
            # Initialize sync client for non-async operations
            self.sync_client = Client(host=self.host)
            
            # Check connectivity and get available models
            await self._check_connectivity()
            await self._load_available_models()
            
            logger.info(f"Ollama agent initialized successfully with {len(self.available_models)} models")
            
        except Exception as e:
            logger.error(f"Failed to initialize Ollama agent: {str(e)}")
            self.is_available = False
            raise_ollama_error(f"Failed to initialize Ollama: {str(e)}")

    async def _check_connectivity(self):
        """Check if Ollama server is reachable"""
        try:
            # Simple health check
            response = await self.async_client.list()
            logger.info("Ollama server connectivity confirmed")
        except Exception as e:
            logger.error(f"Cannot connect to Ollama server: {str(e)}")
            raise_ollama_error(f"Ollama server unreachable: {str(e)}")

    async def _load_available_models(self):
        """Load list of available models from Ollama"""
        try:
            response = await self.async_client.list()
            self.available_models = [model['name'] for model in response['models']]
            
            if not self.available_models:
                logger.warning("No models found in Ollama")
                return
            
            # Check if current model is available
            if self.current_model not in self.available_models:
                logger.warning(f"Configured model '{self.current_model}' not found")
                # Try configured fallback model first
                if self.fallback_model in self.available_models:
                    self.current_model = self.fallback_model
                    logger.info(f"Using configured fallback model: {self.current_model}")
                # Use first available model as last resort
                elif self.available_models:
                    self.current_model = self.available_models[0]
                    logger.info(f"Using first available model: {self.current_model}")
            
            logger.info(f"Available models: {self.available_models}")
            
        except Exception as e:
            logger.error(f"Failed to load available models: {str(e)}")
            raise_ollama_error(f"Failed to get model list: {str(e)}")

    @log_async_execution_time
    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request to Ollama
        
        Args:
            messages: List of message objects with 'role' and 'content'
            model: Model to use (optional, uses default if not specified)
            stream: Whether to stream the response
            **kwargs: Additional parameters for Ollama
            
        Returns:
            Response from Ollama
        """
        if not self.is_available or not self.async_client:
            raise_ollama_error("Ollama client not available")
        
        model = model or self.current_model
        
        if model not in self.available_models:
            raise_ollama_error(f"Model '{model}' not available. Available models: {self.available_models}")
        
        try:
            logger.info(f"Sending chat request to model '{model}' with {len(messages)} messages")
            
            # Prepare options
            options = {
                'temperature': kwargs.get('temperature', 0.7),
                'top_p': kwargs.get('top_p', 0.9),
                'top_k': kwargs.get('top_k', 40),
                'num_predict': kwargs.get('num_predict', 512),
                **{k: v for k, v in kwargs.items() if k not in ['temperature', 'top_p', 'top_k', 'num_predict']}
            }
            
            response = await self.async_client.chat(
                model=model,
                messages=messages,
                stream=stream,
                options=options
            )
            
            logger.info(f"Chat request completed for model '{model}'")
            return response
            
        except Exception as e:
            logger.error(f"Chat request failed: {str(e)}")
            raise_ollama_error(f"Chat request failed: {str(e)}")

    async def chat_stream(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion from Ollama
        
        Args:
            messages: List of message objects
            model: Model to use
            **kwargs: Additional parameters
            
        Yields:
            Streaming response chunks
        """
        if not self.is_available or not self.async_client:
            raise_ollama_error("Ollama client not available")
        
        model = model or self.current_model
        
        try:
            logger.info(f"Starting stream chat with model '{model}'")
            
            options = {
                'temperature': kwargs.get('temperature', 0.7),
                'top_p': kwargs.get('top_p', 0.9),
                'num_predict': kwargs.get('num_predict', 512),
            }
            
            async for chunk in await self.async_client.chat(
                model=model,
                messages=messages,
                stream=True,
                options=options
            ):
                yield chunk
                
        except Exception as e:
            logger.error(f"Stream chat failed: {str(e)}")
            raise_ollama_error(f"Stream chat failed: {str(e)}")

    @log_async_execution_time
    async def generate(
        self, 
        prompt: str, 
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text completion from prompt
        
        Args:
            prompt: Input prompt
            model: Model to use
            **kwargs: Additional parameters
            
        Returns:
            Generated response
        """
        if not self.is_available or not self.async_client:
            raise_ollama_error("Ollama client not available")
        
        model = model or self.current_model
        
        try:
            logger.info(f"Generating text with model '{model}'")
            
            options = {
                'temperature': kwargs.get('temperature', 0.7),
                'top_p': kwargs.get('top_p', 0.9),
                'num_predict': kwargs.get('num_predict', 512),
            }
            
            response = await self.async_client.generate(
                model=model,
                prompt=prompt,
                options=options
            )
            
            logger.info(f"Text generation completed for model '{model}'")
            return response
            
        except Exception as e:
            logger.error(f"Text generation failed: {str(e)}")
            raise_ollama_error(f"Text generation failed: {str(e)}")

    async def extract_farmer_info(
        self, 
        text: str, 
        language: str = "hi",
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract farmer information from text using LLM
        
        Args:
            text: Input text to extract from
            language: Language of the text ('hi' for Hindi, 'en' for English)
            model: Model to use for extraction
            
        Returns:
            Extracted farmer information as structured data
        """
        if not self.is_available:
            raise_ollama_error("Ollama not available for information extraction")
        
        # Create structured prompt for information extraction
        prompt = self._create_extraction_prompt(text, language)
        
        try:
            logger.info(f"Extracting farmer information from {len(text)} characters of text")
            
            response = await self.generate(
                prompt=prompt,
                model=model,
                temperature=0.1,  # Low temperature for consistent extraction
                num_predict=800
            )
            
            # Parse the response
            extracted_info = self._parse_extraction_response(response['response'])
            
            logger.info(f"Successfully extracted farmer information")
            return extracted_info
            
        except Exception as e:
            logger.error(f"Farmer info extraction failed: {str(e)}")
            raise_ollama_error(f"Information extraction failed: {str(e)}")

    def _create_extraction_prompt(self, text: str, language: str) -> str:
        """Create a structured prompt for farmer information extraction"""
        
        language_instruction = {
            'hi': "Text is in Hindi/Hinglish. Extract information accurately.",
            'en': "Text is in English. Extract information accurately.",
        }.get(language, "Extract information accurately.")
        
        prompt = f"""
You are an expert information extraction system for Indian farmers. {language_instruction}

Extract the following information from the given text and return it in valid JSON format:

Text: "{text}"

Extract these fields (use null for missing information):
- name: Farmer's full name
- age: Age in years (number only)
- gender: "male" or "female"
- phone_number: 10-digit phone number
- state: Full state name in English
- district: District name in English
- village: Village name
- land_size_acres: Land size in acres (convert from other units if needed)
- land_ownership: "owned", "leased", or "shared"
- annual_income: Annual income in rupees (convert lakhs/crores to numbers)
- crops: Array of crop names in English
- irrigation_type: "rain_fed", "canal", "borewell", "drip", or "sprinkler"
- family_size: Number of family members
- farming_equipment: Array of equipment owned
- fertilizers_used: Array of fertilizers mentioned

Rules:
1. Return ONLY valid JSON
2. Convert Hindi crop names to English
3. Convert all measurements to standard units
4. Be precise, don't make assumptions
5. Use null for missing information

JSON Response:
"""
        return prompt

    def _parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured data"""
        try:
            # Find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.warning("No JSON found in response, attempting fallback parsing")
                return self._fallback_parse_response(response)
            
            json_str = response[json_start:json_end]
            parsed_data = json.loads(json_str)
            
            # Validate and clean the data
            return self._validate_extracted_data(parsed_data)
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {str(e)}, attempting fallback")
            return self._fallback_parse_response(response)

    def _fallback_parse_response(self, response: str) -> Dict[str, Any]:
        """Fallback parser when JSON parsing fails"""
        extracted = {}
        
        # Simple regex patterns for common fields
        import re
        
        patterns = {
            'name': r'(?:name|नाम)[:=]\s*["\']?([^"\',\n]+)["\']?',
            'age': r'(?:age|उम्र|आयु)[:=]\s*(\d+)',
            'phone_number': r'(?:phone|फोन|mobile)[:=]\s*["\']?(\d{10})["\']?',
            'annual_income': r'(?:income|आय|salary)[:=]\s*["\']?(\d+(?:,\d+)*)["\']?'
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                extracted[field] = match.group(1).strip()
        
        return extracted

    def _validate_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean extracted data"""
        validated = {}
        
        # String fields
        for field in ['name', 'gender', 'phone_number', 'state', 'district', 'village', 'land_ownership', 'irrigation_type']:
            if field in data and data[field]:
                validated[field] = str(data[field]).strip()
        
        # Numeric fields
        for field in ['age', 'land_size_acres', 'annual_income', 'family_size']:
            if field in data and data[field] is not None:
                try:
                    validated[field] = float(data[field]) if field == 'land_size_acres' else int(data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid numeric value for {field}: {data[field]}")
        
        # Array fields
        for field in ['crops', 'farming_equipment', 'fertilizers_used']:
            if field in data and isinstance(data[field], list):
                validated[field] = [str(item).strip() for item in data[field] if item]
        
        return validated

    async def get_available_models(self) -> List[str]:
        """Get list of available models"""
        if not self.is_available:
            return []
        
        try:
            await self._load_available_models()
            return self.available_models
        except Exception as e:
            logger.error(f"Failed to get available models: {str(e)}")
            return []

    async def pull_model(self, model_name: str) -> bool:
        """Pull a model to Ollama"""
        if not self.is_available or not self.async_client:
            raise_ollama_error("Ollama client not available")
        
        try:
            logger.info(f"Pulling model: {model_name}")
            await self.async_client.pull(model_name)
            
            # Refresh available models
            await self._load_available_models()
            
            logger.info(f"Model {model_name} pulled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {str(e)}")
            raise_ollama_error(f"Failed to pull model: {str(e)}")

    async def is_ready(self) -> bool:
        """Check if the agent is ready to process requests"""
        return self.is_available and self.async_client is not None and len(self.available_models) > 0

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the Ollama agent"""
        status = {
            "ollama_available": self.is_available,
            "client_initialized": self.async_client is not None,
            "host": self.host,
            "current_model": self.current_model,
            "available_models": self.available_models,
            "model_count": len(self.available_models)
        }
        
        if self.is_available and self.async_client:
            try:
                # Quick connectivity test
                await self.async_client.list()
                status["connectivity"] = "ok"
            except Exception as e:
                status["connectivity"] = f"error: {str(e)}"
        else:
            status["connectivity"] = "unavailable"
        
        return status

    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.async_client:
                # AsyncClient doesn't need explicit cleanup
                self.async_client = None
            
            self.sync_client = None
            logger.info("Ollama agent cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during Ollama cleanup: {str(e)}")

# Export the agent class
__all__ = ["OllamaAgent"]