"""Unit tests for LLM metrics collector."""

from __future__ import annotations

from core.llm.metrics import LLMetrics


def test_metrics_counters():
    metrics = LLMetrics(namespace="test")
    metrics.record_request(tokens_in=50)
    metrics.record_response(tokens_out=10, latency=0.123)

    assert metrics.total_requests._value.get() == 1  # type: ignore
    assert metrics.total_tokens_in._value.get() == 50  # type: ignore
    assert metrics.total_tokens_out._value.get() == 10  # type: ignore
