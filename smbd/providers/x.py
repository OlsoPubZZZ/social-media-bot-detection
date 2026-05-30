"""X (Twitter) provider — official API v2.

X's API is **paid** (no meaningful free read tier) and rate-limited, but it is
the one platform whose API exposes a usable **follower list with profiles** —
``GET /2/users/:id/followers`` returns each follower's creation date, follower /
following / tweet counts, avatar, and bio. So X is the only adapter that can feed
``smbd.followers`` an *official* data source.

Caveats:
* The followers endpoint gives no "followed at" timestamp, so the join-burst
  detector abstains on X follower data (profile/ratio signals still fire).
* ``fetch_comments`` reads replies via recent search (``conversation_id:<id>``),
  which on standard access only covers roughly the last 7 days.

Auth is an OAuth2 **bearer token** (``X_BEARER_TOKEN``). Tests inject a
``transport`` callable so parsing runs fully offline.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Callable, Dict, List, Optional

from smbd.providers.base import Provider
from smbd.schema import Account, Comment, Follower, Page

_API = "https://api.twitter.com/2"
_USER_FIELDS = "created_at,public_metrics,profile_image_url,description,verified"


def _parse_time(value: object) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _has_avatar(url: Optional[str]) -> Optional[bool]:
    """X serves a known placeholder for accounts with no profile photo."""
    if not url:
        return None
    return "default_profile" not in url


def _account_from_user(user: Dict) -> Account:
    pm = user.get("public_metrics") or {}
    return Account(
        id=str(user.get("id")),
        handle=user.get("username"),
        display_name=user.get("name"),
        created_at=_parse_time(user.get("created_at")),
        followers_count=pm.get("followers_count"),
        following_count=pm.get("following_count"),
        post_count=pm.get("tweet_count"),
        bio=user.get("description"),
        has_avatar=_has_avatar(user.get("profile_image_url")),
        is_verified=user.get("verified"),
    )


class XProvider(Provider):
    name = "x"

    def __init__(
        self,
        bearer_token: Optional[str] = None,
        *,
        transport: Optional[Callable[[str], Dict]] = None,
        max_pages: int = 20,
    ):
        self.bearer_token = (
            bearer_token or os.getenv("X_BEARER_TOKEN") or os.getenv("TWITTER_BEARER_TOKEN")
        )
        self.max_pages = max_pages
        self._uses_http = transport is None
        self._transport = transport or self._http_get

    # --- transport ---

    def _http_get(self, url: str) -> Dict:  # pragma: no cover - exercised only live
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.bearer_token}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, path: str, params: Dict) -> Dict:
        if self._uses_http and not self.bearer_token:
            raise RuntimeError(
                "XProvider needs a bearer token for live calls "
                "(pass bearer_token= or set X_BEARER_TOKEN)."
            )
        url = f"{_API}/{path}?{urllib.parse.urlencode(params)}"
        data = self._transport(url)
        self._check_error(data)
        return data

    @staticmethod
    def _check_error(data: Dict) -> None:
        if not isinstance(data, dict):
            return
        # A request-level failure (no payload), e.g. 401/429. Partial "errors"
        # alongside "data" are per-object and non-fatal, so don't raise on those.
        status = data.get("status")
        if status and int(status) >= 400:
            raise RuntimeError(f"X API error: {data.get('detail') or data.get('title')}")
        if "errors" in data and "data" not in data and "includes" not in data:
            first = (data.get("errors") or [{}])[0]
            raise RuntimeError(
                f"X API error: {first.get('detail') or first.get('message') or data.get('title')}"
            )

    # --- comments (replies in a conversation) ---

    def fetch_comments(self, target: str) -> List[Comment]:
        """``target`` is a tweet id; returns replies in its conversation."""
        params = {
            "query": f"conversation_id:{target}",
            "max_results": 100,
            "tweet.fields": "created_at,public_metrics,lang,conversation_id,author_id",
            "expansions": "author_id",
            "user.fields": _USER_FIELDS,
        }
        comments: List[Comment] = []
        pages = 0
        while True:
            data = self._get("tweets/search/recent", params)
            users = {u["id"]: u for u in (data.get("includes") or {}).get("users", [])}
            for tweet in data.get("data", []):
                author = users.get(tweet.get("author_id"))
                account = _account_from_user(author) if author else Account(
                    id=str(tweet.get("author_id") or "unknown")
                )
                comments.append(
                    Comment(
                        id=str(tweet["id"]),
                        account=account,
                        text=tweet.get("text", ""),
                        created_at=_parse_time(tweet.get("created_at")),
                        lang=tweet.get("lang"),
                        post_id=str(tweet.get("conversation_id") or target),
                    )
                )
            token = (data.get("meta") or {}).get("next_token")
            pages += 1
            if not token or pages >= self.max_pages:
                break
            params["next_token"] = token
        return comments

    # --- followers (officially available on X) ---

    def fetch_followers(self, target: str) -> List[Follower]:
        """``target`` is a user id; returns followers with profile data.

        Note: the endpoint provides no follow timestamp, so ``followed_at`` is
        ``None`` and join-burst detection abstains.
        """
        params = {"max_results": 1000, "user.fields": _USER_FIELDS}
        followers: List[Follower] = []
        pages = 0
        while True:
            data = self._get(f"users/{target}/followers", params)
            for user in data.get("data", []):
                followers.append(Follower(account=_account_from_user(user), followed_at=None))
            token = (data.get("meta") or {}).get("next_token")
            pages += 1
            if not token or pages >= self.max_pages:
                break
            params["pagination_token"] = token
        return followers

    # --- page / user metadata ---

    def fetch_page(self, target: str) -> Page:
        """``target`` is a user id (numeric) or @username."""
        path = f"users/{target}" if str(target).isdigit() else f"users/by/username/{target}"
        data = self._get(path, {"user.fields": _USER_FIELDS})
        user = data.get("data")
        if not user:
            raise RuntimeError(f"X user {target!r} not found")
        owner = _account_from_user(user)
        return Page(id=owner.id, handle=owner.handle, owner=owner)
