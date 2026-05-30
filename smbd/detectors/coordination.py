"""Coordination detector.

Builds a behavioral graph over accounts: an edge connects two accounts that
share near-duplicate text *or* post inside the same timing burst. Connected
components above a size threshold are flagged as coordinated groups — the
"is this page being attacked / artificially amplified?" signal.

Uses a stdlib union-find so the core has no graph-library dependency; an
``igraph``/``networkx`` backend can be slotted in later for richer community
detection.
"""

from __future__ import annotations

from typing import Dict, List

from smbd.detectors.base import Detector
from smbd.features.temporal import detect_bursts
from smbd.features.text import cluster_near_duplicates
from smbd.schema import Comment, Label, Signal


class _UnionFind:
    def __init__(self):
        self.parent: Dict[str, str] = {}
        self.edges: Dict[str, set] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)
        self.edges.setdefault(x, set())

    def find(self, x: str) -> str:
        self.add(x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: str, y: str, reason: str) -> None:
        self.edges[x].add((y, reason))
        self.edges[y].add((x, reason))
        self.parent[self.find(x)] = self.find(y)

    def groups(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for node in self.parent:
            out.setdefault(self.find(node), []).append(node)
        return out


class CoordinationDetector(Detector):
    name = "coordination"

    def analyze(self, comments: List[Comment]) -> Dict[str, List[Signal]]:
        out: Dict[str, List[Signal]] = {}
        by_id = {c.id: c for c in comments}
        uf = _UnionFind()
        for c in comments:
            uf.add(c.account.id)

        shared_text_links = 0
        # Shared-text edges.
        texts = {c.id: c.text for c in comments}
        for cluster in cluster_near_duplicates(
            texts,
            max_hamming=self.config.near_dup_max_hamming,
            min_chars=self.config.duplicate_min_chars,
        ):
            accounts = sorted({by_id[cid].account.id for cid in cluster})
            for other in accounts[1:]:
                uf.union(accounts[0], other, "shared_text")
                shared_text_links += 1

        # Shared-burst edges.
        timestamps = {c.id: c.created_at for c in comments}
        if sum(1 for t in timestamps.values() if t is not None) >= self.config.burst_min_events:
            for burst in detect_bursts(
                timestamps,
                window_seconds=self.config.burst_window_seconds,
                rate_multiplier=self.config.burst_rate_multiplier,
                min_events=self.config.burst_min_events,
            ):
                accounts = sorted({by_id[cid].account.id for cid in burst["ids"]})
                if len(accounts) < 2:
                    continue
                for other in accounts[1:]:
                    uf.union(accounts[0], other, "shared_burst")

        # Emit a signal for every comment whose account is in a coordinated group.
        for root, members in uf.groups().items():
            members = sorted(set(members))
            if len(members) < self.config.coordination_min_group:
                continue
            # A group only counts if it formed from actual shared behavior
            # (an account with no edges is its own singleton component).
            if all(not uf.edges[m] for m in members):
                continue
            score = min(1.0, 0.5 + 0.05 * len(members))
            member_set = set(members)
            for c in comments:
                if c.account.id in member_set:
                    reasons = sorted({r for _, r in uf.edges[c.account.id]})
                    out.setdefault(c.id, []).append(
                        self.signal(
                            score=score,
                            evidence={
                                "reason": "coordinated_behavior_cluster",
                                "group_size": len(members),
                                "link_types": reasons,
                                "group_account_ids": members[:25],
                            },
                            label_hint=Label.COORDINATED,
                        )
                    )
        return out
