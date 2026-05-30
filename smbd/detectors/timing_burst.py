"""Timing burst detector.

Flags comments that arrive in abnormally dense time windows — synchronized
posting that exceeds the organic rate, typical of automated amplification.
Abstains entirely when timestamps are missing.
"""

from __future__ import annotations

from typing import Dict, List

from smbd.detectors.base import Detector
from smbd.features.temporal import detect_bursts
from smbd.schema import Comment, Label, Signal


class TimingBurstDetector(Detector):
    name = "timing_burst"

    def analyze(self, comments: List[Comment]) -> Dict[str, List[Signal]]:
        out: Dict[str, List[Signal]] = {}
        timestamps = {c.id: c.created_at for c in comments}
        if sum(1 for t in timestamps.values() if t is not None) < self.config.burst_min_events:
            return out  # abstain: not enough timestamped data

        bursts = detect_bursts(
            timestamps,
            window_seconds=self.config.burst_window_seconds,
            rate_multiplier=self.config.burst_rate_multiplier,
            min_events=self.config.burst_min_events,
        )

        for burst in bursts:
            ids = burst["ids"]
            span = (burst["end"] - burst["start"]).total_seconds()
            score = min(1.0, 0.4 + 0.05 * len(ids))
            for cid in ids:
                out.setdefault(cid, []).append(
                    self.signal(
                        score=score,
                        evidence={
                            "reason": "synchronized_timing_burst",
                            "window_start": burst["start"].isoformat(),
                            "window_end": burst["end"].isoformat(),
                            "window_seconds": round(span, 1),
                            "events_in_window": len(ids),
                        },
                        label_hint=Label.COORDINATED,
                    )
                )
        return out
