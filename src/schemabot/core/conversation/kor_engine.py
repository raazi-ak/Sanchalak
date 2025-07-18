"""
Kor-based Conversation Engine for PM-KISAN Data Collection

This module uses the Kor library for reliable structured data extraction
from natural language conversations.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun
from kor import create_extraction_chain, Object, Text, Number, Bool

from ..scheme.efr_integration import EFRSchemeClient

logger = logging.getLogger(__name__)

class LMStudioLLM(LLM):
    """LangChain LLM wrapper for LM Studio API"""
    
    model_name: str = "google/gemma-3-4b"
    base_url: str = "http://localhost:1234/v1"
    
    def __init__(self, model_name: str = "google/gemma-3-4b", base_url: str = "http://localhost:1234/v1"):
        super().__init__()
        self.model_name = model_name
        self.base_url = base_url
        
    def _call(self, prompt: str, stop: Optional[List[str]] = None, run_manager: Optional[CallbackManagerForLLMRun] = None) -> str:
        """Make a call to LM Studio API"""
        try:
            import requests
            
            messages = [{"role": "user", "content": prompt}]
            
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 500,
                "stream": False
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"LM Studio API error: {response.status_code}")
                return "I apologize, but I encountered an error processing your request."
                
        except Exception as e:
            logger.error(f"LM Studio API call failed: {e}")
            return "I apologize, but I encountered an error processing your request."
    
    @property
    def _llm_type(self) -> str:
        return "lmstudio"

@dataclass
class ConversationState:
    """Maintains the current state of the conversation"""
    collected_data: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    completion_percentage: float = 0.0

class KorConversationEngine:
    """
    Simple and reliable conversation engine using Kor for structured data extraction
    """
    
    def __init__(self, efr_api_url: str = "http://localhost:8001", model_name: str = "google/gemma-3-4b"):
        self.efr_api_url = efr_api_url
        self.model_name = model_name
        self.efr_client = EFRSchemeClient(efr_api_url)
        
        # Initialize LLM
        self.llm = LMStudioLLM(model_name, "http://localhost:1234/v1")
        
        # Required fields for PM-KISAN
        self.required_fields = [
            "name", "age", "gender", "phone_number", "state", "district", 
            "sub_district_block", "village", "land_size_acres", "land_ownership", 
            "bank_account", "account_number", "ifsc_code", "aadhaar_number", 
            "aadhaar_linked", "category"
        ]
        
        # Create Kor extraction schema
        self.extraction_schema = Object(
            id="farmer_info",
            description="Information about a farmer applying for PM-KISAN scheme",
            attributes=[
                Text(id="name", description="Full name of the farmer", examples=[("My name is John Doe", "John Doe")]),
                Number(id="age", description="Age in years", examples=[("I am 35 years old", 35)]),
                Text(id="gender", description="Gender (male/female/other)", examples=[("I am a man", "male")]),
                Text(id="phone_number", description="10-digit mobile phone number", examples=[("My number is 9876543210", "9876543210")]),
                Text(id="state", description="State of residence", examples=[("I live in Kerala", "Kerala")]),
                Text(id="district", description="District name", examples=[("I'm from Kochi district", "Kochi")]),
                Text(id="sub_district_block", description="Sub-district or block", examples=[("My block is Ernakulum", "Ernakulum")]),
                Text(id="village", description="Village name", examples=[("My village is Kumbakonam", "Kumbakonam")]),
                Number(id="land_size_acres", description="Land size in acres", examples=[("I have 2.5 acres", 2.5)]),
                Text(id="land_ownership", description="Land ownership type: owned/leased/sharecropping/joint", examples=[("I own my land", "owned")]),
                Bool(id="bank_account", description="Whether farmer has bank account", examples=[("I have a bank account", True)]),
                Text(id="account_number", description="Bank account number", examples=[("My account number is 1234567890", "1234567890")]),
                Text(id="ifsc_code", description="Bank IFSC code", examples=[("IFSC code is SBIN0001234", "SBIN0001234")]),
                Text(id="aadhaar_number", description="12-digit Aadhaar number", examples=[("My Aadhaar is 123456789012", "123456789012")]),
                Bool(id="aadhaar_linked", description="Whether Aadhaar is linked to bank account", examples=[("Aadhaar is linked to bank", True)]),
                Text(id="category", description="Social category: general/sc/st/obc/minority/bpl", examples=[("I belong to OBC category", "obc")]),
            ],
            many=False,
        )
        
        # Create extraction chain
        self.extraction_chain = create_extraction_chain(
            self.llm, 
            self.extraction_schema, 
            encoder_or_encoder_class='json'
        )
    
    async def initialize_conversation(self, scheme_code: str = "pm-kisan") -> Tuple[str, ConversationState]:
        """Initialize conversation for PM-KISAN scheme"""
        
        state = ConversationState()
        state.missing_fields = self.required_fields.copy()
        
        initial_message = """Namaste! I'm here to help you with the PM-KISAN scheme. 
This is a great government program that provides Rs 6000 per year to eligible farmers 
like yourself to support your agricultural activities.

I'd like to have a friendly conversation to understand your farming situation and 
see if you qualify for this scheme. Let me start by getting to know you better.

Could you tell me your name and a bit about your farming background?"""
        
        return initial_message, state
    
    async def process_user_input(self, user_input: str, state: ConversationState) -> Tuple[str, ConversationState]:
        """Process user input and extract structured information using Kor"""
        
        try:
            # Extract information using Kor
            extraction_result = self.extraction_chain.invoke(user_input)
            extracted_data = extraction_result.get('data', {}).get('farmer_info', {})
            
            # Update state with extracted data
            for field, value in extracted_data.items():
                if field in self.required_fields and value is not None:
                    state.collected_data[field] = value
                    if field in state.missing_fields:
                        state.missing_fields.remove(field)
            
            # Update completion percentage
            state.completion_percentage = ((len(self.required_fields) - len(state.missing_fields)) / len(self.required_fields)) * 100
            
            # Generate response
            response = self._generate_response(extracted_data, state, user_input)
            
            return response, state
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            return "I apologize, but I encountered an error processing your message. Could you please try again?", state
    
    def _generate_response(self, extracted_data: Dict[str, Any], state: ConversationState, user_input: str) -> str:
        """Generate contextual response based on extracted data"""
        
        # Acknowledge what was extracted
        acknowledgment = ""
        if extracted_data:
            extracted_fields = [f"{field}: {value}" for field, value in extracted_data.items()]
            acknowledgment = f"Thank you! I've noted: {', '.join(extracted_fields)}.\n\n"
        
        # Check if we're done
        if not state.missing_fields:
            return f"{acknowledgment}Excellent! I have all the information I need for your PM-KISAN application. You're {state.completion_percentage:.0f}% complete!"
        
        # Ask for next piece of information
        next_field = state.missing_fields[0]
        field_prompts = {
            "name": "What is your full name?",
            "age": "How old are you?",
            "gender": "What is your gender?",
            "phone_number": "What is your mobile phone number?",
            "state": "Which state do you live in?",
            "district": "Which district are you from?",
            "sub_district_block": "What is your sub-district or block?",
            "village": "Which village are you from?",
            "land_size_acres": "How many acres of land do you have?",
            "land_ownership": "Do you own your land, lease it, or have some other arrangement? (owned/leased/sharecropping/joint)",
            "bank_account": "Do you have a bank account?",
            "account_number": "What is your bank account number?",
            "ifsc_code": "What is your bank's IFSC code?",
            "aadhaar_number": "What is your 12-digit Aadhaar number?",
            "aadhaar_linked": "Is your Aadhaar number linked to your bank account?",
            "category": "What is your social category? (general/sc/st/obc/minority/bpl)",
        }
        
        next_question = field_prompts.get(next_field, f"Could you tell me about {next_field}?")
        
        return f"{acknowledgment}{next_question} ({state.completion_percentage:.0f}% complete)"
    
    def get_completion_percentage(self, state: ConversationState) -> float:
        """Get completion percentage"""
        return state.completion_percentage
    
    def get_missing_fields(self, state: ConversationState) -> List[str]:
        """Get list of missing fields"""
        return state.missing_fields
    
    async def generate_summary(self, state: ConversationState) -> str:
        """Generate summary of collected data"""
        if not state.collected_data:
            return "No data collected yet."
        
        summary = "Collected Information:\n"
        for field, value in state.collected_data.items():
            summary += f"- {field}: {value}\n"
        
        summary += f"\nCompletion: {state.completion_percentage:.0f}%"
        
        return summary 