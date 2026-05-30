"""Provider abstract base class — the single ingestion interface.

Every data source (official API, import, scraper) implements this. The
detection engine never imports a concrete provider, so sources are fully
swappable and new ones are easy to contribute.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from smbd.schema import Comment, Follower, Page


class Provider(ABC):
    """Base for all ingestion adapters."""

    name: str = "base"

    @abstractmethod
    def fetch_comments(self, target: str) -> List[Comment]:
        """Return normalized comments for a target (post id, url, file path, ...)."""
        raise NotImplementedError

    def fetch_followers(self, target: str) -> List[Follower]:  # pragma: no cover - optional
        """Optional: return followers for a page. Default = unsupported."""
        raise NotImplementedError(f"{self.name} provider does not support followers")

    def fetch_page(self, target: str) -> Page:  # pragma: no cover - optional
        """Optional: return a full page bundle. Default = unsupported."""
        raise NotImplementedError(f"{self.name} provider does not support page fetch")
