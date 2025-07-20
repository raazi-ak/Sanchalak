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
    REVIEW = "review"
    ELIGIBILITY_CHECK = "eligibility_check"
    SUMMARY = "summary"
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
        g.add_node("REVIEW", self._review_node)
        g.add_node("ELIGIBILITY_CHECK", self._eligibility_check_node)
        g.add_node("SUMMARY", self._summary_node)
        g.add_node("COMPLETED", self._completed_node)
        
        # Correct flow: BASIC_INFO -> FAMILY_MEMBERS -> EXCLUSION_CRITERIA -> SPECIAL_PROVISIONS -> REVIEW -> ELIGIBILITY_CHECK -> SUMMARY -> COMPLETED
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
            {"SPECIAL_PROVISIONS": "SPECIAL_PROVISIONS", "REVIEW": "REVIEW", "ELIGIBILITY_CHECK": "ELIGIBILITY_CHECK", "END": END}
        )
        
        print(f"🔍 DEBUG: Graph edges configured - BASIC_INFO -> FAMILY_MEMBERS -> EXCLUSION_CRITERIA -> SPECIAL_PROVISIONS -> REVIEW -> ELIGIBILITY_CHECK -> SUMMARY")
        
        g.add_conditional_edges(
            "SPECIAL_PROVISIONS",
            self._special_done,
            {"REVIEW": "REVIEW", "ELIGIBILITY_CHECK": "ELIGIBILITY_CHECK", "SUMMARY": "SUMMARY", "END": END}
        )
        
        g.add_conditional_edges(
            "REVIEW",
            self._review_done,
            {"ELIGIBILITY_CHECK": "ELIGIBILITY_CHECK", "SUMMARY": "SUMMARY", "END": END}
        )
        
        g.add_conditional_edges(
            "ELIGIBILITY_CHECK",
            self._eligibility_check_done,
            {"SUMMARY": "SUMMARY", "END": END}
        )
        
        g.add_conditional_edges(
            "SUMMARY",
            self._summary_done,
            {"COMPLETED": "COMPLETED", "BASIC_INFO": "BASIC_INFO", "FAMILY_MEMBERS": "FAMILY_MEMBERS", "EXCLUSION_CRITERIA": "EXCLUSION_CRITERIA", "SPECIAL_PROVISIONS": "SPECIAL_PROVISIONS", "REVIEW": "REVIEW", "ELIGIBILITY_CHECK": "ELIGIBILITY_CHECK", "END": END}
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
            elif state.stage == ConversationStage.REVIEW:
                return await self._handle_empty_input_review(state)
            elif state.stage == ConversationStage.ELIGIBILITY_CHECK:
                return await self._handle_empty_input_eligibility_check(state)
            elif state.stage == ConversationStage.SUMMARY:
                return await self._handle_empty_input_summary(state)
            else:
                return "Please provide some input or use /help for commands.", state
        
        # Route to the appropriate node based on current stage
        try:
            if state.stage == ConversationStage.BASIC_INFO:
                updated_state = await self._basic_info_node(state)
            elif state.stage == ConversationStage.EXCLUSION_CRITERIA:
                updated_state = await self._exclusion_node(state)
            elif state.stage == ConversationStage.FAMILY_MEMBERS:
                updated_state = await self._family_node(state)
            elif state.stage == ConversationStage.SPECIAL_PROVISIONS:
                updated_state = await self._special_node(state)
            elif state.stage == ConversationStage.REVIEW:
                updated_state = await self._review_node(state)
            elif state.stage == ConversationStage.ELIGIBILITY_CHECK:
                updated_state = await self._eligibility_check_node(state)
            elif state.stage == ConversationStage.SUMMARY:
                updated_state = await self._summary_node(state)
            elif state.stage == ConversationStage.COMPLETED:
                updated_state = await self._completed_node(state)
            else:
                return "❌ Invalid stage. Please restart the conversation.", state
            
            # Check if we need to transition to the next stage
            if updated_state.stage == ConversationStage.BASIC_INFO:
                # Check if basic info is complete
                missing_fields = [f for f in self.required_fields if f not in updated_state.collected_data]
                if not missing_fields:
                    # Transition to family members
                    updated_state.stage = ConversationStage.FAMILY_MEMBERS
                    # Ask first family question
                    if self.family_member_structure:
                        family_question = await self._ask_family_question_with_llm(updated_state)
                        updated_state.response = f"✅ Great! All basic information collected. Now let's collect information about your family members.\n\n{family_question}"
            
            # Check if family stage is complete and should transition to exclusions
            elif updated_state.stage == ConversationStage.FAMILY_MEMBERS:
                # If user said no to family members, transition to exclusions
                if "No family members to add" in updated_state.response:
                    updated_state.stage = ConversationStage.EXCLUSION_CRITERIA
                    # Ask first exclusion question
                    if self.exclusion_fields:
                        first_exclusion = self.exclusion_fields[0]
                        exclusion_question = await self._ask_exclusion_question_with_llm(first_exclusion, updated_state)
                        updated_state.response += f"\n\n{exclusion_question}"
            
            return updated_state.response if hasattr(updated_state, 'response') else "Sorry, no response generated.", updated_state
                
        except Exception as e:
            print(f"⚠️ Chat processing failed: {e}")
            return f"❌ Sorry, I encountered an error: {str(e)}. Please try again.", state

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
            state.stage = ConversationStage.SPECIAL_PROVISIONS
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
                    state.stage = ConversationStage.SPECIAL_PROVISIONS
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
- Next stage: Special Provisions

TASK: Respond intelligently to the user's input and guide them to the next stage.

INSTRUCTIONS:
- Be friendly and conversational
- Acknowledge their input appropriately
- Explain that all eligibility questions are complete
- Guide them to the next section (Special Provisions)
- Keep it simple and natural

EXAMPLE: "I understand you said '{state.user_input}'. All eligibility questions have been completed successfully! Now let's move to the next section where we'll check for any special provisions that might apply to you."

Return only the response, no additional text."""

                    response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                    state.response = response.content.strip()
                    # Don't manually set stage - let the graph transition handle it
                    return state
                except Exception as e:
                    print(f"⚠️ LLM response failed: {e}")
                    state.response = f"I understand you said '{state.user_input}'. All eligibility questions are complete! Moving to special provisions section."
                    state.stage = ConversationStage.SPECIAL_PROVISIONS
                    return state
        
        # Get the first missing exclusion field
        target_field = missing_exclusions[0] if missing_exclusions else None
        
        if not target_field:
            state.response = "✅ All eligibility questions answered! Moving to special provisions section."
            state.stage = ConversationStage.SPECIAL_PROVISIONS
            return state.response, state
        
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
        # Use the new LLM-based special node logic
        updated_state = await self._special_node(state)
        return updated_state.response, updated_state

    async def _handle_empty_input_summary(self, state: ConversationState) -> Tuple[str, ConversationState]:
        """Handle empty input in summary stage"""
        state.response = "Please provide some input or use /help for commands."
        return state.response, state

    async def _handle_empty_input_review(self, state: ConversationState) -> Tuple[str, ConversationState]:
        """Handle empty input in review stage"""
        state.response = "Please provide your review or say 'no' if you don't want to review."
        return state.response, state

    async def _handle_empty_input_eligibility_check(self, state: ConversationState) -> Tuple[str, ConversationState]:
        """Handle empty input in eligibility check stage"""
        state.response = "Please provide your eligibility check or say 'no' if you don't want to check."
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
- For IFSC codes: Accept ANY alphanumeric code that looks like an IFSC - be VERY lenient
- When in doubt, accept the input rather than reject it

DATA TYPES AND ENUMS (from EFR models):
- name: string (any name format is fine)
- age: integer (any reasonable age 18-120)
- gender: string (male/female/other)
- phone_number: string (any phone number format)
- state/district/sub_district_block/village: string (any location name - be very flexible)
- land_size_acres: float (any decimal number)
- land_ownership: enum (owned/leased/sharecropping/joint/institutional/unknown)
- date_of_land_ownership: string (any date format, convert to DD/MM/YYYY)
- bank_account: boolean (true if user has account, false if not)
- account_number: string (any account number format - varies by bank)
- ifsc_code: string (any IFSC code format - varies by bank)
- aadhaar_number: string (any 12-digit number)
- aadhaar_linked: boolean (true if Aadhaar linked to bank account)
- category: enum (general/sc/st/obc/minority/bpl)

LOCATION FIELD RULES:
- state: Accept any state name (e.g., "Sikkim", "Manipur", "Nagaland")
- district: Accept any district name (e.g., "East Sikkim", "Imphal East")
- sub_district_block: Accept any administrative division (e.g., "Gangtok", "Gyalshing", "Mangan", "Namchi")
- village: Accept any village/town name

SPECIAL RULES FOR SPECIFIC FIELDS:
- land_ownership: Accept "owned", "lease", "leased", "sharecropping", "joint", "institutional", "unknown"
- aadhaar_linked: Accept "yes", "no", "linked", "not linked", or any indication of Aadhaar-bank linking
- category: Accept "general", "sc", "st", "obc", "minority", "bpl" (case insensitive)
- bank_account: Accept "yes", "no", account numbers, or any indication of having an account
- account_number: Accept ANY account number format (different banks have different formats)
- ifsc_code: Accept ANY IFSC code format - be VERY lenient, accept any alphanumeric code that looks like an IFSC

EXAMPLES:
- "raazi faisal" for name → valid, extract as "Raazi Faisal"
- "Gangtok" for sub_district_block → valid, extract as "Gangtok"
- "East Sikkim" for district → valid, extract as "East Sikkim"
- "555501167757" for account_number → valid, extract as "555501167757"
- "FDRL00005555" for ifsc_code → valid, extract as "FDRL00005555"
- "SBIN0007777" for ifsc_code → valid, extract as "SBIN0007777"
- "FDRL0005555" for ifsc_code → valid, extract as "FDRL0005555"
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
            print(f"🔍 DEBUG: Validating exclusion input: '{state.user_input}' for field: {target_field}")
            validation_result = await self._validate_exclusion_with_retries(target_field, state.user_input)
            print(f"🔍 DEBUG: Validation result: {validation_result}")
            
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

    async def _clear_llm_context(self):
        """Clear LLM context to prevent conversation history carryover"""
        try:
            # Create a fresh LLM client to clear any internal state
            self.llm = ChatOpenAI(
                openai_api_base=self.llm.openai_api_base,
                openai_api_key=self.llm.openai_api_key,
                model_name=self.llm.model_name,
                temperature=self.llm.temperature,
                max_tokens=self.llm.max_tokens
            )
            print("🔍 DEBUG: LLM context cleared")
        except Exception as e:
            print(f"⚠️ Failed to clear LLM context: {e}")

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
            
            # Auto-infer gender from relation if possible
            if "gender" in missing_fields and member.get("relation"):
                inferred_gender = self._infer_gender_from_relation(member["relation"])
                if inferred_gender:
                    member["gender"] = inferred_gender
                    missing_fields.remove("gender")
                    print(f"🔍 DEBUG: Auto-inferred gender '{inferred_gender}' from relation '{member['relation']}' during incomplete check")
            
            if missing_fields:
                return {"index": i, "member": member, "missing_fields": missing_fields}
        return None

    async def _handle_incomplete_family_member(self, state: ConversationState, incomplete_member: dict) -> ConversationState:
        """Handle incomplete family member by asking for missing details using LLM"""
        member = incomplete_member["member"]
        missing_fields = incomplete_member["missing_fields"]
        
        # Auto-infer gender from relation if relation is available but gender is missing
        if "gender" in missing_fields and member.get("relation"):
            inferred_gender = self._infer_gender_from_relation(member["relation"])
            if inferred_gender:
                member["gender"] = inferred_gender
                missing_fields.remove("gender")
                print(f"🔍 DEBUG: Auto-inferred gender '{inferred_gender}' from relation '{member['relation']}' for incomplete member")
        
        # If no more missing fields after inference, member is complete
        if not missing_fields:
            # Generate completion message using LLM
            completion_prompt = f"""You are a friendly government officer helping with PM-KISAN application.

SITUATION: Successfully completed collecting information for a family member

FAMILY MEMBER INFO:
- Name: {member.get('name', 'Unknown')}
- Relation: {member.get('relation', 'Unknown')}
- Age: {member.get('age', 'Unknown')} years
- Gender: {member.get('gender', 'Unknown')}

TASK: Generate a friendly completion message and ask if they have more family members.

INSTRUCTIONS:
- Be friendly and conversational
- Acknowledge the completed family member
- Ask if they have more family members to add
- Keep it simple and natural

EXAMPLE: "Perfect! I've recorded {member.get('name', 'your family member')} ({member.get('relation', 'relation')}, {member.get('age', 'age')} years, {member.get('gender', 'gender')}). Do you have any other family members to add?"

Return only the message, no additional text."""

            try:
                response = await self.llm.ainvoke([{"role": "system", "content": completion_prompt}])
                state.response = response.content.strip()
            except Exception as e:
                state.response = f"✅ Complete! Added family member: {member['name']} ({member['relation']}, {member['age']} years, {member['gender']}). Do you have another family member to add?"
            return state
        
        if state.user_input and state.user_input.strip():
            # Try to fill in missing field
            missing_field = missing_fields[0]  # Handle one field at a time
            
            validation_result = await self._validate_single_family_field(missing_field, state.user_input, member)
            
            if validation_result.get("is_valid", False):
                # Update the member with the new field
                member[missing_field] = validation_result.get("extracted_value")
                
                # Auto-infer gender if relation was just added
                if missing_field == "relation" and "gender" in missing_fields:
                    inferred_gender = self._infer_gender_from_relation(member["relation"])
                    if inferred_gender:
                        member["gender"] = inferred_gender
                        missing_fields.remove("gender")
                        print(f"🔍 DEBUG: Auto-inferred gender '{inferred_gender}' after relation '{member['relation']}' was added")
                
                # Check if still missing fields using verification system
                completeness = self._verify_family_member_completeness(member)
                
                if not completeness["is_complete"] and completeness["incomplete_info"]:
                    next_field = completeness["incomplete_info"][0]
                    
                    # Generate next question using LLM
                    next_question_prompt = f"""You are a friendly government officer helping with PM-KISAN application.

SITUATION: Successfully collected {missing_field} for a family member, now need to ask for the next field

FAMILY MEMBER INFO SO FAR:
- Name: {member.get('name', 'Unknown')}
- Relation: {member.get('relation', 'Unknown')}
- Age: {member.get('age', 'Unknown')}
- Gender: {member.get('gender', 'Unknown')}

JUST COLLECTED: {missing_field} = {validation_result.get('extracted_value')}
NEXT FIELD NEEDED: {next_field}

TASK: Generate a friendly question asking for the next field.

INSTRUCTIONS:
- Be friendly and conversational
- Acknowledge what was just collected
- Ask for the next field naturally
- Keep it simple and natural

EXAMPLE: "Great! I got their {missing_field}: {validation_result.get('extracted_value')}. Now, what is their {next_field}?"

Return only the question, no additional text."""

                    try:
                        response = await self.llm.ainvoke([{"role": "system", "content": next_question_prompt}])
                        state.response = response.content.strip()
                    except Exception as e:
                        state.response = f"✅ Got {missing_field}: {validation_result.get('extracted_value')}. Now, what is their {next_field}?"
                else:
                    # Member is complete - generate completion message using LLM
                    completion_prompt = f"""You are a friendly government officer helping with PM-KISAN application.

SITUATION: Successfully completed collecting information for a family member

FAMILY MEMBER INFO:
- Name: {member.get('name', 'Unknown')}
- Relation: {member.get('relation', 'Unknown')}
- Age: {member.get('age', 'Unknown')} years
- Gender: {member.get('gender', 'Unknown')}

TASK: Generate a friendly completion message and ask if they have more family members.

INSTRUCTIONS:
- Be friendly and conversational
- Acknowledge the completed family member
- Ask if they have more family members to add
- Keep it simple and natural

EXAMPLE: "Perfect! I've recorded {member.get('name', 'your family member')} ({member.get('relation', 'relation')}, {member.get('age', 'age')} years, {member.get('gender', 'gender')}). Do you have any other family members to add?"

Return only the message, no additional text."""

                    try:
                        response = await self.llm.ainvoke([{"role": "system", "content": completion_prompt}])
                        state.response = response.content.strip()
                    except Exception as e:
                        member_desc = member.get("name") or member.get("relation") or "family member"
                        state.response = f"✅ Complete! Added family member: {member_desc} ({member['relation']}, {member['age']} years, {member['gender']}). Do you have another family member to add?"
            else:
                # Generate error message using LLM
                error_prompt = f"""You are a friendly government officer helping with PM-KISAN application.

SITUATION: User provided invalid input for a family member field

FIELD BEING ASKED FOR: {missing_field}
USER INPUT: "{state.user_input}"
ERROR: {validation_result.get('validation_message', 'Invalid input')}

TASK: Generate a friendly error message asking for the correct information.

INSTRUCTIONS:
- Be friendly and understanding
- Explain what went wrong briefly
- Ask for the correct information
- Keep it simple and encouraging

EXAMPLE: "I didn't quite understand that. Could you please provide their {missing_field}?"

Return only the error message, no additional text."""

                try:
                    response = await self.llm.ainvoke([{"role": "system", "content": error_prompt}])
                    state.response = response.content.strip()
                except Exception as e:
                    state.response = f"❌ {validation_result.get('validation_message', 'Invalid input')}. Please provide their {missing_field}."
        else:
            # Ask for the first missing field using verification system
            completeness = self._verify_family_member_completeness(member)
            if completeness["incomplete_info"]:
                missing_field = completeness["incomplete_info"][0]
                member_desc = member.get("name") or member.get("relation") or "family member"
                
                # Generate question using LLM
                question_prompt = f"""You are a friendly government officer helping with PM-KISAN application.

SITUATION: Need to ask for missing information about a family member

FAMILY MEMBER: {member_desc}
MISSING FIELD: {missing_field}

TASK: Generate a friendly question asking for the missing field.

INSTRUCTIONS:
- Be friendly and conversational
- Ask for the specific missing field
- Keep it simple and natural
- Don't ask for multiple fields at once

EXAMPLE: "I need a bit more information about {member_desc}. What is their {missing_field}?"

Return only the question, no additional text."""

                try:
                    response = await self.llm.ainvoke([{"role": "system", "content": question_prompt}])
                    state.response = response.content.strip()
                except Exception as e:
                    state.response = f"I need more details about {member_desc}. What is their {missing_field}?"
            else:
                # Member is actually complete after gender inference - generate completion message using LLM
                completion_prompt = f"""You are a friendly government officer helping with PM-KISAN application.

SITUATION: Successfully completed collecting information for a family member

FAMILY MEMBER INFO:
- Name: {member.get('name', 'Unknown')}
- Relation: {member.get('relation', 'Unknown')}
- Age: {member.get('age', 'Unknown')} years
- Gender: {member.get('gender', 'Unknown')}

TASK: Generate a friendly completion message and ask if they have more family members.

INSTRUCTIONS:
- Be friendly and conversational
- Acknowledge the completed family member
- Ask if they have more family members to add
- Keep it simple and natural

EXAMPLE: "Perfect! I've recorded {member.get('name', 'your family member')} ({member.get('relation', 'relation')}, {member.get('age', 'age')} years, {member.get('gender', 'gender')}). Do you have any other family members to add?"

Return only the message, no additional text."""

                try:
                    response = await self.llm.ainvoke([{"role": "system", "content": completion_prompt}])
                    state.response = response.content.strip()
                except Exception as e:
                    member_desc = member.get("name") or member.get("relation") or "family member"
                    state.response = f"✅ Complete! Added family member: {member_desc} ({member['relation']}, {member['age']} years, {member['gender']}). Do you have another family member to add?"
        
        return state

    def _infer_gender_from_relation(self, relation: str) -> str:
        """Infer gender from family relation"""
        relation = relation.lower().strip()
        gender_map = {
            "son": "male",
            "father": "male", 
            "brother": "male",
            "husband": "male",
            "daughter": "female",
            "mother": "female",
            "sister": "female", 
            "wife": "female"
        }
        return gender_map.get(relation, None)

    def _verify_family_member_completeness(self, member: dict) -> dict:
        """Verify that a family member has all required fields"""
        required_fields = ["name", "relation", "age", "gender"]
        missing_fields = []
        incomplete_info = []
        
        for field in required_fields:
            if field not in member or not member[field]:
                missing_fields.append(field)
                if field == "name":
                    incomplete_info.append("name")
                elif field == "relation":
                    incomplete_info.append("relation")
                elif field == "age":
                    incomplete_info.append("age")
                elif field == "gender":
                    # Only add gender if it can't be inferred from relation
                    if not member.get("relation") or not self._infer_gender_from_relation(member["relation"]):
                        incomplete_info.append("gender")
        
        return {
            "is_complete": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "incomplete_info": incomplete_info
        }

    def _verify_stage_completeness(self, state: ConversationState) -> dict:
        """Verify that the current stage is complete before transitioning"""
        if state.stage == ConversationStage.BASIC_INFO:
            missing_fields = [f for f in self.required_fields if f not in state.collected_data]
            return {
                "is_complete": len(missing_fields) == 0,
                "missing_fields": missing_fields,
                "message": f"Missing basic info fields: {', '.join(missing_fields)}" if missing_fields else "Basic info complete"
            }
        
        elif state.stage == ConversationStage.FAMILY_MEMBERS:
            if not self.family_member_structure:
                return {"is_complete": True, "missing_fields": [], "message": "No family members required"}
            
            incomplete_members = []
            for i, member in enumerate(state.family_members):
                completeness = self._verify_family_member_completeness(member)
                if not completeness["is_complete"]:
                    incomplete_members.append({
                        "index": i,
                        "member": member,
                        "missing_fields": completeness["missing_fields"],
                        "incomplete_info": completeness["incomplete_info"]
                    })
            
            if incomplete_members:
                return {
                    "is_complete": False,
                    "missing_fields": [f"Member {m['index']+1}: {', '.join(m['incomplete_info'])}" for m in incomplete_members],
                    "message": f"Family members incomplete: {len(incomplete_members)} members need more information"
                }
            else:
                return {"is_complete": True, "missing_fields": [], "message": "All family members complete"}
        
        elif state.stage == ConversationStage.EXCLUSION_CRITERIA:
            missing_exclusions = [f for f in self.exclusion_fields if f not in state.exclusion_data]
            
            # Check conditional fields
            conditional_missing = []
            if "is_government_employee" in state.exclusion_data and state.exclusion_data["is_government_employee"] is True:
                if "government_post" not in state.exclusion_data:
                    conditional_missing.append("government_post")
            
            if "is_pensioner" in state.exclusion_data and state.exclusion_data["is_pensioner"] is True:
                if "government_post" not in state.exclusion_data:
                    conditional_missing.append("government_post")
                if "monthly_pension" not in state.exclusion_data:
                    conditional_missing.append("monthly_pension")
            
            all_missing = missing_exclusions + conditional_missing
            return {
                "is_complete": len(all_missing) == 0,
                "missing_fields": all_missing,
                "message": f"Missing exclusions: {', '.join(all_missing)}" if all_missing else "All exclusions complete"
            }
        
        elif state.stage == ConversationStage.SPECIAL_PROVISIONS:
            missing_specials = [f for f in self.special_provision_fields if f not in state.special_provisions]
            return {
                "is_complete": len(missing_specials) == 0,
                "missing_fields": missing_specials,
                "message": f"Missing special provisions: {', '.join(missing_specials)}" if missing_specials else "All special provisions complete"
            }
        
        return {"is_complete": True, "missing_fields": [], "message": "Stage complete"}

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
                                    
                                    # Auto-infer gender from relation if gender is missing
                                    if not member.get("gender"):
                                        inferred_gender = self._infer_gender_from_relation(member["relation"])
                                        if inferred_gender:
                                            member["gender"] = inferred_gender
                                            print(f"🔍 DEBUG: Auto-inferred gender '{inferred_gender}' from relation '{member['relation']}'")
                            
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
        print(f"🔍 DEBUG: Current family members: {state.family_members}")
        print(f"🔍 DEBUG: User input: '{state.user_input}'")
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
            
            # Use a single, comprehensive LLM prompt to handle all family member processing
            family_processing_prompt = f"""You are a SMART government officer helping with PM-KISAN family member collection.

CURRENT SITUATION:
- Collecting family member information for PM-KISAN application
- {len(state.family_members)} family members already collected: {state.family_members}
- User input: "{state.user_input}"

TASK: Understand the user's input, extract family member information, and generate an appropriate response.

CRITICAL INSTRUCTIONS:
1. FIRST: Determine what the user is trying to communicate:
   - Are they saying they have no more family members? (e.g., "no more", "that's all", "done")
   - Are they providing information about family members?
   - Are they asking a question or making a comment?

2. IF USER IS PROVIDING FAMILY INFO:
   - Extract ALL family member details mentioned (name, relation, age, gender)
   - MANDATORY: AUTOMATICALLY INFER GENDER from relation:
     * son = male, daughter = female, wife = female, husband = male
     * father = male, mother = female, brother = male, sister = female
   - Be smart about understanding natural language (e.g., "he is 14 years old" = age 14)
   - NEVER ask for gender if relation is provided - ALWAYS infer it automatically

3. IF USER IS DONE WITH FAMILY MEMBERS:
   - Acknowledge and transition to next section
   - Be friendly and conversational

4. IF USER IS PROVIDING PARTIAL INFO:
   - Extract what's available and ask for missing details naturally

EXAMPLES:
- "no more family members" → transition to exclusions
- "i have a son rahul he is 14 years old" → add complete member with inferred gender
- "my wife seema is 43 years old" → add complete member with inferred gender
- "he a male" → update existing member's gender

Return ONLY a JSON object:
{{
    "action": "transition_to_exclusions" | "add_complete_member" | "add_partial_member" | "update_existing_member" | "ask_for_missing_details",
    "response": "your friendly, conversational response message",
    "family_members_to_add": [{{"name": "...", "relation": "...", "age": ..., "gender": "..."}}],
    "member_to_update": {{"index": 0, "updates": {{"age": 21, "gender": "male"}}}},
    "missing_details": ["field1", "field2"]
}}"""

            try:
                response = await self.llm.ainvoke([{"role": "system", "content": family_processing_prompt}])
                import json
                import re
                json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    print(f"🔍 DEBUG: LLM Result: {result}")
                    
                    if result.get("action") == "transition_to_exclusions":
                        state.user_input = ""  # Clear input
                        state.response = result.get("response", "Perfect! Moving to the next section.")
                        state.stage = ConversationStage.EXCLUSION_CRITERIA
                        print(f"🔍 DEBUG: Transitioning to exclusions")
                        return state
                    
                    elif result.get("action") == "add_complete_member":
                        # Add complete family member(s)
                        new_members = result.get("family_members_to_add", [])
                        print(f"🔍 DEBUG: Adding complete family members: {new_members}")
                        for member in new_members:
                            state.family_members.append(member)
                        print(f"🔍 DEBUG: Updated family members: {state.family_members}")
                        state.user_input = ""  # Clear input
                        state.response = result.get("response", "Perfect! I've recorded the family member information.")
                        return state
                    
                    elif result.get("action") == "add_partial_member":
                        # Add partial family member and ask for missing details
                        new_members = result.get("family_members_to_add", [])
                        print(f"🔍 DEBUG: Adding partial family members: {new_members}")
                        for member in new_members:
                            state.family_members.append(member)
                        print(f"🔍 DEBUG: Updated family members: {state.family_members}")
                        state.user_input = ""  # Clear input
                        state.response = result.get("response", "Great! I got some information. What else can you tell me?")
                        return state
                    
                    elif result.get("action") == "update_existing_member":
                        # Update existing incomplete member
                        update_info = result.get("member_to_update", {})
                        member_index = update_info.get("index", 0)
                        updates = update_info.get("updates", {})
                        print(f"🔍 DEBUG: Updating member at index {member_index} with updates: {updates}")
                        
                        if member_index < len(state.family_members):
                            for field, value in updates.items():
                                state.family_members[member_index][field] = value
                            print(f"🔍 DEBUG: Updated family members: {state.family_members}")
                        else:
                            print(f"🔍 DEBUG: Invalid member index {member_index}, total members: {len(state.family_members)}")
                        
                        state.user_input = ""  # Clear input
                        state.response = result.get("response", "Got it! What else do you need to tell me?")
                        return state
                    
                    elif result.get("action") == "ask_for_missing_details":
                        state.user_input = ""  # Clear input
                        state.response = result.get("response", "I need a bit more information.")
                        return state
                    
                else:
                    # Fallback - just use the response
                    state.user_input = ""  # Clear input
                    state.response = result.get("response", "I understand. What would you like to tell me?")
                    return state
                        
            except Exception as e:
                print(f"🔍 DEBUG: Family processing failed: {e}")
                # Fallback - just ask for clarification
                state.response = "I didn't quite understand that. Could you please tell me more about your family members?"
                return state
        else:
            # No input - ask LLM-generated initial question
            question = await self._ask_family_question_with_llm(state)
            state.response = question
            return state

    def _get_special_region_info(self, region: str) -> dict:
        """Get information about special regions and their requirements"""
        region_info = {
            "north_east": {
                "name": "North East States",
                "description": "In North Eastern States, where land ownership rights are community-based and it may not be possible to assess the quantum of landholder farmers, an alternate implementation mechanism for eligibility will be developed.",
                "certificate_type": "community_land_certificate",
                "certificate_description": "Community-based land ownership certificate",
                "issued_by": "Village Chief/Council",
                "authenticated_by": "Sub-divisional Officer"
            },
            "manipur": {
                "name": "Manipur",
                "description": "For identification of bona fide beneficiaries under PM-Kisan Scheme in Manipur, a certificate issued by the Village authority (Chairman/Chief) authorizing any tribal family to cultivate a piece of land may be accepted.",
                "certificate_type": "village_authority_certificate",
                "certificate_description": "Village authority certificate for land cultivation",
                "issued_by": "Village Chief/Chairman",
                "authenticated_by": "Sub-divisional Officer"
            },
            "nagaland": {
                "name": "Nagaland",
                "description": "For community-owned cultivable land in Nagaland under permanent cultivation, a certificate issued by the village council/authority/village chieftain regarding land holding, duly verified by the administrative head of the circle/sub-division and countersigned by the Deputy Commissioner of the District, shall suffice.",
                "certificate_type": "village_council_certificate",
                "certificate_description": "Village council certificate for land holding",
                "issued_by": "Village Council/Chief",
                "authenticated_by": "Deputy Commissioner"
            },
            "jharkhand": {
                "name": "Jharkhand",
                "description": "In Jharkhand, the farmer must submit a 'Vanshavali (Lineage)' linked to the entry of land record comprising their ancestor's name, giving a chart of successor.",
                "certificate_type": "vanshavali_certificate",
                "certificate_description": "Vanshavali (Lineage) certificate linked to land records",
                "issued_by": "Village Revenue Officials",
                "authenticated_by": "District Revenue Authority"
            }
        }
        return region_info.get(region, {})

    def _detect_special_region_from_state(self, state_name: str) -> str:
        """Detect special region based on state name"""
        state_name = state_name.lower().strip()
        
        # North East states
        ne_states = ["arunachal pradesh", "assam", "manipur", "meghalaya", "mizoram", "nagaland", "sikkim", "tripura"]
        
        if state_name in ne_states:
            if state_name == "manipur":
                return "manipur"
            elif state_name == "nagaland":
                return "nagaland"
            else:
                return "north_east"
        elif state_name == "jharkhand":
            return "jharkhand"
        else:
            return "none"

    def _get_incomplete_special_provision(self, state: ConversationState) -> dict:
        """Check if there's an incomplete special provision that needs more details"""
        # First, check if we need state information for region detection
        state_name = None
        if 'state' in state.collected_data:
            state_name = state.collected_data['state'].value
        
        # If state is missing, we need to ask for it first
        if not state_name:
            return {
                "type": "state_required",
                "missing_fields": ["state"],
                "provision_info": "state information"
            }
        
        # Auto-detect region from state name
        detected_region = self._detect_special_region_from_state(state_name)
        
        # If region is "none", no special provisions needed - skip to completion
        if detected_region == "none":
            return None
        
        # Check if region_special is missing
        if "region_special" not in state.special_provisions:
            # Set the detected region
            state.special_provisions["region_special"] = detected_region
            region = detected_region
        else:
            region = state.special_provisions.get("region_special")
        
        # If region is special, check for certificate information
        if region in ["north_east", "manipur", "nagaland", "jharkhand"]:
            missing_fields = []
            
            if "has_special_certificate" not in state.special_provisions:
                missing_fields.append("has_special_certificate")
            
            if "has_special_certificate" in state.special_provisions and state.special_provisions["has_special_certificate"]:
                if "certificate_type" not in state.special_provisions:
                    missing_fields.append("certificate_type")
                if "certificate_details" not in state.special_provisions:
                    missing_fields.append("certificate_details")
            
            if missing_fields:
                return {
                    "type": "certificate_info",
                    "region": region,
                    "missing_fields": missing_fields,
                    "provision_info": f"{region} certificate"
                }
        
        return None

    async def _handle_incomplete_special_provision(self, state: ConversationState, incomplete_provision: dict) -> ConversationState:
        """Handle incomplete special provision by asking for missing details"""
        provision_type = incomplete_provision["type"]
        missing_fields = incomplete_provision["missing_fields"]
        
        if state.user_input and state.user_input.strip():
            # Try to fill in missing field
            missing_field = missing_fields[0]  # Handle one field at a time
            
            validation_result = await self._validate_single_special_field(missing_field, state.user_input, incomplete_provision)
            
            if validation_result.get("is_valid", False):
                # Update the special provisions with the new field
                if missing_field == "state":
                    # State is stored in collected_data, but we also need to set region_special
                    region_value = validation_result.get("extracted_value")
                    state.special_provisions["region_special"] = region_value
                else:
                    state.special_provisions[missing_field] = validation_result.get("extracted_value")
                
                # Check if still missing fields
                remaining_incomplete = self._get_incomplete_special_provision(state)
                
                if remaining_incomplete:
                    next_field = remaining_incomplete["missing_fields"][0]
                    provision_info = remaining_incomplete["provision_info"]
                    if missing_field == "state":
                        state.response = f"✅ {validation_result.get('validation_message')}. Now, what is the {next_field} for {provision_info}?"
                    else:
                        state.response = f"✅ Got {missing_field}: {validation_result.get('extracted_value')}. Now, what is the {next_field} for {provision_info}?"
                else:
                    # All provisions are complete
                    region = state.special_provisions.get("region_special", "none")
                    if region == "none":
                        state.response = "✅ No special provisions apply. Application complete!"
                    else:
                        certificate_type = state.special_provisions.get("certificate_type", "")
                        state.response = f"✅ Special provisions recorded for {region} region with {certificate_type} certificate. Application complete!"
                    
                    state.stage = ConversationStage.COMPLETED
            else:
                state.response = f"❌ {validation_result.get('validation_message', 'Invalid input')}. Please provide the {missing_field}."
        else:
            # Ask for the first missing field
            missing_field = missing_fields[0]
            provision_info = incomplete_provision["provision_info"]
            
            if provision_type == "state_required":
                state.response = self._get_state_question()
            elif provision_type == "region_selection":
                state.response = self._get_region_selection_question()
            elif provision_type == "certificate_info":
                region = incomplete_provision["region"]
                state.response = self._get_certificate_question(region, missing_field)
        
        return state

    def _get_state_question(self) -> str:
        """Generate question for state information"""
        return """🏛️ **State Information Required**

I need to know which state you're from to determine if any special provisions apply to you for PM-KISAN.

**Please tell me your state of residence:**

This helps me check if you're from:
• **North East States** (special community-based land ownership)
• **Manipur** (village authority certificates)
• **Nagaland** (village council certificates)
• **Jharkhand** (Vanshavali lineage certificates)
• **Other states** (regular provisions)

What state do you live in?"""

    def _get_region_selection_question(self) -> str:
        """Generate question for region selection"""
        return """🌍 **Special Region Provisions**

Some regions have special provisions for PM-KISAN eligibility. Please tell me which region you're from:

**Special Regions:**
• **North East States** (Arunachal Pradesh, Assam, Meghalaya, Mizoram, Sikkim, Tripura)
• **Manipur** - Village authority certificates
• **Nagaland** - Village council certificates  
• **Jharkhand** - Vanshavali (Lineage) certificates

**Regular Regions:**
• All other states/UTs

Which region are you from? (You can say the state name or 'regular' for normal states)"""

    def _get_certificate_question(self, region: str, field: str) -> str:
        """Generate question for certificate information"""
        region_info = self._get_special_region_info(region)
        
        if field == "has_special_certificate":
            return f"""📋 **Certificate Requirement for {region_info['name']}**

{region_info['description']}

**Do you have a {region_info['certificate_description']}?**

This certificate is issued by {region_info['issued_by']} and authenticated by {region_info['authenticated_by']}.

Please answer: **Yes** or **No**"""
        
        elif field == "certificate_type":
            return f"✅ Great! What type of certificate do you have? (e.g., {region_info['certificate_type']})"
        
        elif field == "certificate_details":
            return f"""📄 **Certificate Details**

Please provide the following details about your certificate:

• **Issued by:** {region_info['issued_by']}
• **Issue date:** (YYYY-MM-DD format)
• **Authenticated by:** {region_info['authenticated_by']}
• **Certificate number:** (if available)

You can provide these details in any format."""
        
        return f"Please provide the {field} for your {region} certificate."

    async def _validate_single_special_field(self, field_name: str, user_input: str, incomplete_provision: dict) -> dict:
        """Validate a single special provision field"""
        try:
            if field_name == "state":
                # Validate and store state information
                state_name = user_input.strip()
                if state_name and len(state_name) >= 2:
                    # Store in collected_data for future reference
                    if not hasattr(self, 'collected_data'):
                        self.collected_data = {}
                    
                    # Create ExtractedField for state
                    from datetime import datetime
                    state_field = ExtractedField(
                        value=state_name,
                        confidence=0.9,
                        source="user_input",
                        timestamp=datetime.now(),
                        raw_input=user_input
                    )
                    self.collected_data['state'] = state_field
                    
                    # Auto-detect region from state
                    detected_region = self._detect_special_region_from_state(state_name)
                    if detected_region != "none":
                        return {
                            "is_valid": True, 
                            "extracted_value": detected_region, 
                            "validation_message": f"State recorded as {state_name}. Detected {detected_region} region - special provisions apply."
                        }
                    else:
                        return {
                            "is_valid": True, 
                            "extracted_value": "none", 
                            "validation_message": f"State recorded as {state_name}. Regular region - no special provisions needed."
                        }
                else:
                    return {"is_valid": False, "validation_message": "Please provide a valid state name"}
            
            elif field_name == "region_special":
                # Auto-detect region from state if available, otherwise validate input
                state_name = None
                if hasattr(self, 'collected_data') and 'state' in self.collected_data:
                    state_name = self.collected_data['state'].value
                
                if state_name:
                    detected_region = self._detect_special_region_from_state(state_name)
                    if detected_region != "none":
                        return {"is_valid": True, "extracted_value": detected_region, "validation_message": f"Detected {detected_region} region from your state"}
                
                # Validate manual input
                valid_regions = ["north_east", "manipur", "nagaland", "jharkhand", "none"]
                input_lower = user_input.lower().strip()
                
                # Map common responses to regions
                region_mapping = {
                    "regular": "none", "normal": "none", "other": "none", "no": "none",
                    "northeast": "north_east", "ne": "north_east", "north east": "north_east",
                    "manipur": "manipur", "nagaland": "nagaland", "jharkhand": "jharkhand"
                }
                
                if input_lower in region_mapping:
                    region = region_mapping[input_lower]
                    return {"is_valid": True, "extracted_value": region, "validation_message": f"Region recorded as {region}"}
                elif input_lower in valid_regions:
                    return {"is_valid": True, "extracted_value": input_lower, "validation_message": f"Region recorded as {input_lower}"}
                else:
                    return {"is_valid": False, "validation_message": f"Please specify a valid region: {', '.join(valid_regions)}"}
            
            elif field_name == "has_special_certificate":
                input_lower = user_input.lower().strip()
                if input_lower in ["yes", "true", "1", "have", "got"]:
                    return {"is_valid": True, "extracted_value": True, "validation_message": "Certificate requirement confirmed"}
                elif input_lower in ["no", "false", "0", "don't have", "dont have"]:
                    return {"is_valid": True, "extracted_value": False, "validation_message": "No certificate required"}
                else:
                    return {"is_valid": False, "validation_message": "Please answer with Yes or No"}
            
            elif field_name == "certificate_type":
                certificate_type = user_input.strip()
                if certificate_type and len(certificate_type) >= 3:
                    return {"is_valid": True, "extracted_value": certificate_type, "validation_message": f"Certificate type recorded as {certificate_type}"}
                else:
                    return {"is_valid": False, "validation_message": "Please provide a valid certificate type"}
            
            elif field_name == "certificate_details":
                # For now, store as string - could be enhanced to extract structured data
                details = user_input.strip()
                if details and len(details) >= 10:
                    return {"is_valid": True, "extracted_value": details, "validation_message": "Certificate details recorded"}
                else:
                    return {"is_valid": False, "validation_message": "Please provide complete certificate details"}
            
            else:
                return {"is_valid": False, "validation_message": f"Unknown field: {field_name}"}
                
        except Exception as e:
            print(f"⚠️ Single special field validation failed: {e}")
            return {"is_valid": False, "validation_message": "Could not validate input. Please try again."}

    async def _validate_special_provision_input_with_retries(self, user_input: str, state: ConversationState) -> dict:
        """Validate special provision input with retries"""
        for attempt in range(self.max_retries):
            try:
                prompt = f"""You are a data validation expert for PM-KISAN special provisions.

USER INPUT: "{user_input}"

SPECIAL PROVISIONS STRUCTURE:
- region_special: enum (north_east, manipur, nagaland, jharkhand, none)
- has_special_certificate: boolean (true if region is special)
- certificate_type: string (if has_special_certificate is true)
- certificate_details: string (if has_special_certificate is true)

REGION DETECTION RULES:
- North East States: Arunachal Pradesh, Assam, Meghalaya, Mizoram, Sikkim, Tripura → "north_east"
- Manipur → "manipur" 
- Nagaland → "nagaland"
- Jharkhand → "jharkhand"
- All other states → "none"

CERTIFICATE REQUIREMENTS:
- north_east: community_land_certificate
- manipur: village_authority_certificate  
- nagaland: village_council_certificate
- jharkhand: vanshavali_certificate

TASK: Extract and validate special provisions from user input.

Return ONLY a JSON object:
{{
    "is_valid": true/false,
    "extracted_provisions": {{
        "region_special": "region_name",
        "has_special_certificate": true/false,
        "certificate_type": "certificate_type_if_applicable",
        "certificate_details": "details_if_applicable"
    }},
    "validation_message": "brief explanation"
}}"""

                response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    
                    # Additional validation
                    if result.get("is_valid") and result.get("extracted_provisions"):
                        provisions = result["extracted_provisions"]
                        
                        # Validate region_special
                        if "region_special" in provisions:
                            valid_regions = ["north_east", "manipur", "nagaland", "jharkhand", "none"]
                            if provisions["region_special"] not in valid_regions:
                                result["is_valid"] = False
                                result["validation_message"] = f"Invalid region: {provisions['region_special']}. Must be one of: {', '.join(valid_regions)}"
                        
                        # Validate has_special_certificate
                        if "has_special_certificate" in provisions:
                            if not isinstance(provisions["has_special_certificate"], bool):
                                result["is_valid"] = False
                                result["validation_message"] = "has_special_certificate must be true or false"
                        
                        # Validate certificate fields if applicable
                        if provisions.get("has_special_certificate") is True:
                            if not provisions.get("certificate_type"):
                                result["is_valid"] = False
                                result["validation_message"] = "Certificate type is required when has_special_certificate is true"
                    
                    return result
                else:
                    return {
                        "is_valid": False,
                        "extracted_provisions": {},
                        "validation_message": "Could not extract special provision information. Please provide region and certificate details."
                    }
                    
            except Exception as e:
                print(f"⚠️ Special provision validation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return {
                        "is_valid": False,
                        "extracted_provisions": {},
                        "validation_message": "Could not process special provision information. Please provide complete details."
                    }

    async def _ask_special_field_question_with_llm(self, field_name: str, state: ConversationState) -> str:
        """Ask special provision field question using LLM for better phrasing"""
        for attempt in range(self.max_retries):
            try:
                special_field_prompts = {
                    "region_special": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: SPECIAL REGION

PROGRESS: {progress}/{total} special provisions collected

TASK: Ask the user if they are from any special region that has special provisions.

INSTRUCTIONS:
- Be friendly and conversational
- Explain that some regions have special provisions for PM-KISAN
- Mention specific regions: North East States (Assam, Manipur, Meghalaya, etc.), Jammu & Kashmir, Ladakh, Andaman & Nicobar, Lakshadweep, Jharkhand
- Ask clearly if they are from any of these regions
- Keep it simple and natural

EXAMPLE: "Are you from any special region like North East States, Jammu & Kashmir, Ladakh, Andaman & Nicobar, Lakshadweep, or Jharkhand? These regions have special provisions for PM-KISAN."

Return only the question, no additional text.""",
                    
                    "has_special_certificate": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: SPECIAL CERTIFICATE

PROGRESS: {progress}/{total} special provisions collected

TASK: Ask the user if they have any special certificates.

INSTRUCTIONS:
- Be friendly and conversational
- Explain that some farmers have special certificates
- Mention types: SC/ST certificate, OBC certificate, disability certificate, etc.
- Ask clearly if they have any such certificates
- Keep it simple and natural

EXAMPLE: "Do you have any special certificates like SC/ST certificate, OBC certificate, disability certificate, or any other government-issued certificates?"

Return only the question, no additional text.""",
                    
                    "certificate_type": """You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: CERTIFICATE TYPE

PROGRESS: {progress}/{total} special provisions collected

TASK: Ask the user what type of special certificate they have.

INSTRUCTIONS:
- Be friendly and conversational
- Ask specifically what type of certificate they mentioned
- Provide options: SC certificate, ST certificate, OBC certificate, disability certificate, etc.
- Keep it simple and natural

EXAMPLE: "What type of certificate do you have? Is it SC certificate, ST certificate, OBC certificate, disability certificate, or something else?"

Return only the question, no additional text."""
                }
                
                if field_name in special_field_prompts:
                    prompt = special_field_prompts[field_name].format(
                        progress=len(state.special_provisions),
                        total=len(self.special_provision_fields)
                    )
                else:
                    prompt = f"""You are a friendly government officer helping with PM-KISAN application.

FIELD TO ASK FOR: {field_name.replace('_', ' ').upper()}

PROGRESS: {len(state.special_provisions)}/{len(self.special_provision_fields)} special provisions collected

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
                print(f"❌ LLM call failed (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    return f"Please provide information about your {field_name.replace('_', ' ')}."
                await asyncio.sleep(1)

    async def _special_node(self, state: ConversationState) -> ConversationState:
        """Smart special provisions collection with state-based logic"""
        state.stage = ConversationStage.SPECIAL_PROVISIONS
        
        print(f"🔍 DEBUG: Entering SPECIAL_NODE")
        
        # Check if we have user input to process
        if state.user_input and state.user_input.strip():
            # Check for developer commands
            if state.user_input.lower().startswith("/skip"):
                state.response = "✅ [DEV] Skipped special provisions. Application complete!"
            state.stage = ConversationStage.COMPLETED
            return state
        
            # Process user input based on current state
            return await self._process_special_provision_input(state)
        else:
            # No input - start the special provisions flow
            return await self._start_special_provisions_flow(state)
    
    async def _start_special_provisions_flow(self, state: ConversationState) -> ConversationState:
        """Start the special provisions flow with explanation and state check"""
        try:
            # First, check if we have the user's state information
            user_state = None
            if 'state' in state.collected_data:
                user_state = state.collected_data['state'].value
                print(f"🔍 DEBUG: User state from collected data: {user_state}")
            
            # If no state provided, ask for it
            if not user_state or user_state == "[SKIPPED]":
                state.response = "Before we check special provisions, I need to know which state you're from. What is your state?"
                return state
            
            # Check if state qualifies for special provisions
            special_regions = ["jammu & kashmir", "ladakh", "manipur", "nagaland", "jharkhand", "assam", "meghalaya", "tripura", "mizoram", "arunachal pradesh", "sikkim", "andaman & nicobar", "lakshadweep"]
            
            if user_state.lower() in special_regions:
                # State qualifies for special provisions
                region_type = self._detect_special_region_from_state(user_state)
                
                # Set the region in special provisions
                state.special_provisions["region_special"] = region_type
                print(f"🔍 DEBUG: Set region_special to: {region_type}")
                
                # Generate LLM-based question for this region
                try:
                    prompt = f"""You are a friendly government officer helping with PM-KISAN application.

USER STATE: {user_state}
REGION TYPE: {region_type}

CERTIFICATE REQUIREMENTS:
- manipur → village_authority_certificate (Village authority certificate)
- nagaland → village_council_certificate (Village council certificate)
- jharkhand → vanshavali_certificate (Lineage certificate)
- north_east → community_land_certificate (Community land certificate)

TASK: Generate a friendly, conversational question asking the user if they have the required certificate for their region.

INSTRUCTIONS:
- Be warm and helpful like a human government officer
- Explain why the certificate is needed for PM-KISAN
- Ask clearly if they have the certificate
- Use natural, conversational language
- Keep it simple and direct

EXAMPLE FOR NAGALAND:
"Since you're from Nagaland, you need a village council certificate for PM-KISAN. This certificate is required to verify your land ownership in tribal areas. Do you have a village council certificate?"

Return only the question, no additional text."""

                    response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
                    state.response = response.content.strip()
                    print(f"🔍 DEBUG: LLM generated question: {state.response}")
                except Exception as e:
                    print(f"⚠️ LLM question generation failed: {e}")
                    # Fallback to template question
                    if region_type == "manipur":
                        state.response = f"Since you're from {user_state}, you need a village authority certificate for PM-KISAN. Do you have a village authority certificate?"
                    elif region_type == "nagaland":
                        state.response = f"Since you're from {user_state}, you need a village council certificate for PM-KISAN. Do you have a village council certificate?"
                    elif region_type == "jharkhand":
                        state.response = f"Since you're from {user_state}, you need a lineage certificate for PM-KISAN. Do you have a lineage certificate?"
                    elif region_type == "north_east":
                        state.response = f"Since you're from {user_state}, you need a community certificate for PM-KISAN. Do you have a community certificate?"
                    else:
                        state.response = f"Since you're from {user_state}, there are special provisions for PM-KISAN. Do you have the required certificates?"
            else:
                # State doesn't qualify for special provisions
                state.special_provisions["region_special"] = "none"
                state.special_provisions["has_special_certificate"] = False
                state.response = f"Since you're from {user_state}, no special provisions apply to you. Your application is complete!"
                state.stage = ConversationStage.COMPLETED
            
            return state
        
        except Exception as e:
            print(f"❌ LLM special provisions flow failed: {e}")
            # Fallback to manual state check
            return await self._fallback_special_provisions_check(state)
    
    async def _fallback_special_provisions_check(self, state: ConversationState) -> ConversationState:
        """Fallback method for special provisions check"""
        user_state = None
        if 'state' in state.collected_data:
            user_state = state.collected_data['state'].value
        
        if not user_state:
            state.response = "Before we check special provisions, I need to know which state you're from. What is your state?"
            return state
        
        # Check if state qualifies for special provisions
        special_regions = ["jammu & kashmir", "ladakh", "manipur", "nagaland", "jharkhand", "assam", "meghalaya", "tripura", "mizoram", "arunachal pradesh", "sikkim", "andaman & nicobar", "lakshadweep"]
        
        if user_state.lower() in special_regions:
            region_type = self._detect_special_region_from_state(user_state)
            state.response = f"Since you're from {user_state}, there are special provisions for PM-KISAN. Are you from the {region_type} region?"
        else:
            state.special_provisions["region_special"] = "none"
            state.special_provisions["has_special_certificate"] = False
            state.response = f"Since you're from {user_state}, no special provisions apply to you. Your application is complete!"
            state.stage = ConversationStage.COMPLETED
        
        return state
    
    async def _process_special_provision_input(self, state: ConversationState) -> ConversationState:
        """Process user input in special provisions stage"""
        user_input = state.user_input.strip()
        print(f"🔍 DEBUG: Processing special provision input: '{user_input}'")
        
        # Check if this is state information (if we were waiting for state)
        if 'state' not in state.collected_data or not state.collected_data.get('state', {}).value or state.collected_data.get('state', {}).value == "[SKIPPED]":
            # We were waiting for state info
            state.collected_data['state'] = ExtractedField(
                value=user_input, confidence=0.9, source="user_input", 
                timestamp=datetime.now(), raw_input=user_input
            )
            print(f"✅ STORED STATE: {user_input}")
            
            # Now check if this state qualifies for special provisions
            return await self._start_special_provisions_flow(state)
        
        # Check for clear negative responses
        clear_negative_words = ["no", "none", "not applicable", "regular", "normal", "no special", "no provisions"]
        if any(word in user_input.lower() for word in clear_negative_words) and len(user_input.lower()) < 15:
            # Check if we already have a region detected
            if state.special_provisions.get("region_special") and state.special_provisions.get("region_special") != "none":
                # User is saying no to certificate for a special region
                state.special_provisions["has_special_certificate"] = False
                state.special_provisions["certificate_type"] = "none"
                region = state.special_provisions.get("region_special")
                state.response = f"✅ Understood. No special certificates for {region} region. Application complete!"
                state.stage = ConversationStage.COMPLETED
                return state
            else:
                # User is saying no to special provisions entirely
                state.special_provisions["region_special"] = "none"
                state.special_provisions["has_special_certificate"] = False
                state.response = "✅ No special provisions apply. Application complete!"
                state.stage = ConversationStage.COMPLETED
                return state
        
        # Try to extract special provision information using LLM
        try:
            # Check if we already have a region and are waiting for certificate info
            current_region = state.special_provisions.get("region_special")
            print(f"🔍 DEBUG: Current region: {current_region}")
            print(f"🔍 DEBUG: User input: '{user_input}'")
            
            if current_region and current_region != "none":
                print(f"🔍 DEBUG: Processing certificate information for region: {current_region}")
                # We have a region, now processing certificate information
                prompt = f"""You are a government officer processing certificate information for PM-KISAN.

USER INPUT: "{user_input}"
REGION: {current_region}

CERTIFICATE TYPES TO EXTRACT:
- has_special_certificate: true/false
- certificate_type: community_land_certificate, village_authority_certificate, village_council_certificate, vanshavali_certificate, none

TASK: Extract certificate information from user input.

INSTRUCTIONS:
- Analyze if user has the required certificate for their region
- If user mentions having a certificate, set has_special_certificate to true
- If user says no or doesn't have a certificate, set has_special_certificate to false
- If user says "i do" or "yes" or similar positive responses, set has_special_certificate to true
- If user says "no" or "don't have" or similar negative responses, set has_special_certificate to false
- Set certificate_type based on region:
  * manipur → village_authority_certificate
  * nagaland → village_council_certificate
  * jharkhand → vanshavali_certificate
  * north_east → community_land_certificate
- If user says no certificate, set has_special_certificate to false and certificate_type to none
- Return valid JSON with extracted values

EXAMPLE OUTPUT:
{{"has_special_certificate": true, "certificate_type": "village_authority_certificate"}}

Return only the JSON, no additional text:"""
            else:
                print(f"🔍 DEBUG: Processing region information")
                # Processing region information
                prompt = f"""You are a government officer processing special provision information for PM-KISAN.

USER INPUT: "{user_input}"

SPECIAL PROVISIONS TO EXTRACT:
- region_special: north_east, manipur, nagaland, jharkhand, none
- has_special_certificate: true/false
- certificate_type: community_land_certificate, village_authority_certificate, village_council_certificate, vanshavali_certificate, none

REGION MAPPING RULES:
- Manipur → region_special: "manipur" (needs village_authority_certificate)
- Nagaland → region_special: "nagaland" (needs village_council_certificate)  
- Jharkhand → region_special: "jharkhand" (needs vanshavali_certificate)
- Other North East states (Assam, Meghalaya, etc.) → region_special: "north_east" (needs community_land_certificate)
- Jammu & Kashmir, Ladakh → region_special: "north_east" (special region provisions)
- Regular states → region_special: "none"

TASK: Extract special provision information from user input.

INSTRUCTIONS:
- Analyze the user input carefully
- Map regions correctly according to the rules above
- If user mentions a specific region, use the exact mapping
- If user mentions certificates, identify the type
- If user says no special provisions, mark as none
- Return valid JSON with extracted values

EXAMPLE OUTPUT:
{{"region_special": "manipur", "has_special_certificate": false, "certificate_type": "none"}}

Return only the JSON, no additional text:"""

            response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
            llm_response = response.content.strip()
            print(f"🔍 DEBUG: LLM response: {llm_response}")
            
            # Try to parse JSON response
            try:
                extracted_data = json.loads(llm_response)
                print(f"🔍 DEBUG: Parsed JSON: {extracted_data}")
                
                # Check if we're processing certificate info or region info
                if state.special_provisions.get("region_special") and state.special_provisions.get("region_special") != "none":
                    # Processing certificate information
                    valid_certificates = ["community_land_certificate", "village_authority_certificate", "village_council_certificate", "vanshavali_certificate", "none"]
                    
                    if extracted_data.get("has_special_certificate"):
                        state.special_provisions["has_special_certificate"] = extracted_data["has_special_certificate"]
                        
                        if extracted_data.get("certificate_type") in valid_certificates:
                            state.special_provisions["certificate_type"] = extracted_data["certificate_type"]
                        else:
                            state.special_provisions["certificate_type"] = "none"
                    else:
                        state.special_provisions["has_special_certificate"] = False
                        state.special_provisions["certificate_type"] = "none"
                    
                    print(f"✅ STORED CERTIFICATE INFO: {state.special_provisions}")
                    
                    # Certificate processing complete
                    region = state.special_provisions.get("region_special")
                    certificate_type = state.special_provisions.get("certificate_type", "none")
                    if certificate_type != "none":
                        state.response = f"✅ Special provisions recorded for {region} region with {certificate_type} certificate. Application complete!"
                    else:
                        state.response = f"✅ Special provisions recorded for {region} region (no certificates). Application complete!"
                    
                    state.stage = ConversationStage.COMPLETED
                    return state
                    
                else:
                    # Processing region information
                    valid_regions = ["north_east", "manipur", "nagaland", "jharkhand", "none"]
                    valid_certificates = ["community_land_certificate", "village_authority_certificate", "village_council_certificate", "vanshavali_certificate", "none"]
                    
                    if extracted_data.get("region_special") in valid_regions:
                        state.special_provisions["region_special"] = extracted_data["region_special"]
                        
                        if extracted_data.get("has_special_certificate"):
                            state.special_provisions["has_special_certificate"] = extracted_data["has_special_certificate"]
                            
                            if extracted_data.get("certificate_type") in valid_certificates:
                                state.special_provisions["certificate_type"] = extracted_data["certificate_type"]
                            else:
                                state.special_provisions["certificate_type"] = "none"
                        else:
                            state.special_provisions["has_special_certificate"] = False
                            state.special_provisions["certificate_type"] = "none"
                        
                        print(f"✅ STORED SPECIAL PROVISIONS: {state.special_provisions}")
                        
                        # Check if we need more information
                        region = state.special_provisions.get("region_special", "none")
                        if region != "none":
                            # Special region detected - need to ask for required certificate
                            if region == "manipur":
                                required_certificate = "village_authority_certificate"
                            elif region == "nagaland":
                                required_certificate = "village_council_certificate"
                            elif region == "jharkhand":
                                required_certificate = "vanshavali_certificate"
                            elif region == "north_east":
                                required_certificate = "community_land_certificate"
                            else:
                                required_certificate = "special_certificate"
                            
                            # Ask for the required certificate
                            question = await self._ask_special_field_question_with_llm("certificate_type", state)
                            state.response = f"✅ Got your region information. Since you're from {region}, you need a {required_certificate}. {question}"
                        else:
                            # No special provisions apply
                            state.response = "✅ No special provisions apply. Application complete!"
                            state.stage = ConversationStage.COMPLETED
                        
                        return state
                    else:
                        # Invalid region extracted
                        question = await self._ask_special_field_question_with_llm("region_special", state)
                        state.response = f"❌ I couldn't understand the region information. {question}"
                        return state
            except json.JSONDecodeError:
                # LLM didn't return valid JSON
                question = await self._ask_special_field_question_with_llm("region_special", state)
                state.response = f"❌ I couldn't understand the special provision information. {question}"
                return state
                
        except Exception as e:
            print(f"❌ LLM special provision processing failed: {e}")
            question = await self._ask_special_field_question_with_llm("region_special", state)
            state.response = f"❌ Sorry, I couldn't process that. {question}"
        return state

    async def _completed_node(self, state: ConversationState) -> ConversationState:
        """Completion node"""
        state.stage = ConversationStage.COMPLETED
        
        # Upload data to EFR database
        upload_result = await self.upload_to_efr_database(state)
        
        if upload_result.get("success"):
            farmer_id = upload_result.get("farmer_id", "Unknown")
            state.response = f"""🎉 Congratulations! Your PM-KISAN application has been successfully submitted and stored in the database.

📋 **Application Details:**
• Farmer ID: {farmer_id}
• Status: Submitted for processing
• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ **Next Steps:**
• Your application will be reviewed for eligibility
• You will receive updates via SMS on your registered mobile number
• Benefits will be transferred directly to your linked bank account

Thank you for using the PM-KISAN application assistant!"""
        else:
            # Store data locally if EFR upload fails
            farmer_data = self.convert_to_efr_farmer_data(state)
            state.response = f"""🎉 Your PM-KISAN application data has been collected successfully!

⚠️ **Note:** Database upload failed, but your data is saved locally.
• Error: {upload_result.get('message', 'Unknown error')}
• Your application data is ready for manual upload

📋 **Collected Information Summary:**
• Name: {farmer_data.get('name', 'N/A')}
• Aadhaar: {farmer_data.get('aadhaar_number', 'N/A')}
• State: {farmer_data.get('state', 'N/A')}
• Land Size: {farmer_data.get('land_size_acres', 'N/A')} acres

Please contact support for assistance with database upload."""
        
        return state

    async def _summary_node(self, state: ConversationState) -> ConversationState:
        """Summary and review node"""
        state.stage = ConversationStage.SUMMARY
        
        # If user provided input, process it
        if state.user_input and state.user_input.strip():
            return await self._process_summary_input(state)
        
        # Generate summary and ask for confirmation
        summary = self._generate_comprehensive_summary(state)
        state.response = summary
        return state

    async def _process_summary_input(self, state: ConversationState) -> ConversationState:
        """Process user input in summary stage"""
        user_input = state.user_input.strip().lower()
        
        # Check for update requests
        if "update" in user_input or "change" in user_input or "edit" in user_input:
            # Try to identify what they want to update
            if any(word in user_input for word in ["basic", "personal", "name", "age", "phone", "address"]):
                state.stage = ConversationStage.BASIC_INFO
                state.response = "✅ Let's update your basic information. What would you like to change?"
            elif any(word in user_input for word in ["family", "member", "wife", "son", "daughter"]):
                state.stage = ConversationStage.FAMILY_MEMBERS
                state.response = "✅ Let's update your family information. What would you like to change?"
            elif any(word in user_input for word in ["exclusion", "eligibility", "government", "employee", "pension"]):
                state.stage = ConversationStage.EXCLUSION_CRITERIA
                state.response = "✅ Let's update your eligibility information. What would you like to change?"
            elif any(word in user_input for word in ["special", "certificate", "region", "nagaland", "manipur"]):
                state.stage = ConversationStage.SPECIAL_PROVISIONS
                state.response = "✅ Let's update your special provisions information. What would you like to change?"
            else:
                state.response = "I can help you update any section. Please specify which section you'd like to update:\n- Basic information (name, age, phone, etc.)\n- Family members\n- Eligibility questions\n- Special provisions"
        elif "yes" in user_input or "correct" in user_input or "submit" in user_input or "confirm" in user_input:
            # User confirms the information is correct
            state.stage = ConversationStage.COMPLETED
            state.response = "🎉 Perfect! Your information has been confirmed and submitted. Your PM-KISAN application is now complete and ready for processing."
        elif "no" in user_input or "incorrect" in user_input or "wrong" in user_input:
            # User says information is incorrect, ask what to update
            state.response = "I understand you'd like to make changes. Which section would you like to update?\n- Basic information (name, age, phone, etc.)\n- Family members\n- Eligibility questions\n- Special provisions"
        else:
            # Unclear input, ask for clarification
            state.response = "I didn't understand. Please respond with:\n- 'Yes' or 'Correct' to confirm and submit\n- 'Update basic info' to change personal details\n- 'Update family' to change family members\n- 'Update eligibility' to change eligibility answers\n- 'Update special' to change special provisions"
        
        return state

    def _generate_comprehensive_summary(self, state: ConversationState) -> str:
        """Generate a comprehensive summary of all collected information"""
        summary_parts = []
        
        # Basic Information Summary
        if state.collected_data:
            summary_parts.append("📋 **BASIC INFORMATION:**")
            for field, data in state.collected_data.items():
                if data.value != "[SKIPPED]":
                    field_display = field.replace("_", " ").title()
                    summary_parts.append(f"  • {field_display}: {data.value}")
        
        # Family Members Summary
        if state.family_members:
            summary_parts.append("\n👥 **FAMILY MEMBERS:**")
            for i, member in enumerate(state.family_members, 1):
                name = member.get("name", "Unknown")
                relation = member.get("relation", "Unknown")
                age = member.get("age", "Unknown")
                gender = member.get("gender", "Unknown")
                summary_parts.append(f"  • {i}. {name} ({relation}, {age} years, {gender})")
        else:
            summary_parts.append("\n👥 **FAMILY MEMBERS:** None")
        
        # Exclusion Criteria Summary
        if state.exclusion_data:
            summary_parts.append("\n🚫 **ELIGIBILITY ANSWERS:**")
            for field, value in state.exclusion_data.items():
                field_display = field.replace("_", " ").title()
                summary_parts.append(f"  • {field_display}: {'Yes' if value else 'No'}")
        
        # Special Provisions Summary
        if state.special_provisions:
            summary_parts.append("\n⚡ **SPECIAL PROVISIONS:**")
            region = state.special_provisions.get("region_special", "None")
            has_cert = state.special_provisions.get("has_special_certificate", False)
            cert_type = state.special_provisions.get("certificate_type", "None")
            
            if region != "none":
                summary_parts.append(f"  • Special Region: {region}")
                summary_parts.append(f"  • Has Certificate: {'Yes' if has_cert else 'No'}")
                if has_cert:
                    summary_parts.append(f"  • Certificate Type: {cert_type}")
            else:
                summary_parts.append("  • No special provisions apply")
        
        # Final confirmation prompt
        summary_parts.append("\n" + "="*50)
        summary_parts.append("🤔 **REVIEW & CONFIRM**")
        summary_parts.append("Please review all the information above.")
        summary_parts.append("\nIs all this information correct to the best of your knowledge?")
        summary_parts.append("\nRespond with:")
        summary_parts.append("• 'Yes' or 'Correct' - to confirm and submit")
        summary_parts.append("• 'Update basic info' - to change personal details")
        summary_parts.append("• 'Update family' - to change family members")
        summary_parts.append("• 'Update eligibility' - to change eligibility answers")
        summary_parts.append("• 'Update special' - to change special provisions")
        
        return "\n".join(summary_parts)

    def _summary_done(self, state: ConversationState) -> str:
        """Determine next step from summary stage"""
        user_input = state.user_input.strip().lower() if state.user_input else ""
        
        # Check for update requests
        if "update" in user_input or "change" in user_input or "edit" in user_input:
            if any(word in user_input for word in ["basic", "personal", "name", "age", "phone", "address"]):
                return "BASIC_INFO"
            elif any(word in user_input for word in ["family", "member", "wife", "son", "daughter"]):
                return "FAMILY_MEMBERS"
            elif any(word in user_input for word in ["exclusion", "eligibility", "government", "employee", "pension"]):
                return "EXCLUSION_CRITERIA"
            elif any(word in user_input for word in ["special", "certificate", "region", "nagaland", "manipur"]):
                return "SPECIAL_PROVISIONS"
            elif any(word in user_input for word in ["review", "check", "verify"]):
                return "REVIEW"
            elif any(word in user_input for word in ["eligibility", "test", "check eligibility"]):
                return "ELIGIBILITY_CHECK"
            else:
                return "SUMMARY"  # Stay in summary to ask for clarification
        
        # Check for confirmation
        if "yes" in user_input or "correct" in user_input or "submit" in user_input or "confirm" in user_input:
            return "COMPLETED"
        
        # Default: stay in summary
        return "END"

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
                print(f"🔍 DEBUG: Returning SUMMARY")
                return "SUMMARY"
        print(f"🔍 DEBUG: Still have missing exclusions: {missing_exclusions}, returning END")
        return "END"
        return "END"

    def _family_done(self, state: ConversationState) -> str:
        # Check if user said no to family members
        response_str = str(state.response) if state.response else ""
        has_no_family_response = "No family members to add" in response_str
        
        # Use the verification system to check completeness
        verification = self._verify_stage_completeness(state)
        print(f"🔍 DEBUG: Family verification: {verification}")
        
        # Check if all family members are complete (have all required fields)
        incomplete_members = []
        for i, member in enumerate(state.family_members):
            completeness = self._verify_family_member_completeness(member)
            if not completeness["is_complete"]:
                incomplete_members.append({
                    "index": i,
                    "member": member,
                    "missing_fields": completeness["missing_fields"],
                    "incomplete_info": completeness["incomplete_info"]
                })
        
        family_count = len(state.family_members)
        print(f"🔍 DEBUG: Family done check - family_count: {family_count}, incomplete_members: {len(incomplete_members)}, has_no_family_response: {has_no_family_response}")
        
        # Only transition to exclusions if:
        # 1. User explicitly said no family members, OR
        # 2. We have complete family members (no incomplete ones) AND user confirmed they're done adding more
        if has_no_family_response:
            print(f"🔍 DEBUG: Family done - user said no family members, transitioning to EXCLUSION_CRITERIA")
            return "EXCLUSION_CRITERIA"
        elif family_count > 0 and len(incomplete_members) == 0:
            # All family members are complete, but check if user is still adding more
            # Look for responses that indicate they want to add more vs they're done
            adding_more_indicators = ["Do you have another family member", "Do you have any more family members"]
            if any(indicator in response_str for indicator in adding_more_indicators):
                print(f"🔍 DEBUG: Family complete but still asking for more - returning END")
                return "END"  # Still asking if they want to add more
            else:
                print(f"�� DEBUG: Family done - all members complete and not asking for more, transitioning to EXCLUSION_CRITERIA")
                return "EXCLUSION_CRITERIA"
        else:
            print(f"🔍 DEBUG: Family not done - incomplete members or no members yet, returning END")
            return "END"  # Still collecting or completing family members

    def _special_done(self, state: ConversationState) -> str:
        # Use the verification system to check completeness
        verification = self._verify_stage_completeness(state)
        print(f"🔍 DEBUG: Special verification: {verification}")
        
        if verification["is_complete"]:
            print(f"🔍 DEBUG: Special provisions complete, transitioning to REVIEW")
            return "REVIEW"
        else:
            print(f"🔍 DEBUG: Special provisions incomplete: {verification['missing_fields']}, returning END")
            return "END"

    # CLI interface methods
    async def initialize_conversation(self, scheme_code: str = "pm-kisan") -> Tuple[str, ConversationState]:
        """Initialize conversation"""
        state = ConversationState()
        
        try:
            # Clear LLM context to prevent conversation history carryover
            await self._clear_llm_context()
            
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

    def convert_to_efr_farmer_data(self, state: ConversationState) -> Dict[str, Any]:
        """Convert conversation state to EFR Farmer model format for database upload"""
        
        # Extract basic information from collected_data
        farmer_data = {}
        
        # Required fields mapping
        field_mapping = {
            'name': 'name',
            'age': 'age',
            'gender': 'gender',
            'phone_number': 'phone_number',
            'state': 'state',
            'district': 'district',
            'sub_district_block': 'sub_district_block',
            'village': 'village',
            'land_size_acres': 'land_size_acres',
            'land_ownership': 'land_ownership',
            'date_of_land_ownership': 'date_of_land_ownership',
            'bank_account': 'bank_account',
            'account_number': 'account_number',
            'ifsc_code': 'ifsc_code',
            'aadhaar_number': 'aadhaar_number',
            'aadhaar_linked': 'aadhaar_linked',
            'category': 'category'
        }
        
        # Map collected data to EFR fields
        for collected_field, efr_field in field_mapping.items():
            if collected_field in state.collected_data:
                value = state.collected_data[collected_field].value
                if value != "[SKIPPED]":
                    farmer_data[efr_field] = value
        
        # Set farmer_id from aadhaar_number
        if 'aadhaar_number' in farmer_data:
            farmer_data['farmer_id'] = farmer_data['aadhaar_number']
        
        # Add family information
        farmer_data['family_members'] = state.family_members
        farmer_data['family_size'] = len(state.family_members) + 1  # +1 for the farmer themselves
        
        # Calculate dependents (family members under 18)
        dependents = 0
        for member in state.family_members:
            age = member.get('age', 0)
            if isinstance(age, (int, float)) and age < 18:
                dependents += 1
        farmer_data['dependents'] = dependents
        
        # Add exclusion criteria
        exclusion_mapping = {
            'is_constitutional_post_holder': 'is_constitutional_post_holder',
            'is_political_office_holder': 'is_political_office_holder',
            'is_government_employee': 'is_government_employee',
            'is_income_tax_payer': 'is_income_tax_payer',
            'is_professional': 'is_professional',
            'is_nri': 'is_nri',
            'is_pensioner': 'is_pensioner'
        }
        
        for exclusion_field, efr_field in exclusion_mapping.items():
            if exclusion_field in state.exclusion_data:
                farmer_data[efr_field] = state.exclusion_data[exclusion_field]
            else:
                farmer_data[efr_field] = False  # Default to False if not answered
        
        # Add conditional fields
        if state.exclusion_data.get('is_government_employee'):
            farmer_data['government_post'] = state.exclusion_data.get('government_post')
        
        if state.exclusion_data.get('is_pensioner'):
            farmer_data['monthly_pension'] = state.exclusion_data.get('monthly_pension')
        
        if state.exclusion_data.get('is_professional'):
            farmer_data['profession'] = state.exclusion_data.get('profession')
        
        # Add special provisions
        if state.special_provisions:
            farmer_data['special_provisions'] = {
                'pm_kisan': {
                    'region_special': state.special_provisions.get('region_special', 'none'),
                    'has_special_certificate': state.special_provisions.get('has_special_certificate', False),
                    'certificate_type': state.special_provisions.get('certificate_type'),
                    'certificate_details': state.special_provisions.get('certificate_details', {})
                }
            }
        
        # Add default values for required EFR fields
        defaults = {
            'pincode': '000000',  # Default pincode
            'crops': [],  # Empty list for crops
            'farming_equipment': [],  # Empty list for equipment
            'irrigation_type': 'unknown',  # Default irrigation type
            'annual_income': 0.0,  # Default income
            'has_kisan_credit_card': False,  # Default KCC status
            'family_definition': 'nuclear',  # Default family definition
            'region': farmer_data.get('state', 'Unknown'),  # Use state as region
            'land_owner': farmer_data.get('land_ownership') == 'owned',  # Derived from land_ownership
            'status': 'completed',  # Processing status
            'audio_metadata': None,
            'extraction_metadata': {
                'method': 'langgraph_conversation',
                'confidence_scores': {},
                'entities_extracted': list(state.collected_data.keys()),
                'processing_time': None
            },
            'pipeline_metadata': {
                'task_id': f"pm_kisan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'processed_at': datetime.now().isoformat(),
                'transcribed_text': None
            }
        }
        
        # Apply defaults for missing fields
        for field, default_value in defaults.items():
            if field not in farmer_data:
                farmer_data[field] = default_value
        
        return farmer_data

    async def upload_to_efr_database(self, state: ConversationState) -> Dict[str, Any]:
        """Upload the collected farmer data to EFR database"""
        try:
            # Convert conversation state to EFR format
            farmer_data = self.convert_to_efr_farmer_data(state)
            
            # Import EFR client
            from pipeline.efr_storage import EFRStorage
            
            # Initialize EFR storage
            efr_storage = EFRStorage()
            
            # Check if EFR is available
            if not efr_storage.health_check():
                return {
                    "success": False,
                    "message": "EFR database is not available",
                    "error": "Connection failed"
                }
            
            # Upload farmer data
            result = efr_storage.add_farmer(farmer_data)
            
            if result.get("success"):
                return {
                    "success": True,
                    "message": f"Farmer data uploaded successfully to EFR database",
                    "farmer_id": farmer_data.get("farmer_id"),
                    "data": farmer_data
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to upload farmer data",
                    "error": result.get("message", "Unknown error"),
                    "data": farmer_data
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error uploading to EFR: {str(e)}",
                "error": str(e)
            }

    def get_efr_data_preview(self, state: ConversationState) -> Dict[str, Any]:
        """Get a preview of the EFR data format for debugging"""
        farmer_data = self.convert_to_efr_farmer_data(state)
        
        # Create a clean preview without metadata
        preview = {
            "farmer_id": farmer_data.get("farmer_id"),
            "name": farmer_data.get("name"),
            "age": farmer_data.get("age"),
            "gender": farmer_data.get("gender"),
            "phone_number": farmer_data.get("phone_number"),
            "state": farmer_data.get("state"),
            "district": farmer_data.get("district"),
            "village": farmer_data.get("village"),
            "land_size_acres": farmer_data.get("land_size_acres"),
            "land_ownership": farmer_data.get("land_ownership"),
            "aadhaar_number": farmer_data.get("aadhaar_number"),
            "aadhaar_linked": farmer_data.get("aadhaar_linked"),
            "bank_account": farmer_data.get("bank_account"),
            "account_number": farmer_data.get("account_number"),
            "ifsc_code": farmer_data.get("ifsc_code"),
            "category": farmer_data.get("category"),
            "family_size": farmer_data.get("family_size"),
            "family_members": farmer_data.get("family_members"),
            "exclusion_criteria": {
                "is_constitutional_post_holder": farmer_data.get("is_constitutional_post_holder"),
                "is_political_office_holder": farmer_data.get("is_political_office_holder"),
                "is_government_employee": farmer_data.get("is_government_employee"),
                "is_income_tax_payer": farmer_data.get("is_income_tax_payer"),
                "is_professional": farmer_data.get("is_professional"),
                "is_nri": farmer_data.get("is_nri"),
                "is_pensioner": farmer_data.get("is_pensioner")
            },
            "special_provisions": farmer_data.get("special_provisions"),
            "status": farmer_data.get("status")
        }
        
        return preview

    async def _extract_basic_family_info(self, user_input: str) -> dict:
        """Extract basic family info from simple statements like 'i have a son' using LLM"""
        try:
            prompt = f"""You are a data extraction expert for PM-KISAN family information.

USER INPUT: "{user_input}"

TASK: Extract basic family member information from the user's statement.

INSTRUCTIONS:
- If the user mentions having a family member (son, daughter, wife, husband, child), extract the relation and gender
- Be flexible with language - "i have a son", "my son", "i got a daughter", etc.
- Infer gender from relation: son/husband = male, daughter/wife = female
- If unclear, return null

EXAMPLES:
- "i have a son" → {{"relation": "son", "gender": "male"}}
- "my daughter" → {{"relation": "daughter", "gender": "female"}}
- "i got a wife" → {{"relation": "wife", "gender": "female"}}
- "my child" → {{"relation": "child", "gender": "male"}} (default to male)

Return ONLY a JSON object or null if no family member mentioned:
{{"relation": "relation_name", "gender": "gender"}}
or
null"""

            response = await self.llm.ainvoke([{"role": "system", "content": prompt}])
            
            # Extract JSON from response
            import json
            import re
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if isinstance(result, dict) and "relation" in result:
                    return result
            
            return None
            
        except Exception as e:
            print(f"🔍 DEBUG: Basic family info extraction failed: {e}")
            return None

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

    async def _review_node(self, state: ConversationState) -> ConversationState:
        """Review node - allows user to review all collected information"""
        state.stage = ConversationStage.REVIEW
        
        if state.user_input and state.user_input.strip():
            user_input = state.user_input.strip().lower()
            
            # Check for commands
            if user_input in ["no", "skip", "continue", "next"]:
                state.response = "✅ Skipping review. Moving to eligibility check."
                state.stage = ConversationStage.ELIGIBILITY_CHECK
                return state
            
            # Check for edit requests
            if any(word in user_input for word in ["edit", "change", "update", "modify"]):
                # Try to identify what they want to edit
                if any(word in user_input for word in ["basic", "personal", "name", "age", "phone", "address"]):
                    state.response = "✅ Redirecting to basic information section for editing."
                    state.stage = ConversationStage.BASIC_INFO
                    return state
                elif any(word in user_input for word in ["family", "member", "wife", "husband", "son", "daughter"]):
                    state.response = "✅ Redirecting to family members section for editing."
                    state.stage = ConversationStage.FAMILY_MEMBERS
                    return state
                elif any(word in user_input for word in ["exclusion", "eligibility", "government", "pension"]):
                    state.response = "✅ Redirecting to exclusion criteria section for editing."
                    state.stage = ConversationStage.EXCLUSION_CRITERIA
                    return state
                elif any(word in user_input for word in ["special", "provision", "certificate", "region"]):
                    state.response = "✅ Redirecting to special provisions section for editing."
                    state.stage = ConversationStage.SPECIAL_PROVISIONS
                    return state
                else:
                    state.response = "❓ What would you like to edit? Please specify: basic info, family members, exclusion criteria, or special provisions."
                    return state
            
            # Check for confirmation
            if user_input in ["yes", "ok", "okay", "confirm", "proceed", "continue"]:
                state.response = "✅ Review confirmed. Moving to eligibility check."
                state.stage = ConversationStage.ELIGIBILITY_CHECK
                return state
            
            # Default response
            state.response = "❓ Please say 'yes' to continue, 'no' to skip review, or specify what you'd like to edit."
            return state
        else:
            # Generate comprehensive review
            review_text = self._generate_comprehensive_review(state)
            state.response = review_text
            return state

    async def _eligibility_check_node(self, state: ConversationState) -> ConversationState:
        """Eligibility check node - tests eligibility by uploading data to EFR and hitting eligibility endpoint"""
        state.stage = ConversationStage.ELIGIBILITY_CHECK
        
        if state.user_input and state.user_input.strip():
            user_input = state.user_input.strip().lower()
            
            # Check for commands
            if user_input in ["no", "skip", "continue", "next"]:
                state.response = "✅ Skipping eligibility check. Moving to summary."
                state.stage = ConversationStage.SUMMARY
                return state
            
            # Check for confirmation
            if user_input in ["yes", "ok", "okay", "confirm", "proceed", "check", "test"]:
                # Perform eligibility check
                eligibility_result = await self._perform_eligibility_check(state)
                state.response = eligibility_result
                state.stage = ConversationStage.SUMMARY
                return state
            
            # Default response
            state.response = "❓ Please say 'yes' to perform eligibility check, 'no' to skip, or 'check' to test eligibility."
            return state
        else:
            # Ask for eligibility check
            state.response = """🔍 **Eligibility Check**

Would you like to test your eligibility for PM-KISAN now?

This will:
• Upload your data to the EFR database
• Run eligibility checks against the scheme rules
• Show you the results

Please respond with:
• 'yes' or 'check' - to perform eligibility check
• 'no' or 'skip' - to skip and continue"""
            return state

    async def _perform_eligibility_check(self, state: ConversationState) -> str:
        """Perform actual eligibility check by uploading to EFR and testing"""
        try:
            print(f"🔍 DEBUG: Starting eligibility check")
            
            # First, upload data to EFR
            upload_result = await self.upload_to_efr_database(state)
            
            if not upload_result.get("success"):
                return f"❌ Failed to upload data for eligibility check: {upload_result.get('message', 'Unknown error')}"
            
            farmer_id = upload_result.get("farmer_id")
            print(f"🔍 DEBUG: Data uploaded with farmer_id: {farmer_id}")
            
            # Now test eligibility using the eligibility endpoint
            async with self.efr_client as client:
                eligibility_url = f"http://localhost:8001/eligibility/pm-kisan/{farmer_id}"
                eligibility_response = await client._fetch_with_retry(eligibility_url)
                
                if not eligibility_response or not eligibility_response.get("success"):
                    return f"❌ Failed to check eligibility: {eligibility_response.get('message', 'Unknown error') if eligibility_response else 'No response'}"
                
                eligibility_data = eligibility_response.get("data", {})
                is_eligible = eligibility_data.get("is_eligible", False)
                reasons = eligibility_data.get("reasons", [])
                warnings = eligibility_data.get("warnings", [])
                
                # Format the response
                result = f"""🎯 **Eligibility Check Results**

📋 **Farmer ID:** {farmer_id}
✅ **Status:** {'ELIGIBLE' if is_eligible else 'NOT ELIGIBLE'}

"""
                
                if is_eligible:
                    result += "🎉 **Congratulations!** You are eligible for PM-KISAN benefits.\n\n"
                else:
                    result += "❌ **Not Eligible** - Please review the reasons below:\n\n"
                
                if reasons:
                    result += "📝 **Reasons:**\n"
                    for reason in reasons:
                        result += f"• {reason}\n"
                    result += "\n"
                
                if warnings:
                    result += "⚠️ **Warnings:**\n"
                    for warning in warnings:
                        result += f"• {warning}\n"
                    result += "\n"
                
                result += f"📊 **Next Steps:** {'Your application will be processed for benefits.' if is_eligible else 'Please address the issues above and try again.'}"
                
                return result
                
        except Exception as e:
            print(f"❌ Eligibility check failed: {e}")
            return f"❌ Eligibility check failed: {str(e)}"

    def _generate_comprehensive_review(self, state: ConversationState) -> str:
        """Generate a comprehensive review of all collected information"""
        review = """📋 **Application Review**

Please review all the information collected so far:

"""
        
        # Basic Information
        review += "👤 **Basic Information:**\n"
        if state.collected_data:
            for field, data in state.collected_data.items():
                if hasattr(data, 'value'):
                    review += f"• {field.replace('_', ' ').title()}: {data.value}\n"
                else:
                    review += f"• {field.replace('_', ' ').title()}: {data}\n"
        else:
            review += "• No basic information collected\n"
        review += "\n"
        
        # Family Members
        review += "👨‍👩‍👧‍👦 **Family Members:**\n"
        if state.family_members:
            for i, member in enumerate(state.family_members, 1):
                review += f"• Member {i}: {member.get('name', 'N/A')} ({member.get('relation', 'N/A')}, {member.get('age', 'N/A')} years, {member.get('gender', 'N/A')})\n"
        else:
            review += "• No family members added\n"
        review += "\n"
        
        # Exclusion Criteria
        review += "🚫 **Exclusion Criteria:**\n"
        if state.exclusion_data:
            for field, value in state.exclusion_data.items():
                if field not in ["government_post", "monthly_pension"]:  # Skip conditional fields
                    review += f"• {field.replace('_', ' ').title()}: {'Yes' if value else 'No'}\n"
            
            # Show conditional fields if applicable
            if state.exclusion_data.get("is_government_employee"):
                review += f"• Government Post: {state.exclusion_data.get('government_post', 'N/A')}\n"
            if state.exclusion_data.get("is_pensioner"):
                review += f"• Monthly Pension: Rs. {state.exclusion_data.get('monthly_pension', 'N/A')}\n"
        else:
            review += "• No exclusion criteria answered\n"
        review += "\n"
        
        # Special Provisions
        review += "🏛️ **Special Provisions:**\n"
        if state.special_provisions:
            for field, value in state.special_provisions.items():
                review += f"• {field.replace('_', ' ').title()}: {value}\n"
        else:
            review += "• No special provisions recorded\n"
        review += "\n"
        
        review += """**Review Options:**
• Say 'yes' or 'confirm' to proceed
• Say 'no' or 'skip' to skip review
• Say 'edit [section]' to modify information (e.g., 'edit basic info', 'edit family members')

What would you like to do?"""
        
        return review

    def _review_done(self, state: ConversationState) -> str:
        """Determine next step after review"""
        if state.user_input and state.user_input.strip():
            user_input = state.user_input.strip().lower()
            
            if user_input in ["yes", "ok", "okay", "confirm", "proceed", "continue"]:
                return "ELIGIBILITY_CHECK"
            elif user_input in ["no", "skip"]:
                return "ELIGIBILITY_CHECK"
            elif any(word in user_input for word in ["edit", "change", "update", "modify"]):
                # Determine which section to edit
                if any(word in user_input for word in ["basic", "personal", "name", "age", "phone", "address"]):
                    return "BASIC_INFO"
                elif any(word in user_input for word in ["family", "member", "wife", "husband", "son", "daughter"]):
                    return "FAMILY_MEMBERS"
                elif any(word in user_input for word in ["exclusion", "eligibility", "government", "pension"]):
                    return "EXCLUSION_CRITERIA"
                elif any(word in user_input for word in ["special", "provision", "certificate", "region"]):
                    return "SPECIAL_PROVISIONS"
                else:
                    return "REVIEW"  # Stay in review for clarification
        
        return "REVIEW"  # Stay in review

    def _eligibility_check_done(self, state: ConversationState) -> str:
        """Determine next step after eligibility check"""
        if state.user_input and state.user_input.strip():
            user_input = state.user_input.strip().lower()
            
            if user_input in ["yes", "ok", "okay", "confirm", "proceed", "check", "test"]:
                return "SUMMARY"  # After eligibility check, move to summary
            elif user_input in ["no", "skip"]:
                return "SUMMARY"
        
        return "ELIGIBILITY_CHECK"  # Stay in eligibility check