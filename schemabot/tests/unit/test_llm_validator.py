"""Unit tests for LLM response validator."""

from __future__ import annotations

from core.llm.response_validator import LLMResponseValidator, ValidationErrorReport


def test_validator_pass():
    validator = LLMResponseValidator(strict=False)
    report = validator.validate("यह एक वैध उत्तर है।")
    assert isinstance(report, ValidationErrorReport)
    assert report.passed is True


def test_validator_fail_safety():
    validator = LLMResponseValidator()
    report = validator.validate("<script>alert('xss')</script>")
    assert report.passed is False
    assert any(err.code == "unsafe_content" for err in report.errors)
