"""Temporal features — inter-arrival times and burst detection."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple


def sorted_events(timestamps: Dict[str, Optional[datetime]]) -> List[Tuple[str, datetime]]:
    """Return (id, timestamp) pairs that have a timestamp, sorted ascending."""
    have = [(cid, ts) for cid, ts in timestamps.items() if ts is not None]
    have.sort(key=lambda x: x[1])
    return have


def detect_bursts(
    timestamps: Dict[str, Optional[datetime]],
    window_seconds: int = 60,
    rate_multiplier: float = 4.0,
    min_events: int = 5,
) -> List[Dict]:
    """Find time windows whose local rate far exceeds the overall rate.

    Returns a list of bursts; each is ``{"start", "end", "ids": [...]}``.
    A sliding window of ``window_seconds`` flags a burst when it contains both
    ``>= min_events`` items and ``>= rate_multiplier`` times the events expected
    from the average rate over the whole span.
    """
    events = sorted_events(timestamps)
    if len(events) < min_events:
        return []

    span = (events[-1][1] - events[0][1]).total_seconds()
    if span <= 0:
        # Everything at the same instant: that is itself a burst.
        return [{"start": events[0][1], "end": events[-1][1], "ids": [e[0] for e in events]}]

    avg_rate = len(events) / span  # events per second
    expected_in_window = avg_rate * window_seconds
    threshold = max(min_events, rate_multiplier * expected_in_window)

    # Collect every qualifying sliding window, then merge overlapping ones so a
    # single dense cluster becomes one maximal burst (not one per trailing event).
    n = len(events)
    left = 0
    candidates: List[List[int]] = []  # [left_idx, right_idx]
    for right in range(n):
        while (events[right][1] - events[left][1]).total_seconds() > window_seconds:
            left += 1
        if right - left + 1 >= threshold:
            if candidates and left <= candidates[-1][1]:
                candidates[-1][1] = right  # overlaps previous window: extend it
            else:
                candidates.append([left, right])

    bursts: List[Dict] = []
    for lo, hi in candidates:
        ids = [events[k][0] for k in range(lo, hi + 1)]
        bursts.append({"start": events[lo][1], "end": events[hi][1], "ids": ids})
    return bursts
