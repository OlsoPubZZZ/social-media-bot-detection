"""Account weakness detector.

Per-comment signal based on the *author's* profile: brand-new account, missing
avatar, empty bio, no posts, or an auto-generated-looking handle. Each
contributing attribute is recorded as evidence. Abstains on attributes whose
data is missing.
"""

from __future__ import annotations

from typing import Dict, List

from smbd.detectors.base import Detector
from smbd.features.account import (
    account_age_days,
    handle_looks_generated,
    profile_weaknesses,
)
from smbd.schema import Comment, Label, Signal


class AccountWeaknessDetector(Detector):
    name = "account_weakness"

    def analyze(self, comments: List[Comment]) -> Dict[str, List[Signal]]:
        out: Dict[str, List[Signal]] = {}
        reference = self.reference_time(comments)

        for c in comments:
            acct = c.account
            reasons: List[str] = []
            score = 0.0

            age = account_age_days(acct, reference)
            if age is not None and age <= self.config.new_account_days:
                reasons.append(f"new_account({int(age)}d)")
                score += 0.35

            if handle_looks_generated(acct.handle, self.config.handle_digit_ratio):
                reasons.append("auto_generated_handle")
                score += 0.3

            weak = profile_weaknesses(acct)
            if weak:
                reasons.extend(weak)
                score += 0.15 * len(weak)

            if not reasons:
                continue  # abstain: nothing weak (or nothing known)

            out.setdefault(c.id, []).append(
                self.signal(
                    score=score,
                    evidence={
                        "reason": "weak_or_new_profile",
                        "attributes": reasons,
                        "handle": acct.handle,
                    },
                    label_hint=Label.SUSPICIOUS,
                )
            )
        return out
