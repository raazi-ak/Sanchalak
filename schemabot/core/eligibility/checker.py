#schemabot\core\eligibility\checker.py

from typing import Dict, Any, List, Tuple, Optional, Union
from datetime import datetime, date
import re
from decimal import Decimal, InvalidOperation
import structlog

from core.scheme.models import GovernmentScheme, EligibilityRule, Operator, DataType

logger = structlog.get_logger(__name__)

class EligibilityResult:
    def __init__(self, is_eligible: bool, score: float = 0.0):
        self.is_eligible = is_eligible
        self.score = score  # 0-100 eligibility score
        self.passed_rules: List[str] = []
        self.failed_rules: List[str] = []
        self.missing_fields: List[str] = []
        self.warnings: List[str] = []
        self.recommendations: List[str] = []

class EligibilityChecker:
    def __init__(self):
        self.type_converters = {
            DataType.STRING: str,
            DataType.INTEGER: int,
            DataType.FLOAT: float,
            DataType.BOOLEAN: self._convert_boolean,
            DataType.DATE: self._convert_date,
            DataType.LIST: self._convert_list
        }
    
    def check_eligibility(
        self, 
        farmer_data: Dict[str, Any], 
        scheme: GovernmentScheme
    ) -> EligibilityResult:
        """
        Comprehensive eligibility check with detailed results
        """
        result = EligibilityResult(False)
        
        try:
            # Step 1: Check for missing required fields
            missing_fields = self._check_missing_fields(farmer_data, scheme)
            result.missing_fields = missing_fields
            
            if missing_fields:
                result.recommendations.append(
                    f"Please provide: {', '.join(missing_fields)}"
                )
                return result
            
            # Step 2: Evaluate eligibility rules
            rule_results = []
            for rule in scheme.eligibility.rules:
                rule_result = self._evaluate_rule(farmer_data, rule)
                rule_results.append(rule_result)
                
                if rule_result['passed']:
                    result.passed_rules.append(rule.rule_id)
                else:
                    result.failed_rules.append(rule.rule_id)
                    if rule_result['reason']:
                        result.recommendations.append(rule_result['reason'])
            
            # Step 3: Apply eligibility logic (ALL/ANY)
            if scheme.eligibility.logic == "ALL":
                rules_passed = all(r['passed'] for r in rule_results)
            else:  # ANY
                rules_passed = any(r['passed'] for r in rule_results)
            
            # Step 4: Check exclusion criteria
            exclusion_failed = self._check_exclusions(farmer_data, scheme.eligibility.exclusion_criteria)
            
            # Step 5: Calculate final eligibility
            result.is_eligible = rules_passed and not exclusion_failed
            
            # Step 6: Calculate eligibility score
            result.score = self._calculate_eligibility_score(rule_results, scheme)
            
            # Step 7: Generate recommendations
            if not result.is_eligible:
                result.recommendations.extend(
                    self._generate_improvement_recommendations(farmer_data, scheme, rule_results)
                )
            
            logger.info(
                f"Eligibility check completed",
                scheme_code=scheme.code,
                is_eligible=result.is_eligible,
                score=result.score,
                passed_rules=len(result.passed_rules),
                failed_rules=len(result.failed_rules)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Eligibility check failed: {e}", scheme_code=scheme.code)
            result.warnings.append("Error occurred during eligibility check")
            return result
    
    def _check_missing_fields(self, farmer_data: Dict[str, Any], scheme: GovernmentScheme) -> List[str]:
        """Check for missing required fields"""
        required_fields = set()
        
        # Fields from rules
        for rule in scheme.eligibility.rules:
            required_fields.add(rule.field)
        
        # Fields from required criteria
        required_fields.update(scheme.eligibility.required_criteria)
        
        missing = []
        for field in required_fields:
            if field not in farmer_data or farmer_data[field] is None:
                missing.append(field)
        
        return missing
    
    def _evaluate_rule(self, farmer_data: Dict[str, Any], rule: EligibilityRule) -> Dict[str, Any]:
        """Evaluate a single eligibility rule"""
        try:
            if rule.field not in farmer_data:
                return {
                    'passed': False,
                    'reason': f"Missing required field: {rule.field}",
                    'rule_id': rule.rule_id
                }
            
            farmer_value = farmer_data[rule.field]
            
            # Convert values to appropriate types
            try:
                converted_farmer_value = self._convert_value(farmer_value, rule.data_type)
                converted_rule_value = self._convert_value(rule.value, rule.data_type)
            except (ValueError, TypeError) as e:
                return {
                    'passed': False,
                    'reason': f"Invalid data type for {rule.field}: {e}",
                    'rule_id': rule.rule_id
                }
            
            # Evaluate based on operator
            passed = self._apply_operator(
                converted_farmer_value, 
                converted_rule_value, 
                rule.operator
            )
            
            reason = None if passed else self._generate_rule_failure_reason(
                rule, converted_farmer_value, converted_rule_value
            )
            
            return {
                'passed': passed,
                'reason': reason,
                'rule_id': rule.rule_id,
                'farmer_value': converted_farmer_value,
                'expected_value': converted_rule_value
            }
            
        except Exception as e:
            logger.error(f"Rule evaluation error: {e}", rule_id=rule.rule_id)
            return {
                'passed': False,
                'reason': f"Error evaluating rule {rule.rule_id}",
                'rule_id': rule.rule_id
            }
    
    def _convert_value(self, value: Any, data_type: DataType) -> Any:
        """Convert value to appropriate type"""
        if value is None:
            return None
        
        converter = self.type_converters.get(data_type)
        if not converter:
            raise ValueError(f"Unsupported data type: {data_type}")
        
        return converter(value)
    
    def _convert_boolean(self, value: Any) -> bool:
        """Convert value to boolean"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'y')
        if isinstance(value, (int, float)):
            return bool(value)
        raise ValueError(f"Cannot convert {value} to boolean")
    
    def _convert_date(self, value: Any) -> date:
        """Convert value to date"""
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            # Try common date formats
            formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse date: {value}")
        raise ValueError(f"Cannot convert {value} to date")
    
    def _convert_list(self, value: Any) -> List[Any]:
        """Convert value to list"""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Try to parse comma-separated values
            return [item.strip() for item in value.split(',')]
        return [value]
    
    def _apply_operator(self, farmer_value: Any, rule_value: Any, operator: Operator) -> bool:
        """Apply comparison operator"""
        try:
            if operator == Operator.EQUALS:
                return farmer_value == rule_value
            elif operator == Operator.NOT_EQUALS:
                return farmer_value != rule_value
            elif operator == Operator.GREATER_THAN:
                return farmer_value > rule_value
            elif operator == Operator.LESS_THAN:
                return farmer_value < rule_value
            elif operator == Operator.GREATER_EQUAL:
                return farmer_value >= rule_value
            elif operator == Operator.LESS_EQUAL:
                return farmer_value <= rule_value
            elif operator == Operator.BETWEEN:
                if isinstance(rule_value, list) and len(rule_value) == 2:
                    return rule_value[0] <= farmer_value <= rule_value[1]
                return False
            elif operator == Operator.IN:
                if isinstance(rule_value, list):
                    return farmer_value in rule_value
                return farmer_value == rule_value
            elif operator == Operator.NOT_IN:
                if isinstance(rule_value, list):
                    return farmer_value not in rule_value
                return farmer_value != rule_value
            else:
                return False
                
        except (TypeError, ValueError):
            return False
    
    def _check_exclusions(self, farmer_data: Dict[str, Any], exclusion_criteria: List[str]) -> bool:
        """Check if farmer meets any exclusion criteria"""
        for criterion in exclusion_criteria:
            if criterion in farmer_data and farmer_data[criterion]:
                return True
        return False
    
    def _calculate_eligibility_score(self, rule_results: List[Dict], scheme: GovernmentScheme) -> float:
        """Calculate eligibility score (0-100)"""
        if not rule_results:
            return 0.0
        
        passed_count = sum(1 for r in rule_results if r['passed'])
        total_count = len(rule_results)
        
        base_score = (passed_count / total_count) * 100
        
        # Adjust score based on logic type
        if scheme.eligibility.logic == "ALL" and passed_count < total_count:
            # Penalize heavily for ALL logic when not all rules pass
            base_score *= 0.5
        
        return round(base_score, 2)
    
    def _generate_rule_failure_reason(
        self, 
        rule: EligibilityRule, 
        farmer_value: Any, 
        expected_value: Any
    ) -> str:
        """Generate human-readable reason for rule failure"""
        field_name = rule.field.replace('_', ' ').title()
        
        if rule.operator == Operator.EQUALS:
            return f"{field_name} should be {expected_value}, but got {farmer_value}"
        elif rule.operator == Operator.GREATER_THAN:
            return f"{field_name} should be greater than {expected_value}, but got {farmer_value}"
        elif rule.operator == Operator.LESS_THAN:
            return f"{field_name} should be less than {expected_value}, but got {farmer_value}"
        elif rule.operator == Operator.BETWEEN:
            return f"{field_name} should be between {expected_value[0]} and {expected_value[1]}, but got {farmer_value}"
        elif rule.operator == Operator.IN:
            return f"{field_name} should be one of {expected_value}, but got {farmer_value}"
        else:
            return f"{field_name} does not meet the requirement: {rule.description}"
    
    def _generate_improvement_recommendations(
        self, 
        farmer_data: Dict[str, Any], 
        scheme: GovernmentScheme, 
        rule_results: List[Dict]
    ) -> List[str]:
        """Generate recommendations for improving eligibility"""
        recommendations = []
        
        for result in rule_results:
            if not result['passed'] and result.get('reason'):
                recommendations.append(result['reason'])
        
        # Add scheme-specific recommendations
        if scheme.metadata.category == "housing":
            recommendations.append("Consider checking other housing schemes if you don't qualify for this one")
        elif scheme.metadata.category == "agriculture":
            recommendations.append("Ensure all land documents are updated and verified")
        
        return recommendations[:5]  # Limit to top 5 recommendations
