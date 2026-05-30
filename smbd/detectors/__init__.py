"""Detectors turn features into :class:`~smbd.schema.Signal` objects.

Each detector inspects the *whole* batch of comments (so corpus-level patterns
like duplicate text, bursts, and coordination are visible) and returns a map of
``comment_id -> [Signal, ...]``. Detectors that lack the data they need simply
return nothing for that item (they abstain) rather than guessing.
"""

from smbd.detectors.base import Detector
from smbd.detectors.duplicate_text import DuplicateTextDetector
from smbd.detectors.timing_burst import TimingBurstDetector
from smbd.detectors.coordination import CoordinationDetector
from smbd.detectors.account_weakness import AccountWeaknessDetector
from smbd.detectors.ratio_anomaly import RatioAnomalyDetector

DEFAULT_DETECTORS = [
    DuplicateTextDetector,
    TimingBurstDetector,
    CoordinationDetector,
    AccountWeaknessDetector,
    RatioAnomalyDetector,
]

__all__ = [
    "Detector",
    "DuplicateTextDetector",
    "TimingBurstDetector",
    "CoordinationDetector",
    "AccountWeaknessDetector",
    "RatioAnomalyDetector",
    "DEFAULT_DETECTORS",
]
