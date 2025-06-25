# eligibility_checker.py

import json
import logging
from datetime import datetime
from dateutil import parser as date_parser
from typing import Dict, List, Any, Tuple

logger = logging.getLogger("eligibility_checker")
logging.basicConfig(level=logging.INFO)

class RuleResult:
    def __init__(self, rule_id, field, operator, expected_value, actual_value, passed, description):
        self.rule_id = rule_id
        self.field = field
        self.operator = operator
        self.expected_value = expected_value
        self.actual_value = actual_value
        self.passed = passed
        self.description = description

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "field": self.field,
            "operator": self.operator,
            "expected_value": self._serialize(self.expected_value),
            "actual_value": self._serialize(self.actual_value),
            "passed": self.passed,
            "description": self.description
        }

    def _serialize(self, val):
        if isinstance(val, datetime):
            return val.isoformat()
        return val

class EligibilityResult:
    def __init__(self, is_eligible, rule_results, explanations=None, recommendations=None):
        self.is_eligible = is_eligible
        self.rule_results = rule_results
        self.explanations = explanations or []
        self.recommendations = recommendations or []

    def to_dict(self):
        return {
            "is_eligible": self.is_eligible,
            "rule_results": [r.to_dict() for r in self.rule_results],
            "explanations": self.explanations,
            "recommendations": self.recommendations
        }

class EligibilityChecker:
    def __init__(self):
        self.type_handlers = {
            "string": self._compare_strings,
            "number": self._compare_numbers,
            "boolean": self._compare_booleans,
            "date": self._compare_dates,
            "array": self._compare_arrays
        }

    def check(self, applicant_data: Dict, scheme_def: Dict) -> EligibilityResult:
        rules = scheme_def.get("eligibility", {}).get("rules", [])
        logic = scheme_def.get("eligibility", {}).get("logic", "ALL").upper()

        rule_results = []
        for rule in rules:
            result = self._evaluate_rule(rule, applicant_data)
            rule_results.append(result)

        if logic == "ANY":
            eligible = any(r.passed for r in rule_results)
        else:
            eligible = all(r.passed for r in rule_results)

        explanations = self._generate_explanations(rule_results, logic)
        recommendations = self._generate_recommendations(rule_results, scheme_def)

        return EligibilityResult(eligible, rule_results, explanations, recommendations)

    def _evaluate_rule(self, rule, applicant_data):
        rule_id = rule.get("rule_id", "rule_" + str(id(rule)))
        field = rule.get("field")
        operator = rule.get("operator")
        expected_value = rule.get("value")
        data_type = rule.get("data_type", "string")
        description = rule.get("description", f"Check {field} {operator} {expected_value}")

        actual_value = self._get_value(applicant_data, field)
        passed = False
        if actual_value is not None:
            compare_func = self.type_handlers.get(data_type, self._compare_strings)
            try:
                passed = compare_func(actual_value, operator, expected_value)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule_id}: {e}")
                passed = False
        else:
            # Missing data fails the rule
            passed = False

        return RuleResult(rule_id, field, operator, expected_value, actual_value, passed, description)

    def _get_value(self, data, field):
        # Support nested fields with dot notation
        parts = field.split('.')
        val = data
        for part in parts:
            if isinstance(val, dict) and part in val:
                val = val[part]
            else:
                return None
        return val

    def _compare_strings(self, actual, operator, expected):
        actual_str = str(actual).lower()
        expected_str = str(expected).lower()
        if operator == "==":
            return actual_str == expected_str
        elif operator == "!=":
            return actual_str != expected_str
        elif operator == "contains":
            return expected_str in actual_str
        elif operator == "not_contains":
            return expected_str not in actual_str
        elif operator == "starts_with":
            return actual_str.startswith(expected_str)
        elif operator == "ends_with":
            return actual_str.endswith(expected_str)
        elif operator == "in":
            return actual_str in [str(e).lower() for e in expected] if isinstance(expected, list) else False
        elif operator == "not_in":
            return actual_str not in [str(e).lower() for e in expected] if isinstance(expected, list) else False
        else:
            return False

    def _compare_numbers(self, actual, operator, expected):
        try:
            actual_num = float(actual)
            expected_num = float(expected)
            if operator == "==":
                return abs(actual_num - expected_num) < 0.001
            elif operator == "!=":
                return abs(actual_num - expected_num) >= 0.001
            elif operator == ">":
                return actual_num > expected_num
            elif operator == ">=":
                return actual_num >= expected_num
            elif operator == "<":
                return actual_num < expected_num
            elif operator == "<=":
                return actual_num <= expected_num
            elif operator == "between":
                if isinstance(expected, list) and len(expected) == 2:
                    return float(expected[0]) <= actual_num <= float(expected[1])
                return False
            elif operator == "in":
                return actual_num in [float(e) for e in expected] if isinstance(expected, list) else False
            elif operator == "not_in":
                return actual_num not in [float(e) for e in expected] if isinstance(expected, list) else True
            else:
                return False
        except:
            return False

    def _compare_booleans(self, actual, operator, expected):
        def to_bool(val):
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                return val.lower() in ["true", "yes", "1", "t"]
            if isinstance(val, (int, float)):
                return bool(val)
            return False
        actual_bool = to_bool(actual)
        expected_bool = to_bool(expected)
        if operator == "==":
            return actual_bool == expected_bool
        elif operator == "!=":
            return actual_bool != expected_bool
        else:
            return False

    def _compare_dates(self, actual, operator, expected):
        try:
            if isinstance(actual, str):
                actual_dt = date_parser.parse(actual)
            elif isinstance(actual, datetime):
                actual_dt = actual
            else:
                return False
            if isinstance(expected, str):
                expected_dt = date_parser.parse(expected)
            elif isinstance(expected, datetime):
                expected_dt = expected
            else:
                return False
            if operator == "==":
                return actual_dt.date() == expected_dt.date()
            elif operator == "!=":
                return actual_dt.date() != expected_dt.date()
            elif operator == "before" or operator == "<":
                return actual_dt < expected_dt
            elif operator == "after" or operator == ">":
                return actual_dt > expected_dt
            elif operator == "between":
                if isinstance(expected, list) and len(expected) == 2:
                    start_dt = date_parser.parse(expected[0])
                    end_dt = date_parser.parse(expected[1])
                    return start_dt <= actual_dt <= end_dt
                return False
            else:
                return False
        except:
            return False

    def _compare_arrays(self, actual, operator, expected):
        if not isinstance(actual, list):
            if isinstance(actual, str):
                try:
                    import json
                    actual = json.loads(actual)
                except:
                    actual = [actual]
            else:
                actual = [actual]
        if operator == "contains":
            return expected in actual
        elif operator == "not_contains":
            return expected not in actual
        elif operator == "contains_all":
            if isinstance(expected, list):
                return all(e in actual for e in expected)
            return False
        elif operator == "contains_any":
            if isinstance(expected, list):
                return any(e in actual for e in expected)
            return False
        elif operator == "size" or operator == "length":
            return len(actual) == int(expected)
        elif operator == "size_gt":
            return len(actual) > int(expected)
        elif operator == "size_lt":
            return len(actual) < int(expected)
        elif operator == "==":
            if isinstance(expected, list):
                return set(actual) == set(expected)
            return False
        else:
            return False

    def _generate_explanations(self, rule_results, logic):
        explanations = []
        total = len(rule_results)
        passed = sum(r.passed for r in rule_results)
        if logic == "ANY":
            explanations.append(f"Any of {total} conditions met: {passed} passed.")
        else:
            explanations.append(f"All {total} conditions met: {passed} passed.")
        for r in rule_results:
            status = "✓" if r.passed else "✗"
            explanations.append(f"{status} {r.description}")
        return explanations

    def _generate_recommendations(self, rule_results, scheme_def):
        recs = []
        failed = [r for r in rule_results if not r.passed]
        if not failed:
            recs.append("Eligible! Proceed with application.")
        else:
            recs.append("To qualify, consider:")
            for r in failed:
                recs.append(f"- {r.description}")
        return recs
