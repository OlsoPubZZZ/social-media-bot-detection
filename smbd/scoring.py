"""Scoring & aggregation.

Runs every detector over a batch of comments, combines their signals into a
per-comment suspicion score + label + confidence, and rolls those up into the
percentage breakdown the product reports.

The combine step uses a weighted "noisy-OR": each signal contributes
independently, so multiple weak signals accumulate but no single detector can
dominate beyond its weight. This is intentionally simple and inspectable —
calibration weights live in :class:`~smbd.config.Config`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type

from smbd.config import Config, DEFAULT_CONFIG
from smbd.detectors import DEFAULT_DETECTORS
from smbd.detectors.base import Detector
from smbd.schema import Comment, Label, Signal


@dataclass
class CommentResult:
    comment: Comment
    score: float  # aggregate suspicion in [0, 1]
    label: Label
    confidence: float  # [0, 1] — how much evidence backed the decision
    signals: List[Signal] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "comment_id": self.comment.id,
            "account_id": self.comment.account.id,
            "handle": self.comment.account.handle,
            "text": self.comment.text,
            "score": round(self.score, 3),
            "label": self.label.value,
            "confidence": round(self.confidence, 3),
            "signals": [s.to_dict() for s in self.signals],
        }


@dataclass
class BatchResult:
    results: List[CommentResult]
    config: Config
    # How many deterministic detectors ran — used as the confidence baseline
    # when the optional LLM layer re-scores enriched comments.
    n_detectors: int = len(DEFAULT_DETECTORS)

    def breakdown(self) -> Dict[str, float]:
        """Percentage of comments per label (the 'are these comments real?' output)."""
        n = len(self.results) or 1
        counts = Counter(r.label.value for r in self.results)
        order = [
            Label.GENUINE,
            Label.SUSPICIOUS,
            Label.SPAM,
            Label.COORDINATED,
            Label.LOW_CONFIDENCE,
        ]
        return {lbl.value: round(100.0 * counts.get(lbl.value, 0) / n, 1) for lbl in order}

    def to_dict(self) -> dict:
        return {
            "total": len(self.results),
            "breakdown_pct": self.breakdown(),
            "results": [r.to_dict() for r in self.results],
        }


# How many of the detectors had the data they needed (per comment) determines
# confidence. We approximate "coverage" by which detectors produced *any* signal
# OR could have (timestamps present, counts present, ...). To keep it simple and
# honest, confidence rises with the number of distinct detector families that
# weighed in and with score extremity.
def _confidence(signals: List[Signal], score: float, n_detectors: int) -> float:
    distinct = len({s.name for s in signals})
    coverage = distinct / max(n_detectors, 1)
    # Extreme scores (very low or very high) are more confident than borderline.
    extremity = abs(score - 0.5) * 2
    return round(min(1.0, 0.4 * coverage + 0.6 * extremity), 3)


def _aggregate_score(signals: List[Signal]) -> float:
    """Weighted noisy-OR over signal scores."""
    if not signals:
        return 0.0
    prod = 1.0
    for s in signals:
        contribution = min(1.0, s.score * s.weight)
        prod *= 1.0 - contribution
    return 1.0 - prod


def _pick_label(score: float, signals: List[Signal], confidence: float, cfg: Config) -> Label:
    if confidence < cfg.min_confidence_coverage:
        return Label.LOW_CONFIDENCE
    if score < cfg.genuine_below:
        return Label.GENUINE
    # Above the suspicious bar: let the strongest signal's hint refine the label.
    if score >= cfg.suspicious_at and signals:
        top = max(signals, key=lambda s: s.score * s.weight)
        if top.label_hint in (Label.SPAM, Label.COORDINATED):
            return top.label_hint
    return Label.SUSPICIOUS


def rescore(result: CommentResult, config: Config, n_detectors: int) -> CommentResult:
    """Recompute a comment's score/confidence/label from its current signals.

    Used after the optional LLM layer appends an ``llm_text_judgment`` signal,
    so the aggregate reflects the new evidence. Mutates and returns ``result``.
    """
    result.score = _aggregate_score(result.signals)
    result.confidence = _confidence(result.signals, result.score, n_detectors)
    result.label = _pick_label(result.score, result.signals, result.confidence, config)
    return result


def analyze_comments(
    comments: List[Comment],
    config: Optional[Config] = None,
    detector_classes: Optional[List[Type[Detector]]] = None,
) -> BatchResult:
    """Run the full detector pipeline and score every comment."""
    cfg = config or DEFAULT_CONFIG
    classes = detector_classes or DEFAULT_DETECTORS
    detectors = [cls(cfg) for cls in classes]

    # Collect signals from every detector.
    per_comment: Dict[str, List[Signal]] = {c.id: [] for c in comments}
    for det in detectors:
        produced = det.analyze(comments)
        for cid, sigs in produced.items():
            per_comment.setdefault(cid, []).extend(sigs)

    results: List[CommentResult] = []
    for c in comments:
        sigs = per_comment.get(c.id, [])
        score = _aggregate_score(sigs)
        conf = _confidence(sigs, score, len(detectors))
        label = _pick_label(score, sigs, conf, cfg)
        results.append(
            CommentResult(comment=c, score=score, label=label, confidence=conf, signals=sigs)
        )

    return BatchResult(results=results, config=cfg, n_detectors=len(detectors))
