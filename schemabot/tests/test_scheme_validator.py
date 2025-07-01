from pathlib import Path

import pytest
from schemabot.core.scheme.validator import SchemeValidator, SchemeValidationError


def test_load_valid_scheme(tmp_path: Path, sample_scheme_yml: str):
    f = tmp_path / "pm_kisan.yaml"
    f.write_text(sample_scheme_yml)
    validator = SchemeValidator(tmp_path)
    scheme = validator.load_scheme("pm_kisan.yaml")
    assert scheme.code == "PM_KISAN"


def test_invalid_scheme_raises(tmp_path: Path):
    (tmp_path / "bad.yaml").write_text("just: bad")
    validator = SchemeValidator(tmp_path)
    with pytest.raises(SchemeValidationError):
        validator.load_scheme("bad.yaml")
with pytest.raises(SchemeValidationError):
    validator.load_scheme("bad.yaml")
    