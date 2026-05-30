"""YouTube provider — official Data API v3.

Unlike Instagram, YouTube's API returns **public comments on any public video**,
so this is the first adapter that works on arbitrary third-party content. Each
comment carries the author's channel id, display name, avatar URL, like count,
and timestamp.

With ``enrich_authors=True`` the provider makes a second (batched) call to
``channels.list`` for the commenters' channels, filling in **channel creation
date**, **subscriber count**, and **video count** — which lets the account-age
and profile-weakness detectors actually fire on YouTube data.

**Limitation:** like every platform, YouTube does not expose the *identities* of
a channel's subscribers via the API (``subscriptions.list`` only covers the
authorized user's own subscriptions, with consent). So ``fetch_followers``
raises — analyze followers via the import provider instead.

Tests inject a ``transport`` callable so parsing/enrichment run fully offline.
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

_API = "https://www.googleapis.com/youtube/v3"


def _parse_time(value: object) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _to_int(value: object) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class YouTubeProvider(Provider):
    name = "youtube"

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        transport: Optional[Callable[[str], Dict]] = None,
        max_pages: int = 20,
        enrich_authors: bool = False,
    ):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.max_pages = max_pages
        self.enrich_authors = enrich_authors
        self._uses_http = transport is None
        self._transport = transport or self._http_get

    # --- transport ---

    def _http_get(self, url: str) -> Dict:  # pragma: no cover - exercised only live
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, path: str, params: Dict) -> Dict:
        if self._uses_http and not self.api_key:
            raise RuntimeError(
                "YouTubeProvider needs an API key for live calls "
                "(pass api_key= or set YOUTUBE_API_KEY)."
            )
        params = dict(params)
        if self.api_key:
            params.setdefault("key", self.api_key)
        url = f"{_API}/{path}?{urllib.parse.urlencode(params)}"
        return self._fetch(url)

    def _fetch(self, url: str) -> Dict:
        data = self._transport(url)
        if isinstance(data, dict) and data.get("error"):
            msg = (data["error"] or {}).get("message", "unknown error")
            raise RuntimeError(f"YouTube API error: {msg}")
        return data

    # --- comments (supported on any public video) ---

    def fetch_comments(self, target: str) -> List[Comment]:
        """``target`` is a video id. Paginates top-level comment threads."""
        params = {
            "part": "snippet",
            "videoId": target,
            "maxResults": 100,
            "textFormat": "plainText",
            "order": "time",
        }
        data = self._get("commentThreads", params)
        comments: List[Comment] = []
        pages = 0
        while True:
            for item in data.get("items", []):
                comment = self._to_comment(item, target)
                if comment is not None:
                    comments.append(comment)
            token = data.get("nextPageToken")
            pages += 1
            if not token or pages >= self.max_pages:
                break
            data = self._get("commentThreads", {**params, "pageToken": token})

        if self.enrich_authors:
            self._enrich_authors(comments)
        return comments

    def _to_comment(self, item: Dict, video_id: str) -> Optional[Comment]:
        top = (item.get("snippet") or {}).get("topLevelComment") or {}
        snip = top.get("snippet") or {}
        text = snip.get("textOriginal") or snip.get("textDisplay")
        if text is None:
            return None
        channel_id = (snip.get("authorChannelId") or {}).get("value")
        handle = snip.get("authorDisplayName")
        account = Account(
            id=str(channel_id or handle or top.get("id")),
            handle=handle,
            display_name=handle,
            has_avatar=bool(snip.get("authorProfileImageUrl")),
        )
        return Comment(
            id=str(top.get("id") or item.get("id")),
            account=account,
            text=str(text),
            created_at=_parse_time(snip.get("publishedAt")),
            likes=_to_int(snip.get("likeCount")),
            post_id=str(video_id),
        )

    def _enrich_authors(self, comments: List[Comment]) -> None:
        """Fill channel age / subscriber / video counts via batched channels.list."""
        by_channel: Dict[str, List[Account]] = {}
        for c in comments:
            cid = c.account.id
            if cid and cid.startswith("UC"):  # a real channel id, not a fallback
                by_channel.setdefault(cid, []).append(c.account)
        ids = list(by_channel)
        for start in range(0, len(ids), 50):  # channels.list accepts up to 50 ids
            chunk = ids[start : start + 50]
            data = self._get(
                "channels", {"part": "snippet,statistics", "id": ",".join(chunk)}
            )
            for item in data.get("items", []):
                stats = item.get("statistics") or {}
                snip = item.get("snippet") or {}
                created = _parse_time(snip.get("publishedAt"))
                subs = None if stats.get("hiddenSubscriberCount") else _to_int(stats.get("subscriberCount"))
                videos = _to_int(stats.get("videoCount"))
                for acct in by_channel.get(item.get("id"), []):
                    acct.created_at = created
                    acct.followers_count = subs
                    acct.post_count = videos

    # --- page / channel metadata (supported) ---

    def fetch_page(self, target: str) -> Page:
        """``target`` is a channel id. Returns the channel's own metadata."""
        data = self._get("channels", {"part": "snippet,statistics", "id": target})
        items = data.get("items") or []
        if not items:
            raise RuntimeError(f"YouTube channel {target!r} not found")
        item = items[0]
        stats = item.get("statistics") or {}
        snip = item.get("snippet") or {}
        subs = None if stats.get("hiddenSubscriberCount") else _to_int(stats.get("subscriberCount"))
        owner = Account(
            id=str(item.get("id") or target),
            handle=snip.get("title"),
            display_name=snip.get("title"),
            created_at=_parse_time(snip.get("publishedAt")),
            followers_count=subs,
            post_count=_to_int(stats.get("videoCount")),
        )
        return Page(id=str(item.get("id") or target), handle=snip.get("title"), owner=owner)

    # --- followers / subscribers (NOT available via the API) ---

    def fetch_followers(self, target: str):
        raise NotImplementedError(
            "YouTube's Data API does not expose a channel's subscriber identities "
            "(subscriptions.list only returns the authorized user's own subscriptions, "
            "with their consent). Analyze followers by importing data you legitimately "
            "have via ImportProvider.fetch_followers, then smbd.followers.analyze_followers."
        )
