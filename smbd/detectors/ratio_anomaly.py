"""Follow-ratio / engagement anomaly detector.

Flags accounts that follow far more profiles than follow them back — a cheap,
robust correlate of mass-follow bots and purchased accounts. Abstains when
follower/following counts are unavailable.
"""

from __future__ import annotations

from typing import Dict, List

from smbd.detectors.base import Detector
from smbd.features.account import follow_ratio
from smbd.schema import Comment, Label, Signal


class RatioAnomalyDetector(Detector):
    name = "ratio_anomaly"

    def analyze(self, comments: List[Comment]) -> Dict[str, List[Signal]]:
        out: Dict[str, List[Signal]] = {}
        for c in comments:
            ratio = follow_ratio(c.account)
            if ratio is None:
                continue  # abstain
            if ratio < self.config.extreme_follow_ratio:
                continue
            # Scale: at the threshold -> ~0.4; saturates well above it.
            score = min(1.0, 0.4 + 0.1 * (ratio / self.config.extreme_follow_ratio))
            out.setdefault(c.id, []).append(
                self.signal(
                    score=score,
                    evidence={
                        "reason": "abnormal_follow_ratio",
                        "following": c.account.following_count,
                        "followers": c.account.followers_count,
                        "ratio": round(ratio, 1),
                        "threshold": self.config.extreme_follow_ratio,
                    },
                    label_hint=Label.SUSPICIOUS,
                )
            )
        return out
