"""Account features — age, follow ratio, profile completeness, handle shape."""

from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from smbd.schema import Account

_DIGIT_RUN_SUFFIX = re.compile(r"\d{4,}$")


def account_age_days(account: Account, reference: Optional[datetime]) -> Optional[float]:
    """Age in days relative to ``reference`` (e.g. dataset max timestamp).

    Returns ``None`` when the data needed to decide is missing — callers should
    then *abstain* rather than treat the account as old or new.
    """
    if account.created_at is None or reference is None:
        return None
    return (reference - account.created_at).total_seconds() / 86400.0


def follow_ratio(account: Account) -> Optional[float]:
    """following / max(followers, 1). High = follows many, followed by few."""
    if account.following_count is None or account.followers_count is None:
        return None
    return account.following_count / max(account.followers_count, 1)


def handle_digit_ratio(handle: Optional[str]) -> Optional[float]:
    if not handle:
        return None
    digits = sum(c.isdigit() for c in handle)
    return digits / len(handle)


def handle_looks_generated(handle: Optional[str], digit_ratio_threshold: float) -> bool:
    """Heuristic: long digit suffix or a high overall digit ratio in the handle."""
    if not handle:
        return False
    if _DIGIT_RUN_SUFFIX.search(handle):
        return True
    ratio = handle_digit_ratio(handle)
    return ratio is not None and ratio >= digit_ratio_threshold


def profile_weaknesses(account: Account) -> List[str]:
    """List of present-and-weak profile attributes (each is shown as evidence)."""
    weak: List[str] = []
    if account.has_avatar is False:
        weak.append("no_avatar")
    if account.bio is not None and account.bio.strip() == "":
        weak.append("empty_bio")
    if account.post_count is not None and account.post_count == 0:
        weak.append("no_posts")
    return weak
