import asyncio
import json
import re
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Tuple, Optional
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..scheme.efr_integration import EFRSchemeClient

class ConversationStage(Enum):
    BASIC_INFO = "basic_info"
    EXCLUSION_CRITERIA = "exclusion_criteria"
    FAMILY_MEMBERS = "family_members"
    SPECIAL_PROVISIONS = "special_provisions"
    COMPLETED = "completed"

@dataclass
class ExtractedField:
    value: Any
    confidence: float
    source: str
    timestamp: datetime
    raw_input: str

@dataclass
class ConversationState:
    collected_data: Dict[str, ExtractedField] = field(default_factory=dict)
    exclusion_data: Dict[str, Any] = field(default_factory=dict)
    family_members: List[Dict[str, Any]] = field(default_factory=list)
    special_provisions: Dict[str, Any] = field(default_factory=dict)
    chat_history: List[Any] = field(default_factory=list)
    stage: ConversationStage = ConversationStage.BASIC_INFO
    debug_log: List[str] = field(default_factory=list)
    user_input: str = ""
    response: str = ""
    turn_count: int = 0

class SimpleLangGraphEngine:
    """Simple, robust conversational engine with dual prompts and retries"""
    
    def __init__(self, llm_url: str = "http://localhost:1234/v1"):
        self.llm = ChatOpenAI(
            openai_api_base=llm_url,
            openai_api_key="not-needed",
            model_name="qwen2.5-7b-instruct",
            temperature=0.3,
            max_tokens=1024
        )
        self.efr_client = EFRSchemeClient()
        
        # Scheme data
        self.scheme_definition: Dict[str, Any] = {}
        self.required_fields: List[str] = []
        self.exclusion_fields: List[str] = []
        self.special_provision_fields: List[str] = []
        self.family_member_structure: Dict[str, Any] = {}
        
        # Retry settings
        self.max_retries = 3
        self.retry_delay = 1.0
        
        self.graph = None

    async def initialize(self, scheme_code: str = "pm-kisan"):
        """Initialize with scheme data from server"""
        try:
            async with self.efr_client as client:
                scheme_resp = await client._fetch_with_retry(f"http://localhost:8002/schemes/{scheme_code.upper()}")
                if not scheme_resp or not scheme_resp.get("success"):
                    raise RuntimeError(f"Failed to fetch scheme details for {scheme_code.upper()}")
                
                self.scheme_definition = scheme_resp.get("data", {})
                
                # Get all field lists from scheme
                self.required_fields = self.scheme_definition.get("validation_rules", {}).get("required_for_eligibility", [])
                self.exclusion_fields = [
                    "is_constitutional_post_holder", "is_political_office_holder", "is_government_employee", 
                    "is_income_tax_payer", "is_professional", "is_nri", "is_pensioner"
                ]
                # Check if family members are required - they are always required for PM-KISAN
                self.family_member_structure = {
                    "relation": {"type": "enum", "values": ["husband", "wife", "son", "daughter", "father", "mother", "brother", "sister", "other"]},
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                    "gender": {"type": "enum", "values": ["male", "female", "other"]}
                }
                self.special_provision_fields = list(self.scheme_definition.get("data_model", {}).get("special_provisions", {}).keys())
                
                print(f"✅ Loaded scheme: {len(self.required_fields)} required, {len(self.exclusion_fields)} exclusions, {len(self.special_provision_fields)} special")
                
        except Exception as e:
            print(f"❌ Failed to initialize: {e}")
            raise
        
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build simple state graph"""
        g = StateGraph(ConversationState)
        
        g.add_node("BASIC_INFO", self._basic_info_node)
        g.add_node("EXCLUSION_CRITERIA", self._exclusion_node)
        g.add_node("FAMILY_MEMBERS", self._family_node)
        g.add_node("SPECIAL_PROVISIONS", self._special_node)
        g.add_node("COMPLETED", self._completed_node)
        
        # Correct flow: BASIC_INFO -> FAMILY_MEMBERS -> EXCLUSION_CRITERIA -> SPECIAL_PROVISIONS
        g.add_conditional_edges(
            "BASIC_INFO",
            self._basic_info_done,
            {"FAMILY_MEMBERS": "FAMILY_MEMBERS", "END": END}
        )
        
        g.add_conditional_edges(
            "FAMILY_MEMBERS",
            self._family_done,
            {"EXCLUSION_CRITERIA": "EXCLUSION_CRITERIA", "END": END}
        )
        
        g.add_conditional_edges(
            "EXCLUSION_CRITERIA",
            self._exclusion_done,
            {"SPECIAL_PROVISIONS": "SPECIAL_PROVISIONS", "COMPLETED": "COMPLETED", "END": END}
        )
        
        print(f"🔍 DEBUG: Graph edges configured - BASIC_INFO -> FAMILY_MEMBERS -> EXCLUSION_CRITERIA -> SPECIAL_PROVISIONS")
        
        g.add_conditional_edges(
            "SPECIAL_PROVISIONS",
            self._special_done,
            {"COMPLETED": "COMPLETED", "END": END}
        )
        
        g.add_edge("COMPLETED", END)
        g.set_entry_point("BASIC_INFO")
        
        return g.compile()

    async def chat(self, user_input: str, state: ConversationState = None) -> Tuple[str, ConversationState]:
        """Main chat interface with retries"""
        if state is None:
            state = ConversationState()
        
        state.user_input = user_input
        state.turn_count += 1
        
        # If no user input, we need to ask a question proactively
        if not user_input.strip():
            # Handle different stages
            if state.stage == ConversationStage.BASIC_INFO:
                return await self._handle_empty_input_basic_info(state)
            elif state.stage == ConversationStage.EXCLUSION_CRITERIA:
                return await self._handle_empty_input_exclusion(state)
            elif state.stage == ConversationStage.FAMILY_MEMBERS:
                return await self._handle_empty_input_family(state)
            elif state.stage == ConversationStage.SPECIAL_PROVISIONS:
                return await self._handle_empty_input_special(state)
            else:
                return "Please provide some input or use /help for commands.", state
        
        # Run with retries
        for attempt in range(self.max_retries):
            try:
                config = {"configurable": {"thread_id": "default"}}
                result = await self.graph.ainvoke(state, config)
                
                if isinstance(result, dict):
                    for key, value in result.items():
                        if hasattr(state, key):
                            setattr(state, key, value)
                    updated_state = state
                else:
                    updated_state = result
                
                return updated_state.response if hasattr(updated_state, 'response') else "Sorry, no response generated.", updated_state
                
            except Exception as e:
                print(f"⚠️ Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return f"❌ Sorry, I encountered an error after {self.max_retries} attempts. Please try again.", state

    async def _handle_empty_input_basic_info(self, state: ConversationState) -> Tuple[str, ConversationState]:
        """Handle empty input in basic info stage"""
        missing_fields = [f for f in self.required_fields if f not in state.collected_data]
        
        if not missing_fields:
            state.response = "✅ Great! All basic information collected. Now let's collect information about your family members."
            # Don't manually set stage - let the graph transition handle it
            return state.response, state
        
        target_field = missing_fields[0]
        question = await self._ask_for_field_with_retries(target_field, state)
        state.response = question
        return question, state

    async def _handle_empty_input_exclusion(self, state: ConversationState) -> Tuple[str, ConversationState]:
        """Handle empty input in exclusion stage"""
        print(f"🔍 DEBUG: Handling empty input in exclusion stage")
        print(f"🔍 DEBUG: Current stage: {state.stage}")
        print(f"🔍 DEBUG: Missing exclusions: {[f for f in self.exclusion_fields if f not in state.exclusion_data]}")
        
        missing_exclusions = [f for f in self.exclusion_fields if f not in state.exclusion_data]
        
        if not missing_exclusions:
            state.response = "✅ All eligibility questions answered! Moving to special provisions section."
            # Don't manually set stage - let the graph transition handle it
            return state
        
        # If no missing exclusions but we have user input, it might be for conditional fields
        if not missing_exclusions and state.user_input and state.user_input.strip():
            # Check if we're waiting for government post
            if ("is_government_employee" in state.exclusion_data and 
                state.exclusion_data["is_government_employee"] is True and
                "government_post" not in state.exclusion_data):
                
                government_post = state.user_input.strip()
                state.exclusion_data["government_post"] = government_post
                
                # Simply record the data - exemption logic is handled by Prolog rules
                state.response = f"✅ Recorded government post: {government_post}"
                
                # Check if all exclusions are complete
                missing_exclusions = [f for f in self.exclusion_fields if f not in state.exclusion_data]
                if not missing_exclusions:
                    state.response += "\n\n✅ All eligibility questions answered! Moving to special provisions section."
                    # Don't manually set stage - let the graph transition handle it
                else:
                    # Automatically ask next question
                    next_question = await self._get_next_exclusion_question(state)
                    if next_question:
                        state.response += f"\n\n{next_question}"
                return state
            
            elif ("is_pensioner" in state.exclusion_data and 
                  state.exclusion_data["is_pensioner"] is True and
                  "government_post" not in state.exclusion_data):
                
                government_post = state.user_input.strip()
                state.exclusion_data["government_post"] = government_post
                
                # Always ask for monthly pension amount after recording government post
                # We'll determine exemption after we have both pieces of information
                state.response = f"✅ Recorded government post: {government_post}"
                question = await self._ask_pension_amount_question(state)
                state.response += f"\n\n{question}"
                return state
            
            # If we have user input but don't know what to do with it, use LLM to respond intelligently
            else:
                try:
                    prompt = f"""You are a friendly government officer helping with PM-KISAN application.

CURRENT SITUATION:
- All exclusion questions have been answered
- User provided input: "{state.user_input}"
- Current stage: Exclusion Criteria
- Next stage: Family Members

TASK: Respond intelligently to the user's input and guide them to the next stage.

INSTRUCTIONS:
- Be friendly and conversational
- Acknowledge their input appropriately
- Explain that all eligibility questions are complete
- Guide them to the next section (Family Members)
- Keep it simple and natural

EXAMPLE: "I understand you said '{state.user_input}'. All eligibility questions have been completed successfully! Now let's move to the next section where we'll collect information about your family members."

Return only the response, no additional text."""

                    response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                    state.response = response.content.strip()
                    # Don't manually set stage - let the graph transition handle it
                    return state
                except Exception as e:
                    print(f"⚠️ LLM response failed: {e}")
                    state.response = f"I understand you said '{state.user_input}'. All eligibility questions are complete! Moving to special provisions section."
                    # Don't manually set stage - let the graph transition handle it
                    return state
        
        # Check for conditional follow-up questions
        if target_field == "is_government_employee" and target_field in state.exclusion_data and state.exclusion_data[target_field] is True:
            if "government_post" not in state.exclusion_data:
                question = await self._ask_government_post_question(state)
                state.response = question
                return question, state
        
        if target_field == "is_pensioner" and target_field in state.exclusion_data and state.exclusion_data[target_field] is True:
            if "monthly_pension" not in state.exclusion_data:
                question = await self._ask_pension_amount_question(state)
                state.response = question
                return question, state
        
        # Ask the main exclusion question
        question = await self._ask_exclusion_question_with_llm(target_field, state)
        state.response = question
        print(f"🔍 DEBUG: Generated question: {question}")
        return question, state

    async def _handle_empty_input_family(self, state: ConversationState) -> Tuple[str, ConversationState]:
        """Handle empty input in family stage"""
        if not self.family_member_structure:
            state.stage = ConversationStage.SPECIAL_PROVISIONS
            state.response = "✅ No family member information required. Moving to next section."
            return state.response, state
        
        question = await self._ask_family_question_with_llm(state)
        state.response = question
        return state.response, state

    async def _handle_empty_input_special(self, state: ConversationState) -> Tuple[str, ConversationState]:
        """Handle empty input in special provisions stage"""
        if not self.special_provision_fields:
            state.stage = ConversationStage.COMPLETED
            state.response = "✅ No special provisions required. Application complete!"
            return state.response, state
        
        missing_specials = [f for f in self.special_provision_fields if f not in state.special_provisions]
        
        if not missing_specials:
            state.stage = ConversationStage.COMPLETED
            state.response = "✅ All special provisions collected. Application complete!"
            return state.response, state
        
        target_field = missing_specials[0]
        state.response = f"Please provide information about {target_field.replace('_', ' ')}."
        return state.response, state

    async def _basic_info_node(self, state: ConversationState) -> ConversationState:
        """Simple basic info collection with dual prompts and retries"""
        state.stage = ConversationStage.BASIC_INFO
        
        # Get next missing field
        missing_fields = [f for f in self.required_fields if f not in state.collected_data]
        
        if not missing_fields:
            state.response = "✅ Great! All basic information collected. Now let's collect information about your family members."
            # Don't manually set stage - let the graph transition handle it
            # Automatically ask first family question
            if self.family_member_structure:
                family_question = await self._ask_family_question_with_llm(state)
                state.response += f"\n\n{family_question}"
            return state
        
        target_field = missing_fields[0]
        next_field = missing_fields[1] if len(missing_fields) > 1 else "completion"
        
        print(f"🔍 DEBUG: Target field: {target_field}")
        print(f"🔍 DEBUG: User input: '{state.user_input}'")
        
        # If user provided input, validate it
        if state.user_input and state.user_input.strip():
            validation_result = await self._validate_field_with_retries(target_field, state.user_input, next_field)
            
            if validation_result.get("is_valid", False):
                # Store the data
                extracted_value = validation_result.get("extracted_value")
                state.collected_data[target_field] = ExtractedField(
                    value=extracted_value, confidence=0.95, source="llm_validation", 
                    timestamp=datetime.now(), raw_input=state.user_input
                )
                print(f"✅ STORED: {target_field} = {extracted_value}")
                
                # Ask for next field automatically
                if next_field != "completion":
                    next_question = await self._ask_for_field_with_retries(next_field, state)
                    state.response = f"✅ {validation_result.get('validation_message', 'Data recorded successfully')}.\n\n{next_question}"
                else:
                    # All basic info complete, move to family
                    state.response = "✅ Great! All basic information collected. Now let's collect information about your family members."
                    # Don't manually set stage - let the graph transition handle it
                    # Automatically ask first family question
                    if self.family_member_structure:
                        family_question = await self._ask_family_question_with_llm(state)
                        state.response += f"\n\n{family_question}"
            else:
                # Ask for the same field again
                question = await self._ask_for_field_with_retries(target_field, state)
                state.response = f"❌ {validation_result.get('validation_message', 'Invalid data provided')}. Please try again.\n\n{question}"
        else:
            # First time asking for this field
            question = await self._ask_for_field_with_retries(target_field, state)
            state.response = question
        
        state.debug_log.append(f"BASIC_INFO T{state.turn_count}: Processed {target_field}")
        return state

    async def _ask_for_field_with_retries(self, field_name: str, state: ConversationState) -> str:
        """Ask for a field with retries"""
        for attempt in range(self.max_retries):
            try:
                # Field-specific prompts for clarity
                field_prompts = {
                    "aadhaar_linked": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: AADHAAR LINKED TO BANK ACCOUNT

PROGRESS: {progress}/{total} fields collected

TASK: Ask the user if their Aadhaar number is linked to their bank account.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly: "Is your Aadhaar number linked to your bank account?"
- Explain this is required for direct benefit transfer
- Keep it simple

EXAMPLE: "Is your Aadhaar number linked to your bank account? This is required for direct benefit transfer of the PM-KISAN amount."

Return only the question, no additional text.""",
                    
                    "category": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: SOCIAL CATEGORY

PROGRESS: {progress}/{total} fields collected

TASK: Ask the user for their social category as per government records.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly for their social category
- Explain this is for government records
- Provide the options: general, sc, st, obc, minority, bpl
- Keep it simple

EXAMPLE: "What is your social category? Please choose from: general, sc (Scheduled Caste), st (Scheduled Tribe), obc (Other Backward Class), minority, or bpl (Below Poverty Line)."

Return only the question, no additional text.""",
                    
                    "land_ownership": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: LAND OWNERSHIP TYPE

PROGRESS: {progress}/{total} fields collected

TASK: Ask the user about their land ownership arrangement.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly about their land ownership type
- Explain the options: owned (you own it), leased (you rent it), sharecropping (you share crops), joint (shared with family), institutional (government/trust land)
- Keep it simple

EXAMPLE: "What type of land ownership do you have? Is it owned (you own it), leased (you rent it), sharecropping (you share crops), joint (shared with family), or institutional (government/trust land)?"

Return only the question, no additional text.""",
                    
                    "bank_account": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: BANK ACCOUNT STATUS

PROGRESS: {progress}/{total} fields collected

TASK: Ask the user if they have a bank account (yes/no question).

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly: "Do you have a bank account?"
- Explain this is for direct benefit transfer
- Keep it simple

EXAMPLE: "Do you have a bank account? This is needed for direct benefit transfer of the PM-KISAN amount."

Return only the question, no additional text.""",
                    
                    "account_number": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: BANK ACCOUNT NUMBER

PROGRESS: {progress}/{total} fields collected

TASK: Ask the user for their bank account number.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly for the account number
- Mention this is for direct benefit transfer
- Keep it simple

EXAMPLE: "What is your bank account number? This is needed to transfer the PM-KISAN amount directly to your account."

Return only the question, no additional text.""",
                    
                    "ifsc_code": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: IFSC CODE

PROGRESS: {progress}/{total} fields collected

TASK: Ask the user for their bank's IFSC code.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly for the IFSC code
- Explain this identifies the bank branch
- Keep it simple

EXAMPLE: "What is your bank's IFSC code? This identifies your bank branch for the transfer."

Return only the question, no additional text."""
                }
                
                if field_name in field_prompts:
                    prompt = field_prompts[field_name].format(
                        progress=len(state.collected_data),
                        total=len(self.required_fields)
                    )
                else:
                    prompt = f"""You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: {field_name.replace('_', ' ').upper()}

PROGRESS: {len(state.collected_data)}/{len(self.required_fields)} fields collected

TASK: Ask the user to provide their {field_name.replace('_', ' ')} information.

INSTRUCTIONS:
- Be friendly and conversational
- Explain what you need clearly
- Provide examples if helpful
- Keep it simple and natural

EXAMPLE: "Could you please tell me your {field_name.replace('_', ' ')}?"

Return only the question, no additional text."""

                response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                return response.content.strip()
                
            except Exception as e:
                print(f"⚠️ Ask attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return f"Could you please provide your {field_name.replace('_', ' ')}?"

    async def _validate_field_with_retries(self, field_name: str, user_input: str, next_field: str) -> Dict[str, Any]:
        """Validate field with retries and fallback"""
        for attempt in range(self.max_retries):
            try:
                prompt = f"""You are a data validation expert for PM-KISAN application.

FIELD TO VALIDATE: {field_name}
USER INPUT: "{user_input}"

TASK: Validate the user input and extract the correct value.

VALIDATION RULES:
- Accept any reasonable input that could be valid for this field
- Be flexible and understanding
- Convert to appropriate format if needed
- If unclear, ask for clarification rather than reject

DATA TYPES AND ENUMS (from EFR models):
- name: string (any name format is fine)
- age: integer (any reasonable age 18-120)
- gender: string (male/female/other)
- phone_number: string (any phone number format)
- state/district/village: string (any location name)
- land_size_acres: float (any decimal number)
- land_ownership: enum (owned/leased/sharecropping/joint/institutional/unknown)
- date_of_land_ownership: string (any date format, convert to DD/MM/YYYY)
- bank_account: boolean (true if user has account, false if not)
- account_number: string (any account number format - varies by bank)
- ifsc_code: string (any IFSC code format - varies by bank)
- aadhaar_number: string (any 12-digit number)
- aadhaar_linked: boolean (true if Aadhaar linked to bank account)
- category: enum (general/sc/st/obc/minority/bpl)

SPECIAL RULES FOR SPECIFIC FIELDS:
- land_ownership: Accept "owned", "lease", "leased", "sharecropping", "joint", "institutional", "unknown"
- aadhaar_linked: Accept "yes", "no", "linked", "not linked", or any indication of Aadhaar-bank linking
- category: Accept "general", "sc", "st", "obc", "minority", "bpl" (case insensitive)
- bank_account: Accept "yes", "no", account numbers, or any indication of having an account
- account_number: Accept ANY account number format (different banks have different formats)
- ifsc_code: Accept ANY IFSC code format (different banks have different formats)

EXAMPLES:
- "raazi faisal" for name → valid, extract as "Raazi Faisal"
- "555501167757" for account_number → valid, extract as "555501167757"
- "FDRL00005555" for ifsc_code → valid, extract as "FDRL00005555"
- "3 june 2010" for date → valid, extract as "03/06/2010"
- "owned" for land_ownership → valid, extract as "owned"
- "yes" for aadhaar_linked → valid, extract as true
- "general" for category → valid, extract as "general"
- "sc" for category → valid, extract as "sc"
- "555501167757" for bank_account → valid, extract as true (has account)

Return ONLY a JSON object:
{{
    "is_valid": true/false,
    "extracted_value": "the extracted value",
    "validation_message": "brief explanation",
    "next_field": "{next_field}"
}}"""

                response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    # Fallback: accept the input as-is
                    return {
                        "is_valid": True,
                        "extracted_value": user_input.strip(),
                        "validation_message": "Data accepted",
                        "next_field": next_field
                    }
                    
            except Exception as e:
                print(f"⚠️ Validation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    # Final fallback: accept the input
                    return {
                        "is_valid": True,
                        "extracted_value": user_input.strip(),
                        "validation_message": "Data accepted (fallback)",
                        "next_field": next_field
                    }

    async def _validate_exclusion_with_retries(self, field_name: str, user_input: str) -> Dict[str, Any]:
        """Validate exclusion field with retries"""
        for attempt in range(self.max_retries):
            try:
                prompt = f"""You are a data validation expert for PM-KISAN eligibility questions.

FIELD TO VALIDATE: {field_name}
USER INPUT: "{user_input}"

TASK: Validate the user input and extract a clear yes/no answer.

VALIDATION RULES:
- Only accept clear yes/no answers
- Be strict about yes/no validation
- Convert various forms of yes/no to boolean
- If unclear, mark as invalid and ask for clarification

ACCEPTED YES ANSWERS: yes, y, true, correct, yeah, yep, si, haan, han
ACCEPTED NO ANSWERS: no, n, false, nope, nahi, nahin

EXAMPLES:
- "yes" → valid, extract as true
- "no" → valid, extract as false  
- "okay let's begin" → invalid, not a yes/no answer
- "I am not" → valid, extract as false
- "I don't have" → valid, extract as false
- "maybe" → invalid, not clear yes/no

Return ONLY a JSON object:
{{
    "is_valid": true/false,
    "extracted_value": true/false (only if is_valid is true),
    "validation_message": "brief explanation"
}}"""

                response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    # Fallback: strict pattern matching
                    user_lower = user_input.lower().strip()
                    if user_lower in ["yes", "y", "true", "correct", "yeah", "yep", "si", "haan", "han"]:
                        return {"is_valid": True, "extracted_value": True, "validation_message": "Understood as yes"}
                    elif user_lower in ["no", "n", "false", "nope", "nahi", "nahin"]:
                        return {"is_valid": True, "extracted_value": False, "validation_message": "Understood as no"}
                    else:
                        return {"is_valid": False, "validation_message": "Please answer with a clear 'yes' or 'no'"}
                    
            except Exception as e:
                print(f"⚠️ Exclusion validation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    # Final fallback: strict pattern matching
                    user_lower = user_input.lower().strip()
                    if user_lower in ["yes", "y", "true", "correct", "yeah", "yep"]:
                        return {"is_valid": True, "extracted_value": True, "validation_message": "Understood as yes"}
                    elif user_lower in ["no", "n", "false", "nope"]:
                        return {"is_valid": True, "extracted_value": False, "validation_message": "Understood as no"}
                    else:
                        return {"is_valid": False, "validation_message": "Please answer with a clear 'yes' or 'no'"}

    async def _exclusion_node(self, state: ConversationState) -> ConversationState:
        """Simple exclusion criteria collection with conditional logic"""
        state.stage = ConversationStage.EXCLUSION_CRITERIA
        
        missing_exclusions = [f for f in self.exclusion_fields if f not in state.exclusion_data]
        
        print(f"🔍 DEBUG: Exclusion node - missing: {missing_exclusions}")
        print(f"🔍 DEBUG: Current exclusion data: {state.exclusion_data}")
        
        # Check for conditional fields that become mandatory when their parent field is True
        conditional_fields = []
        
        # If government employee is True, government_post becomes mandatory
        if ("is_government_employee" in state.exclusion_data and 
            state.exclusion_data["is_government_employee"] is True and
            "government_post" not in state.exclusion_data):
            conditional_fields.append("government_post")
        
        # If pensioner is True, both government_post and monthly_pension become mandatory
        if ("is_pensioner" in state.exclusion_data and 
            state.exclusion_data["is_pensioner"] is True):
            if "government_post" not in state.exclusion_data:
                conditional_fields.append("government_post")
            if "monthly_pension" not in state.exclusion_data:
                conditional_fields.append("monthly_pension")
        
        print(f"🔍 DEBUG: Conditional fields needed: {conditional_fields}")
        print(f"🔍 DEBUG: Is pensioner: {state.exclusion_data.get('is_pensioner')}")
        print(f"🔍 DEBUG: Has government_post: {'government_post' in state.exclusion_data}")
        print(f"🔍 DEBUG: Has monthly_pension: {'monthly_pension' in state.exclusion_data}")
        
        # If we have missing conditional fields, ask for the first one
        if conditional_fields:
            print(f"🔍 DEBUG: Processing conditional field: {conditional_fields[0]}")
            target_conditional = conditional_fields[0]
            if target_conditional == "government_post":
                if state.user_input and state.user_input.strip():
                    government_post = state.user_input.strip()
                    state.exclusion_data["government_post"] = government_post
                    state.response = f"✅ Recorded government post: {government_post}"
                    
                    # If this was for pensioner, ask for monthly pension next
                    if ("is_pensioner" in state.exclusion_data and 
                        state.exclusion_data["is_pensioner"] is True and
                        "monthly_pension" not in state.exclusion_data):
                        question = await self._ask_pension_amount_question(state)
                        state.response += f"\n\n{question}"
                    else:
                        # Check if all exclusions are complete
                        missing_exclusions = [f for f in self.exclusion_fields if f not in state.exclusion_data]
                        if not missing_exclusions:
                            state.response += "\n\n✅ All eligibility questions answered! Moving to next section."
                            # Don't set stage here - let the graph transition handle it
                        else:
                            # Automatically ask next question
                            next_question = await self._get_next_exclusion_question(state)
                            if next_question:
                                state.response += f"\n\n{next_question}"
                else:
                    question = await self._ask_government_post_question(state)
                    state.response = question
                return state
            elif target_conditional == "monthly_pension":
                print(f"🔍 DEBUG: Processing monthly_pension input: {state.user_input}")
                if state.user_input and state.user_input.strip():
                    try:
                        pension_amount = float(state.user_input.strip())
                        state.exclusion_data["monthly_pension"] = pension_amount
                        state.response = f"✅ Recorded monthly pension: Rs. {pension_amount}"
                        
                        print(f"🔍 DEBUG: Recorded monthly_pension: {pension_amount}")
                        
                        # Check if all exclusions are complete
                        missing_exclusions = [f for f in self.exclusion_fields if f not in state.exclusion_data]
                        print(f"🔍 DEBUG: Missing exclusions after recording pension: {missing_exclusions}")
                        print(f"🔍 DEBUG: family_member_structure: {self.family_member_structure}")
                        
                        if not missing_exclusions:
                            print(f"🔍 DEBUG: No missing exclusions, moving to family members")
                            state.response += "\n\n✅ All eligibility questions answered! Moving to family members section."
                        else:
                            # Automatically ask next question
                            next_question = await self._get_next_exclusion_question(state)
                            if next_question:
                                state.response += f"\n\n{next_question}"
                    except ValueError:
                        state.response = "❓ Please provide a valid number for your monthly pension amount in rupees."
                        question = await self._ask_pension_amount_question(state)
                        state.response += f"\n\n{question}"
                else:
                    question = await self._ask_pension_amount_question(state)
                    state.response = question
                return state
        
        # If no missing exclusions and no conditional fields, we're done
        if not missing_exclusions:
            print(f"🔍 DEBUG: No missing exclusions, conditional fields: {conditional_fields}")
            if not conditional_fields:
                print(f"🔍 DEBUG: Moving to next stage - no conditional fields needed")
                state.response = "✅ All eligibility questions answered! Moving to next section."
                # Don't manually set stage - let the graph transition handle it
                return state
            else:
                print(f"🔍 DEBUG: Still have conditional fields to process: {conditional_fields}")
        

        
        # If we get here, we have missing exclusions, so get the next target field
        target_field = missing_exclusions[0]
        print(f"🔍 DEBUG: Target field: {target_field}")
        print(f"🔍 DEBUG: User input: '{state.user_input}'")
        print(f"🔍 DEBUG: Processing regular exclusion field")
        
        # If user provided input, validate it
        if state.user_input and state.user_input.strip():
            validation_result = await self._validate_exclusion_with_retries(target_field, state.user_input)
            
            if validation_result.get("is_valid", False):
                # Store the data
                extracted_value = validation_result.get("extracted_value")
                state.exclusion_data[target_field] = extracted_value
                print(f"✅ STORED EXCLUSION: {target_field} = {extracted_value}")
                
                # Check for conditional follow-up questions
                if target_field == "is_government_employee" and extracted_value is True:
                    question = await self._ask_government_post_question(state)
                    state.response = f"✅ {validation_result.get('validation_message', 'Data recorded successfully')}.\n\n{question}"
                elif target_field == "is_pensioner" and extracted_value is True:
                    question = await self._ask_government_post_question(state)
                    state.response = f"✅ {validation_result.get('validation_message', 'Data recorded successfully')}.\n\n{question}"
                else:
                    # Check if all exclusions are complete
                    remaining_exclusions = [f for f in self.exclusion_fields if f not in state.exclusion_data]
                    if not remaining_exclusions:
                        state.response = f"✅ {validation_result.get('validation_message', 'Data recorded successfully')}.\n\n✅ All eligibility questions answered! Moving to special provisions section."
                    else:
                        # Ask next exclusion question
                        next_question = await self._get_next_exclusion_question(state)
                        if next_question:
                            state.response = f"✅ {validation_result.get('validation_message', 'Data recorded successfully')}.\n\n{next_question}"
                        else:
                            state.response = f"✅ {validation_result.get('validation_message', 'Data recorded successfully')}."
            else:
                # Ask for the same field again with validation message
                question = await self._ask_exclusion_question_with_llm(target_field, state)
                state.response = f"❌ {validation_result.get('validation_message', 'Invalid response')}. Please try again.\n\n{question}"
        else:
            # First time asking for this field
            question = await self._ask_exclusion_question_with_llm(target_field, state)
            state.response = question

        
        return state

    async def _get_next_exclusion_question(self, state: ConversationState) -> str:
        """Get the next exclusion question to ask automatically"""
        missing_exclusions = [f for f in self.exclusion_fields if f not in state.exclusion_data]
        
        if not missing_exclusions:
            return None  # No more questions
        
        next_field = missing_exclusions[0]
        return await self._ask_exclusion_question_with_llm(next_field, state)

    async def _ask_exclusion_question_with_llm(self, field_name: str, state: ConversationState) -> str:
        """Ask exclusion question using LLM for better phrasing"""
        for attempt in range(self.max_retries):
            try:
                exclusion_prompts = {
                    "is_constitutional_post_holder": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: CONSTITUTIONAL POST HOLDER STATUS

PROGRESS: {progress}/{total} exclusion questions answered

TASK: Ask the user if they are currently or have ever been a holder of constitutional posts.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly about constitutional posts
- Explain what constitutional posts are (President, Vice President, Governor, etc.)
- Keep it simple and natural

EXAMPLE: "Are you currently or have you ever been a holder of constitutional posts like President, Vice President, Governor, or similar positions? Please answer with yes or no."

Return only the question, no additional text.""",
                    
                    "is_political_office_holder": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: POLITICAL OFFICE HOLDER STATUS

PROGRESS: {progress}/{total} exclusion questions answered

TASK: Ask the user if they are currently or have ever been a political office holder.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly about political office positions
- Explain what political offices are (Minister, MP, MLA, Mayor, etc.)
- Keep it simple and natural

EXAMPLE: "Are you currently or have you ever been a political office holder like Minister, MP, MLA, Mayor, or District Panchayat Chairperson? Please answer with yes or no."

Return only the question, no additional text.""",
                    
                    "is_government_employee": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: GOVERNMENT EMPLOYMENT STATUS

PROGRESS: {progress}/{total} exclusion questions answered

TASK: Ask the user if they are currently a government employee.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly about government employment
- Explain this includes Central or State Government
- Keep it simple and natural

EXAMPLE: "Are you currently a government employee in Central or State Government? Please answer with yes or no."

Return only the question, no additional text.""",
                    
                    "is_pensioner": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: PENSIONER STATUS

PROGRESS: {progress}/{total} exclusion questions answered

TASK: Ask the user if they are a pensioner with high monthly pension.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly about pensioner status
- Mention the Rs. 10,000 monthly pension threshold
- Keep it simple and natural

EXAMPLE: "Are you a pensioner with monthly pension of Rs. 10,000 or more? Please answer with yes or no."

Return only the question, no additional text.""",
                    
                    "is_income_tax_payer": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: INCOME TAX PAYER STATUS

PROGRESS: {progress}/{total} exclusion questions answered

TASK: Ask the user if they are an income tax payer.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly about income tax payment
- Mention the last assessment year
- Keep it simple and natural

EXAMPLE: "Are you an income tax payer in the last assessment year? Please answer with yes or no."

Return only the question, no additional text.""",
                    
                    "is_professional": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: PROFESSIONAL STATUS

PROGRESS: {progress}/{total} exclusion questions answered

TASK: Ask the user if they are a practicing professional.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly about professional status
- Explain what professionals are (Doctors, Engineers, Lawyers, CAs, Architects)
- Keep it simple and natural

EXAMPLE: "Are you a professional like Doctor, Engineer, Lawyer, CA, or Architect who is currently practicing and registered? Please answer with yes or no."

Return only the question, no additional text.""",
                    
                    "is_nri": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: NRI STATUS

PROGRESS: {progress}/{total} exclusion questions answered

TASK: Ask the user if they are a Non-Resident Indian.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly about NRI status
- Explain this is as per Income Tax Act, 1961
- Keep it simple and natural

EXAMPLE: "Are you a Non-Resident Indian (NRI) as per Income Tax Act, 1961? Please answer with yes or no."

Return only the question, no additional text."""
                }
                
                if field_name in exclusion_prompts:
                    prompt = exclusion_prompts[field_name].format(
                        progress=len(state.exclusion_data),
                        total=len(self.exclusion_fields)
                    )
                else:
                    prompt = f"""You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: {field_name.replace('_', ' ').upper()}

PROGRESS: {len(state.exclusion_data)}/{len(self.exclusion_fields)} exclusion questions answered

TASK: Ask the user about their {field_name.replace('_', ' ')} status.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly about this status
- Keep it simple and natural
- Ask for yes/no answer

EXAMPLE: "Are you a {field_name.replace('_', ' ')}? Please answer with yes or no."

Return only the question, no additional text."""

                response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                return response.content.strip()
                
            except Exception as e:
                print(f"⚠️ Exclusion question attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return self._get_exclusion_question(field_name)

    async def _ask_government_post_question(self, state: ConversationState) -> str:
        """Ask for government post details"""
        for attempt in range(self.max_retries):
            try:
                # Check if this is being asked in pension context
                pension_context = (
                    "is_pensioner" in state.exclusion_data and 
                    state.exclusion_data["is_pensioner"] is True and
                    "monthly_pension" in state.exclusion_data and
                    state.exclusion_data["monthly_pension"] >= 10000
                )
                
                if pension_context:
                    prompt = """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: GOVERNMENT POST DETAILS

TASK: Ask the user for their government post when they were working.

INSTRUCTIONS:
- Be friendly and conversational
- Explain this is needed for complete information
- Keep it simple and natural

EXAMPLE: "What was your government post when you were working? Please provide the specific position or designation."

Return only the question, no additional text."""
                else:
                    prompt = """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: GOVERNMENT POST DETAILS

TASK: Ask the user for their specific government post/position.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly for their government post
- Explain this is needed for complete information
- Keep it simple and natural

EXAMPLE: "What is your government post or position? For example: Teacher, Officer, Clerk, Group D, MTS, etc."

Return only the question, no additional text."""

                response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                return response.content.strip()
                
            except Exception as e:
                print(f"⚠️ Government post question attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    # Check if this is pension context
                    pension_context = (
                        "is_pensioner" in state.exclusion_data and 
                        state.exclusion_data["is_pensioner"] is True and
                        "monthly_pension" in state.exclusion_data and
                        state.exclusion_data["monthly_pension"] >= 10000
                    )
                    
                    if pension_context:
                        return "What was your government post when you were working? Please provide the specific position or designation."
                    else:
                        return "What is your government post or position? (e.g., Teacher, Officer, Clerk, Group D, MTS)."

    async def _ask_pension_amount_question(self, state: ConversationState) -> str:
        """Ask for monthly pension amount"""
        for attempt in range(self.max_retries):
            try:
                prompt = """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: MONTHLY PENSION AMOUNT

TASK: Ask the user for their monthly pension amount.

INSTRUCTIONS:
- Be friendly and conversational
- Ask clearly for the monthly pension amount
- Explain this is needed for eligibility verification
- Ask for the amount in rupees
- Keep it simple and natural

EXAMPLE: "What is your monthly pension amount in rupees? Please provide the number."

Return only the question, no additional text."""

                response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                return response.content.strip()
                
            except Exception as e:
                print(f"⚠️ Pension amount question attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return "What is your monthly pension amount in rupees? Please provide the number."

    def _get_exclusion_question(self, field_name: str) -> str:
        """Get a clear question for exclusion criteria"""
        exclusion_questions = {
            "is_constitutional_post_holder": "Are you currently or have you ever been a holder of constitutional posts (like President, Vice President, Governor, etc.)? (yes/no)",
            "is_political_office_holder": "Are you currently or have you ever been a political office holder (like Minister, MP, MLA, Mayor, District Panchayat Chairperson)? (yes/no)",
            "is_government_employee": "Are you currently a government employee (Central or State Government)? (yes/no)",
            "is_pensioner": "Are you a pensioner with monthly pension of Rs. 10,000 or more? (yes/no)",
            "is_income_tax_payer": "Are you an income tax payer in the last assessment year? (yes/no)",
            "is_professional": "Are you a professional (Doctor, Engineer, Lawyer, CA, Architect) who is practicing and registered? (yes/no)",
            "is_nri": "Are you a Non-Resident Indian (NRI) as per Income Tax Act, 1961? (yes/no)"
        }
        
        return exclusion_questions.get(field_name, f"Are you a {field_name.replace('_', ' ')}? (yes/no)")

    async def _ask_family_question_with_llm(self, state: ConversationState) -> str:
        """Ask family member questions using LLM for better phrasing"""
        for attempt in range(self.max_retries):
            try:
                family_count = len(state.family_members)
                
                family_prompt = f"""You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: FAMILY MEMBER INFORMATION

FAMILY MEMBER STRUCTURE REQUIRED:
{self.family_member_structure}

PROGRESS: {family_count} family members already collected
{state.family_members}

PM-KISAN FAMILY GUIDELINES:
According to PM-KISAN scheme guidelines, the farmer's family consists of:
- Husband, wife and minor children (under 18 years)
- Family is the basic unit for determining eligibility
- IMPORTANT: If there are adult children (18+ years) in the household, the entire family becomes INELIGIBLE for the scheme
- Only families with minor children or no children are eligible

TASK: Ask the user about family member information in a conversational way.

INSTRUCTIONS:
- Be friendly and conversational
- If no family members collected yet, FIRST explain the PM-KISAN family definition and eligibility rules
- Clearly warn that adult children (18+) make the entire household INELIGIBLE
- Then ask if they have family members to include according to these guidelines
- If some family members already collected, ask if they have more to add
- Explain what information is needed: name, relation, age, gender
- Keep it simple and natural

EXAMPLES:
- Initial: "Now let's collect your family information. According to PM-KISAN guidelines, your eligible family includes your wife and minor children (under 18 years only). Important: If you have any adult children (18+ years) in your household, your family becomes ineligible for the scheme. Do you have family members fitting the eligible criteria? If yes, please share their details."
- Follow-up: "Do you have any other eligible family members (wife or minor children under 18) to add?"

Return only the question, no additional text."""

                response = await self.llm.ainvoke([{"role": "system", "content": family_prompt}])
                return response.content.strip()
                
            except Exception as e:
                print(f"🔍 DEBUG: Family question LLM attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    if family_count > 0:
                        return "Do you have any more family members to add to this application?"
                    else:
                        return "Do you have any family members to include in this PM-KISAN application? Please provide their details or say 'no'."
                await asyncio.sleep(self.retry_delay)

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM with a prompt and return the response"""
        try:
            response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
            return response.content.strip()
        except Exception as e:
            print(f"🔍 DEBUG: LLM call failed: {e}")
            return '{"action": "ask_details", "response_message": "Please provide family member details (name, relation, age, gender) or say \'no\' if you don\'t have any."}'



    async def _extract_family_members_with_llm(self, user_input: str, state: ConversationState) -> list:
        """Extract all family member details using LLM"""
        try:
            extract_prompt = f"""Extract ALL family member details from user input.

REQUIRED STRUCTURE PER MEMBER:
{self.family_member_structure}

USER INPUT: "{user_input}"

TASK: Extract ALL family members mentioned. If names are missing, use relation as placeholder.

Return JSON array format:
[
  {{"name": "Son", "relation": "son", "age": 21, "gender": "male"}},
  {{"name": "Wife", "relation": "wife", "age": 40, "gender": "female"}}
]

If no family members found, return empty array [].
Only return the JSON array, no other text."""

            response = await self.llm.ainvoke([{"role": "system", "content": extract_prompt}])
            
            try:
                import json
                result = json.loads(response.content.strip())
                if isinstance(result, list):
                    valid_members = []
                    for member in result:
                        if isinstance(member, dict) and "relation" in member and "age" in member:
                            # Fill in missing fields with defaults
                            if "name" not in member or not member["name"]:
                                member["name"] = member["relation"].title()
                            if "gender" not in member or not member["gender"]:
                                # Guess gender based on relation
                                if member["relation"].lower() in ["son", "father", "brother", "husband"]:
                                    member["gender"] = "male"
                                elif member["relation"].lower() in ["daughter", "mother", "sister", "wife"]:
                                    member["gender"] = "female"
                                else:
                                    member["gender"] = "other"
                            valid_members.append(member)
                    return valid_members
            except Exception as parse_error:
                print(f"🔍 DEBUG: JSON parse error: {parse_error}")
            
        except Exception as e:
            print(f"🔍 DEBUG: Family extraction failed: {e}")
        
        return []

    def _get_incomplete_family_member(self, state: ConversationState) -> dict:
        """Check if there's an incomplete family member that needs more details"""
        for i, member in enumerate(state.family_members):
            required_fields = ["name", "relation", "age", "gender"]
            missing_fields = [field for field in required_fields if field not in member or not member[field]]
            if missing_fields:
                return {"index": i, "member": member, "missing_fields": missing_fields}
        return None

    async def _handle_incomplete_family_member(self, state: ConversationState, incomplete_member: dict) -> ConversationState:
        """Handle incomplete family member by asking for missing details"""
        member = incomplete_member["member"]
        missing_fields = incomplete_member["missing_fields"]
        
        if state.user_input and state.user_input.strip():
            # Try to fill in missing field
            missing_field = missing_fields[0]  # Handle one field at a time
            
            validation_result = await self._validate_single_family_field(missing_field, state.user_input, member)
            
            if validation_result.get("is_valid", False):
                # Update the member with the new field
                member[missing_field] = validation_result.get("extracted_value")
                
                # Check if still missing fields
                remaining_missing = [field for field in ["name", "relation", "age", "gender"] if field not in member or not member[field]]
                
                if remaining_missing:
                    next_field = remaining_missing[0]
                    state.response = f"✅ Got {missing_field}: {validation_result.get('extracted_value')}. Now, what is their {next_field}?"
                else:
                    state.response = f"✅ Complete! Added family member: {member['name']} ({member['relation']}, {member['age']} years, {member['gender']}). Do you have another family member to add?"
            else:
                state.response = f"❌ {validation_result.get('validation_message', 'Invalid input')}. Please provide their {missing_field}."
        else:
            # Ask for the first missing field
            missing_field = missing_fields[0]
            member_desc = member.get("name", "family member")
            state.response = f"I need more details about {member_desc}. What is their {missing_field}?"
        
        return state

    async def _validate_family_input_with_retries(self, user_input: str, state: ConversationState) -> dict:
        """Validate family member input with retries"""
        for attempt in range(self.max_retries):
            try:
                prompt = f"""You are a data validation expert for PM-KISAN family member information.

USER INPUT: "{user_input}"

REQUIRED FAMILY MEMBER STRUCTURE:
{self.family_member_structure}

TASK: Extract and validate ALL family members mentioned. Each member MUST have:
- name: string (family member's name)
- relation: enum (husband, wife, son, daughter, father, mother, brother, sister, other)  
- age: integer (age in years)
- gender: enum (male, female, other)

VALIDATION RULES:
- Extract as much information as possible for each member
- Age must be a valid number if provided
- Relation must be one of the allowed values if provided
- Gender must be one of the allowed values if provided
- If some fields are missing, still extract what's available and mark as valid for partial extraction
- Only mark as invalid if the input is completely unusable

EXAMPLES:
- "I have a son who's 21 years old and a wife who's 40 years old" → VALID (extract partial info, gender missing)
- "My son John is 21 years old, he's male, and my wife Mary is 40 years old, she's female" → VALID (complete info)
- "I have a son, Rahul, 21 years old, wife, Seema, 42 years old" → VALID (extract partial info, genders missing)

Return ONLY a JSON object:
{{
    "is_valid": true/false,
    "extracted_members": [
        {{"name": "John", "relation": "son", "age": 21, "gender": "male"}},
        {{"name": "Mary", "relation": "wife", "age": 40, "gender": "female"}}
    ],
    "validation_message": "brief explanation"
}}"""

                response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    
                    # Additional validation of extracted members - allow partial extraction
                    if result.get("is_valid") and result.get("extracted_members"):
                        members = result["extracted_members"]
                        for member in members:
                            # Validate relation if provided
                            if "relation" in member and member["relation"]:
                                valid_relations = ["husband", "wife", "son", "daughter", "father", "mother", "brother", "sister", "other"]
                                if member["relation"].lower() not in valid_relations:
                                    result["is_valid"] = False
                                    result["validation_message"] = f"Invalid relation: {member['relation']}. Must be one of: {', '.join(valid_relations)}"
                                    break
                                else:
                                    member["relation"] = member["relation"].lower()  # Normalize
                            
                            # Validate gender if provided
                            if "gender" in member and member["gender"]:
                                valid_genders = ["male", "female", "other"]
                                if member["gender"].lower() not in valid_genders:
                                    result["is_valid"] = False
                                    result["validation_message"] = f"Invalid gender: {member['gender']}. Must be one of: {', '.join(valid_genders)}"
                                    break
                                else:
                                    member["gender"] = member["gender"].lower()  # Normalize
                            
                            # Validate age if provided
                            if "age" in member and member["age"]:
                                try:
                                    age = int(member["age"])
                                    if age < 0 or age > 150:
                                        result["is_valid"] = False
                                        result["validation_message"] = f"Invalid age: {age}. Must be between 0 and 150"
                                        break
                                    member["age"] = age  # Ensure it's an integer
                                except (ValueError, TypeError):
                                    result["is_valid"] = False
                                    result["validation_message"] = f"Invalid age format: {member['age']}. Must be a number"
                                    break
                            
                            # Ensure we have at least some useful information
                            if not any(member.get(field) for field in ["name", "relation", "age"]):
                                result["is_valid"] = False
                                result["validation_message"] = "Could not extract meaningful family member information"
                                break
                    
                    return result
                else:
                    return {
                        "is_valid": False,
                        "extracted_members": [],
                        "validation_message": "Could not extract family member information. Please provide name, relation, age, and gender for each member."
                    }
                    
            except Exception as e:
                print(f"⚠️ Family validation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return {
                        "is_valid": False,
                        "extracted_members": [],
                        "validation_message": "Could not process family member information. Please provide complete details."
                    }

    async def _validate_single_family_field(self, field_name: str, user_input: str, existing_member: dict) -> dict:
        """Validate a single family member field"""
        try:
            if field_name == "age":
                try:
                    age = int(user_input.strip())
                    if 0 <= age <= 150:
                        return {"is_valid": True, "extracted_value": age, "validation_message": f"Age recorded as {age}"}
                    else:
                        return {"is_valid": False, "validation_message": "Age must be between 0 and 150"}
                except ValueError:
                    return {"is_valid": False, "validation_message": "Please provide age as a number"}
            
            elif field_name == "relation":
                valid_relations = ["husband", "wife", "son", "daughter", "father", "mother", "brother", "sister", "other"]
                relation = user_input.strip().lower()
                if relation in valid_relations:
                    return {"is_valid": True, "extracted_value": relation, "validation_message": f"Relation recorded as {relation}"}
                else:
                    return {"is_valid": False, "validation_message": f"Relation must be one of: {', '.join(valid_relations)}"}
            
            elif field_name == "gender":
                valid_genders = ["male", "female", "other"]
                gender = user_input.strip().lower()
                if gender in valid_genders:
                    return {"is_valid": True, "extracted_value": gender, "validation_message": f"Gender recorded as {gender}"}
                else:
                    return {"is_valid": False, "validation_message": f"Gender must be one of: {', '.join(valid_genders)}"}
            
            elif field_name == "name":
                name = user_input.strip()
                if name and len(name) >= 2:
                    return {"is_valid": True, "extracted_value": name, "validation_message": f"Name recorded as {name}"}
                else:
                    return {"is_valid": False, "validation_message": "Please provide a valid name (at least 2 characters)"}
            
            else:
                return {"is_valid": False, "validation_message": f"Unknown field: {field_name}"}
                
        except Exception as e:
            print(f"⚠️ Single field validation failed: {e}")
            return {"is_valid": False, "validation_message": "Could not validate input. Please try again."}

    async def _family_node(self, state: ConversationState) -> ConversationState:
        """Robust family member collection with proper validation"""
        print(f"🔍 DEBUG: Entering FAMILY_NODE")
        state.stage = ConversationStage.FAMILY_MEMBERS
        
        if not self.family_member_structure:
            state.response = "✅ No family member information required. Moving to next section."
            return state
        
        # Check if we have incomplete family members that need more details
        incomplete_member = self._get_incomplete_family_member(state)
        if incomplete_member:
            return await self._handle_incomplete_family_member(state, incomplete_member)
        
        # If we have user input, try to process it
        if state.user_input and state.user_input.strip():
            # Check for developer commands
            if state.user_input.lower().startswith("/skip"):
                state.response = "✅ [DEV] Skipped family member collection. Moving to next section."
                return state
            elif state.user_input.lower().startswith("/skipall"):
                state.response = "✅ [DEV] Skipped all family member collection. Moving to next section."
                return state
            
            # Try to extract and validate family members from input
            print(f"🔍 DEBUG: Processing family input: '{state.user_input}'")
            
            # Check if user says no family
            if any(word in state.user_input.lower() for word in ["no", "none", "don't have", "dont have", "no family", "no one"]):
                state.user_input = ""  # Clear input so other nodes don't process it
                state.response = "✅ No family members to add. Moving to next section."
                return state
            
            # Try to extract family members
            validation_result = await self._validate_family_input_with_retries(state.user_input, state)
            
            if validation_result.get("is_valid", False):
                extracted_members = validation_result.get("extracted_members", [])
                
                # Add validated members (even if partial)
                for member in extracted_members:
                    state.family_members.append(member)
                
                # CRITICAL: Clear user input so other nodes don't process it
                state.user_input = ""
                
                # Check if any members are incomplete
                incomplete_members = []
                for i, member in enumerate(extracted_members):
                    missing_fields = [field for field in ["name", "relation", "age", "gender"] if field not in member or not member[field]]
                    if missing_fields:
                        incomplete_members.append({"index": len(state.family_members) - len(extracted_members) + i, "member": member, "missing_fields": missing_fields})
                
                if incomplete_members:
                    # Some members are incomplete, ask for missing details
                    first_incomplete = incomplete_members[0]
                    member = first_incomplete["member"]
                    missing_field = first_incomplete["missing_fields"][0]
                    
                    member_desc = member.get("name") or member.get("relation") or "family member"
                    state.response = f"✅ Got information about {member_desc}. What is their {missing_field}?"
                else:
                    # All members are complete
                    if len(extracted_members) == 1:
                        member = extracted_members[0]
                        state.response = f"✅ Added family member: {member['name']} ({member['relation']}, {member['age']} years, {member['gender']}). Do you have another family member to add?"
                    else:
                        member_list = ", ".join([f"{m['name']} ({m['relation']}, {m['age']} years, {m['gender']})" for m in extracted_members])
                        state.response = f"✅ Added {len(extracted_members)} family members: {member_list}. Do you have any more family members to add?"
                
                print(f"🔍 DEBUG: Family node cleared user_input after extraction")
                return state
            else:
                # Validation failed, ask for clarification
                state.response = f"❌ {validation_result.get('validation_message', 'Invalid family member information')}. Please provide complete details: name, relation, age, and gender for each family member."
                return state
        else:
            # No input - ask LLM-generated initial question
            question = await self._ask_family_question_with_llm(state)
            state.response = question
            return state

    async def _special_node(self, state: ConversationState) -> ConversationState:
        """Simple special provisions collection"""
        print(f"🔍 DEBUG: Entering SPECIAL_NODE")
        state.stage = ConversationStage.SPECIAL_PROVISIONS
        
        if not self.special_provision_fields:
            state.stage = ConversationStage.COMPLETED
            state.response = "✅ No special provisions required. Application complete!"
            return state
        
        missing_specials = [f for f in self.special_provision_fields if f not in state.special_provisions]
        
        if not missing_specials:
            state.stage = ConversationStage.COMPLETED
            state.response = "✅ All special provisions collected. Application complete!"
            return state
        
        target_field = missing_specials[0]
        
        if state.user_input and state.user_input.strip():
            # Check for developer commands
            if state.user_input.lower().startswith("/skip"):
                state.special_provisions[target_field] = "[SKIPPED]"
                state.response = f"✅ [DEV] Skipped {target_field}. Moving to next special provision."
            elif state.user_input.lower().startswith("/skipall"):
                # Skip all remaining special provisions
                for field in missing_specials:
                    state.special_provisions[field] = "[SKIPPED]"
                state.stage = ConversationStage.COMPLETED
                state.response = "✅ [DEV] Skipped all special provisions. Application complete!"
            else:
                state.special_provisions[target_field] = state.user_input.strip()
                state.response = f"✅ Recorded {target_field.replace('_', ' ')}."
        else:
            state.response = f"Please provide information about {target_field.replace('_', ' ')}."
        
        return state

    async def _completed_node(self, state: ConversationState) -> ConversationState:
        """Completion node"""
        state.stage = ConversationStage.COMPLETED
        state.response = "🎉 Congratulations! All information has been collected successfully. Your PM-KISAN application data is now ready for processing and eligibility verification."
        return state

    # Transition functions
    def _basic_info_done(self, state: ConversationState) -> str:
        missing_fields = [f for f in self.required_fields if f not in state.collected_data]
        return "FAMILY_MEMBERS" if not missing_fields else "END"

    def _exclusion_done(self, state: ConversationState) -> str:
        missing_exclusions = [f for f in self.exclusion_fields if f not in state.exclusion_data]
        
        # Check for conditional fields that need follow-up
        if "is_government_employee" in state.exclusion_data and state.exclusion_data["is_government_employee"] is True:
            if "government_post" not in state.exclusion_data:
                return "END"  # Still need to ask for government post
        
        if "is_pensioner" in state.exclusion_data and state.exclusion_data["is_pensioner"] is True:
            if "government_post" not in state.exclusion_data:
                return "END"  # Still need to ask for government post
            if "monthly_pension" not in state.exclusion_data:
                return "END"  # Still need to ask for monthly pension amount
        
        if not missing_exclusions:
            print(f"🔍 DEBUG: No missing exclusions, checking special provisions: {bool(self.special_provision_fields)}")
            if self.special_provision_fields:
                print(f"🔍 DEBUG: Returning SPECIAL_PROVISIONS")
                return "SPECIAL_PROVISIONS"
            else:
                print(f"🔍 DEBUG: Returning COMPLETED")
                return "COMPLETED"
        print(f"🔍 DEBUG: Still have missing exclusions: {missing_exclusions}, returning END")
        return "END"
        return "END"

    def _family_done(self, state: ConversationState) -> str:
        # Check if user said no to family members or we have collected family members
        family_count = len(state.family_members)
        response_str = str(state.response) if state.response else ""
        has_no_family_response = "No family members to add" in response_str
        print(f"🔍 DEBUG: Family done check - family_count: {family_count}, has_no_family_response: {has_no_family_response}, response: {response_str}")
        
        if has_no_family_response or family_count > 0:
            print(f"🔍 DEBUG: Family done - transitioning to EXCLUSION_CRITERIA")
            return "EXCLUSION_CRITERIA"
        else:
            print(f"🔍 DEBUG: Family not done - returning END")
            return "END"  # Still collecting family members

    def _special_done(self, state: ConversationState) -> str:
        missing_specials = [f for f in self.special_provision_fields if f not in state.special_provisions]
        return "COMPLETED" if not missing_specials else "END"

    # CLI interface methods
    async def initialize_conversation(self, scheme_code: str = "pm-kisan") -> Tuple[str, ConversationState]:
        """Initialize conversation"""
        state = ConversationState()
        
        try:
            await self.initialize(scheme_code)
            
            scheme_name = self.scheme_definition.get("name", "the scheme")
            welcome_msg = f"""🚀 Welcome to the PM-KISAN application assistant!

I'll help you apply by collecting the required information through a simple conversation.

📋 **Required Information**: {len(self.required_fields)} fields
🔍 **Eligibility Questions**: {len(self.exclusion_fields)} questions
👥 **Family Info**: {"Required" if self.family_member_structure else "Not required"}
⚡ **Special Provisions**: {len(self.special_provision_fields)} additional fields

Let's begin! What is your full name?"""

            state.debug_log.append(f"[SIMPLE] Initialized {scheme_name}")
            return welcome_msg, state
            
        except Exception as e:
            return f"❌ Failed to initialize: {str(e)}", state

    async def process_user_input(self, user_input: str, state: ConversationState) -> Tuple[str, ConversationState]:
        """Process user input"""
        try:
            response, updated_state = await self.chat(user_input, state)
            updated_state.debug_log.append(f"[SIMPLE] Processed input in stage: {updated_state.stage.value}")
            return response, updated_state
        except Exception as e:
            state.debug_log.append(f"[SIMPLE] Error: {str(e)}")
            return f"❌ Sorry, I encountered an error: {str(e)}", state

    def get_conversation_summary(self, state: ConversationState) -> str:
        """Generate progress summary"""
        collected_count = len(state.collected_data)
        exclusion_count = len(state.exclusion_data)
        family_count = len(state.family_members)
        special_count = len(state.special_provisions)
        
        total_required = len(self.required_fields)
        total_exclusions = len(self.exclusion_fields)
        total_specials = len(self.special_provision_fields)
        
        summary_parts = []
        
        if total_required > 0:
            summary_parts.append(f"Basic: {collected_count}/{total_required}")
        
        if total_exclusions > 0:
            summary_parts.append(f"Exclusions: {exclusion_count}/{total_exclusions}")
        
        if self.family_member_structure:
            summary_parts.append(f"Family: {family_count} members")
        
        if total_specials > 0:
            summary_parts.append(f"Special: {special_count}/{total_specials}")
        
        stage_name = state.stage.value.replace("_", " ").title()
        summary_parts.append(f"Stage: {stage_name}")
        
        return " | ".join(summary_parts) 