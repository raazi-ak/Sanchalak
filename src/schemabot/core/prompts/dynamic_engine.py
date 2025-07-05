from typing import Dict, Any, List, Optional, Tuple
from ..scheme.models import GovernmentScheme
from ..scheme.parser import SchemeParser
from ..scheme.canonical_integration import CanonicalIntegration
from ..eligibility.checker import EligibilityChecker, EligibilityResult
from .templates import PromptBuilder, ConversationStage
import structlog
import re

logger = structlog.get_logger(__name__)

class ConversationContext:
    """Manages conversation state and context"""
    
    def __init__(self, scheme_code: str):
        self.scheme_code = scheme_code
        self.stage = ConversationStage.GREETING
        self.collected_data: Dict[str, Any] = {}
        self.conversation_history: List[Dict[str, str]] = []
        self.current_field: Optional[str] = None
        self.attempts_count: Dict[str, int] = {}
        self.eligibility_result: Optional[EligibilityResult] = None

class DynamicPromptEngine:
    """Main engine for generating dynamic prompts based on conversation context"""
    
    def __init__(self, scheme_parser: SchemeParser, eligibility_checker: EligibilityChecker):
        self.scheme_parser = scheme_parser
        self.eligibility_checker = eligibility_checker
        self.canonical_integration = CanonicalIntegration()
        self.prompt_builder = PromptBuilder()
        self.data_extractors = self._initialize_data_extractors()
    
    async def generate_initial_prompt(self, scheme_code: str) -> Tuple[str, ConversationContext]:
        """Generate the initial greeting prompt using canonical data"""
        # Initialize canonical integration
        await self.canonical_integration.initialize()
        
        # Get canonical scheme info
        scheme_info = self.canonical_integration.get_scheme_info_for_prompts(scheme_code)
        if not scheme_info:
            return "I'm sorry, I couldn't find information about that scheme.", None
        
        context = ConversationContext(scheme_code)
        required_fields = self.canonical_integration.get_required_fields(scheme_code)
        
        if not required_fields:
            return "This scheme doesn't require any specific information to check eligibility.", context
        
        context.current_field = required_fields[0]
        context.stage = ConversationStage.GREETING
        
        # Prepare template variables using canonical data
        variables = {
            "scheme_name": scheme_info["scheme_name"],
            "ministry": scheme_info["ministry"],
            "description": scheme_info["description"],
            "benefits_summary": f"Comprehensive benefits for {scheme_info['scheme_name']}",
            "first_required_field": self._format_field_request_canonical(scheme_code, required_fields[0])
        }
        
        prompt = self.prompt_builder.build_prompt(ConversationStage.GREETING, variables)
        
        logger.info(f"Generated initial prompt for scheme: {scheme_code} using canonical data")
        return prompt, context
    
    async def generate_followup_prompt(
        self, 
        context: ConversationContext, 
        user_input: str
    ) -> str:
        """Generate follow-up prompt based on user input and context using canonical data"""
        
        # Initialize canonical integration if needed
        await self.canonical_integration.initialize()
        
        # Get canonical scheme info
        scheme_info = self.canonical_integration.get_scheme_info_for_prompts(context.scheme_code)
        if not scheme_info:
            return "I'm sorry, there was an error accessing the scheme information."
        
        # Add user input to conversation history
        context.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
        # Extract data from user input using canonical field definitions
        extracted_data = self._extract_data_from_input_canonical(user_input, context.current_field, context.scheme_code)
        
        # Update collected data if extraction was successful
        if extracted_data:
            context.collected_data.update(extracted_data)
            context.attempts_count[context.current_field] = 0  # Reset attempts
        else:
            # Increment attempts for current field
            context.attempts_count[context.current_field] = context.attempts_count.get(context.current_field, 0) + 1
        
        # Determine next action based on current state
        return await self._determine_next_action_canonical(context, user_input, scheme_info)
    
    def _determine_next_action(
        self, 
        context: ConversationContext, 
        user_input: str, 
        scheme: GovernmentScheme
    ) -> str:
        """Determine the next action based on conversation state"""
        
        required_fields = self.scheme_parser.get_required_fields(context.scheme_code)
        missing_fields = [f for f in required_fields if f not in context.collected_data]
        
        # Check if we need clarification
        if context.current_field and context.attempts_count.get(context.current_field, 0) > 0:
            if context.attempts_count[context.current_field] >= 3:
                # Too many attempts, move to next field or end
                missing_fields = [f for f in missing_fields if f != context.current_field]
                if missing_fields:
                    context.current_field = missing_fields[0]
                    context.stage = ConversationStage.DATA_COLLECTION
                else:
                    return self._generate_eligibility_check(context, scheme)
            else:
                # Ask for clarification
                context.stage = ConversationStage.CLARIFICATION
                return self._generate_clarification_prompt(context, user_input, scheme)
        
        # Check if all data is collected
        if not missing_fields:
            return self._generate_eligibility_check(context, scheme)
        
        # Continue data collection
        context.current_field = missing_fields[0]
        context.stage = ConversationStage.DATA_COLLECTION
        
        return self._generate_data_collection_prompt(context, user_input, scheme, missing_fields)
    
    async def _determine_next_action_canonical(
        self, 
        context: ConversationContext, 
        user_input: str, 
        scheme_info: Dict[str, Any]
    ) -> str:
        """Determine the next action based on conversation state using canonical data"""
        
        required_fields = self.canonical_integration.get_required_fields(context.scheme_code)
        missing_fields = [f for f in required_fields if f not in context.collected_data]
        
        # Check if we need clarification
        if context.current_field and context.attempts_count.get(context.current_field, 0) > 0:
            if context.attempts_count[context.current_field] >= 3:
                # Too many attempts, move to next field or end
                missing_fields = [f for f in missing_fields if f != context.current_field]
                if missing_fields:
                    context.current_field = missing_fields[0]
                    context.stage = ConversationStage.DATA_COLLECTION
                else:
                    return await self._generate_eligibility_check_canonical(context, scheme_info)
            else:
                # Ask for clarification
                context.stage = ConversationStage.CLARIFICATION
                return self._generate_clarification_prompt_canonical(context, user_input, context.scheme_code)
        
        # Check if all data is collected
        if not missing_fields:
            return await self._generate_eligibility_check_canonical(context, scheme_info)
        
        # Continue data collection
        context.current_field = missing_fields[0]
        context.stage = ConversationStage.DATA_COLLECTION
        
        return self._generate_data_collection_prompt_canonical(context, user_input, context.scheme_code, missing_fields)
    
    def _generate_data_collection_prompt(
        self, 
        context: ConversationContext, 
        user_input: str, 
        scheme: GovernmentScheme,
        missing_fields: List[str]
    ) -> str:
        """Generate data collection prompt"""
        
        variables = {
            "scheme_name": scheme.name,
            "collected_data": self._format_collected_data(context.collected_data),
            "missing_fields": self._format_missing_fields(missing_fields, scheme),
            "user_input": user_input,
            "next_field": self._format_field_request(scheme, missing_fields[0]),
            "current_field": context.current_field or "unknown"
        }
        
        return self.prompt_builder.build_prompt(ConversationStage.DATA_COLLECTION, variables)
    
    def _generate_clarification_prompt(
        self, 
        context: ConversationContext, 
        user_input: str, 
        scheme: GovernmentScheme
    ) -> str:
        """Generate clarification prompt"""
        
        field_metadata = self.scheme_parser.get_field_metadata(context.scheme_code, context.current_field)
        
        variables = {
            "scheme_name": scheme.name,
            "clarification_needed": f"Information for {context.current_field} was not clear",
            "user_input": user_input,
            "expected_format": field_metadata.get('description', 'Valid information') if field_metadata else 'Valid information',
            "field_name": context.current_field,
            "example_format": self._get_field_example(context.current_field, field_metadata)
        }
        
        return self.prompt_builder.build_prompt(ConversationStage.CLARIFICATION, variables)
    
    def _generate_eligibility_check(self, context: ConversationContext, scheme: GovernmentScheme) -> str:
        """Generate eligibility result prompt"""
        
        # Perform eligibility check
        eligibility_result = self.eligibility_checker.check_eligibility(context.collected_data, scheme)
        context.eligibility_result = eligibility_result
        context.stage = ConversationStage.RESULT_DELIVERY
        
        # Format result details
        if eligibility_result.is_eligible:
            result_details = self._format_eligible_result(scheme, eligibility_result)
            additional_instructions = "Congratulate the farmer and provide next steps for application."
        else:
            result_details = self._format_ineligible_result(scheme, eligibility_result)
            additional_instructions = "Be empathetic and provide helpful recommendations."
        
        variables = {
            "scheme_name": scheme.name,
            "eligibility_status": "ELIGIBLE" if eligibility_result.is_eligible else "NOT ELIGIBLE",
            "eligibility_score": eligibility_result.score,
            "result_details": result_details,
            "additional_instructions": additional_instructions
        }
        
        return self.prompt_builder.build_prompt(ConversationStage.RESULT_DELIVERY, variables)
    
    def _extract_data_from_input(
        self, 
        user_input: str, 
        field_name: str, 
        scheme: GovernmentScheme
    ) -> Optional[Dict[str, Any]]:
        """Extract structured data from user input"""
        
        if not field_name:
            return None
        
        extractor = self.data_extractors.get(field_name)
        if extractor:
            return extractor(user_input)
        
        # Generic extraction based on field metadata
        field_metadata = self.scheme_parser.get_field_metadata(scheme.code, field_name)
        if field_metadata:
            return self._generic_data_extraction(user_input, field_name, field_metadata)
        
        return None
    
    def _extract_data_from_input_canonical(
        self, 
        user_input: str, 
        field_name: str, 
        scheme_code: str
    ) -> Optional[Dict[str, Any]]:
        """Extract structured data from user input using canonical field definitions"""
        
        if not field_name:
            return None
        
        # Get canonical field metadata
        field_metadata = self.canonical_integration.get_field_metadata(scheme_code, field_name)
        if not field_metadata:
            return None
        
        # Use existing extractors if available
        extractor = self.data_extractors.get(field_name)
        if extractor:
            return extractor(user_input)
        
        # Use canonical field metadata for extraction
        return self._generic_data_extraction_canonical(user_input, field_name, field_metadata)
    
    def _initialize_data_extractors(self) -> Dict[str, callable]:
        """Initialize field-specific data extractors"""
        return {
            "age": self._extract_age,
            "annual_income": self._extract_income,
            "land_size": self._extract_land_size,
            "family_size": self._extract_number,
            "gender": self._extract_gender,
            "caste": self._extract_caste,
            "state": self._extract_state,
            "district": self._extract_location,
        }
    
    def _extract_age(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract age from user input"""
        # Look for numbers in the input
        numbers = re.findall(r'\b(\d{1,3})\b', user_input)
        for num in numbers:
            age = int(num)
            if 0 <= age <= 120:  # Reasonable age range
                return {"age": age}
        return None
    
    def _extract_income(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract income from user input"""
        # Look for numbers, possibly with currency symbols
        income_pattern = r'(?:rs\.?|rupees?|₹)?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:rs\.?|rupees?|₹)?'
        matches = re.findall(income_pattern, user_input.lower())
        
        if matches:
            # Take the largest number found
            income_str = max(matches, key=lambda x: float(x.replace(',', '')))
            income = float(income_str.replace(',', ''))
            return {"annual_income": income}
        
        return None
    
    def _extract_land_size(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract land size from user input"""
        # Look for numbers with area units
        land_pattern = r'(\d+(?:\.\d+)?)\s*(acre|hectare|bigha|katha|guntha)s?'
        matches = re.findall(land_pattern, user_input.lower())
        
        if matches:
            size, unit = matches[0]
            # Convert to standard unit (acres)
            size = float(size)
            if unit == "hectare":
                size *= 2.47105  # Convert hectares to acres
            elif unit == "bigha":
                size *= 0.62  # Approximate conversion
            
            return {"land_size": size}
        
        return None
    
    def _extract_number(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract a simple number from user input"""
        numbers = re.findall(r'\b(\d+)\b', user_input)
        if numbers:
            return {"number": int(numbers[0])}
        return None
    
    def _extract_gender(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract gender from user input"""
        user_lower = user_input.lower()
        if any(word in user_lower for word in ['male', 'man', 'boy', 'he', 'his']):
            return {"gender": "male"}
        elif any(word in user_lower for word in ['female', 'woman', 'girl', 'she', 'her']):
            return {"gender": "female"}
        return None
    
    def _extract_caste(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract caste category from user input"""
        user_lower = user_input.lower()
        caste_mapping = {
            'sc': ['sc', 'scheduled caste', 'dalit'],
            'st': ['st', 'scheduled tribe', 'tribal'],
            'obc': ['obc', 'other backward class', 'backward'],
            'general': ['general', 'open', 'unreserved']
        }
        
        for category, keywords in caste_mapping.items():
            if any(keyword in user_lower for keyword in keywords):
                return {"caste": category}
        
        return None
    
    def _extract_state(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract state from user input"""
        # This would typically use a comprehensive list of Indian states
        indian_states = [
            'andhra pradesh', 'assam', 'bihar', 'gujarat', 'haryana', 'himachal pradesh',
            'karnataka', 'kerala', 'madhya pradesh', 'maharashtra', 'odisha', 'punjab',
            'rajasthan', 'tamil nadu', 'telangana', 'uttar pradesh', 'west bengal'
        ]
        
        user_lower = user_input.lower()
        for state in indian_states:
            if state in user_lower:
                return {"state": state.title()}
        
        return None
    
    def _extract_location(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract location information from user input"""
        # Simple location extraction - in production, use NER or location APIs
        return {"location": user_input.strip()}
    
    def _generic_data_extraction(
        self, 
        user_input: str, 
        field_name: str, 
        field_metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generic data extraction based on field metadata"""
        
        data_type = field_metadata.get('data_type')
        
        if data_type == 'integer':
            numbers = re.findall(r'\b(\d+)\b', user_input)
            if numbers:
                return {field_name: int(numbers[0])}
        
        elif data_type == 'float':
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', user_input)
            if numbers:
                return {field_name: float(numbers[0])}
        
        elif data_type == 'boolean':
            user_lower = user_input.lower()
            if any(word in user_lower for word in ['yes', 'true', 'have', 'own']):
                return {field_name: True}
            elif any(word in user_lower for word in ['no', 'false', 'dont', "don't"]):
                return {field_name: False}
        
        else:  # string or other
            return {field_name: user_input.strip()}
        
        return None
    
    def _generic_data_extraction_canonical(
        self, 
        user_input: str, 
        field_name: str, 
        field_metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generic data extraction based on canonical field metadata"""
        
        data_type = field_metadata.get('data_type')
        
        if data_type == 'integer':
            numbers = re.findall(r'\b(\d+)\b', user_input)
            if numbers:
                return {field_name: int(numbers[0])}
        
        elif data_type == 'float':
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', user_input)
            if numbers:
                return {field_name: float(numbers[0])}
        
        elif data_type == 'boolean':
            user_lower = user_input.lower()
            if any(word in user_lower for word in ['yes', 'true', 'have', 'own']):
                return {field_name: True}
            elif any(word in user_lower for word in ['no', 'false', 'dont', "don't"]):
                return {field_name: False}
        
        elif data_type == 'enum':
            values = field_metadata.get('values', [])
            user_lower = user_input.lower()
            for value in values:
                if value.lower() in user_lower:
                    return {field_name: value}
        
        else:  # string or other
            return {field_name: user_input.strip()}
        
        return None
    
    def _format_benefits_summary(self, scheme: GovernmentScheme) -> str:
        """Format benefits for display"""
        benefits = []
        for benefit in scheme.benefits:
            if benefit.amount:
                benefits.append(f"{benefit.description} (₹{benefit.amount:,.0f})")
            else:
                benefits.append(benefit.description)
        
        return "; ".join(benefits[:3])  # Limit to first 3 benefits
    
    def _format_field_request(self, scheme: GovernmentScheme, field_name: str) -> str:
        """Format field request with context"""
        field_metadata = self.scheme_parser.get_field_metadata(scheme.code, field_name)
        
        if field_metadata:
            return f"{field_name.replace('_', ' ').title()}: {field_metadata['description']}"
        else:
            return f"{field_name.replace('_', ' ').title()}"
    
    def _format_field_request_canonical(self, scheme_code: str, field_name: str) -> str:
        """Format field request using canonical data"""
        field_metadata = self.canonical_integration.get_field_metadata(scheme_code, field_name)
        
        if field_metadata:
            return f"{field_name.replace('_', ' ').title()}: {field_metadata['description']}"
        else:
            return f"{field_name.replace('_', ' ').title()}"
    
    def _format_collected_data(self, collected_data: Dict[str, Any]) -> str:
        """Format collected data for display"""
        if not collected_data:
            return "None collected yet"
        
        formatted = []
        for key, value in collected_data.items():
            formatted.append(f"- {key.replace('_', ' ').title()}: {value}")
        
        return "\n".join(formatted)
    
    def _format_missing_fields(self, missing_fields: List[str], scheme: GovernmentScheme) -> str:
        """Format missing fields for display"""
        formatted = []
        for field in missing_fields:
            field_metadata = self.scheme_parser.get_field_metadata(scheme.code, field)
            description = field_metadata.get('description', '') if field_metadata else ''
            formatted.append(f"- {field.replace('_', ' ').title()}: {description}")
        
        return "\n".join(formatted)
    
    def _get_field_example(self, field_name: str, field_metadata: Optional[Dict[str, Any]]) -> str:
        """Get example format for a field"""
        examples = {
            "age": "Example: 35 years old, or just '35'",
            "annual_income": "Example: Rs. 50,000 or 50000 rupees",
            "land_size": "Example: 2.5 acres or 1 hectare",
            "gender": "Example: Male or Female",
            "caste": "Example: SC, ST, OBC, or General"
        }
        
        return examples.get(field_name, "Please provide clear information")
    
    def _format_eligible_result(self, scheme: GovernmentScheme, result: EligibilityResult) -> str:
        """Format eligible result details"""
        details = [f"Congratulations! You qualify for {scheme.name}."]
        
        # Add benefits
        details.append("\nBENEFITS YOU'LL RECEIVE:")
        for benefit in scheme.benefits:
            if benefit.amount:
                details.append(f"• {benefit.description}: ₹{benefit.amount:,.0f} {benefit.frequency or ''}")
            else:
                details.append(f"• {benefit.description}")
        
        # Add documents needed
        if scheme.documents:
            details.append("\nREQUIRED DOCUMENTS:")
            for doc in scheme.documents:
                details.append(f"• {doc}")
        
        # Add application modes
        if scheme.application_modes:
            details.append(f"\nAPPLICATION METHODS: {', '.join(scheme.application_modes)}")
        
        return "\n".join(details)
    
    def _format_ineligible_result(self, scheme: GovernmentScheme, result: EligibilityResult) -> str:
        """Format ineligible result details"""
        details = [f"Unfortunately, you don't currently qualify for {scheme.name}."]
        
        # Add reasons
        if result.recommendations:
            details.append("\nREASONS:")
            for reason in result.recommendations[:3]:  # Limit to top 3
                details.append(f"• {reason}")
        
        # Add improvement suggestions
        details.append(f"\nYour eligibility score: {result.score}%")
        
        if result.score > 70:
            details.append("You're close to qualifying! Consider addressing the issues mentioned above.")
        
        return "\n".join(details)

    # Canonical prompt generation methods
    def _generate_data_collection_prompt_canonical(
        self, 
        context: ConversationContext, 
        user_input: str, 
        scheme_code: str,
        missing_fields: List[str]
    ) -> str:
        """Generate data collection prompt using canonical data"""
        
        field_name = context.current_field
        field_metadata = self.canonical_integration.get_field_metadata(scheme_code, field_name)
        
        if not field_metadata:
            return f"Please provide your {field_name.replace('_', ' ')}"
        
        description = field_metadata.get('description', '')
        data_type = field_metadata.get('data_type', 'string')
        values = field_metadata.get('values', [])
        
        prompt = f"Please provide your {field_name.replace('_', ' ').title()}"
        
        if description:
            prompt += f": {description}"
        
        if data_type == 'enum' and values:
            prompt += f"\n\nAvailable options: {', '.join(values)}"
        
        # Add examples
        examples = self.canonical_integration.get_field_prompt_examples(scheme_code, field_name)
        if examples:
            prompt += f"\n\nExamples:\n" + "\n".join([f"• {ex}" for ex in examples[:3]])
        
        return prompt
    
    def _generate_clarification_prompt_canonical(
        self, 
        context: ConversationContext, 
        user_input: str, 
        scheme_code: str
    ) -> str:
        """Generate clarification prompt using canonical data"""
        
        field_name = context.current_field
        field_metadata = self.canonical_integration.get_field_metadata(scheme_code, field_name)
        
        if not field_metadata:
            return f"I didn't understand your response for {field_name.replace('_', ' ')}. Could you please clarify?"
        
        description = field_metadata.get('description', '')
        data_type = field_metadata.get('data_type', 'string')
        values = field_metadata.get('values', [])
        
        prompt = f"I need clarification about your {field_name.replace('_', ' ').title()}"
        
        if description:
            prompt += f": {description}"
        
        if data_type == 'enum' and values:
            prompt += f"\n\nPlease choose from: {', '.join(values)}"
        
        # Add examples
        examples = self.canonical_integration.get_field_prompt_examples(scheme_code, field_name)
        if examples:
            prompt += f"\n\nExamples:\n" + "\n".join([f"• {ex}" for ex in examples[:2]])
        
        return prompt
    
    async def _generate_eligibility_check_canonical(self, context: ConversationContext, scheme_info: Dict[str, Any]) -> str:
        """Generate eligibility check prompt using canonical data"""
        
        # Validate collected data using canonical Pydantic models
        is_valid, errors, validated_data = self.canonical_integration.validate_collected_data(
            context.scheme_code, context.collected_data
        )
        
        if not is_valid:
            # Data validation failed
            error_msg = "I found some issues with the information provided:\n"
            for error in errors[:3]:  # Show first 3 errors
                error_msg += f"• {error}\n"
            error_msg += "\nPlease provide correct information for these fields."
            return error_msg
        
        # Data is valid, proceed with eligibility check
        context.stage = ConversationStage.ELIGIBILITY_CHECK
        
        # Format collected data for display
        formatted_data = self._format_collected_data(context.collected_data)
        
        prompt = f"Thank you! I have collected all the required information for {scheme_info['scheme_name']}.\n\n"
        prompt += f"COLLECTED DATA:\n{formatted_data}\n\n"
        prompt += "I'm now checking your eligibility for this scheme. This may take a moment..."
        
        # Store validated data for eligibility checking
        context.collected_data = validated_data
        
        return prompt
