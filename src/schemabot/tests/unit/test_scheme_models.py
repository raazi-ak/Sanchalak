"""
Unit tests for scheme models and validation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from core.scheme.models import (
    DataType,
    EligibilityRule, 
    Operator,
    Scheme,
    SchemeRegistry,
    SchemeSummary
)


class TestDataType:
    """Test DataType enum."""
    
    def test_all_data_types_exist(self):
        """Test all expected data types are defined."""
        expected_types = {
            "string", "integer", "float", "boolean", 
            "date", "list", "decimal"
        }
        actual_types = {dt.value for dt in DataType}
        assert expected_types.issubset(actual_types)
    
    def test_data_type_string_representation(self):
        """Test string representation of data types."""
        assert str(DataType.STRING) == "string"
        assert str(DataType.INTEGER) == "integer"
        assert str(DataType.FLOAT) == "float"


class TestOperator:
    """Test Operator enum."""
    
    def test_all_operators_exist(self):
        """Test all expected operators are defined."""
        expected_ops = {
            "eq", "ne", "gt", "gte", "lt", "lte",
            "in", "not_in", "between", "contains",
            "starts_with", "ends_with", "regex"
        }
        actual_ops = {op.value for op in Operator}
        assert expected_ops.issubset(actual_ops)
    
    def test_operator_aliases(self):
        """Test operator aliases work correctly."""
        assert Operator.EQ.value == "eq"
        assert Operator.EQUALS.value == "eq"  # Alias
        assert Operator.GT.value == "gt"
        assert Operator.GREATER_THAN.value == "gt"  # Alias


class TestEligibilityRule:
    """Test EligibilityRule model."""
    
    def test_valid_rule_creation(self):
        """Test creating valid eligibility rules."""
        rule = EligibilityRule(
            field="age",
            operator=Operator.GTE,
            value=18,
            data_type=DataType.INTEGER,
            description="Minimum age requirement"
        )
        
        assert rule.field == "age"
        assert rule.operator == Operator.GTE
        assert rule.value == 18
        assert rule.data_type == DataType.INTEGER
        assert rule.description == "Minimum age requirement"
        assert rule.error_message is None
    
    def test_rule_with_custom_error_message(self):
        """Test rule with custom error message."""
        rule = EligibilityRule(
            field="income",
            operator=Operator.LTE,
            value=200000,
            data_type=DataType.INTEGER,
            error_message="Annual income must not exceed ₹2,00,000"
        )
        
        assert rule.error_message == "Annual income must not exceed ₹2,00,000"
    
    def test_rule_with_between_operator(self):
        """Test rule with between operator requires list value."""
        rule = EligibilityRule(
            field="age",
            operator=Operator.BETWEEN,
            value=[18, 60],
            data_type=DataType.INTEGER
        )
        
        assert rule.value == [18, 60]
    
    def test_rule_with_in_operator(self):
        """Test rule with 'in' operator."""
        rule = EligibilityRule(
            field="state",
            operator=Operator.IN,
            value=["UP", "MP", "RJ"],
            data_type=DataType.STRING
        )
        
        assert rule.value == ["UP", "MP", "RJ"]
    
    def test_invalid_rule_missing_field(self):
        """Test validation fails for missing field."""
        with pytest.raises(ValidationError) as exc_info:
            EligibilityRule(
                operator=Operator.EQ,
                value=18,
                data_type=DataType.INTEGER
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("field",) for error in errors)
    
    def test_invalid_rule_missing_operator(self):
        """Test validation fails for missing operator."""
        with pytest.raises(ValidationError) as exc_info:
            EligibilityRule(
                field="age",
                value=18,
                data_type=DataType.INTEGER
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("operator",) for error in errors)


class TestScheme:
    """Test Scheme model."""
    
    @pytest.fixture
    def valid_scheme_data(self) -> Dict[str, Any]:
        """Valid scheme data for testing."""
        return {
            "code": "PM_KISAN",
            "name": "PM Kisan Samman Nidhi",
            "category": "agriculture",
            "description": "Direct income support to farmers",
            "eligibility_rules": [
                {
                    "field": "age",
                    "operator": "gte",
                    "value": 18,
                    "data_type": "integer",
                    "description": "Minimum age 18 years"
                },
                {
                    "field": "land_holding",
                    "operator": "lte",
                    "value": 2.0,
                    "data_type": "float",
                    "description": "Maximum 2 hectares land"
                }
            ],
            "benefit_amount": 6000,
            "benefit_frequency": "annual",
            "application_process": "online",
            "required_documents": ["aadhaar", "bank_passbook", "land_records"],
            "language_support": ["hi", "en"],
            "contact_info": {
                "helpline": "1800-115-526",
                "website": "https://pmkisan.gov.in"
            }
        }
    
    def test_valid_scheme_creation(self, valid_scheme_data):
        """Test creating a valid scheme."""
        scheme = Scheme.model_validate(valid_scheme_data)
        
        assert scheme.code == "PM_KISAN"
        assert scheme.name == "PM Kisan Samman Nidhi"
        assert scheme.category == "agriculture"
        assert len(scheme.eligibility_rules) == 2
        assert scheme.benefit_amount == 6000
        assert "hi" in scheme.language_support
        assert "en" in scheme.language_support
    
    def test_scheme_code_validation(self, valid_scheme_data):
        """Test scheme code validation."""
        # Valid codes
        valid_codes = ["PM_KISAN", "ATAL_PENSION", "AYUSHMAN_BHARAT"]
        for code in valid_codes:
            valid_scheme_data["code"] = code
            scheme = Scheme.model_validate(valid_scheme_data)
            assert scheme.code == code
    
    def test_invalid_scheme_code(self, valid_scheme_data):
        """Test invalid scheme codes."""
        invalid_codes = ["pm-kisan", "PM KISAN", "pm_kisan", "123_SCHEME"]
        for code in invalid_codes:
            valid_scheme_data["code"] = code
            with pytest.raises(ValidationError) as exc_info:
                Scheme.model_validate(valid_scheme_data)
            
            errors = exc_info.value.errors()
            assert any("code" in str(error["loc"]) for error in errors)
    
    def test_scheme_language_validation(self, valid_scheme_data):
        """Test language support validation."""
        # Valid languages
        valid_scheme_data["language_support"] = ["hi", "en", "bn", "te", "ta"]
        scheme = Scheme.model_validate(valid_scheme_data)
        assert len(scheme.language_support) == 5
        
        # Invalid language
        valid_scheme_data["language_support"] = ["xyz"]
        with pytest.raises(ValidationError):
            Scheme.model_validate(valid_scheme_data)
    
    def test_scheme_benefit_amount_validation(self, valid_scheme_data):
        """Test benefit amount validation."""
        # Valid amounts
        valid_amounts = [1000, 5000, 12000, 50000]
        for amount in valid_amounts:
            valid_scheme_data["benefit_amount"] = amount
            scheme = Scheme.model_validate(valid_scheme_data)
            assert scheme.benefit_amount == amount
        
        # Invalid amounts
        invalid_amounts = [-1000, 0]
        for amount in invalid_amounts:
            valid_scheme_data["benefit_amount"] = amount
            with pytest.raises(ValidationError):
                Scheme.model_validate(valid_scheme_data)
    
    def test_scheme_to_summary(self, valid_scheme_data):
        """Test converting scheme to summary."""
        scheme = Scheme.model_validate(valid_scheme_data)
        summary = scheme.to_summary()
        
        assert isinstance(summary, SchemeSummary)
        assert summary.code == scheme.code
        assert summary.name == scheme.name
        assert summary.category == scheme.category
        assert summary.benefit_amount == scheme.benefit_amount


class TestSchemeSummary:
    """Test SchemeSummary model."""
    
    def test_scheme_summary_creation(self):
        """Test creating scheme summary."""
        summary = SchemeSummary(
            code="PM_KISAN",
            name="PM Kisan Samman Nidhi",
            category="agriculture", 
            description="Direct income support",
            benefit_amount=6000,
            language_support=["hi", "en"]
        )
        
        assert summary.code == "PM_KISAN"
        assert summary.name == "PM Kisan Samman Nidhi"
        assert summary.benefit_amount == 6000


class TestSchemeRegistry:
    """Test SchemeRegistry model."""
    
    @pytest.fixture
    def valid_registry_data(self) -> Dict[str, Any]:
        """Valid registry data for testing."""
        return {
            "schemes": [
                {
                    "code": "PM_KISAN",
                    "file": "pm_kisan.yaml",
                    "status": "active",
                    "priority": 1,
                    "category": "agriculture"
                },
                {
                    "code": "ATAL_PENSION",
                    "file": "atal_pension.yaml", 
                    "status": "active",
                    "priority": 2,
                    "category": "pension"
                }
            ],
            "categories": ["agriculture", "pension", "health"],
            "last_updated": "2024-01-15T10:00:00Z"
        }
    
    def test_valid_registry_creation(self, valid_registry_data):
        """Test creating valid registry."""
        registry = SchemeRegistry.model_validate(valid_registry_data)
        
        assert len(registry.schemes) == 2
        assert len(registry.categories) == 3
        assert "agriculture" in registry.categories
        assert "pension" in registry.categories
    
    def test_registry_scheme_entries(self, valid_registry_data):
        """Test registry scheme entries."""
        registry = SchemeRegistry.model_validate(valid_registry_data)
        
        pm_kisan = next((s for s in registry.schemes if s.code == "PM_KISAN"), None)
        assert pm_kisan is not None
        assert pm_kisan.file == "pm_kisan.yaml"
        assert pm_kisan.status == "active"
        assert pm_kisan.priority == 1
    
    def test_registry_get_active_schemes(self, valid_registry_data):
        """Test getting active schemes from registry."""
        # Add inactive scheme
        valid_registry_data["schemes"].append({
            "code": "INACTIVE_SCHEME",
            "file": "inactive.yaml",
            "status": "inactive", 
            "priority": 99,
            "category": "test"
        })
        
        registry = SchemeRegistry.model_validate(valid_registry_data)
        active_schemes = registry.get_active_schemes()
        
        assert len(active_schemes) == 2  # Only active schemes
        codes = [s.code for s in active_schemes]
        assert "PM_KISAN" in codes
        assert "ATAL_PENSION" in codes
        assert "INACTIVE_SCHEME" not in codes
    
    def test_registry_get_by_category(self, valid_registry_data):
        """Test getting schemes by category."""
        registry = SchemeRegistry.model_validate(valid_registry_data)
        agriculture_schemes = registry.get_by_category("agriculture")
        
        assert len(agriculture_schemes) == 1
        assert agriculture_schemes[0].code == "PM_KISAN"
    
    def test_empty_registry(self):
        """Test empty registry validation."""
        registry_data = {
            "schemes": [],
            "categories": [],
            "last_updated": "2024-01-15T10:00:00Z"
        }
        
        registry = SchemeRegistry.model_validate(registry_data)
        assert len(registry.schemes) == 0
        assert len(registry.categories) == 0


# ============================================================================
# Integration Tests for Model Interactions
# ============================================================================

class TestModelIntegrations:
    """Test interactions between different models."""
    
    def test_scheme_with_complex_rules(self):
        """Test scheme with complex eligibility rules."""
        scheme_data = {
            "code": "COMPLEX_SCHEME",
            "name": "Complex Eligibility Scheme",
            "category": "test",
            "description": "Test scheme with complex rules",
            "eligibility_rules": [
                {
                    "field": "age",
                    "operator": "between",
                    "value": [18, 60],
                    "data_type": "integer"
                },
                {
                    "field": "state",
                    "operator": "in",
                    "value": ["UP", "MP", "RJ"],
                    "data_type": "string"
                },
                {
                    "field": "income",
                    "operator": "lte",
                    "value": 500000,
                    "data_type": "integer"
                }
            ],
            "benefit_amount": 12000,
            "language_support": ["hi", "en"]
        }
        
        scheme = Scheme.model_validate(scheme_data)
        assert len(scheme.eligibility_rules) == 3
        
        # Check between rule
        age_rule = next((r for r in scheme.eligibility_rules if r.field == "age"), None)
        assert age_rule.operator == Operator.BETWEEN
        assert age_rule.value == [18, 60]
        
        # Check in rule
        state_rule = next((r for r in scheme.eligibility_rules if r.field == "state"), None)
        assert state_rule.operator == Operator.IN
        assert state_rule.value == ["UP", "MP", "RJ"]
    
    def test_scheme_registry_with_priorities(self):
        """Test scheme registry with priority-based ordering."""
        registry_data = {
            "schemes": [
                {
                    "code": "LOW_PRIORITY",
                    "file": "low.yaml",
                    "status": "active",
                    "priority": 5,
                    "category": "test"
                },
                {
                    "code": "HIGH_PRIORITY", 
                    "file": "high.yaml",
                    "status": "active",
                    "priority": 1,
                    "category": "test"
                },
                {
                    "code": "MED_PRIORITY",
                    "file": "med.yaml", 
                    "status": "active",
                    "priority": 3,
                    "category": "test"
                }
            ],
            "categories": ["test"],
            "last_updated": "2024-01-15T10:00:00Z"
        }
        
        registry = SchemeRegistry.model_validate(registry_data)
        sorted_schemes = registry.get_schemes_by_priority()
        
        # Should be sorted by priority (ascending)
        assert sorted_schemes[0].code == "HIGH_PRIORITY"
        assert sorted_schemes[1].code == "MED_PRIORITY" 
        assert sorted_schemes[2].code == "LOW_PRIORITY"


# ============================================================================
# Property-based Testing
# ============================================================================

@pytest.mark.parametrize("operator,value,data_type", [
    (Operator.EQ, "test", DataType.STRING),
    (Operator.GT, 100, DataType.INTEGER),
    (Operator.LTE, 99.5, DataType.FLOAT),
    (Operator.IN, ["a", "b", "c"], DataType.STRING),
    (Operator.BETWEEN, [1, 10], DataType.INTEGER),
])
def test_eligibility_rule_combinations(operator, value, data_type):
    """Test various combinations of operators, values, and data types."""
    rule = EligibilityRule(
        field="test_field",
        operator=operator,
        value=value,
        data_type=data_type
    )
    
    assert rule.field == "test_field"
    assert rule.operator == operator
    assert rule.value == value
    assert rule.data_type == data_type


@pytest.mark.parametrize("language", ["hi", "en", "bn", "te", "ta", "mr", "gu", "or"])
def test_supported_languages(language):
    """Test all supported languages are valid."""
    scheme_data = {
        "code": "TEST_SCHEME",
        "name": "Test Scheme",
        "category": "test",
        "description": "Test description",
        "eligibility_rules": [],
        "benefit_amount": 1000,
        "language_support": [language]
    }
    
    scheme = Scheme.model_validate(scheme_data)
    assert language in scheme.language_support