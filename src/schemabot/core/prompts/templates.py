#schemabot\core\prompts\templates.py

from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel

class ConversationStage(str, Enum):
    GREETING = "greeting"
    DATA_COLLECTION = "data_collection"
    CLARIFICATION = "clarification"
    ELIGIBILITY_CHECK = "eligibility_check"
    RESULT_DELIVERY = "result_delivery"
    FOLLOWUP = "followup"

class PromptTemplate(BaseModel):
    stage: ConversationStage
    template: str
    required_variables: List[str]
    optional_variables: List[str] = []

class SchemePromptTemplates:
    """Centralized prompt templates for different conversation stages"""
    
    GREETING_TEMPLATE = PromptTemplate(
        stage=ConversationStage.GREETING,
        template="""You are Sanchalak, a helpful government scheme assistant. You help farmers check their eligibility for the {scheme_name} scheme.

SCHEME INFORMATION:
- Name: {scheme_name}
- Ministry: {ministry}
- Description: {description}
- Benefits: {benefits_summary}

YOUR ROLE:
1. Greet the farmer warmly
2. Explain that you'll help check eligibility for {scheme_name}
3. Mention that you'll need to ask a few questions
4. Ask for the first required piece of information

IMPORTANT CONSTRAINTS:
- ONLY discuss {scheme_name} scheme eligibility
- Do NOT provide general farming advice
- Do NOT discuss other schemes unless specifically asked
- Keep responses conversational but focused
- Ask for ONE piece of information at a time

Start the conversation by greeting the farmer and asking for: {first_required_field}""",
        required_variables=["scheme_name", "ministry", "description", "benefits_summary", "first_required_field"]
    )
    
    DATA_COLLECTION_TEMPLATE = PromptTemplate(
        stage=ConversationStage.DATA_COLLECTION,
        template="""Continue helping the farmer with {scheme_name} eligibility check.

COLLECTED INFORMATION:
{collected_data}

STILL NEEDED:
{missing_fields}

USER'S RESPONSE: "{user_input}"

CONTEXT:
- You are collecting information to check eligibility for {scheme_name}
- The farmer just provided: "{user_input}"
- Next information needed: {next_field}

INSTRUCTIONS:
1. If the user provided valid information for {current_field}, acknowledge it positively
2. If the information is unclear or invalid, ask for clarification
3. Then ask for the next required field: {next_field}
4. If user asks unrelated questions, politely redirect to scheme eligibility
5. Keep responses brief and focused

RESPONSE FORMAT:
- Acknowledge what they provided (if valid)
- Ask for the next piece of information clearly
- Explain why this information is needed for {scheme_name}""",
        required_variables=["scheme_name", "collected_data", "missing_fields", "user_input", "next_field", "current_field"]
    )
    
    CLARIFICATION_TEMPLATE = PromptTemplate(
        stage=ConversationStage.CLARIFICATION,
        template="""The farmer provided unclear information for {scheme_name} eligibility check.

ISSUE: {clarification_needed}
USER SAID: "{user_input}"
EXPECTED: {expected_format}

INSTRUCTIONS:
1. Politely explain that the information needs clarification
2. Provide examples of the expected format
3. Ask them to provide the information again
4. Be helpful and patient

Example response format for {field_name}:
{example_format}""",
        required_variables=["scheme_name", "clarification_needed", "user_input", "expected_format", "field_name", "example_format"]
    )
    
    ELIGIBILITY_RESULT_TEMPLATE = PromptTemplate(
        stage=ConversationStage.RESULT_DELIVERY,
        template="""Deliver the eligibility result for {scheme_name}.

ELIGIBILITY STATUS: {eligibility_status}
ELIGIBILITY SCORE: {eligibility_score}%

{result_details}

INSTRUCTIONS:
1. Clearly state whether they are eligible or not
2. If eligible: Explain benefits and next steps
3. If not eligible: Explain reasons and provide recommendations
4. Be empathetic and helpful
5. Offer to help with questions about the result

{additional_instructions}""",
        required_variables=["scheme_name", "eligibility_status", "eligibility_score", "result_details", "additional_instructions"]
    )

class PromptBuilder:
    """Builds dynamic prompts based on conversation context"""
    
    def __init__(self):
        self.templates = SchemePromptTemplates()
    
    def build_prompt(
        self, 
        stage: ConversationStage, 
        variables: Dict[str, Any]
    ) -> str:
        """Build prompt for specific conversation stage"""
        
        template_map = {
            ConversationStage.GREETING: self.templates.GREETING_TEMPLATE,
            ConversationStage.DATA_COLLECTION: self.templates.DATA_COLLECTION_TEMPLATE,
            ConversationStage.CLARIFICATION: self.templates.CLARIFICATION_TEMPLATE,
            ConversationStage.RESULT_DELIVERY: self.templates.ELIGIBILITY_RESULT_TEMPLATE,
        }
        
        template = template_map.get(stage)
        if not template:
            raise ValueError(f"No template found for stage: {stage}")
        
        # Validate required variables
        missing_vars = set(template.required_variables) - set(variables.keys())
        if missing_vars:
            raise ValueError(f"Missing required variables: {missing_vars}")
        
        # Build prompt
        try:
            return template.template.format(**variables)
        except KeyError as e:
            raise ValueError(f"Template formatting error: {e}")
