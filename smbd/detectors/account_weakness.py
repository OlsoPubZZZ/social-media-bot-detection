"""Account weakness detector.

Per-comment signal based on the *author's* profile: brand-new account, missing
avatar, empty bio, no posts, or an auto-generated-looking handle. Each
contributing attribute is recorded as evidence. Abstains on attributes whose
data is missing.
"""

from __future__ import annotations

from typing import Dict, List

from smbd.detectors.base import Detector
from smbd.features.account import profile_suspicion
from smbd.schema import Comment, Label, Signal


class AccountWeaknessDetector(Detector):
    name = "account_weakness"

    def analyze(self, comments: List[Comment]) -> Dict[str, List[Signal]]:
        out: Dict[str, List[Signal]] = {}
        reference = self.reference_time(comments)

        for c in comments:
            score, reasons = profile_suspicion(c.account, reference, self.config)
            if not reasons:
                continue  # abstain: nothing weak (or nothing known)

            out.setdefault(c.id, []).append(
                self.signal(
                    score=score,
                    evidence={
                        "reason": "weak_or_new_profile",
                        "attributes": reasons,
                        "handle": c.account.handle,
                    },
                    label_hint=Label.SUSPICIOUS,
                )
            )
        return out
