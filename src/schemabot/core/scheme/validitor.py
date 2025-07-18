"""
YAML scheme validation layer.

Responsibilities
----------------
* Parse YAML into Pydantic models
* Perform structural & semantic checks
* Emit rich error objects understood by API responses
"""

from __future__ import annotations

import pathlib
from typing import List

import yaml
from pydantic import ValidationError

from src.schemabot.core.scheme.models import Scheme, SchemeRegistry

class SchemeValidationError(Exception):
    """Raised when a scheme file fails validation."""

    def __init__(self, path: pathlib.Path, err: ValidationError) -> None:
        super().__init__(f"{path} failed validation")
        self.path = path
        self.err = err


class SchemeValidator:
    """
    Validate single scheme files and the global registry.

    Usage:
        validator = SchemeValidator(base_dir=Path('schemas'))
        scheme = validator.load_scheme('pm_kisan.yaml')
        registry = validator.load_registry()
    """

    def __init__(self, base_dir: pathlib.Path) -> None:
        self.base_dir = base_dir

    # --------------------------------------------------------------------- #
    # Public helpers
    # --------------------------------------------------------------------- #

    def load_scheme(self, filename: str) -> Scheme:
        path = self.base_dir / filename
        data = self._read_yaml(path)
        try:
            scheme = Scheme.model_validate(data)
            return scheme
        except ValidationError as exc:
                        raise SchemeValidationError(path, exc) from exc

    def load_registry(self) -> SchemeRegistry:
        path = self.base_dir / "schemes_registry.yaml"
        data = self._read_yaml(path)
        try:
            reg = SchemeRegistry.model_validate(data)
        except ValidationError as exc:
            raise SchemeValidationError(path, exc) from exc

        # Cross-file referential integrity
        missing: List[str] = [
            code for code in reg.registered_codes
            if not (self.base_dir / f"{code}.yaml").exists()
        ]
        if missing:
            raise RuntimeError(
                f"Registry references missing scheme files: {missing}"
            )
        return reg

    # --------------------------------------------------------------------- #
    # Internals
    # --------------------------------------------------------------------- #

    @staticmethod
    def _read_yaml(path: pathlib.Path) -> dict:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"{path} does not contain a YAML mapping at root")
        return data
