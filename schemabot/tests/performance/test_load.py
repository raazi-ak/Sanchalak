"""Simple locust-style load test using pytest-benchmark."""

from __future__ import annotations

import pytest


@pytest.mark.performance
def test_list_schemes_benchmark(benchmark, client):
    benchmark(lambda: client.get("/schemes/").json())
