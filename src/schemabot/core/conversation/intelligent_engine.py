"""
Intelligent Conversation Engine for Natural PM-KISAN Data Collection

This module implements a modern, context-aware conversation system that:
1. Uses natural language processing to extract multiple fields from responses
2. Maintains intelligent context management and memory
3. Provides conversational grounding and implicit understanding
4. Adapts dynamically to user responses and conversation flow
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from langchain.memory import ConversationSummaryBufferMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from sentence_transformers import SentenceTransformer
import numpy as np

from ..scheme.efr_integration import EFRSchemeClient
from api.models.conversation import ConversationContext, ConversationStage

logger = logging.getLogger(__name__)

class ExtractionConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

@dataclass
class ExtractedField:
    """Represents a field extracted from natural language"""
    field_name: str
    value: Any
    confidence: ExtractionConfidence
    source_text: str
    needs_clarification: bool = False
    
@dataclass
class ConversationState:
    """Maintains the current state of the conversation"""
    collected_fields: Dict[str, ExtractedField] = field(default_factory=dict)
    pending_clarifications: List[str] = field(default_factory=list)
    conversation_context: str = ""
    user_intent: str = ""
    last_extraction_attempt: Optional[datetime] = None
    conversation_flow_stage: str = "greeting"
    
class IntelligentConversationEngine:
    """
    Modern conversation engine that uses natural language processing
    and intelligent context management for PM-KISAN data collection.
    """
    
    def __init__(self, efr_api_url: str = "http://localhost:8001", model_name: str = "google/gemma-3-4b"):
        self.efr_api_url = efr_api_url
        self.model_name = model_name
        self.efr_client = EFRSchemeClient(efr_api_url)
        
        # Initialize semantic similarity model for context management
        self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Cache for scheme data
        self.scheme_cache = {}
        
        # Required fields for PM-KISAN (from enhanced YAML)
        self.required_fields = {
            "name": {"type": "string", "description": "Full name of the farmer"},
            "age": {"type": "integer", "description": "Age in years"},
            "gender": {"type": "string", "description": "Gender (male/female/other)"},
            "phone_number": {"type": "string", "description": "Mobile phone number"},
            "state": {"type": "string", "description": "State of residence"},
            "district": {"type": "string", "description": "District"},
            "sub_district_block": {"type": "string", "description": "Sub-district or block"},
            "village": {"type": "string", "description": "Village name"},
            "land_size_acres": {"type": "float", "description": "Land size in acres"},
            "land_ownership": {"type": "string", "description": "Type of land ownership (owned/leased/sharecropping/joint)"},
            "date_of_land_ownership": {"type": "string", "description": "Date of land ownership (YYYY-MM-DD format)"},
            "bank_account": {"type": "boolean", "description": "Whether farmer has bank account"},
            "account_number": {"type": "string", "description": "Bank account number"},
            "ifsc_code": {"type": "string", "description": "Bank IFSC code"},
            "aadhaar_number": {"type": "string", "description": "12-digit Aadhaar number"},
            "aadhaar_linked": {"type": "boolean", "description": "Whether Aadhaar is linked to bank account"},
            "category": {"type": "string", "description": "Social category (general/sc/st/obc/minority/bpl)"}
        }
        
        # Context-aware conversation templates
        self.conversation_templates = {
            "greeting": self._create_greeting_template(),
            "natural_extraction": self._create_extraction_template(),
            "clarification": self._create_clarification_template(),
            "summary": self._create_summary_template()
        }
        
    def _create_greeting_template(self) -> ChatPromptTemplate:
        """Create a natural, conversational greeting template"""
        return ChatPromptTemplate.from_messages([
            ("system", """You are a helpful government officer assisting with PM-KISAN scheme applications. 
            You are having a natural, friendly conversation with a farmer to collect required information.
            
            PM-KISAN provides Rs 6000 per year to eligible farmers. You need to collect information naturally
            through conversation, not like a rigid form.
            
            Start with a warm greeting and explain the scheme briefly. Then begin collecting information
            in a natural, conversational way. Extract multiple pieces of information from each response
            when possible.
            
            Be helpful when users are confused about requirements. For example:
            - Land ownership types: "owned" (you own it), "leased" (you rent it), "sharecropping", "joint"
            - When someone says "I own the land", extract as "owned"
            - Be patient and explain things clearly
            
            IMPORTANT: Have a natural conversation, don't ask rigid questions one by one."""),
            
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
    
    def _create_extraction_template(self) -> ChatPromptTemplate:
        """Create template for natural language information extraction"""
        return ChatPromptTemplate.from_messages([
            ("system", """You are an expert at extracting structured information from natural conversation.
            
            Extract the following fields from the farmer's response:
            {required_fields}
            
            EXTRACTION RULES:
            1. Extract multiple fields from a single response when possible
            2. Use conversational context to understand implicit meanings
            3. Handle variations in language (e.g., "I own the land" -> land_ownership: "owned")
            4. Be confident about obvious extractions, less confident about ambiguous ones
            5. Don't ask for the same information twice if you already have it
            
            Already collected: {collected_fields}
            
            Return JSON format:
            {{
                "extracted_fields": {{
                    "field_name": {{
                        "value": "extracted_value",
                        "confidence": "high/medium/low",
                        "source_text": "relevant part of user input"
                    }}
                }},
                "needs_clarification": ["field_name1", "field_name2"],
                "conversation_response": "Natural response to continue conversation"
            }}"""),
            
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "User input: {input}"),
        ])
    
    def _create_clarification_template(self) -> ChatPromptTemplate:
        """Create template for asking clarifying questions naturally"""
        return ChatPromptTemplate.from_messages([
            ("system", """You are a helpful government officer who needs to clarify some information
            about the PM-KISAN application.
            
            Ask for clarification about: {clarification_fields}
            
            Be natural and conversational. Don't be rigid. Explain why you need the information
            and provide examples when helpful.
            
            Examples:
            - "Could you help me understand your land situation better? Do you own the land, 
              lease it from someone, or have some other arrangement?"
            - "I need your exact age for the application. How old are you?"
            - "For the banking details, what's your account number and IFSC code?"
            
            Current conversation context: {conversation_context}
            Already collected: {collected_fields}"""),
            
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
    
    def _create_summary_template(self) -> ChatPromptTemplate:
        """Create template for summarizing collected information"""
        return ChatPromptTemplate.from_messages([
            ("system", """You are summarizing the information collected for a PM-KISAN application.
            
            Collected information: {collected_fields}
            
            Create a natural summary and ask the user to confirm if everything is correct.
            Then proceed with eligibility check.
            
            If any required information is missing, ask for it naturally."""),
            
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
    
    async def initialize_conversation(self, scheme_code: str = "pm-kisan") -> Tuple[str, ConversationState]:
        """Initialize a new conversation with intelligent context setup"""
        try:
            # Load scheme data
            async with self.efr_client as client:
                scheme_data = await client.get_scheme(scheme_code)
                self.scheme_cache[scheme_code] = scheme_data
            
            # Create conversation state
            state = ConversationState()
            state.conversation_flow_stage = "greeting"
            
            # Generate natural greeting
            template = self.conversation_templates["greeting"]
            
            # Use a more natural greeting approach
            greeting_prompt = template.format_prompt(
                chat_history=[],
                input="Hello"
            )
            
            initial_response = """Namaste! I'm here to help you with the PM-KISAN scheme. 
            This is a great government program that provides Rs 6000 per year to eligible farmers 
            like yourself to support your agricultural activities.

            I'd like to have a friendly conversation to understand your farming situation and 
            see if you qualify for this scheme. Let me start by getting to know you better.
            
            Could you tell me your name and a bit about your farming background?"""
            
            state.conversation_context = "Started PM-KISAN conversation with greeting"
            return initial_response, state
            
        except Exception as e:
            logger.error(f"Error initializing conversation: {e}")
            return "I apologize, but I'm having trouble starting the conversation. Please try again.", ConversationState()
    
    async def process_user_input(self, user_input: str, state: ConversationState, 
                               chat_history: List[BaseMessage]) -> Tuple[str, ConversationState]:
        """Process user input with intelligent natural language understanding"""
        
        # Update conversation context
        state.conversation_context += f"\nUser: {user_input}"
        
        # Extract information using natural language processing
        extracted_data = await self._extract_information(user_input, state, chat_history)
        
        # Update state with extracted information
        self._update_state_with_extractions(state, extracted_data)
        
        # Generate appropriate response based on conversation stage
        response = await self._generate_contextual_response(extracted_data, state, chat_history)
        
        # Update conversation flow stage
        self._update_conversation_stage(state)
        
        return response, state
    
    async def _extract_information(self, user_input: str, state: ConversationState, 
                                 chat_history: List[BaseMessage]) -> Dict[str, Any]:
        """Extract structured information from natural language using LLM"""
        
        try:
            # Create extraction prompt with context
            template = self.conversation_templates["natural_extraction"]
            
            # Format required fields for extraction
            required_fields_str = "\n".join([
                f"- {field}: {info['description']}" 
                for field, info in self.required_fields.items()
                if field not in state.collected_fields
            ])
            
            collected_fields_str = "\n".join([
                f"- {field}: {extracted.value}" 
                for field, extracted in state.collected_fields.items()
            ])
            
            extraction_prompt = template.format_prompt(
                required_fields=required_fields_str,
                collected_fields=collected_fields_str,
                chat_history=chat_history[-5:],  # Keep recent context
                input=user_input
            )
            
            # Use LLM to extract information using LM Studio client
            import requests
            
            # Create a more structured extraction prompt
            extraction_system_prompt = """You are an expert at extracting structured information from natural language. 
            
Your task is to extract specific information from user input and return it as valid JSON.

IMPORTANT: Only return a valid JSON object. Do not include any explanation or additional text.

The JSON should contain only the fields that you can extract from the user's input.
Use these exact field names: name, age, gender, phone_number, state, district, sub_district_block, village, land_size_acres, land_ownership, date_of_land_ownership, bank_account, account_number, ifsc_code, aadhaar_number, aadhaar_linked, category

Example response format:
{"name": "John Doe", "age": 35, "state": "Kerala"}

If no information can be extracted, return: {}"""

            user_extraction_prompt = f"""Extract information from this user input: "{user_input}"

Available fields to extract:
{required_fields_str}

Already collected:
{collected_fields_str}

Return only valid JSON:"""
            
            messages = [
                {"role": "system", "content": extraction_system_prompt},
                {"role": "user", "content": user_extraction_prompt}
            ]
            
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.1,  # Very low temperature for structured extraction
                "max_tokens": 200,
                "stream": False
            }
            
            response = requests.post(
                "http://localhost:1234/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                llm_response = result["choices"][0]["message"]["content"]
                
                # Parse LLM response to extract structured data
                extracted_data = self._parse_llm_extraction(llm_response, user_input, state)
                return extracted_data
            else:
                logger.error(f"LLM extraction failed: {response.status_code}")
                # Fallback to simple extraction
                return self._simple_extraction_fallback(user_input, state)
                
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            # Fallback to simple extraction
            return self._simple_extraction_fallback(user_input, state)
    
    def _parse_llm_extraction(self, llm_response: str, user_input: str, state: ConversationState) -> Dict[str, Any]:
        """Parse LLM response to extract structured data"""
        
        try:
            import json
            import re
            
            # Clean up the response
            llm_response = llm_response.strip()
            
            # First try to parse the whole response as JSON
            try:
                parsed_data = json.loads(llm_response)
            except json.JSONDecodeError:
                # If that fails, try to find JSON in the response
                json_match = re.search(r'\{[^}]*\}', llm_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    parsed_data = json.loads(json_str)
                else:
                    # If no JSON found, return empty dict
                    parsed_data = {}
            
            # Validate and structure the extracted data
            extracted_fields = {}
            
            if isinstance(parsed_data, dict):
                for field, value in parsed_data.items():
                    if field in self.required_fields and field not in state.collected_fields:
                        # Skip empty or null values
                        if value and str(value).strip():
                            extracted_fields[field] = {
                                "value": value,
                                "confidence": "high",
                                "source_text": user_input
                            }
                        
            return extracted_fields
                
        except Exception as e:
            logger.error(f"Failed to parse LLM extraction: {e}")
            
        # If JSON parsing fails, fallback to simple extraction
        return self._simple_extraction_fallback(user_input, state)
    
    def _simple_extraction_fallback(self, user_input: str, state: ConversationState) -> Dict[str, Any]:
        """Simple fallback extraction when LLM fails"""
        
        import re
        
        extracted_fields = {}
        input_lower = user_input.lower()
        
        # Name extraction - improved patterns
        if "name" not in state.collected_fields:
            name_patterns = [
                r"(?:my name is|i am|i'm|name is|called)\s+([a-zA-Z\s]+)",
                r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # Capitalized words at start
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    if len(name) > 1 and name.replace(" ", "").isalpha():
                        extracted_fields["name"] = {
                            "value": name,
                            "confidence": "medium",
                            "source_text": user_input
                        }
                        break
        
        # Age extraction
        if "age" not in state.collected_fields:
            import re
            age_patterns = [
                r"(\d+)\s*(?:years?\s*old|yr|yrs)",
                r"age\s*is\s*(\d+)",
                r"i\s*am\s*(\d+)",
                r"(\d+)\s*years?"
            ]
            
            for pattern in age_patterns:
                match = re.search(pattern, input_lower)
                if match:
                    age = int(match.group(1))
                    if 18 <= age <= 120:
                        extracted_fields["age"] = {
                            "value": age,
                            "confidence": "high",
                            "source_text": user_input
                        }
                        break
        
        # Gender extraction
        if "gender" not in state.collected_fields:
            if any(word in input_lower for word in ["male", "man", "boy"]):
                extracted_fields["gender"] = {
                    "value": "male",
                    "confidence": "high",
                    "source_text": user_input
                }
            elif any(word in input_lower for word in ["female", "woman", "girl"]):
                extracted_fields["gender"] = {
                    "value": "female",
                    "confidence": "high",
                    "source_text": user_input
                }
        
        # Land ownership extraction
        if "land_ownership" not in state.collected_fields:
            if any(phrase in input_lower for phrase in ["i own", "my land", "own the land"]):
                extracted_fields["land_ownership"] = {
                    "value": "owned",
                    "confidence": "high",
                    "source_text": user_input
                }
            elif any(phrase in input_lower for phrase in ["lease", "rent", "rented"]):
                extracted_fields["land_ownership"] = {
                    "value": "leased",
                    "confidence": "high",
                    "source_text": user_input
                }
        
        # Phone number extraction
        if "phone_number" not in state.collected_fields:
            import re
            phone_pattern = r"(\d{10})"
            match = re.search(phone_pattern, user_input)
            if match:
                extracted_fields["phone_number"] = {
                    "value": match.group(1),
                    "confidence": "high",
                    "source_text": user_input
                }
        
        # Land size extraction
        if "land_size_acres" not in state.collected_fields:
            import re
            land_patterns = [
                r"(\d+\.?\d*)\s*(acres?|acre)",
                r"(\d+\.?\d*)\s*acre",
                r"(\d+\.?\d*)\s*hectare"
            ]
            
            for pattern in land_patterns:
                match = re.search(pattern, input_lower)
                if match:
                    size = float(match.group(1))
                    # Convert hectares to acres if needed
                    if "hectare" in match.group(0):
                        size *= 2.47  # 1 hectare = 2.47 acres
                    extracted_fields["land_size_acres"] = {
                        "value": size,
                        "confidence": "high",
                        "source_text": user_input
                    }
                    break
        
        # Location extraction (basic)
        location_fields = ["state", "district", "village", "sub_district_block"]
        for field in location_fields:
            if field not in state.collected_fields:
                # This would use more sophisticated NER in real implementation
                if field == "state" and any(state_name in input_lower for state_name in 
                    ["kerala", "karnataka", "tamil nadu", "andhra pradesh", "telangana", "maharashtra", 
                     "gujarat", "rajasthan", "punjab", "haryana", "uttar pradesh", "bihar", "west bengal"]):
                    for state_name in ["kerala", "karnataka", "tamil nadu", "andhra pradesh", "telangana", 
                                     "maharashtra", "gujarat", "rajasthan", "punjab", "haryana", 
                                     "uttar pradesh", "bihar", "west bengal"]:
                        if state_name in input_lower:
                            extracted_fields[field] = {
                                "value": state_name.title(),
                                "confidence": "high",
                                "source_text": user_input
                            }
                            break
        
        return extracted_fields
    
    def _generate_extraction_response(self, extracted_fields: Dict[str, Any], state: ConversationState) -> str:
        """Generate natural response based on extracted information"""
        
        if not extracted_fields:
            return "I'd like to know more about you. Could you tell me your name, age, and where you're from?"
        
        # Acknowledge what was extracted
        acknowledgments = []
        for field, data in extracted_fields.items():
            if field == "name":
                acknowledgments.append(f"Nice to meet you, {data['value']}!")
            elif field == "age":
                acknowledgments.append(f"I see you're {data['value']} years old")
            elif field == "land_ownership":
                acknowledgments.append(f"Great that you {data['value']} your land")
            elif field == "land_size_acres":
                acknowledgments.append(f"So you have {data['value']} acres of land")
        
        response = " ".join(acknowledgments)
        
        # Ask for next needed information
        missing_fields = set(self.required_fields.keys()) - set(state.collected_fields.keys()) - set(extracted_fields.keys())
        
        if missing_fields:
            # Prioritize important fields
            priority_fields = ["name", "age", "phone_number", "state", "district", "village", "land_size_acres"]
            next_field = None
            
            for field in priority_fields:
                if field in missing_fields:
                    next_field = field
                    break
            
            if not next_field:
                next_field = list(missing_fields)[0]
            
            # Ask for next field naturally
            if next_field == "phone_number":
                response += " What's your mobile phone number?"
            elif next_field == "state":
                response += " Which state do you live in?"
            elif next_field == "district":
                response += " What's your district?"
            elif next_field == "village":
                response += " And which village are you from?"
            elif next_field == "land_size_acres":
                response += " How much land do you have in acres?"
            elif next_field == "bank_account":
                response += " Do you have a bank account?"
            elif next_field == "aadhaar_number":
                response += " Could you provide your Aadhaar number?"
            else:
                response += f" I also need to know about your {next_field.replace('_', ' ')}."
        
        return response if response else "Thank you for that information. Let me ask you about a few more details."
    
    def _update_state_with_extractions(self, state: ConversationState, extracted_data: Dict[str, Any]):
        """Update conversation state with extracted information"""
        
        for field_name, field_data in extracted_data.get("extracted_fields", {}).items():
            if field_name not in state.collected_fields:  # Don't overwrite existing data
                state.collected_fields[field_name] = ExtractedField(
                    field_name=field_name,
                    value=field_data["value"],
                    confidence=ExtractionConfidence(field_data["confidence"]),
                    source_text=field_data["source_text"]
                )
        
        # Update pending clarifications
        state.pending_clarifications = extracted_data.get("needs_clarification", [])
        state.last_extraction_attempt = datetime.now()
    
    async def _generate_contextual_response(self, extracted_data: Dict[str, Any], 
                                          state: ConversationState, 
                                          chat_history: List[BaseMessage]) -> str:
        """Generate contextual response using LLM"""
        
        try:
            import json
            import requests
            
            # Create context for LLM response generation
            missing_fields = self.get_missing_fields(state)
            completion_percentage = self.get_completion_percentage(state)
            
            # Create prompt for contextual response
            context_prompt = f"""
You are a friendly and helpful assistant for the PM-KISAN scheme. 
You're having a natural conversation with a farmer to collect their information.

Current conversation progress: {completion_percentage:.0f}% complete

Information extracted from user's last message:
{json.dumps(extracted_data, indent=2) if extracted_data else "No information extracted"}

Already collected information:
{json.dumps({k: v.value for k, v in state.collected_fields.items()}, indent=2) if state.collected_fields else "None"}

Still need to collect: {missing_fields}

Generate a natural, conversational response that:
1. Acknowledges any information just provided
2. Asks for the next needed information naturally
3. Provides helpful context when needed (e.g., explain land ownership types if user seems confused)
4. Maintains a friendly, helpful tone
5. Is concise but warm

Response:"""
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant for government scheme applications. Be conversational and friendly."},
                {"role": "user", "content": context_prompt}
            ]
            
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 200,
                "stream": False
            }
            
            response = requests.post(
                "http://localhost:1234/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                logger.error(f"LLM response generation failed: {response.status_code}")
                return self._generate_extraction_response(extracted_data, state)
                
        except Exception as e:
            logger.error(f"LLM response generation error: {e}")
            return self._generate_extraction_response(extracted_data, state)
    
    def _update_conversation_stage(self, state: ConversationState):
        """Update the conversation flow stage based on current state"""
        
        total_required = len(self.required_fields)
        collected_count = len(state.collected_fields)
        
        if collected_count == 0:
            state.conversation_flow_stage = "greeting"
        elif collected_count < total_required * 0.7:
            state.conversation_flow_stage = "data_collection"
        elif collected_count < total_required:
            state.conversation_flow_stage = "clarification"
        else:
            state.conversation_flow_stage = "summary"
    
    def get_missing_fields(self, state: ConversationState) -> List[str]:
        """Get list of missing required fields"""
        return [field for field in self.required_fields.keys() if field not in state.collected_fields]
    
    def get_completion_percentage(self, state: ConversationState) -> float:
        """Get percentage of required fields collected"""
        return (len(state.collected_fields) / len(self.required_fields)) * 100
    
    async def generate_summary(self, state: ConversationState) -> str:
        """Generate summary of collected information"""
        
        if not state.collected_fields:
            return "No information has been collected yet."
        
        summary_parts = ["Here's the information I've collected so far:\n"]
        
        for field_name, extracted in state.collected_fields.items():
            field_desc = self.required_fields.get(field_name, {}).get("description", field_name)
            summary_parts.append(f"• {field_desc}: {extracted.value}")
        
        missing_fields = self.get_missing_fields(state)
        if missing_fields:
            summary_parts.append(f"\nStill need: {', '.join(missing_fields)}")
        
        completion = self.get_completion_percentage(state)
        summary_parts.append(f"\nCompletion: {completion:.1f}%")
        
        return "\n".join(summary_parts) 