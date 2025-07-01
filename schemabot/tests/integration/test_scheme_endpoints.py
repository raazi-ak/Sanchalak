"""Integration tests for scheme API."""

from __future__ import annotations

import pytest


@pytest.mark.integration
async def test_list_schemes(async_client):
    resp = await async_client.get("/schemes/")
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, list)
