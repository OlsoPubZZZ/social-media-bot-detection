"""Follow-ratio / engagement anomaly detector.

Flags accounts that follow far more profiles than follow them back — a cheap,
robust correlate of mass-follow bots and purchased accounts. Abstains when
follower/following counts are unavailable.
"""

from __future__ import annotations

from typing import Dict, List

from smbd.detectors.base import Detector
from smbd.features.account import ratio_suspicion
from smbd.schema import Comment, Label, Signal


class RatioAnomalyDetector(Detector):
    name = "ratio_anomaly"

    def analyze(self, comments: List[Comment]) -> Dict[str, List[Signal]]:
        out: Dict[str, List[Signal]] = {}
        for c in comments:
            result = ratio_suspicion(c.account, self.config)
            if result is None:
                continue  # abstain
            score, evidence = result
            out.setdefault(c.id, []).append(
                self.signal(score=score, evidence=evidence, label_hint=Label.SUSPICIOUS)
            )
        return out
