"""Anthropic implementation of :class:`~smbd.llm.base.LLMClient`.

Kept deliberately thin: it satisfies the provider-agnostic ``complete()``
contract so the rest of SMBD never depends on a specific vendor. The Anthropic
specifics that matter for cost/quality live here:

* **Prompt caching** — the (stable) system prompt is sent as a cached block, so
  repeated judge batches pay ~0.1x on the prefix.
* **Model default** — ``claude-opus-4-8`` per Anthropic guidance; override with
  ``model=`` (Haiku is far cheaper for this classification workload).

Thinking is intentionally left off for this path: the judge/narration calls are
short, simple classification — adaptive thinking would add latency and cost
without improving label quality. Flip it on via ``thinking=`` if you disagree.
"""

from __future__ import annotations

from typing import Any, List, Optional

from smbd.llm.base import LLMClient

DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicLLM(LLMClient):
    name = "anthropic"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        max_tokens: int = 2048,
        client: Any = None,
        thinking: Optional[dict] = None,
    ):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "AnthropicLLM requires the 'anthropic' package. "
                "Install it with: pip install 'smbd[llm]'"
            ) from exc

        self._anthropic = anthropic
        self.model = model
        self.max_tokens = max_tokens
        self.thinking = thinking
        if client is not None:
            self._client = client
        elif api_key is not None:
            self._client = anthropic.Anthropic(api_key=api_key)
        else:
            # Resolves ANTHROPIC_API_KEY from the environment.
            self._client = anthropic.Anthropic()

    def complete(self, prompt: str, *, system: Optional[str] = None) -> str:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            # Cache the stable system prompt across calls (prefix cache).
            kwargs["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        if self.thinking is not None:
            kwargs["thinking"] = self.thinking

        response = self._client.messages.create(**kwargs)
        return "".join(block.text for block in response.content if block.type == "text")
