"""
Conversation-level context utilities for prompt construction.

The module offers:
* Context store tied to a Conversation ID
* Rolling window of previous messages (token-aware)
* Helper for building final prompt payloads
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Deque, List

from pydantic import BaseModel, Field, PositiveInt

log = get_logger(__name__)


class Msg(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str
    ts: datetime = Field(default_factory=datetime.utcnow)
    tokens: PositiveInt


class ConversationContext(BaseModel):
    conv_id: str
    lang: str = "en"
    max_tokens: PositiveInt = 4096
    history: Deque[Msg] = Field(default_factory=lambda: deque(maxlen=50))

    def add(self, role: str, content: str, tokens: int) -> None:
        self.history.append(
            Msg(role=role, content=content, tokens=tokens)
        )
        log.debug("context.add", conv_id=self.conv_id, role=role, tokens=tokens)

    # ---- Prompt helpers -------------------------------------------------- #

    def remaining_budget(self) -> int:
        used = sum(m.tokens for m in self.history)
        return max(self.max_tokens - used, 0)

    def to_prompt(self, intro: str | None = None) -> List[dict]:
        """
        Assemble messages for the LLM in OpenAI-style format.

        intro is inserted as a system message before history.
        """
        prompt: List[dict] = []
        if intro:
            prompt.append({"role": "system", "content": intro})
        for m in self.history:
            prompt.append({"role": m.role, "content": m.content})
        log.debug("context.to_prompt", conv_id=self.conv_id, segments=len(prompt))
        return prompt
