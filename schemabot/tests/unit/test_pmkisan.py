"""
Full-flow validation of the PM-KISAN scheme definition.

Coverage:
1.  YAML → Pydantic parsing / validator
2.  Rule engine success & failure paths
3.  /eligibility/check endpoint
4.  Conversation flow with data collection completion
"""

from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from core.scheme.validator import SchemeValidator
from core.eligibility.checker import EligibilityChecker
from app.main import fastapi_app


DATA_DIR = Path(__file__).parent "Sanchalak"/ "schemabot" / "schemas"
SCHEMA_FILE = "pm-kisan-scheme.yaml"


# --------------------------------------------------------------------------- #
# 1.  YAML → Pydantic                                                         #
# --------------------------------------------------------------------------- #

def test_yaml_parses_cleanly() -> None:
    v = SchemeValidator(DATA_DIR)
    scheme = v.load_scheme(SCHEMA_FILE)
    assert scheme.code == "PMKISAN"
    # sanity-check a couple of rules
    rule_ids = {r.rule_id for r in scheme.eligibility.rules}
    assert rule_ids >= {"pmk_001", "pmk_006"}


# --------------------------------------------------------------------------- #
# 2.  Rule engine                                                             #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            dict(
                is_farmer=True,
                annual_income=75_000,
                land_size=0.25,
                government_employee=False,
                income_tax_payer=False,
                is_indian_citizen=True,
            ),
            True,
        ),
        (
            dict(  # government employee → ineligible
                is_farmer=True,
                annual_income=25_000,
                land_size=1.0,
                government_employee=True,
                income_tax_payer=False,
                is_indian_citizen=True,
            ),
            False,
        ),
    ],
)
def test_rule_engine_outcomes(payload, expected) -> None:
    checker = EligibilityChecker(DATA_DIR / SCHEMA_FILE)
    result = checker.check(payload)
    assert result.is_eligible is expected


# --------------------------------------------------------------------------- #
# 3.  Direct API hit                                                          #
# --------------------------------------------------------------------------- #

def test_api_single_shot(tmp_path) -> None:
    client = TestClient(fastapi_app)

    applicant = {
        "scheme_code": "PMKISAN",
        "farmer_data": {
            "is_farmer": True,
            "annual_income": 80_000,
            "land_size": 0.2,
            "government_employee": False,
            "income_tax_payer": False,
            "is_indian_citizen": True,
        },
    }

    r = client.post("/eligibility/check", json=applicant)
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    assert body["result"]["is_eligible"] is True
    assert body["result"]["failed_rule_ids"] == []


# --------------------------------------------------------------------------- #
# 4.  Conversational flow                                                     #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_conversation_flow() -> None:
    conv_id = str(uuid4())

    async with httpx.AsyncClient(app=fastapi_app, base_url="http://test") as c:
        # start
        r = await c.post("/conversations/", json={"scheme_code": "PMKISAN", "conversation_id": conv_id})
        assert r.status_code == 201

        # send minimal fields in two messages
        await c.post(
            f"/conversations/{conv_id}/messages",
            json={"role": "user", "content": "I am a land-holding farmer with 0.3 acres."},
        )
        await c.post(
            f"/conversations/{conv_id}/messages",
            json={"role": "user", "content": "My family earns ₹80,000 a year and none of us pay income tax."},
        )

        # end conversation – backend should compute eligibility
        r_end = await c.post(f"/conversations/{conv_id}/end")
        assert r_end.status_code == 200
        payload = r_end.json()
        assert payload["eligibility"]["is_eligible"] is True
