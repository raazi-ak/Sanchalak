"""Unit tests for scheme validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.scheme.validator import SchemeValidator, SchemeValidationError


def test_load_valid(tmp_path: Path):
    (tmp_path / "valid.yaml").write_text("""
code: TEST
name: Test Scheme
category: test
eligibility_rules: []
benefit_amount: 1000
language_support: [en]
    """.strip())

    validator = SchemeValidator(tmp_path)
    scheme = validator.load_scheme("valid.yaml")
    assert scheme.code == "TEST"


def test_invalid_yaml(tmp_path: Path):
    (tmp_path / "bad.yaml").write_text("not: a: mapping")

    validator = SchemeValidator(tmp_path)
    with pytest.raises(SchemeValidationError):
        validator.load_scheme("bad.yaml")
