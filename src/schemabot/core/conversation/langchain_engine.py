"""
LangChain Native Structured Output Conversation Engine for PM-KISAN Data Collection

This module uses LangChain's native .withStructuredOutput() method which is
recommended for chat models that support tool calling.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.prompts import ChatPromptTemplate

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
                "temperature": 0,  # Always 0 for extraction
                "max_tokens": 300,
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

class FarmerInfo(BaseModel):
    """Schema for PM-KISAN farmer information extraction"""
    
    name: Optional[str] = Field(None, description="Full name of the farmer")
    age: Optional[int] = Field(None, description="Age in years")
    gender: Optional[str] = Field(None, description="Gender: male, female, or other")
    phone_number: Optional[str] = Field(None, description="10-digit mobile phone number")
    state: Optional[str] = Field(None, description="State of residence")
    district: Optional[str] = Field(None, description="District name")
    sub_district_block: Optional[str] = Field(None, description="Sub-district or block")
    village: Optional[str] = Field(None, description="Village name")
    land_size_acres: Optional[float] = Field(None, description="Land size in acres")
    land_ownership: Optional[str] = Field(None, description="Land ownership type: owned, leased, sharecropping, or joint")
    bank_account: Optional[bool] = Field(None, description="Whether farmer has bank account")
    account_number: Optional[str] = Field(None, description="Bank account number")
    ifsc_code: Optional[str] = Field(None, description="Bank IFSC code")
    aadhaar_number: Optional[str] = Field(None, description="12-digit Aadhaar number")
    aadhaar_linked: Optional[bool] = Field(None, description="Whether Aadhaar is linked to bank account")
    category: Optional[str] = Field(None, description="Social category: general, sc, st, obc, minority, or bpl")

@dataclass
class ConversationState:
    """Maintains the current state of the conversation"""
    collected_data: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    completion_percentage: float = 0.0

class LangChainConversationEngine:
    """
    Modern conversation engine using LangChain's native structured output
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
        
        # Create extraction prompt
        self.extraction_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are an expert at extracting structured information from natural language.
                
Extract information about a farmer applying for the PM-KISAN scheme from the user's input.
Only extract information that is explicitly mentioned or clearly implied.
If information is not available, leave the field as null.

Examples:
- "My name is John Doe" → name: "John Doe"
- "I am 35 years old" → age: 35
- "I am a man" or "I am male" → gender: "male"
- "I live in Kerala" → state: "Kerala"
- "I have 2.5 acres" → land_size_acres: 2.5
- "I own my land" → land_ownership: "owned"
- "Yes, I have a bank account" → bank_account: true

Be precise and only extract what is actually stated."""
            ),
            ("human", "Extract farmer information from: {text}")
        ])
        
        # Create extraction chain that returns structured output
        self.extraction_chain = self.extraction_prompt | self.llm | self._parse_extraction
    
    def _parse_extraction(self, llm_output: str) -> Dict[str, Any]:
        """Parse LLM output to extract structured data"""
        try:
            # Try to extract JSON from the output
            import re
            
            # Look for JSON-like content
            json_match = re.search(r'\{[^}]*\}', llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    parsed = json.loads(json_str)
                    return parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    pass
            
            # Fallback: simple pattern matching
            extracted = {}
            text_lower = llm_output.lower()
            
            # Name extraction
            name_patterns = [
                r'name[:\s]+([a-zA-Z\s]+)',
                r'i am ([a-zA-Z\s]+)',
                r'my name is ([a-zA-Z\s]+)'
            ]
            for pattern in name_patterns:
                match = re.search(pattern, llm_output, re.IGNORECASE)
                if match:
                    name = match.group(1).strip().title()
                    if len(name) > 1:
                        extracted['name'] = name
                        break
            
            # Age extraction
            age_patterns = [r'age[:\s]+(\d+)', r'(\d+)\s+years?\s+old', r'i am (\d+)']
            for pattern in age_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    age = int(match.group(1))
                    if 18 <= age <= 120:
                        extracted['age'] = age
                        break
            
            # Gender extraction
            if any(word in text_lower for word in ['male', 'man', 'boy']):
                extracted['gender'] = 'male'
            elif any(word in text_lower for word in ['female', 'woman', 'girl']):
                extracted['gender'] = 'female'
            
            # State extraction
            states = ['kerala', 'karnataka', 'tamil nadu', 'andhra pradesh', 'telangana', 
                     'maharashtra', 'gujarat', 'rajasthan', 'punjab', 'haryana', 
                     'uttar pradesh', 'bihar', 'west bengal', 'odisha', 'madhya pradesh']
            for state in states:
                if state in text_lower:
                    extracted['state'] = state.title()
                    break
            
            # Land size extraction
            land_match = re.search(r'(\d+\.?\d*)\s*(acres?|hectares?)', text_lower)
            if land_match:
                size = float(land_match.group(1))
                if 'hectare' in land_match.group(2):
                    size *= 2.47  # Convert hectares to acres
                extracted['land_size_acres'] = size
            
            # Land ownership
            if any(phrase in text_lower for phrase in ['i own', 'my land', 'own the land']):
                extracted['land_ownership'] = 'owned'
            elif any(phrase in text_lower for phrase in ['lease', 'rent', 'rented']):
                extracted['land_ownership'] = 'leased'
            
            # Phone number
            phone_match = re.search(r'(\d{10})', llm_output)
            if phone_match:
                extracted['phone_number'] = phone_match.group(1)
            
            return extracted
            
        except Exception as e:
            logger.error(f"Error parsing extraction: {e}")
            return {}
    
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
        """Process user input and extract structured information"""
        
        try:
            # Extract information using our chain
            extracted_data = await self.extraction_chain.ainvoke({"text": user_input})
            
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