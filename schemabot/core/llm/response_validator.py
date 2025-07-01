"""
LLM Response Validation for Sanchalak.

This module provides comprehensive validation of LLM responses to ensure
quality, safety, and compliance with government service standards for
the farmer scheme eligibility bot.
"""

import re
import json
import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple, Union
from enum import Enum

import structlog
from pydantic import BaseModel, Field, validator

logger = structlog.get_logger(__name__)


class ValidationLevel(Enum):
    """Validation strictness levels."""
    STRICT = "strict"      # Fail on any validation error
    MODERATE = "moderate"  # Allow minor formatting issues
    LENIENT = "lenient"    # Only fail on critical issues


class ValidationError(Enum):
    """Types of validation errors."""
    EMPTY_RESPONSE = "empty_response"
    TOO_LONG = "too_long"
    TOO_SHORT = "too_short"
    INVALID_JSON = "invalid_json"
    MISSING_REQUIRED_FIELDS = "missing_required_fields"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    INCONSISTENT_DATA = "inconsistent_data"
    LANGUAGE_MISMATCH = "language_mismatch"
    FACTUAL_ERROR = "factual_error"
    POLICY_VIOLATION = "policy_violation"
    FORMATTING_ERROR = "formatting_error"
    SPAM_DETECTED = "spam_detected"
    HALLUCINATION = "hallucination"


@dataclass
class ValidationResult:
    """Result of response validation."""
    is_valid: bool
    confidence_score: float  # 0.0 to 1.0
    errors: List[ValidationError]
    warnings: List[str]
    corrected_response: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ResponseSchema(BaseModel):
    """Expected structure for LLM responses."""
    content: str = Field(..., description="Main response content")
    intent: Optional[str] = Field(None, description="Detected user intent")
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Extracted user data")
    next_question: Optional[str] = Field(None, description="Follow-up question")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Response confidence")
    language: str = Field("hi", description="Response language")

    @validator('content')
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        return v.strip()


class LLMResponseValidator:
    """Comprehensive LLM response validator."""

    def __init__(self, validation_level: ValidationLevel = ValidationLevel.MODERATE):
        self.validation_level = validation_level

        # Load validation rules and patterns
        self._init_validation_rules()
        self._init_language_patterns()
        self._init_content_filters()

        # Statistics
        self.validation_stats = {
            "total_validations": 0,
            "passed_validations": 0,
            "failed_validations": 0,
            "errors_by_type": {},
            "avg_confidence": 0.0
        }

        logger.info(f"Response validator initialized with {validation_level.value} level")

    def _init_validation_rules(self):
        """Initialize validation rules."""
        self.rules = {
            "min_length": 10,
            "max_length": 2000,
            "min_confidence": 0.3,
            "required_fields": ["content"],
            "max_json_depth": 5,
            "max_retries": 3
        }

        # Adjust rules based on validation level
        if self.validation_level == ValidationLevel.STRICT:
            self.rules["min_confidence"] = 0.7
            self.rules["min_length"] = 20
        elif self.validation_level == ValidationLevel.LENIENT:
            self.rules["min_confidence"] = 0.1
            self.rules["min_length"] = 5

    def _init_language_patterns(self):
        """Initialize language detection patterns."""
        self.language_patterns = {
            "hi": [
                r'[ऀ-ॿ]+',  # Devanagari script
                r'(?:है|हैं|की|का|के|में|से|को|पर|यह|वह|आप|हम|मैं)'
            ],
            "en": [
                r'(?:the|and|or|but|in|on|at|to|for|of|with|by)',
                r'[a-zA-Z]+'
            ],
            "bn": [
                r'[ঀ-৿]+',  # Bengali script
                r'(?:এর|এবং|বা|কিন্তু|মধ্যে|উপর|এ|দিয়ে|জন্য)'
            ]
        }

    def _init_content_filters(self):
        """Initialize content filtering patterns."""
        self.inappropriate_patterns = [
            # Offensive language (basic patterns)
            r'(?:spam|scam|fraud|fake|cheat|lie|stupid|idiot)',

            # Political bias indicators
            r'(?:corrupt|politician|party|election|vote)',

            # Financial scam indicators
            r'(?:money back guarantee|100% profit|get rich quick|lottery|winner)',

            # Spam indicators
            r'(?:click here|visit now|call immediately|limited time|act now)',

            # Repetitive content
            r'(.{10,}){3,}'  # Same content repeated 3+ times
        ]

        self.factual_warning_patterns = [
            # Absolute claims that might be incorrect
            r'(?:always|never|all|none|every|impossible|guaranteed)',

            # Uncertain information
            r'(?:I think|maybe|probably|might be|could be|perhaps)'
        ]

    async def validate_response(
        self,
        response: Union[str, Dict[str, Any]],
        expected_language: str = "hi",
        context: Optional[Dict[str, Any]] = None,
        schema: Optional[ResponseSchema] = None
    ) -> ValidationResult:
        """
        Validate an LLM response comprehensively.

        Args:
            response: Raw LLM response (string or dict)
            expected_language: Expected response language
            context: Conversation context for validation
            schema: Expected response schema

        Returns:
            ValidationResult: Comprehensive validation result
        """
        self.validation_stats["total_validations"] += 1

        errors = []
        warnings = []
        confidence_score = 1.0
        corrected_response = None

        try:
            # Parse response if it's a string
            if isinstance(response, str):
                parsed_response = await self._parse_string_response(response)
            else:
                parsed_response = response

            # Basic validation
            basic_errors, basic_warnings = await self._validate_basic_structure(parsed_response)
            errors.extend(basic_errors)
            warnings.extend(basic_warnings)

            # Content validation
            if "content" in parsed_response:
                content_errors, content_warnings = await self._validate_content(
                    parsed_response["content"], expected_language
                )
                errors.extend(content_errors)
                warnings.extend(content_warnings)

            # Schema validation
            if schema:
                schema_errors, schema_warnings = await self._validate_schema(parsed_response, schema)
                errors.extend(schema_errors)
                warnings.extend(schema_warnings)

            # Context validation
            if context:
                context_errors, context_warnings = await self._validate_context_consistency(
                    parsed_response, context
                )
                errors.extend(context_errors)
                warnings.extend(context_warnings)

            # Safety validation
            safety_errors, safety_warnings = await self._validate_safety(parsed_response)
            errors.extend(safety_errors)
            warnings.extend(safety_warnings)

            # Calculate confidence score
            confidence_score = await self._calculate_confidence_score(
                parsed_response, errors, warnings
            )

            # Attempt correction if needed
            if errors and self.validation_level != ValidationLevel.STRICT:
                corrected_response = await self._attempt_correction(
                    parsed_response, errors
                )

            # Determine if validation passed
            is_valid = await self._determine_validity(errors, confidence_score)

            # Update statistics
            if is_valid:
                self.validation_stats["passed_validations"] += 1
            else:
                self.validation_stats["failed_validations"] += 1

            for error in errors:
                self.validation_stats["errors_by_type"][error.value] = (
                    self.validation_stats["errors_by_type"].get(error.value, 0) + 1
                )

            # Update average confidence
            total = self.validation_stats["total_validations"]
            current_avg = self.validation_stats["avg_confidence"]
            self.validation_stats["avg_confidence"] = (
                (current_avg * (total - 1) + confidence_score) / total
            )

            result = ValidationResult(
                is_valid=is_valid,
                confidence_score=confidence_score,
                errors=errors,
                warnings=warnings,
                corrected_response=corrected_response,
                metadata={
                    "original_response": response,
                    "parsed_response": parsed_response,
                    "validation_level": self.validation_level.value,
                    "context_provided": context is not None,
                    "schema_provided": schema is not None
                }
            )

            logger.debug(
                "Response validation completed",
                is_valid=is_valid,
                confidence_score=confidence_score,
                error_count=len(errors),
                warning_count=len(warnings)
            )

            return result

        except Exception as e:
            logger.error(f"Error during response validation: {e}", exc_info=True)
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                errors=[ValidationError.FORMATTING_ERROR],
                warnings=[f"Validation error: {str(e)}"],
                metadata={"validation_error": str(e)}
            )

    async def _parse_string_response(self, response: str) -> Dict[str, Any]:
        """Parse string response into structured format."""
        response = response.strip()

        # Try to parse as JSON first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from response
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Look for structured patterns
        structured_data = {"content": response}

        # Extract potential fields using patterns
        intent_match = re.search(r'intent[:\s]+([^
]+)', response, re.IGNORECASE)
        if intent_match:
            structured_data["intent"] = intent_match.group(1).strip()

        confidence_match = re.search(r'confidence[:\s]+([0-9.]+)', response, re.IGNORECASE)
        if confidence_match:
            try:
                structured_data["confidence"] = float(confidence_match.group(1))
            except ValueError:
                pass

        return structured_data

    async def _validate_basic_structure(self, response: Dict[str, Any]) -> Tuple[List[ValidationError], List[str]]:
        """Validate basic response structure."""
        errors = []
        warnings = []

        # Check if response is empty
        if not response or (isinstance(response, dict) and not any(response.values())):
            errors.append(ValidationError.EMPTY_RESPONSE)
            return errors, warnings

        # Check required fields
        for field in self.rules["required_fields"]:
            if field not in response or not response[field]:
                errors.append(ValidationError.MISSING_REQUIRED_FIELDS)
                warnings.append(f"Missing required field: {field}")

        # Check content length
        content = response.get("content", "")
        if isinstance(content, str):
            if len(content) < self.rules["min_length"]:
                errors.append(ValidationError.TOO_SHORT)
            elif len(content) > self.rules["max_length"]:
                errors.append(ValidationError.TOO_LONG)

        # Check JSON depth if response is nested
        if isinstance(response, dict):
            depth = self._calculate_json_depth(response)
            if depth > self.rules["max_json_depth"]:
                warnings.append(f"Response structure is too deep: {depth} levels")

        return errors, warnings

    async def _validate_content(self, content: str, expected_language: str) -> Tuple[List[ValidationError], List[str]]:
        """Validate response content."""
        errors = []
        warnings = []

        if not content or not isinstance(content, str):
            errors.append(ValidationError.EMPTY_RESPONSE)
            return errors, warnings

        # Language validation
        detected_language = await self._detect_language(content)
        if detected_language != expected_language:
            if self.validation_level == ValidationLevel.STRICT:
                errors.append(ValidationError.LANGUAGE_MISMATCH)
            else:
                warnings.append(f"Language mismatch: expected {expected_language}, got {detected_language}")

        # Inappropriate content check
        for pattern in self.inappropriate_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                if self.validation_level == ValidationLevel.STRICT:
                    errors.append(ValidationError.INAPPROPRIATE_CONTENT)
                else:
                    warnings.append("Potentially inappropriate content detected")
                break

        # Factual warning patterns
        for pattern in self.factual_warning_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                warnings.append("Response contains uncertain language")
                break

        # Spam detection
        if await self._detect_spam(content):
            errors.append(ValidationError.SPAM_DETECTED)

        # Repetition check
        if await self._detect_repetition(content):
            warnings.append("Response contains repetitive content")

        return errors, warnings

    async def _validate_schema(self, response: Dict[str, Any], schema: ResponseSchema) -> Tuple[List[ValidationError], List[str]]:
        """Validate response against expected schema."""
        errors = []
        warnings = []

        try:
            # Validate using Pydantic schema
            validated = schema(**response)

            # Additional custom validations
            if hasattr(validated, 'confidence') and validated.confidence is not None:
                if validated.confidence < self.rules["min_confidence"]:
                    if self.validation_level == ValidationLevel.STRICT:
                        errors.append(ValidationError.INCONSISTENT_DATA)
                    else:
                        warnings.append(f"Low confidence score: {validated.confidence}")

        except Exception as e:
            errors.append(ValidationError.INVALID_JSON)
            warnings.append(f"Schema validation failed: {str(e)}")

        return errors, warnings

    async def _validate_context_consistency(self, response: Dict[str, Any], context: Dict[str, Any]) -> Tuple[List[ValidationError], List[str]]:
        """Validate response consistency with conversation context."""
        errors = []
        warnings = []

        # Check if response is relevant to context
        content = response.get("content", "")

        # Extract context information
        user_message = context.get("last_user_message", "")
        conversation_topic = context.get("topic", "")
        collected_data = context.get("collected_data", {})

        # Topic consistency
        if conversation_topic and not await self._is_topic_relevant(content, conversation_topic):
            warnings.append("Response may not be relevant to conversation topic")

        # Data consistency
        extracted_data = response.get("extracted_data", {})
        if extracted_data and collected_data:
            inconsistencies = await self._check_data_consistency(extracted_data, collected_data)
            if inconsistencies:
                errors.append(ValidationError.INCONSISTENT_DATA)
                warnings.extend(inconsistencies)

        return errors, warnings

    async def _validate_safety(self, response: Dict[str, Any]) -> Tuple[List[ValidationError], List[str]]:
        """Validate response for safety and policy compliance."""
        errors = []
        warnings = []

        content = response.get("content", "")

        # Check for policy violations
        policy_violations = await self._check_policy_violations(content)
        if policy_violations:
            errors.append(ValidationError.POLICY_VIOLATION)
            warnings.extend(policy_violations)

        # Check for potential hallucinations
        if await self._detect_hallucination(content):
            warnings.append("Potential hallucination detected")

        return errors, warnings

    async def _calculate_confidence_score(self, response: Dict[str, Any], errors: List[ValidationError], warnings: List[str]) -> float:
        """Calculate overall confidence score for the response."""
        base_score = 1.0

        # Reduce score for errors
        error_penalty = {
            ValidationError.EMPTY_RESPONSE: 0.9,
            ValidationError.TOO_LONG: 0.1,
            ValidationError.TOO_SHORT: 0.2,
            ValidationError.INVALID_JSON: 0.3,
            ValidationError.MISSING_REQUIRED_FIELDS: 0.4,
            ValidationError.INAPPROPRIATE_CONTENT: 0.8,
            ValidationError.INCONSISTENT_DATA: 0.5,
            ValidationError.LANGUAGE_MISMATCH: 0.2,
            ValidationError.POLICY_VIOLATION: 0.9,
            ValidationError.SPAM_DETECTED: 0.9,
            ValidationError.HALLUCINATION: 0.6
        }

        for error in errors:
            penalty = error_penalty.get(error, 0.3)
            base_score -= penalty

        # Reduce score for warnings (less severe)
        warning_penalty = 0.05
        base_score -= len(warnings) * warning_penalty

        # Consider response-provided confidence
        response_confidence = response.get("confidence")
        if response_confidence is not None:
            base_score = (base_score + response_confidence) / 2

        return max(0.0, min(1.0, base_score))

    async def _attempt_correction(self, response: Dict[str, Any], errors: List[ValidationError]) -> Optional[str]:
        """Attempt to correct common response issues."""
        if not response.get("content"):
            return None

        content = response["content"]
        corrected = content

        # Fix common formatting issues
        corrected = re.sub(r'\s+', ' ', corrected)  # Multiple spaces
        corrected = corrected.strip()

        # Remove repetitive content
        corrected = re.sub(r'(.{20,}?)+', r'', corrected)

        # Truncate if too long
        if len(corrected) > self.rules["max_length"]:
            corrected = corrected[:self.rules["max_length"]] + "..."

        return corrected if corrected != content else None

    async def _determine_validity(self, errors: List[ValidationError], confidence_score: float) -> bool:
        """Determine if response is valid based on errors and confidence."""
        critical_errors = {
            ValidationError.EMPTY_RESPONSE,
            ValidationError.INAPPROPRIATE_CONTENT,
            ValidationError.POLICY_VIOLATION,
            ValidationError.SPAM_DETECTED
        }

        # Check for critical errors
        if any(error in critical_errors for error in errors):
            return False

        # Check confidence threshold
        if confidence_score < self.rules["min_confidence"]:
            return False

        # Validation level specific rules
        if self.validation_level == ValidationLevel.STRICT:
            return len(errors) == 0
        elif self.validation_level == ValidationLevel.MODERATE:
            return len(errors) <= 2
        else:  # LENIENT
            return len(errors) <= 5

    # Helper methods

    def _calculate_json_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate the maximum depth of a JSON object."""
        if not isinstance(obj, (dict, list)):
            return current_depth

        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._calculate_json_depth(v, current_depth + 1) for v in obj.values())
        else:  # list
            if not obj:
                return current_depth
            return max(self._calculate_json_depth(item, current_depth + 1) for item in obj)

    async def _detect_language(self, text: str) -> str:
        """Detect the primary language of the text."""
        scores = {}

        for lang, patterns in self.language_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text, re.IGNORECASE))
                score += matches
            scores[lang] = score

        # Return language with highest score, default to Hindi
        return max(scores, key=scores.get) if scores else "hi"

    async def _detect_spam(self, content: str) -> bool:
        """Detect if content appears to be spam."""
        spam_indicators = [
            len(re.findall(r'[!]{3,}', content)) > 0,  # Multiple exclamation marks
            len(re.findall(r'[A-Z]{10,}', content)) > 0,  # Long uppercase sequences
            len(re.findall(r'(.){5,}', content)) > 0,  # Repeated characters
            'http' in content.lower() and content.count('http') > 2,  # Multiple URLs
        ]

        return sum(spam_indicators) >= 2

    async def _detect_repetition(self, content: str) -> bool:
        """Detect repetitive content."""
        words = content.split()
        if len(words) < 10:
            return False

        # Check for repeated phrases
        phrases = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
        unique_phrases = set(phrases)

        return len(unique_phrases) / len(phrases) < 0.7  # Less than 70% unique

    async def _is_topic_relevant(self, content: str, topic: str) -> bool:
        """Check if content is relevant to the conversation topic."""
        # Simple keyword-based relevance check
        topic_words = topic.lower().split()
        content_words = content.lower().split()

        overlap = len(set(topic_words) & set(content_words))
        return overlap > 0 or len(topic_words) == 0

    async def _check_data_consistency(self, new_data: Dict[str, Any], existing_data: Dict[str, Any]) -> List[str]:
        """Check for inconsistencies between new and existing data."""
        inconsistencies = []

        for key, value in new_data.items():
            if key in existing_data and existing_data[key] != value:
                inconsistencies.append(f"Inconsistent {key}: was {existing_data[key]}, now {value}")

        return inconsistencies

    async def _check_policy_violations(self, content: str) -> List[str]:
        """Check for government policy violations."""
        violations = []

        # Check for promises of guaranteed benefits
        if re.search(r'(?:guaranteed|promise|ensure).*(?:benefit|money|amount)', content, re.IGNORECASE):
            violations.append("Cannot guarantee specific benefits")

        # Check for political bias
        if re.search(r'(?:best|worst)\s+(?:government|minister|party)', content, re.IGNORECASE):
            violations.append("Potential political bias detected")

        return violations

    async def _detect_hallucination(self, content: str) -> bool:
        """Detect potential hallucinations in the response."""
        # Look for very specific claims that might be fabricated
        specific_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # Specific dates
            r'₹\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?',  # Specific amounts
            r'phone:\s*\d{10}',  # Phone numbers
            r'email:\s*\S+@\S+\.\S+'  # Email addresses
        ]

        for pattern in specific_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return self.validation_stats.copy()

    def reset_statistics(self):
        """Reset validation statistics."""
        self.validation_stats = {
            "total_validations": 0,
            "passed_validations": 0,
            "failed_validations": 0,
            "errors_by_type": {},
            "avg_confidence": 0.0
        }


# Global validator instance
response_validator = LLMResponseValidator()


# Utility function for quick validation
async def validate_response(
    response: Union[str, Dict[str, Any]],
    expected_language: str = "hi",
    validation_level: ValidationLevel = ValidationLevel.MODERATE
) -> ValidationResult:
    """Quick response validation utility."""
    validator = LLMResponseValidator(validation_level)
    return await validator.validate_response(response, expected_language)


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def test_validation():
        # Test with valid response
        valid_response = {
            "content": "आपकी आयु 35 वर्ष है। PM किसान योजना के लिए आपको अपनी भूमि की जानकारी देनी होगी।",
            "intent": "collect_land_info",
            "confidence": 0.85,
            "language": "hi"
        }

        result = await validate_response(valid_response, "hi")
        print("Valid response result:", result.is_valid, result.confidence_score)

        # Test with invalid response
        invalid_response = "Click here to get rich quick!!!"

        result = await validate_response(invalid_response, "hi", ValidationLevel.STRICT)
        print("Invalid response result:", result.is_valid, result.errors)

    asyncio.run(test_validation())