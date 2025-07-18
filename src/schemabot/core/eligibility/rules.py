#schemabot\core\eligibility\rules.py

from typing import Dict, Any, List, Union, Optional
from datetime import datetime, date
import structlog
from decimal import Decimal, InvalidOperation
from src.schemabot.core.scheme.models import EligibilityRule, Operator, DataType

logger = structlog.get_logger(__name__)

class RuleEvaluationError(Exception):
    """Raised when rule evaluation fails"""
    pass

class RuleProcessor:
    """Advanced rule processing and evaluation engine"""
    
    def __init__(self):
        self.operator_map = {
            Operator.EQUALS: self._equals,
            Operator.NOT_EQUALS: self._not_equals,
            Operator.GREATER_THAN: self._greater_than,
            Operator.LESS_THAN: self._less_than,
            Operator.GREATER_EQUAL: self._greater_equal,
            Operator.LESS_EQUAL: self._less_equal,
            Operator.BETWEEN: self._between,
            Operator.IN: self._in,
            Operator.NOT_IN: self._not_in,
        }
        
        self.type_validators = {
            DataType.STRING: self._validate_string,
            DataType.INTEGER: self._validate_integer,
            DataType.FLOAT: self._validate_float,
            DataType.BOOLEAN: self._validate_boolean,
            DataType.DATE: self._validate_date,
            DataType.LIST: self._validate_list,
        }

    def evaluate_rule(
        self, 
        rule: EligibilityRule, 
        farmer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate a single eligibility rule against farmer data
        
        Returns:
            Dict containing evaluation result, score, and metadata
        """
        try:
            # Check if field exists in farmer data
            if rule.field not in farmer_data:
                return {
                    "passed": False,
                    "score": 0.0,
                    "rule_id": rule.rule_id,
                    "field": rule.field,
                    "reason": f"Missing required field: {rule.field}",
                    "severity": "high",
                    "farmer_value": None,
                    "expected_value": rule.value
                }
            
            farmer_value = farmer_data[rule.field]
            
            # Validate and convert data types
            validation_result = self._validate_and_convert(
                farmer_value, rule.value, rule.data_type
            )
            
            if not validation_result["valid"]:
                return {
                    "passed": False,
                    "score": 0.0,
                    "rule_id": rule.rule_id,
                    "field": rule.field,
                    "reason": validation_result["error"],
                    "severity": "medium",
                    "farmer_value": farmer_value,
                    "expected_value": rule.value
                }
            
            # Apply operator logic
            operator_func = self.operator_map.get(rule.operator)
            if not operator_func:
                raise RuleEvaluationError(f"Unsupported operator: {rule.operator}")
            
            result = operator_func(
                validation_result["farmer_value"], 
                validation_result["rule_value"]
            )
            
            # Calculate rule score
            score = self._calculate_rule_score(result, rule, farmer_value)
            
            return {
                "passed": result,
                "score": score,
                "rule_id": rule.rule_id,
                "field": rule.field,
                "reason": None if result else self._generate_failure_reason(rule, farmer_value),
                "severity": "low" if result else self._determine_severity(rule),
                "farmer_value": validation_result["farmer_value"],
                "expected_value": validation_result["rule_value"]
            }
            
        except Exception as e:
            logger.error(f"Rule evaluation error: {e}", rule_id=rule.rule_id)
            return {
                "passed": False,
                "score": 0.0,
                "rule_id": rule.rule_id,
                "field": rule.field,
                "reason": f"Evaluation error: {str(e)}",
                "severity": "high",
                "farmer_value": farmer_data.get(rule.field),
                "expected_value": rule.value
            }

    def evaluate_compound_rules(
        self, 
        rules: List[EligibilityRule], 
        farmer_data: Dict[str, Any],
        logic: str = "ALL"
    ) -> Dict[str, Any]:
        """
        Evaluate multiple rules with specified logic
        
        Args:
            rules: List of eligibility rules
            farmer_data: Farmer's data
            logic: "ALL" or "ANY"
        
        Returns:
            Compound evaluation result
        """
        if not rules:
            return {
                "passed": True,
                "score": 100.0,
                "total_rules": 0,
                "passed_rules": 0,
                "failed_rules": 0,
                "rule_results": []
            }
        
        rule_results = []
        passed_count = 0
        total_score = 0.0
        
        for rule in rules:
            result = self.evaluate_rule(rule, farmer_data)
            rule_results.append(result)
            
            if result["passed"]:
                passed_count += 1
            
            total_score += result["score"]
        
        # Apply logic
        if logic == "ALL":
            overall_passed = passed_count == len(rules)
            # Penalize heavily if not all rules pass
            if not overall_passed:
                total_score *= 0.5
        else:  # ANY
            overall_passed = passed_count > 0
        
        avg_score = total_score / len(rules) if rules else 0.0
        
        return {
            "passed": overall_passed,
            "score": round(avg_score, 2),
            "total_rules": len(rules),
            "passed_rules": passed_count,
            "failed_rules": len(rules) - passed_count,
            "rule_results": rule_results,
            "logic": logic
        }

    # Type validation methods
    def _validate_and_convert(
        self, 
        farmer_value: Any, 
        rule_value: Any, 
        data_type: DataType
    ) -> Dict[str, Any]:
        """Validate and convert values to appropriate types"""
        try:
            validator = self.type_validators.get(data_type)
            if not validator:
                return {
                    "valid": False,
                    "error": f"Unsupported data type: {data_type}"
                }
            
            converted_farmer = validator(farmer_value)
            converted_rule = validator(rule_value)
            
            return {
                "valid": True,
                "farmer_value": converted_farmer,
                "rule_value": converted_rule
            }
            
        except (ValueError, TypeError) as e:
            return {
                "valid": False,
                "error": f"Type conversion error: {str(e)}"
            }

    def _validate_string(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _validate_integer(self, value: Any) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            return int(value.strip())
        if isinstance(value, float):
            return int(value)
        raise ValueError(f"Cannot convert {value} to integer")

    def _validate_float(self, value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Handle currency formatting
            cleaned = value.strip().replace(',', '').replace('₹', '').replace('Rs.', '')
            return float(cleaned)
        raise ValueError(f"Cannot convert {value} to float")

    def _validate_boolean(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'y', 'on')
        if isinstance(value, (int, float)):
            return bool(value)
        raise ValueError(f"Cannot convert {value} to boolean")

    def _validate_date(self, value: Any) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            # Common date formats
            formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse date: {value}")
        raise ValueError(f"Cannot convert {value} to date")

    def _validate_list(self, value: Any) -> List[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(',')]
        return [value]

    # Operator methods
    def _equals(self, farmer_value: Any, rule_value: Any) -> bool:
        return farmer_value == rule_value

    def _not_equals(self, farmer_value: Any, rule_value: Any) -> bool:
        return farmer_value != rule_value

    def _greater_than(self, farmer_value: Any, rule_value: Any) -> bool:
        return farmer_value > rule_value

    def _less_than(self, farmer_value: Any, rule_value: Any) -> bool:
        return farmer_value < rule_value

    def _greater_equal(self, farmer_value: Any, rule_value: Any) -> bool:
        return farmer_value >= rule_value

    def _less_equal(self, farmer_value: Any, rule_value: Any) -> bool:
        return farmer_value <= rule_value

    def _between(self, farmer_value: Any, rule_value: List[Any]) -> bool:
        if not isinstance(rule_value, list) or len(rule_value) != 2:
            return False
        return rule_value[0] <= farmer_value <= rule_value[1]

    def _in(self, farmer_value: Any, rule_value: Union[List[Any], Any]) -> bool:
        if isinstance(rule_value, list):
            return farmer_value in rule_value
        return farmer_value == rule_value

    def _not_in(self, farmer_value: Any, rule_value: Union[List[Any], Any]) -> bool:
        if isinstance(rule_value, list):
            return farmer_value not in rule_value
        return farmer_value != rule_value

    # Helper methods
    def _calculate_rule_score(
        self, 
        passed: bool, 
        rule: EligibilityRule, 
        farmer_value: Any
    ) -> float:
        """Calculate a score for individual rule (0-100)"""
        if passed:
            return 100.0
        
        # Partial scoring for numeric fields
        if rule.data_type in [DataType.INTEGER, DataType.FLOAT]:
            try:
                if rule.operator == Operator.GREATER_EQUAL:
                    ratio = float(farmer_value) / float(rule.value)
                    return min(90.0, ratio * 100)
                elif rule.operator == Operator.LESS_EQUAL:
                    ratio = float(rule.value) / float(farmer_value)
                    return min(90.0, ratio * 100)
            except (ValueError, ZeroDivisionError, TypeError):
                pass
        
        return 0.0

    def _generate_failure_reason(self, rule: EligibilityRule, farmer_value: Any) -> str:
        """Generate human-readable failure reason"""
        field_name = rule.field.replace('_', ' ').title()
        
        reasons = {
            Operator.EQUALS: f"{field_name} should be {rule.value}, but got {farmer_value}",
            Operator.NOT_EQUALS: f"{field_name} should not be {rule.value}",
            Operator.GREATER_THAN: f"{field_name} should be greater than {rule.value}, but got {farmer_value}",
            Operator.LESS_THAN: f"{field_name} should be less than {rule.value}, but got {farmer_value}",
            Operator.GREATER_EQUAL: f"{field_name} should be at least {rule.value}, but got {farmer_value}",
            Operator.LESS_EQUAL: f"{field_name} should be at most {rule.value}, but got {farmer_value}",
            Operator.BETWEEN: f"{field_name} should be between {rule.value[0]} and {rule.value[1]}, but got {farmer_value}",
            Operator.IN: f"{field_name} should be one of {rule.value}, but got {farmer_value}",
            Operator.NOT_IN: f"{field_name} should not be one of {rule.value}",
        }
        
        return reasons.get(rule.operator, f"{field_name} does not meet requirement: {rule.description}")

    def _determine_severity(self, rule: EligibilityRule) -> str:
        """Determine severity of rule failure"""
        # Critical fields
        critical_fields = ['age', 'citizenship', 'land_ownership']
        if rule.field in critical_fields:
            return "high"
        
        # Important fields
        important_fields = ['annual_income', 'bank_account_linked']
        if rule.field in important_fields:
            return "medium"
        
        return "low"

class RuleOptimizer:
    """Optimize rule evaluation order and performance"""
    
    def __init__(self):
        self.processor = RuleProcessor()
    
    def optimize_rule_order(self, rules: List[EligibilityRule]) -> List[EligibilityRule]:
        """
        Optimize rule evaluation order for better performance
        Put cheaper/faster rules first, and high-impact rules early
        """
        def rule_priority(rule: EligibilityRule) -> int:
            # Higher priority = evaluated first
            priority = 0
            
            # Critical fields get highest priority
            if rule.field in ['citizenship', 'age']:
                priority += 100
            
            # Simple operators are faster
            if rule.operator in [Operator.EQUALS, Operator.NOT_EQUALS]:
                priority += 50
            
            # Boolean fields are fastest
            if rule.data_type == DataType.BOOLEAN:
                priority += 25
            
            return priority
        
        return sorted(rules, key=rule_priority, reverse=True)
    
    def get_rule_statistics(self, rule_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate statistics from rule evaluation results"""
        if not rule_results:
            return {"total": 0, "passed": 0, "failed": 0, "average_score": 0.0}
        
        total = len(rule_results)
        passed = sum(1 for r in rule_results if r["passed"])
        failed = total - passed
        avg_score = sum(r["score"] for r in rule_results) / total
        
        # Group by severity
        severity_counts = {}
        for result in rule_results:
            if not result["passed"]:
                severity = result.get("severity", "unknown")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total) * 100,
            "average_score": round(avg_score, 2),
            "severity_breakdown": severity_counts,
            "most_common_failures": self._get_most_common_failures(rule_results)
        }
    
    def _get_most_common_failures(self, rule_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get most common failure patterns"""
        failure_counts = {}
        
        for result in rule_results:
            if not result["passed"] and result["reason"]:
                field = result["field"]
                if field not in failure_counts:
                    failure_counts[field] = {
                        "field": field,
                        "count": 0,
                        "reasons": []
                    }
                failure_counts[field]["count"] += 1
                if result["reason"] not in failure_counts[field]["reasons"]:
                    failure_counts[field]["reasons"].append(result["reason"])
        
        return sorted(failure_counts.values(), key=lambda x: x["count"], reverse=True)[:5]