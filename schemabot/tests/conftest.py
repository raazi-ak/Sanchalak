"""
Test configuration and fixtures for Sanchalak.
"""

import sys
import os
from pathlib import Path
from typing import Any, Generator

import pytest

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ["SANCHALAK_ENVIRONMENT"] = "test"
os.environ["PYTHONPATH"] = str(project_root)

# Try to import app modules, but don't fail if they're not ready
try:
    from app.config import get_settings
    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False

try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Configure anyio backend for async tests."""
    return "asyncio"


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    if not APP_AVAILABLE or not FASTAPI_AVAILABLE:
        yield None
    
    try:
        from app.main import fastapi_app
        with TestClient(fastapi_app) as c:
            yield c
    except ImportError:
        return None


@pytest.fixture
@pytest.fixture
def sample_scheme_yaml() -> str:
    """Sample PM-KISAN scheme YAML for testing."""
    return """
code: "PMKISAN"
name: "PM-KISAN Samman Nidhi"
description: "Income support scheme for farmers"
category: "agriculture"
ministry: "Ministry of Agriculture & Farmers Welfare"
launch_date: "2019-02-24"
status: "active"
languages:
  - "en"
  - "hi"
eligibility:
  logic: "ALL"
  rules:
    - rule_id: "pmk_001"
      field: "is_farmer"
      operator: "equals"
      value: true
      data_type: "boolean"
      description: "Must be a farmer"
    - rule_id: "pmk_002"
      field: "land_size"
      operator: "greater_than"
      value: 0
      data_type: "float"
      description: "Must own agricultural land"
    - rule_id: "pmk_003"
      field: "government_employee"
      operator: "equals"
      value: false
      data_type: "boolean"
      description: "Must not be a government employee"
benefits:
  - "₹6,000 per year in three installments"
  - "Direct benefit transfer to bank account"
documents_required:
  - "Aadhaar card"
  - "Land ownership documents"
  - "Bank account details"
"""


@pytest.fixture
def eligible_farmer_data() -> dict[str, Any]:
    """Sample eligible farmer data."""
    return {
        "is_farmer": True,
        "annual_income": 75000,
        "land_size": 0.5,
        "government_employee": False,
        "income_tax_payer": False,
        "is_indian_citizen": True,
        "age": 45
    }


@pytest.fixture
def ineligible_farmer_data() -> dict[str, Any]:
    """Sample ineligible farmer data."""
    return {
        "is_farmer": True,
        "annual_income": 50000,
        "land_size": 1.0,
        "government_employee": True,
        "income_tax_payer": False,
        "is_indian_citizen": True,
        "age": 40
    }
