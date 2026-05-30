"""Duplicate / templated text detector.

Flags comments whose text is (near-)identical across many accounts — the
classic signature of copy-paste spam and scripted campaigns.
"""

from __future__ import annotations

from typing import Dict, List

from smbd.detectors.base import Detector
from smbd.features.text import cluster_near_duplicates
from smbd.schema import Comment, Label, Signal


class DuplicateTextDetector(Detector):
    name = "duplicate_text"

    def analyze(self, comments: List[Comment]) -> Dict[str, List[Signal]]:
        out: Dict[str, List[Signal]] = {}
        texts = {c.id: c.text for c in comments}
        by_id = {c.id: c for c in comments}

        clusters = cluster_near_duplicates(
            texts,
            max_hamming=self.config.near_dup_max_hamming,
            min_chars=self.config.duplicate_min_chars,
        )

        for cluster in clusters:
            distinct_accounts = {by_id[cid].account.id for cid in cluster}
            if len(distinct_accounts) < self.config.duplicate_min_cluster:
                continue
            # More accounts repeating the same text -> stronger signal.
            score = min(1.0, 0.4 + 0.1 * len(distinct_accounts))
            sample = by_id[cluster[0]].text.strip()[:140]
            for cid in cluster:
                siblings = [s for s in cluster if s != cid][:10]
                out.setdefault(cid, []).append(
                    self.signal(
                        score=score,
                        evidence={
                            "reason": "duplicate_or_templated_text",
                            "cluster_size": len(cluster),
                            "distinct_accounts": len(distinct_accounts),
                            "sample_text": sample,
                            "sibling_comment_ids": siblings,
                        },
                        label_hint=Label.SPAM,
                    )
                )
        return out
