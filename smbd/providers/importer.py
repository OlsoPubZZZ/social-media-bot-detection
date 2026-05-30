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


def _is_meta_comments(data: Any) -> bool:
    if isinstance(data, dict):
        if "comments_v2" in data:  # Facebook
            return True
        return any(isinstance(data.get(k), list) for k in
                   ("comments_media_comments", "post_comments_1", "post_comments"))
    if isinstance(data, list) and data and isinstance(data[0], dict):  # Instagram (bare list)
        return "Comment" in (data[0].get("string_map_data") or {})
    return False


def _meta_comments(data: Any) -> List[Comment]:
    """Parse the comment section of a Facebook/Instagram export.

    These are the comments *you authored* (the export owner) — Meta does not
    include other people's comments on your posts — so every comment shares one
    author. Useful for reviewing your own activity, not for finding bots on your
    posts (use the official API adapter for that).
    """
    out: List[Comment] = []
    # Facebook: comments_v2 -> data[].comment.{comment, author}
    if isinstance(data, dict) and "comments_v2" in data:
        for i, entry in enumerate(data["comments_v2"]):
            text = author = None
            for d in (entry.get("data") or []):
                c = d.get("comment") or {}
                text = c.get("comment") or text
                author = c.get("author") or author
            if not text:
                continue
            account = Account(id=str(author or "you"), display_name=author or "you")
            out.append(Comment(id=f"c_{i}", account=account, text=text,
                               created_at=_parse_dt(entry.get("timestamp"))))
        return out

    # Instagram: string_map_data -> {"Comment": {value, timestamp}, "Media Owner": {value}}
    entries: Any = data
    if isinstance(data, dict):
        for key in ("comments_media_comments", "post_comments_1", "post_comments"):
            if isinstance(data.get(key), list):
                entries = data[key]
                break
    for i, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        smd = entry.get("string_map_data") or {}
        comment = smd.get("Comment") or {}
        text = comment.get("value")
        if not text:
            continue
        owner = (smd.get("Media Owner") or {}).get("value")
        out.append(Comment(id=f"c_{i}", account=Account(id="you", display_name="you"),
                           text=text, created_at=_parse_dt(comment.get("timestamp")),
                           post_id=owner or None))
    return out


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
        if _is_meta_comments(data):
            return _meta_comments(data)  # Facebook/Instagram export (your own comments)
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
