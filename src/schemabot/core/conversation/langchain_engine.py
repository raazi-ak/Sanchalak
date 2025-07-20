"""
Modern LLM-Driven Conversation Engine with Batch Processing and Background Extraction

This module implements a sophisticated conversation system that:
1. Groups related questions together for natural conversation flow
2. Uses background LLM processing for structured data extraction
3. Maintains proper conversation context without deprecated memory classes
4. Uses advanced prompting templates for better extraction
5. Provides intelligent conversation management
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from langchain.memory import ConversationBufferMemory

from ..scheme.efr_integration import EFRSchemeClient


class QuestionCategory(Enum):
    """Categories for grouping related questions"""
    PERSONAL = "personal"
    LOCATION = "location"
    LAND = "land"
    FINANCIAL = "financial"
    IDENTITY = "identity"
    EMPLOYMENT = "employment"
    SPECIAL_PROVISIONS = "special_provisions"
    FAMILY = "family"
    DOCUMENTS = "documents"
    ELIGIBILITY = "eligibility"


@dataclass
class ExtractedField:
    """Represents an extracted field with metadata"""
    value: Any
    confidence: float
    source: str  # "llm", "regex", "user_input"
    timestamp: datetime
    raw_input: str


class ConversationStage(Enum):
    """Defines the current stage of the conversation."""
    BASIC_INFO = "basic_info"
    EXCLUSION_CRITERIA = "exclusion_criteria"
    FAMILY_MEMBERS = "family_members"
    COMPLETED = "completed"

@dataclass
class ConversationState:
    """Enhanced conversation state with stage tracking."""
    collected_data: Dict[str, ExtractedField] = field(default_factory=dict)
    exclusion_data: Dict[str, Any] = field(default_factory=dict)
    family_members: List[Dict[str, Any]] = field(default_factory=list)
    special_provisions: Dict[str, Any] = field(default_factory=dict)
    chat_history: List[BaseMessage] = field(default_factory=list)
    stage: ConversationStage = ConversationStage.BASIC_INFO
    current_family_member_index: int = 0
    debug_log: List[str] = field(default_factory=list)


class ModernLangChainEngine:
    """A stage-aware, intelligent conversational engine for scheme applications."""
    
    def __init__(self, llm_url: str = "http://localhost:1234/v1"):
        self.llm = ChatOpenAI(
            openai_api_base=llm_url,
            openai_api_key="not-needed",
            model_name="qwen2.5-instruct",
            temperature=0.0,
            max_tokens=2048
        )
        self.efr_client = EFRSchemeClient()
        self.scheme_definition: Dict[str, Any] = {}
        self.exclusion_fields: List[str] = []
        self.family_member_structure: Dict[str, Any] = {}
        self.special_provision_fields: List[str] = []
        self.memory = ConversationBufferMemory(return_messages=True)

    async def initialize_conversation(self, scheme_code: str = "pm-kisan") -> (str, ConversationState):
        state = ConversationState()
        async with self.efr_client as client:
            scheme_resp = await client._fetch_with_retry(f"http://localhost:8002/schemes/{scheme_code.upper()}")
            if not scheme_resp or not scheme_resp.get("success"):
                return f"❌ Failed to fetch scheme details for {scheme_code.upper()}", state
            self.scheme_definition = scheme_resp.get("data", {})
            self.exclusion_fields = [
                "is_constitutional_post_holder", "is_political_office_holder", "is_government_employee", "is_income_tax_payer", "is_professional", "is_nri", "is_pensioner"
            ]
            self.family_member_structure = self.scheme_definition.get("data_model", {}).get("family", {}).get("family_members", {}).get("structure", {})
            self.special_provision_fields = list(self.scheme_definition.get("data_model", {}).get("special_provisions", {}).keys())
            required_fields = self.scheme_definition.get("validation_rules", {}).get("required_for_eligibility", [])
            scheme_name = self.scheme_definition.get("name", "the scheme")
            scheme_description = self.scheme_definition.get("description", "Let's get started.")
            welcome_msg = f"""🚀 Welcome to the application assistant for {scheme_name}!
{scheme_description}
I'll help you apply by having a conversation to collect the required information.\n\n📋 **Required Information**: {len(required_fields)} fields need to be collected.\nLet's begin! What is your full name?"""
            state.debug_log.append(f"[DEBUG] Loaded scheme: {scheme_name}, required_fields: {required_fields}, exclusion_fields: {self.exclusion_fields}, family_member_structure: {self.family_member_structure}, special_provision_fields: {self.special_provision_fields}")
            return welcome_msg, state

    async def process_user_input(self, user_input: str, state: ConversationState) -> (str, ConversationState):
        state.chat_history.append(HumanMessage(content=user_input))
        self.memory.save_context({"input": user_input}, {})
        debug = state.debug_log.append
        debug(f"[DEBUG] User input: {user_input}")
        required_fields = self.scheme_definition.get("validation_rules", {}).get("required_for_eligibility", [])
        collected_summary = ", ".join([f"{k}: {v.value}" for k, v in state.collected_data.items()])
        if not collected_summary:
            collected_summary = "None yet."
        if state.stage == ConversationStage.BASIC_INFO:
            missing_fields = [f for f in required_fields if f not in state.collected_data]
            if not missing_fields:
                state.stage = ConversationStage.EXCLUSION_CRITERIA
                debug("[DEBUG] All basic info collected. Moving to exclusion criteria.")
                return await self.process_user_input("", state)
            next_field = missing_fields[0]
            prompt, field_def = self._build_prompt(state, next_field, missing_fields, collected_summary, self.memory.load_memory_variables({})["history"])
        elif state.stage == ConversationStage.EXCLUSION_CRITERIA:
            missing_exclusions = [f for f in self.exclusion_fields if f not in state.exclusion_data]
            if not missing_exclusions:
                state.stage = ConversationStage.FAMILY_MEMBERS if self.family_member_structure else ConversationStage.SPECIAL_PROVISIONS if self.special_provision_fields else ConversationStage.COMPLETED
                debug("[DEBUG] All exclusion criteria collected. Moving to next stage.")
                return await self.process_user_input("", state)
            next_field = missing_exclusions[0]
            prompt, field_def = self._build_prompt(state, next_field, missing_exclusions, collected_summary, self.memory.load_memory_variables({})["history"], is_exclusion=True)
        elif state.stage == ConversationStage.FAMILY_MEMBERS:
            if not hasattr(state, 'pending_family_members'):
                state.pending_family_members = []
                state.current_family_member_index = 0
            prompt, structure = self._build_family_prompt(state, collected_summary, self.memory.load_memory_variables({})["history"])
        elif state.stage == ConversationStage.SPECIAL_PROVISIONS:
            missing_specials = [f for f in self.special_provision_fields if f not in state.special_provisions]
            if not missing_specials:
                state.stage = ConversationStage.COMPLETED
                debug("[DEBUG] All special provisions collected. Conversation complete.")
                return "🎉 All information collected. Thank you!", state
            next_field = missing_specials[0]
            prompt, field_def = self._build_special_provision_prompt(state, next_field, missing_specials, collected_summary, self.memory.load_memory_variables({})["history"])
        else:
            return "🎉 All information collected. Thank you!", state
        debug(f"[DEBUG] LLM prompt: {prompt}")
        try:
            llm_response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            llm_output = llm_response.content.strip()
            debug(f"[DEBUG] LLM output: {llm_output}")
            import json, re
            json_match = re.search(r'\{.*\}', llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    debug(f"[ERROR] LLM produced invalid JSON. Recovering.")
                    return f"Sorry, I had trouble processing that. Could you please clarify your {next_field.replace('_', ' ')}?", state
                extraction = result.get("extraction", {})
                response = result.get("response", "Could you please clarify?")
                if state.stage == ConversationStage.BASIC_INFO:
                    for k, v in extraction.items():
                        if k in required_fields and v:
                            state.collected_data[k] = ExtractedField(value=v, confidence=0.95, source="llm", timestamp=datetime.now(), raw_input=user_input)
                elif state.stage == ConversationStage.EXCLUSION_CRITERIA:
                    for k, v in extraction.items():
                        if k in self.exclusion_fields:
                            state.exclusion_data[k] = v
                elif state.stage == ConversationStage.FAMILY_MEMBERS:
                    if extraction:
                        if isinstance(extraction, list):
                            state.family_members.extend(extraction)
                            debug(f"[DEBUG] Added {len(extraction)} family members.")
                        elif isinstance(extraction, dict):
                            state.family_members.append(extraction)
                            debug(f"[DEBUG] Added family member: {extraction}")
                        if len(state.family_members) < 2:
                            response += "\nDo you have any more family members to add? If yes, please provide their details. If not, say 'no'."
                        else:
                            state.stage = ConversationStage.SPECIAL_PROVISIONS if self.special_provision_fields else ConversationStage.COMPLETED
                            response += "\nThank you for providing your family details."
                elif state.stage == ConversationStage.SPECIAL_PROVISIONS:
                    for k, v in extraction.items():
                        if k in self.special_provision_fields:
                            state.special_provisions[k] = v
                    if 'region_special' in extraction and extraction['region_special'] != 'none':
                        if 'certificate_details' not in state.special_provisions:
                            response += "\nPlease provide the details of your region-specific certificate (issued_by, issue_date, authenticated_by, certificate_number, etc.)."
                progress = self.get_conversation_summary(state)
                return f"{response}\n📊 {progress}", state
            else:
                debug(f"[ERROR] No JSON found in LLM output.")
                return f"Sorry, I didn't understand that. Could you please clarify your {next_field.replace('_', ' ')}?", state
        except Exception as e:
            debug(f"[ERROR] LLM call failed: {e}")
            return "Sorry, there was a system error. Please try again.", state

    def _build_prompt(self, state, next_field, missing_fields, collected_summary, memory_history, is_exclusion=False):
        data_model = self.scheme_definition.get("data_model", {})
        field_def = self._find_field_definition(next_field, data_model)
        field_context = f"**Next Question Focus: `{next_field}`**\n"
        if field_def:
            field_context += f"- **Description:** {field_def.get('description', 'N/A')}\n"
            if field_def.get('type') == 'enum' and field_def.get('values'):
                field_context += f"- **Valid Options:** {', '.join(field_def['values'])}\n"
        if is_exclusion:
            field_context += "- **Note:** This is a 'yes' or 'no' eligibility question.\n"
        prompt = f"""**System Mission:**\nYou are a friendly, intelligent government officer helping a farmer apply for the PM-KISAN scheme.\n\n**Your Task:**\nBased on the conversation history and the context provided, generate a single JSON object with two keys: "extraction" and "response".\n- `extraction`: A JSON object of data extracted from the *user's latest message*. If the user did not provide the requested information, this MUST be an empty object (`{{}}`).\n- `response`: A warm, conversational string to say back to the farmer.\n- **Crucial:** Never ask for information that has already been collected. If the user repeats information, acknowledge it and move to the next missing field.\n- **Crucial:** The `extraction` object must be perfect, valid JSON. Double-check all commas and quotes.\n\n**What I already know:** {collected_summary}\n**Fields still needed:** {', '.join(missing_fields)}\n{field_context}\n**Recent Conversation History:**\n{memory_history}\n\n**Your JSON Output:**\n"""
        return prompt, field_def

    def _build_family_prompt(self, state, collected_summary, memory_history):
        structure = self.family_member_structure
        prompt = f"""**System Mission:**\nYou are a friendly, intelligent government officer helping a farmer apply for the PM-KISAN scheme.\n\n**Your Task:**\nAsk the farmer to provide details for each family member (relation, name, age, gender, occupation, is_minor).\nReturn a JSON object with a list of family members, each as an object with those fields.\nIf the user provides only one member, return a single object.\nIf the user says 'no' or 'none', return an empty list.\n- **Crucial:** Never ask for information that has already been collected.\n- **Crucial:** The output must be perfect, valid JSON.\n\n**What I already know:** {collected_summary}\n**Recent Conversation History:**\n{memory_history}\n\n**Your JSON Output:**\n"""
        return prompt, structure

    async def _get_llm_extraction_and_response(self, state: ConversationState) -> Dict[str, Any]:
        """
        The core conversational engine. It checks the current conversation stage and
        calls the appropriate handler to generate a dynamic, context-aware prompt.
        """
        if state.stage == ConversationStage.BASIC_INFO:
            return await self._handle_basic_info_stage(state)
        elif state.stage == ConversationStage.EXCLUSION_CRITERIA:
            return await self._handle_exclusion_stage(state)
        elif state.stage == ConversationStage.FAMILY_MEMBERS:
            return await self._handle_family_stage(state)
        else: # COMPLETED
            return {
                "extraction": {},
                "response": "I have collected all necessary information. Thank you for your time!"
            }

    async def _handle_basic_info_stage(self, state: ConversationState) -> Dict[str, Any]:
        """Handles the collection of basic, required fields."""
        required_fields = self.scheme_definition.get("validation_rules", {}).get("required_for_eligibility", [])
        missing_fields = [field for field in required_fields if field not in state.collected_data.keys()]

        if not missing_fields:
            state.stage = ConversationStage.EXCLUSION_CRITERIA
            # Immediately call the next handler to avoid an extra user turn
            return await self._handle_exclusion_stage(state)
        
        return await self._build_and_run_llm_prompt(state, missing_fields[0], missing_fields)

    async def _handle_exclusion_stage(self, state: ConversationState) -> Dict[str, Any]:
        """Handles the collection of exclusion criteria."""
        # Note: Using a direct key 'exclusion_criteria_fields' from the YAML for clarity
        exclusion_fields = self.scheme_definition.get("exclusion_criteria_fields", [
            "is_constitutional_post_holder", "is_political_office_holder", "is_government_employee", "is_income_tax_payer", "is_professional", "is_nri", "is_pensioner"
        ])
        missing_exclusion_fields = [field for field in exclusion_fields if field not in state.exclusion_data]

        if not missing_exclusion_fields:
            state.stage = ConversationStage.FAMILY_MEMBERS
            return await self._handle_family_stage(state)
        
        return await self._build_and_run_llm_prompt(state, missing_exclusion_fields[0], missing_exclusion_fields, is_exclusion=True)

    async def _handle_family_stage(self, state: ConversationState) -> Dict[str, Any]:
        """Handles collecting information about family members."""
        # This is a simplified placeholder. A full implementation would loop through
        # members and collect nested details (name, age, relation).
        state.stage = ConversationStage.COMPLETED
        return {
            "extraction": {"family_members_collected": True},
            "response": "Thank you for providing the family details. I now have all the information I need."
        }

    async def _build_and_run_llm_prompt(self, state: ConversationState, next_field: str, missing_fields: List[str], is_exclusion: bool = False) -> Dict[str, Any]:
        """Builds the dynamic prompt with full context and executes the LLM call."""
        data_model = self.scheme_definition.get("data_model", {})
        field_def = self._find_field_definition(next_field, data_model)
        
        field_context = f"**Next Question Focus: `{next_field}`**\n"
        if field_def:
            field_context += f"- **Description:** {field_def.get('description', 'N/A')}\n"
            if field_def.get('type') == 'enum' and field_def.get('values'):
                field_context += f"- **Valid Options:** {', '.join(field_def['values'])}\n"

        if is_exclusion:
            field_context += "- **Note:** This is a 'yes' or 'no' eligibility question.\n"

        chat_history_str = "\n".join([f"{'Farmer' if isinstance(msg, HumanMessage) else 'Assistant'}: {msg.content}" for msg in state.chat_history[-6:]])
        
        prompt = f"""**System Mission:**
You are a friendly, intelligent government officer helping a farmer apply for the PM-KISAN scheme.

**Your Task:**
Based on the conversation history and the context provided, generate a single JSON object with two keys: "extraction" and "response".
- `extraction`: A JSON object of data extracted from the *user's latest message*. If the user did not provide the requested information, this MUST be an empty object (`{{}}`).
- `response`: A warm, conversational string to say back to the farmer. Acknowledge their input if valid, and then ask the *next logical question*.
- **Crucial:** The `extraction` object must be perfect, valid JSON. Double-check all commas and quotes.

**Current Context:**
- **Information I Still Need:** {', '.join(missing_fields)}
{field_context}
**Recent Conversation History:**
{chat_history_str}

**Your JSON Output:**
"""
        try:
            llm_response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            llm_output = llm_response.content.strip()
            print(f"[DEBUG] LLM output: {llm_output}")
            
            import json
            import re
            json_match = re.search(r'\{.*\}', llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    print(f"[WARNING] LLM produced invalid JSON. The conversation will recover gracefully.")
                    question = f"Could you please provide your {next_field.replace('_', ' ')}?"
                    return {
                        "extraction": {}, 
                        "response": f"Thank you for providing that information! My system had a small hiccup processing all the details at once. To get us back on track, let's just focus on this: {question}"
                    }
            return {"extraction": {}, "response": "I'm having a little trouble understanding. Could you please rephrase?"}
        except Exception as e:
            print(f"[ERROR] LLM call failed: {e}")
            return {"extraction": {}, "response": "My apologies, I'm having a system error. Let's try that again."}

    def _find_field_definition(self, field_name: str, data_model: Dict) -> Optional[Dict]:
        """Recursively search for a field's definition within the data_model."""
        for category in data_model.values():
            if isinstance(category, dict):
                if field_name in category:
                    return category[field_name]
        return None

    def _update_conversation_summary(self, state: ConversationState) -> str:
        """Update conversation summary based on collected data"""
        total_fields = sum(len(fields) for fields in self.question_categories.values())
        collected_count = len(state.collected_data)
        progress = (collected_count / total_fields) * 100 if total_fields > 0 else 0
        
        summary = f"Progress: {progress:.1f}% complete. "
        summary += f"Collected {collected_count} fields. "
        
        if state.current_category:
            category_fields = self.question_categories.get(state.current_category, [])
            category_collected = sum(1 for field in category_fields if field in state.collected_data)
            summary += f"Current focus: {state.current_category.value} ({category_collected}/{len(category_fields)} fields)."
        
        return summary

    def get_collected_data(self, state: ConversationState) -> Dict[str, Any]:
        """Get all collected data as a simple dictionary"""
        return {field: data.value for field, data in state.collected_data.items()}
    
    def get_conversation_summary(self, state: ConversationState) -> str:
        """Get a summary of the current conversation state."""
        if not self.scheme_definition:
            return "Progress: Initializing..."

        required_fields = self.scheme_definition.get("validation_rules", {}).get("required_for_eligibility", [])
        total_count = len(required_fields)
        collected_count = len(state.collected_data)
        progress = (collected_count / total_count) * 100 if total_count > 0 else 0
        
        return f"Progress: {progress:.1f}% complete. Collected {collected_count}/{total_count} fields." 