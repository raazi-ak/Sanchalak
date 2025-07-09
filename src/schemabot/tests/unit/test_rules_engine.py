"""Unit tests for rule evaluation engine."""

from __future__ import annotations

import pytest

from core.eligibility.rules import RuleProcessor
from core.scheme.models import EligibilityRule, Operator, DataType


@pytest.fixture
def processor() -> RuleProcessor:
    return RuleProcessor()


def test_rule_pass(processor: RuleProcessor):
    rule = EligibilityRule(
        field="age", operator=Operator.GTE, value=18, data_type=DataType.INTEGER
    )
    assert processor.evaluate_rule(rule, {"age": 25}) is True


def test_rule_fail(processor: RuleProcessor):
    rule = EligibilityRule(
        field="land_holding", operator=Operator.LTE, value=2.0, data_type=DataType.FLOAT
    )
    assert processor.evaluate_rule(rule, {"land_holding": 3.5}) is False
