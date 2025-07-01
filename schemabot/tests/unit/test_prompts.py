"""Unit tests for prompt context manager."""

from __future__ import annotations

from core.prompts.context import ConversationContext


def test_context_add_and_budget():
    ctx = ConversationContext(conv_id="abc", max_tokens=100)
    ctx.add("user", "Hello", tokens=5)
    ctx.add("assistant", "Hi there", tokens=5)
    assert ctx.remaining_budget() == 90
    prompt = ctx.to_prompt(intro="System intro")
    assert prompt[0]["role"] == "system"
    assert len(prompt) == 3
