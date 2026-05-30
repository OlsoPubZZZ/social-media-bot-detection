"""SMBD — Social Media Bot Detection Tool.

A platform-agnostic engine that scores social media engagement (comments,
followers, amplification) for fake/bot/coordinated activity and emits
human-readable evidence for every flag.

The core engine runs with no credentials and no AI key. Provider adapters feed
data in; an optional LLM layer enriches ambiguous cases and narrates evidence.
"""

from smbd.schema import (
    Account,
    Comment,
    Follower,
    Interaction,
    Page,
    Signal,
    Label,
)

__version__ = "0.1.0"

__all__ = [
    "Account",
    "Comment",
    "Follower",
    "Interaction",
    "Page",
    "Signal",
    "Label",
    "__version__",
]
