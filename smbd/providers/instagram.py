"""Instagram provider — official Graph API (the legal, sustainable path).

**What the official API can do:** read comments on media owned by the
business/creator account whose token you hold, and read that account's own
metadata (follower *count*, media count). That's it.

**What it cannot do — read carefully:** the Instagram Graph API does **not**
expose a list of your individual followers, nor any follower's creation date,
follower count, or profile photo. Instagram withholds follower-level profiles by
design. So follower-quality analysis (the "are these followers real?" product
question) cannot be powered by this adapter — feed :class:`~smbd.followers`
follower data via the import provider or the optional scraper plugin instead.
``fetch_followers`` here raises with that explanation rather than pretending.

Tests inject a ``transport`` callable so the parsing logic runs fully offline;
the default transport uses stdlib ``urllib`` (no extra dependency).
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Callable, Dict, List, Optional

from smbd.providers.base import Provider
from smbd.schema import Account, Comment, Page

_GRAPH = "https://graph.facebook.com"


def _parse_ig_time(value: object) -> Optional[datetime]:
    """Parse Instagram timestamps, e.g. ``2026-05-01T10:00:00+0000``."""
    if not value:
        return None
    text = str(value).strip()
    # Insert a colon into a ``+0000`` / ``-0500`` offset so fromisoformat accepts it.
    if len(text) >= 5 and text[-5] in "+-" and text[-3] != ":":
        text = text[:-2] + ":" + text[-2:]
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


class InstagramProvider(Provider):
    name = "instagram"

    def __init__(
        self,
        access_token: Optional[str] = None,
        *,
        version: str = "v21.0",
        transport: Optional[Callable[[str], Dict]] = None,
        max_pages: int = 20,
    ):
        self.access_token = (
            access_token
            or os.getenv("IG_ACCESS_TOKEN")
            or os.getenv("INSTAGRAM_ACCESS_TOKEN")
        )
        self.version = version
        self.max_pages = max_pages
        self._uses_http = transport is None
        self._transport = transport or self._http_get

    # --- transport ---

    def _http_get(self, url: str) -> Dict:  # pragma: no cover - exercised only live
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, path: str, params: Dict) -> Dict:
        if self._uses_http and not self.access_token:
            raise RuntimeError(
                "InstagramProvider needs an access token for live calls "
                "(pass access_token= or set IG_ACCESS_TOKEN)."
            )
        params = dict(params)
        if self.access_token:
            params.setdefault("access_token", self.access_token)
        url = f"{_GRAPH}/{self.version}/{path}?{urllib.parse.urlencode(params)}"
        return self._fetch(url)

    def _fetch(self, url: str) -> Dict:
        data = self._transport(url)
        if isinstance(data, dict) and data.get("error"):
            msg = (data["error"] or {}).get("message", "unknown error")
            raise RuntimeError(f"Instagram API error: {msg}")
        return data

    # --- comments (supported) ---

    def fetch_comments(self, target: str) -> List[Comment]:
        """``target`` is a media id you own. Paginates the comments edge."""
        data = self._get(
            f"{target}/comments",
            {"fields": "id,text,timestamp,username,like_count,from", "limit": 100},
        )
        comments: List[Comment] = []
        pages = 0
        while True:
            for row in data.get("data", []):
                comment = self._to_comment(row, target)
                if comment is not None:
                    comments.append(comment)
            nxt = (data.get("paging") or {}).get("next")
            pages += 1
            if not nxt or pages >= self.max_pages:
                break
            data = self._fetch(nxt)
        return comments

    def _to_comment(self, row: Dict, media_id: str) -> Optional[Comment]:
        text = row.get("text")
        if text is None:
            return None
        frm = row.get("from") or {}
        handle = frm.get("username") or row.get("username")
        account = Account(id=str(frm.get("id") or handle or row.get("id")), handle=handle)
        return Comment(
            id=str(row.get("id")),
            account=account,
            text=str(text),
            created_at=_parse_ig_time(row.get("timestamp")),
            likes=row.get("like_count"),
            post_id=str(media_id),
        )

    # --- page metadata (supported, counts only) ---

    def fetch_page(self, target: str) -> Page:
        """``target`` is an IG user id. Returns the account's own metadata."""
        data = self._get(target, {"fields": "username,followers_count,follows_count,media_count"})
        pid = str(data.get("id") or target)
        owner = Account(
            id=pid,
            handle=data.get("username"),
            followers_count=data.get("followers_count"),
            following_count=data.get("follows_count"),
            post_count=data.get("media_count"),
        )
        return Page(id=pid, handle=data.get("username"), owner=owner)

    # --- followers (NOT available via the official API) ---

    def fetch_followers(self, target: str):
        raise NotImplementedError(
            "Instagram's Graph API does not expose individual followers — there is no "
            "per-follower id, creation date, follower count, or profile photo available. "
            "To analyze follower quality, load follower profiles you legitimately have via "
            "ImportProvider.fetch_followers (CSV/JSON) or the optional scraper plugin, then "
            "run smbd.followers.analyze_followers."
        )
