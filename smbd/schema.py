"""Normalized data model — the contract every provider adapter targets.

Every adapter (Instagram, YouTube, X, CSV import, scraper) converts its
platform-specific payload into these types. Detectors operate *only* on these
types, so they are completely decoupled from where the data came from.

Fields are optional on purpose: adapters fill what they can, and detectors
degrade gracefully on missing data (an absent ``created_at`` makes the
account-age signal *abstain* rather than guess).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Label(str, Enum):
    """Per-item classification produced by scoring."""

    GENUINE = "genuine"
    SUSPICIOUS = "suspicious"
    SPAM = "spam"
    COORDINATED = "coordinated"
    LOW_CONFIDENCE = "low_confidence"


@dataclass
class Account:
    """A social media account/profile."""

    id: str
    handle: Optional[str] = None
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    bio: Optional[str] = None
    has_avatar: Optional[bool] = None
    is_verified: Optional[bool] = None
    external_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(asdict(self))


@dataclass
class Comment:
    """A comment/reply authored by an :class:`Account`."""

    id: str
    account: Account
    text: str
    created_at: Optional[datetime] = None
    likes: Optional[int] = None
    parent_id: Optional[str] = None
    post_id: Optional[str] = None
    lang: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = _serialize(asdict(self))
        return d


@dataclass
class Follower:
    """A follow relationship to a page."""

    account: Account
    followed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(asdict(self))


@dataclass
class Interaction:
    """A generic actor -> target interaction (like, reply, mention, ...)."""

    actor: Account
    target_id: str
    type: str
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(asdict(self))


@dataclass
class Page:
    """A page/channel/profile under analysis."""

    id: str
    handle: Optional[str] = None
    owner: Optional[Account] = None
    followers: List[Follower] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(asdict(self))


@dataclass
class Signal:
    """A single piece of suspicion evidence emitted by a detector.

    ``score`` is the detector's suspicion contribution in ``[0, 1]`` and
    ``weight`` is how much this detector counts toward the aggregate (set from
    config). ``evidence`` is a structured dict that explains *why* the signal
    fired — this is what powers the "why was this flagged?" product output.
    """

    name: str
    score: float
    weight: float
    evidence: Dict[str, Any] = field(default_factory=dict)
    # Optional hint about which label this signal points toward.
    label_hint: Optional[Label] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.label_hint is not None:
            d["label_hint"] = self.label_hint.value
        return _serialize(d)


def _serialize(value: Any) -> Any:
    """Recursively make a structure JSON-friendly (datetimes -> ISO, enums -> value)."""
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value
