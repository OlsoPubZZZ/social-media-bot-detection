"""Detector abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

from smbd.config import Config
from smbd.schema import Comment, Signal


class Detector(ABC):
    """Base for all detectors.

    Subclasses implement :meth:`analyze`, which receives the full list of
    comments and returns ``{comment_id: [Signal, ...]}``. Returning nothing for
    a comment means "this detector has no opinion / abstains".
    """

    #: Stable key used to look up this detector's weight in :class:`Config`.
    name: str = "base"

    def __init__(self, config: Config):
        self.config = config

    @property
    def weight(self) -> float:
        return self.config.weights.get(self.name, 1.0)

    @abstractmethod
    def analyze(self, comments: List[Comment]) -> Dict[str, List[Signal]]:  # pragma: no cover
        raise NotImplementedError

    # --- helpers shared by subclasses ---

    @staticmethod
    def reference_time(comments: List[Comment]) -> Optional[datetime]:
        """Latest comment timestamp, used as 'now' for account-age math."""
        times = [c.created_at for c in comments if c.created_at is not None]
        return max(times) if times else None

    def signal(self, score: float, evidence: dict, label_hint=None) -> Signal:
        return Signal(
            name=self.name,
            score=max(0.0, min(1.0, score)),
            weight=self.weight,
            evidence=evidence,
            label_hint=label_hint,
        )
