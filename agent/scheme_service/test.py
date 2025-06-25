# test.py

import unittest
from eligibility_checker import EligibilityChecker, RuleResult
from scheme_service import SchemeRepository, SchemeService
from yaml_parser import YAMLSchemeParser, SchemeDefinition

class TestEligibilityAlgorithm(unittest.TestCase):
    def setUp(self):
        self.checker = EligibilityChecker()
        self.scheme = {
            "eligibility": {
                "rules": [
                    {"rule_id": "r1", "field": "age", "operator": ">=", "value": 18, "data_type": "number"},
                    {"rule_id": "r2", "field": "income", "operator": "<", "value": 50000, "data_type": "number"},
                    {"rule_id": "r3", "field": "is_farmer", "operator": "==", "value": True, "data_type": "boolean"}
                ],
                "logic": "ALL"
            }
        }
        self.applicant = {
            "age": 25,
            "income": 30000,
            "is_farmer": True
        }

    def test_all_rules_pass(self):
        result = self.checker.check(self.applicant, self.scheme)
        self.assertTrue(result.is_eligible)
        self.assertEqual(len(result.rule_results), 3)
        self.assertTrue(all(r.passed for r in result.rule_results))

    def test_one_rule_fail(self):
        applicant = self.applicant.copy()
        applicant["income"] = 60000
        result = self.checker.check(applicant, self.scheme)
        self.assertFalse(result.is_eligible)
        self.assertTrue(any(not r.passed for r in result.rule_results))

class TestSchemeService(unittest.TestCase):
    def setUp(self):
        self.repo = SchemeRepository('test_schemes')
        self.service = SchemeService(self.repo)
        self.scheme_data = {
            "metadata": {
                "scheme_id": "test001",
                "name": "Test Scheme",
                "description": "Test description",
                "agency": "Test Agency",
                "version": "1.0.0"
            },
            "benefits": {
                "type": "Financial",
                "amount": 1000,
                "description": "Test benefit"
            },
            "eligibility": {
                "rules": [
                    {"rule_id": "r1", "field": "age", "operator": ">=", "value": 18, "data_type": "number"}
                ],
                "logic": "ALL"
            }
        }

    def test_create_and_get(self):
        scheme, errors = self.service.create(self.scheme_data)
        self.assertEqual(errors, [])
        self.assertEqual(scheme["metadata"]["scheme_id"], "test001")
        fetched = self.service.get("test001")
        self.assertIsNotNone(fetched)

    def test_update(self):
        self.scheme_data["metadata"]["description"] = "Updated"
        scheme, errors = self.service.update("test001", self.scheme_data)
        self.assertEqual(scheme["metadata"]["description"], "Updated")

    def test_delete(self):
        success = self.service.delete("test001")
        self.assertTrue(success)
        self.assertIsNone(self.service.get("test001"))

if __name__ == '__main__':
    unittest.main()
