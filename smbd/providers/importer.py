"""Import provider — CSV / JSON / in-memory rows -> normalized comments.

This is the zero-credential, platform-agnostic entry point: feed it any data
you legitimately have (a platform export, a CSV you assembled, pasted rows) and
the full detection engine runs.

Recognized columns / keys (all optional except ``text``):

    comment_id, text, created_at, likes, parent_id, post_id, lang,
    account_id, handle, display_name, account_created_at,
    followers_count, following_count, post_count, bio, has_avatar,
    is_verified, external_url

``created_at`` / ``account_created_at`` accept ISO-8601 (``2026-05-01T12:00:00``)
or epoch seconds. Booleans accept true/false/1/0/yes/no.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from smbd.providers.base import Provider
from smbd.schema import Account, Comment, Follower


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    # Epoch seconds?
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError):
        pass
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_bool(value: Any) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "t"}


def _row_to_account(row: Dict[str, Any], index: int) -> Account:
    return Account(
        id=str(row.get("account_id") or row.get("handle") or f"acct_{index}"),
        handle=row.get("handle") or None,
        display_name=row.get("display_name") or None,
        created_at=_parse_dt(row.get("account_created_at")),
        followers_count=_parse_int(row.get("followers_count")),
        following_count=_parse_int(row.get("following_count")),
        post_count=_parse_int(row.get("post_count")),
        bio=row.get("bio") if row.get("bio") is not None else None,
        has_avatar=_parse_bool(row.get("has_avatar")),
        is_verified=_parse_bool(row.get("is_verified")),
        external_url=row.get("external_url") or None,
    )


def _row_to_comment(row: Dict[str, Any], index: int) -> Optional[Comment]:
    text = row.get("text")
    if text is None or str(text).strip() == "":
        return None
    return Comment(
        id=str(row.get("comment_id") or f"c_{index}"),
        account=_row_to_account(row, index),
        text=str(text),
        created_at=_parse_dt(row.get("created_at")),
        likes=_parse_int(row.get("likes")),
        parent_id=row.get("parent_id") or None,
        post_id=row.get("post_id") or None,
        lang=row.get("lang") or None,
    )


def _row_to_follower(row: Dict[str, Any], index: int) -> Follower:
    return Follower(
        account=_row_to_account(row, index),
        followed_at=_parse_dt(row.get("followed_at")),
    )


# --- Meta ("Download Your Information") export support --------------------------
# Instagram exports followers/following as objects with a string_list_data entry
# ({value: username, timestamp}); Facebook exports friends/followers as
# {name, timestamp}. These are *your own* data, handed to you by the platform.

_META_KEYS = (
    "relationships_followers",
    "relationships_following",
    "friends_v2",
    "followers_v2",
    "following_v2",
)


def _is_meta_export(data: Any) -> bool:
    if isinstance(data, dict):
        return any(k in data for k in _META_KEYS)
    if isinstance(data, list) and data:
        return isinstance(data[0], dict) and "string_list_data" in data[0]
    return False


def _meta_followers(data: Any) -> List[Follower]:
    entries: Any = None
    kind = "ig"
    if isinstance(data, dict):
        for key in ("relationships_followers", "relationships_following"):
            if key in data:
                entries, kind = data[key], "ig"
                break
        if entries is None:
            for key in ("friends_v2", "followers_v2", "following_v2"):
                if key in data:
                    entries, kind = data[key], "fb"
                    break
    elif isinstance(data, list):
        entries, kind = data, "ig"  # IG sometimes exports a bare list

    followers: List[Follower] = []
    for i, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        if kind == "ig":
            sld = (entry.get("string_list_data") or [{}])[0]
            username = sld.get("value")
            ts = sld.get("timestamp")
            account = Account(id=str(username or f"f_{i}"), handle=username or None)
        else:  # facebook
            name = entry.get("name")
            ts = entry.get("timestamp")
            account = Account(id=str(name or f"f_{i}"), display_name=name or None)
        followers.append(Follower(account=account, followed_at=_parse_dt(ts)))
    return followers


class ImportProvider(Provider):
    """Load normalized comments from files or in-memory rows."""

    name = "import"

    def fetch_comments(self, target: str) -> List[Comment]:
        """``target`` is a path to a ``.csv`` or ``.json`` file."""
        if target.lower().endswith(".json"):
            with open(target, "r", encoding="utf-8") as fh:
                return self.from_json(fh.read())
        with open(target, "r", encoding="utf-8", newline="") as fh:
            return self.from_csv(fh.read())

    def from_csv(self, content: str) -> List[Comment]:
        reader = csv.DictReader(io.StringIO(content))
        return self.from_rows(reader)

    def from_json(self, content: str) -> List[Comment]:
        data = json.loads(content)
        if isinstance(data, dict):
            data = data.get("comments", [])
        return self.from_rows(data)

    def from_rows(self, rows: Iterable[Dict[str, Any]]) -> List[Comment]:
        comments: List[Comment] = []
        for i, row in enumerate(rows):
            comment = _row_to_comment(row, i)
            if comment is not None:
                comments.append(comment)
        return comments

    # --- followers ---

    def fetch_followers(self, target: str) -> List[Follower]:
        """``target`` is a path to a ``.csv`` or ``.json`` file of follower rows.

        Recognized columns/keys (all optional): the same account fields as
        comments (``account_id``, ``handle``, ``account_created_at``,
        ``followers_count``, ``following_count``, ``post_count``, ``bio``,
        ``has_avatar``, ``is_verified``, ``external_url``) plus ``followed_at``.
        """
        if target.lower().endswith(".json"):
            with open(target, "r", encoding="utf-8") as fh:
                return self.followers_from_json(fh.read())
        with open(target, "r", encoding="utf-8", newline="") as fh:
            return self.followers_from_csv(fh.read())

    def followers_from_csv(self, content: str) -> List[Follower]:
        return self.followers_from_rows(csv.DictReader(io.StringIO(content)))

    def followers_from_json(self, content: str) -> List[Follower]:
        data = json.loads(content)
        if _is_meta_export(data):
            return _meta_followers(data)  # Facebook/Instagram export file
        if isinstance(data, dict):
            data = data.get("followers", [])
        return self.followers_from_rows(data)

    def followers_from_rows(self, rows: Iterable[Dict[str, Any]]) -> List[Follower]:
        return [_row_to_follower(row, i) for i, row in enumerate(rows)]
