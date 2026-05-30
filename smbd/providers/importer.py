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
from smbd.schema import Account, Comment


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


def _row_to_comment(row: Dict[str, Any], index: int) -> Optional[Comment]:
    text = row.get("text")
    if text is None or str(text).strip() == "":
        return None

    account = Account(
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
    return Comment(
        id=str(row.get("comment_id") or f"c_{index}"),
        account=account,
        text=str(text),
        created_at=_parse_dt(row.get("created_at")),
        likes=_parse_int(row.get("likes")),
        parent_id=row.get("parent_id") or None,
        post_id=row.get("post_id") or None,
        lang=row.get("lang") or None,
    )


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
