"""Integration tests for health endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.integration
async def test_liveness(async_client):
    resp = await async_client.get("/health/liveness")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
