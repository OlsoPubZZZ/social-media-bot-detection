"""Coordination detector.

Builds a behavioral graph over accounts. An edge connects two accounts that
share **near-duplicate text**, post inside the same **timing burst**, or post
the same **URL/link** (even with different wording). Connected components above
a size threshold are flagged as coordinated groups — the "is this page being
attacked / artificially amplified?" signal.

Each group also reports a **cohesion** score (realized edges / possible edges):
a tight clique of accounts all linked to each other is far more suspicious than
a loose chain, and cohesion makes that visible in the evidence.

Uses a stdlib union-find so the core has no graph-library dependency; a
``networkx``/``igraph`` backend with modularity-based community detection can be
slotted in later as an optional extra.
"""

from __future__ import annotations

from itertools import combinations
from typing import Dict, List

from smbd.detectors.base import Detector
from smbd.features.temporal import detect_bursts
from smbd.features.text import cluster_near_duplicates, extract_urls
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

        # Shared-URL edges: accounts posting the same link, regardless of wording.
        url_accounts: Dict[str, set] = {}
        for c in comments:
            for url in set(extract_urls(c.text)):
                url_accounts.setdefault(url, set()).add(c.account.id)
        for accounts_with_url in url_accounts.values():
            accounts = sorted(accounts_with_url)
            if len(accounts) < 2:
                continue
            for other in accounts[1:]:
                uf.union(accounts[0], other, "shared_url")

        # Emit a signal for every comment whose account is in a coordinated group.
        for root, members in uf.groups().items():
            members = sorted(set(members))
            if len(members) < self.config.coordination_min_group:
                continue
            # A group only counts if it formed from actual shared behavior
            # (an account with no edges is its own singleton component).
            if all(not uf.edges[m] for m in members):
                continue
            cohesion = self._cohesion(uf, members)
            # Denser cliques score a little higher than loose chains.
            score = min(1.0, 0.5 + 0.04 * len(members) + 0.2 * cohesion)
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
                                "cohesion": cohesion,
                                "group_account_ids": members[:25],
                            },
                            label_hint=Label.COORDINATED,
                        )
                    )
        return out

    @staticmethod
    def _cohesion(uf: "_UnionFind", members: List[str]) -> float:
        """Realized undirected edges within the group / possible edges (0–1)."""
        member_set = set(members)
        pairs = set()
        for m in members:
            for other, _reason in uf.edges.get(m, set()):
                if other in member_set and other != m:
                    pairs.add(frozenset((m, other)))
        possible = len(members) * (len(members) - 1) / 2
        return round(len(pairs) / possible, 2) if possible else 0.0
