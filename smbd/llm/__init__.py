"""Optional LLM enrichment layer.

The core engine never requires this. When an AI key is configured, the LLM is
used to (a) judge ambiguous text the deterministic signals can't settle and
(b) narrate evidence in natural language. Milestone 1 ships the interface plus
a ``NullLLM`` so everything runs key-free; Milestone 2 fills in real clients.
"""

from smbd.llm.base import LLMClient, NullLLM
from smbd.llm.enrich import enrich_batch

# AnthropicLLM is imported lazily via get_anthropic() so the package imports
# cleanly without the optional `anthropic` dependency installed.


def get_anthropic(**kwargs):
    """Construct an :class:`AnthropicLLM` (requires the ``llm`` extra)."""
    from smbd.llm.anthropic_client import AnthropicLLM

    return AnthropicLLM(**kwargs)


__all__ = ["LLMClient", "NullLLM", "enrich_batch", "get_anthropic"]
