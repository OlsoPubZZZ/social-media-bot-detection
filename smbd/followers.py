"""Follower analysis — "Are these followers real people?"

Runs follower-appropriate detectors over a list of :class:`~smbd.schema.Follower`
objects and produces a follower quality score, a likely-fake estimate, and
suspicious join-time clusters. It deliberately reuses the comment engine's
machinery — the shared profile/ratio scoring (``features.account``), the burst
detector (``features.temporal``), and the scoring math (``scoring``) — so the
heuristics live in exactly one place.

**Data-access reality:** this needs *per-follower profile data* (account age,
follower counts, avatar, bio, join time). Instagram's official Graph API does
**not** expose that, so in practice this engine runs on follower data obtained
via import (CSV/JSON you legitimately have) or the optional scraper plugin —
not the official Instagram adapter.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from smbd.config import Config, DEFAULT_CONFIG
from smbd.features.account import profile_suspicion, ratio_suspicion
from smbd.features.temporal import detect_bursts
from smbd.schema import Follower, Label, Signal
from smbd.scoring import _aggregate_score, _confidence, _pick_label

#: Detector families that can fire on a follower (used as the confidence baseline).
FOLLOWER_SIGNALS = ("account_weakness", "ratio_anomaly", "follow_burst")

_FAKE_LIKELY = (Label.SUSPICIOUS, Label.SPAM, Label.COORDINATED)


@dataclass
class FollowerResult:
    follower: Follower
    score: float
    label: Label
    confidence: float
    signals: List[Signal] = field(default_factory=list)

    def to_dict(self) -> dict:
        acct = self.follower.account
        return {
            "account_id": acct.id,
            "handle": acct.handle,
            "label": self.label.value,
            "score": round(self.score, 3),
            "confidence": round(self.confidence, 3),
            # Surface the profile facts the user asked about, per follower.
            "account_created_at": acct.created_at.isoformat() if acct.created_at else None,
            "followers_count": acct.followers_count,
            "following_count": acct.following_count,
            "has_avatar": acct.has_avatar,
            "followed_at": self.follower.followed_at.isoformat() if self.follower.followed_at else None,
            "signals": [s.to_dict() for s in self.signals],
        }


@dataclass
class FollowerBatchResult:
    results: List[FollowerResult]
    config: Config
    n_detectors: int = len(FOLLOWER_SIGNALS)

    def breakdown(self) -> Dict[str, float]:
        n = len(self.results) or 1
        counts = Counter(r.label.value for r in self.results)
        order = [Label.GENUINE, Label.SUSPICIOUS, Label.SPAM, Label.COORDINATED, Label.LOW_CONFIDENCE]
        return {lbl.value: round(100.0 * counts.get(lbl.value, 0) / n, 1) for lbl in order}

    def quality_score(self) -> Optional[float]:
        """0-100: 100 = every follower looks like a real, healthy account."""
        if not self.results:
            return None
        avg = sum(r.score for r in self.results) / len(self.results)
        return round(100.0 * (1.0 - avg), 1)

    def confidence_band(self) -> str:
        if not self.results:
            return "no_data"
        avg = sum(r.confidence for r in self.results) / len(self.results)
        return "high" if avg >= 0.66 else "medium" if avg >= 0.4 else "low"

    def likely_fake(self) -> Dict[str, float]:
        n = len(self.results) or 1
        count = sum(1 for r in self.results if r.label in _FAKE_LIKELY)
        return {"count": count, "pct": round(100.0 * count / n, 1)}

    def suspicious_clusters(self) -> List[Dict]:
        """Groups of followers that joined together in a coordinated burst."""
        seen: Dict[str, Dict] = {}
        for r in self.results:
            for s in r.signals:
                if s.name != "follow_burst":
                    continue
                key = str(s.evidence.get("window_start"))
                if key not in seen:
                    seen[key] = {
                        "window_start": s.evidence.get("window_start"),
                        "window_end": s.evidence.get("window_end"),
                        "size": s.evidence.get("cluster_size"),
                        "account_ids": s.evidence.get("member_account_ids", []),
                    }
        return sorted(seen.values(), key=lambda c: -(c.get("size") or 0))

    def to_dict(self) -> dict:
        return {
            "total": len(self.results),
            "follower_quality_score": self.quality_score(),
            "confidence_band": self.confidence_band(),
            "likely_fake": self.likely_fake(),
            "breakdown_pct": self.breakdown(),
            "results": [r.to_dict() for r in self.results],
        }


def _reference_time(followers: List[Follower]) -> Optional[datetime]:
    """'Now' for account-age math: latest known join or account-creation time."""
    times: List[datetime] = []
    for f in followers:
        if f.followed_at is not None:
            times.append(f.followed_at)
        if f.account.created_at is not None:
            times.append(f.account.created_at)
    return max(times) if times else None


def analyze_followers(
    followers: List[Follower], config: Optional[Config] = None
) -> FollowerBatchResult:
    """Score every follower and roll up into quality / fake-likely / clusters."""
    cfg = config or DEFAULT_CONFIG
    reference = _reference_time(followers)
    per: Dict[str, List[Signal]] = {f.account.id: [] for f in followers}

    # Per-account profile + ratio signals (reuse shared scoring helpers).
    for f in followers:
        score, reasons = profile_suspicion(f.account, reference, cfg)
        if reasons:
            per[f.account.id].append(
                Signal(
                    name="account_weakness",
                    score=min(1.0, score),
                    weight=cfg.weights.get("account_weakness", 1.0),
                    evidence={
                        "reason": "weak_or_new_profile",
                        "attributes": reasons,
                        "handle": f.account.handle,
                    },
                    label_hint=Label.SUSPICIOUS,
                )
            )
        ratio = ratio_suspicion(f.account, cfg)
        if ratio is not None:
            rscore, evidence = ratio
            per[f.account.id].append(
                Signal(
                    name="ratio_anomaly",
                    score=rscore,
                    weight=cfg.weights.get("ratio_anomaly", 1.0),
                    evidence=evidence,
                    label_hint=Label.SUSPICIOUS,
                )
            )

    # Coordinated mass-follow bursts over join time.
    timestamps = {f.account.id: f.followed_at for f in followers}
    if sum(1 for t in timestamps.values() if t is not None) >= cfg.follow_burst_min_events:
        for burst in detect_bursts(
            timestamps,
            window_seconds=cfg.follow_burst_window_seconds,
            rate_multiplier=cfg.burst_rate_multiplier,
            min_events=cfg.follow_burst_min_events,
        ):
            members = sorted(set(burst["ids"]))
            if len(members) < cfg.coordination_min_group:
                continue
            score = min(1.0, 0.5 + 0.04 * len(members))
            evidence = {
                "reason": "coordinated_follow_burst",
                "window_start": burst["start"].isoformat(),
                "window_end": burst["end"].isoformat(),
                "cluster_size": len(members),
                "member_account_ids": members[:25],
            }
            for aid in members:
                per.setdefault(aid, []).append(
                    Signal(
                        name="follow_burst",
                        score=score,
                        weight=cfg.weights.get("follow_burst", 1.0),
                        evidence=evidence,
                        label_hint=Label.COORDINATED,
                    )
                )

    results: List[FollowerResult] = []
    for f in followers:
        sigs = per.get(f.account.id, [])
        score = _aggregate_score(sigs)
        conf = _confidence(sigs, score, len(FOLLOWER_SIGNALS))
        label = _pick_label(score, sigs, conf, cfg)
        results.append(FollowerResult(follower=f, score=score, label=label, confidence=conf, signals=sigs))

    return FollowerBatchResult(results=results, config=cfg)
