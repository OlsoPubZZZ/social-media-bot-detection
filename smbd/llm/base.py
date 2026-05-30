"""Provider-agnostic LLM interface.

Keep this tiny: anything that can turn a prompt into text (Anthropic, OpenAI, a
local model) implements :class:`LLMClient`. Detection never depends on a
specific vendor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional


class LLMClient(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, prompt: str, *, system: Optional[str] = None) -> str:
        """Return a text completion for ``prompt``."""
        raise NotImplementedError


class NullLLM(LLMClient):
    """No-op client used when no AI key is configured.

    Lets the whole pipeline run key-free. Returns an empty string so callers
    fall back to deterministic, template-based evidence narration.
    """

    name = "null"

    def complete(self, prompt: str, *, system: Optional[str] = None) -> str:
        return ""
