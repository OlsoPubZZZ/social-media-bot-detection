"""Account features — age, follow ratio, profile completeness, handle shape."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from smbd.schema import Account

if TYPE_CHECKING:  # avoid a runtime import cycle (config has no feature deps)
    from smbd.config import Config

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


# --- shared suspicion scoring (used by both the comment detector and the -------
#     follower analyzer, so the heuristics stay in exactly one place) -----------

def profile_suspicion(
    account: Account, reference: Optional[datetime], config: "Config"
) -> Tuple[float, List[str]]:
    """Suspicion contribution from an account's profile: new account, generated
    handle, missing avatar / empty bio / no posts. Returns ``(score, reasons)``;
    ``score`` is 0 with no reasons (the caller then abstains). Abstains per-attribute
    on missing data — e.g. no ``created_at`` means the age check doesn't fire."""
    reasons: List[str] = []
    score = 0.0

    age = account_age_days(account, reference)
    if age is not None and age <= config.new_account_days:
        reasons.append(f"new_account({int(age)}d)")
        score += 0.35

    if handle_looks_generated(account.handle, config.handle_digit_ratio):
        reasons.append("auto_generated_handle")
        score += 0.3

    weak = profile_weaknesses(account)
    if weak:
        reasons.extend(weak)
        score += 0.15 * len(weak)

    return score, reasons


def ratio_suspicion(account: Account, config: "Config") -> Optional[Tuple[float, Dict]]:
    """Suspicion from an abnormal follow ratio. Returns ``(score, evidence)`` or
    ``None`` when counts are missing or the ratio is within normal range."""
    ratio = follow_ratio(account)
    if ratio is None or ratio < config.extreme_follow_ratio:
        return None
    score = min(1.0, 0.4 + 0.1 * (ratio / config.extreme_follow_ratio))
    evidence = {
        "reason": "abnormal_follow_ratio",
        "following": account.following_count,
        "followers": account.followers_count,
        "ratio": round(ratio, 1),
        "threshold": config.extreme_follow_ratio,
    }
    return score, evidence
