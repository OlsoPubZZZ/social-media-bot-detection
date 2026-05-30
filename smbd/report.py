"""Reporting — turn scored results into the product outputs.

Each function returns a plain dict (JSON-ready). Evidence is narrated with
deterministic templates so explanations work with no AI key; when an
:class:`~smbd.llm.base.LLMClient` is supplied it can rewrite the narration in
richer language (Milestone 2).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Optional

from smbd.llm.base import LLMClient, NullLLM
from smbd.schema import Label, Signal
from smbd.scoring import BatchResult, CommentResult


# --- "Are these comments real?" -------------------------------------------------

def comments_report(batch: BatchResult) -> Dict:
    """% genuine / suspicious / spam / coordinated / low-confidence."""
    return {
        "question": "Are these comments real?",
        "total_comments": len(batch.results),
        "breakdown_pct": batch.breakdown(),
        "summary": _comments_summary(batch),
    }


def _comments_summary(batch: BatchResult) -> str:
    b = batch.breakdown()
    genuine = b[Label.GENUINE.value]
    flagged = 100.0 - genuine - b[Label.LOW_CONFIDENCE.value]
    return (
        f"{genuine:.0f}% of comments look genuine; {flagged:.0f}% show signs of "
        f"spam, coordination, or suspicious authorship; "
        f"{b[Label.LOW_CONFIDENCE.value]:.0f}% lacked enough data to judge."
    )


# --- "Is this page being attacked / artificially amplified?" --------------------

def amplification_report(batch: BatchResult) -> Dict:
    """Coordination groups, repeated-text clusters, and timing bursts."""
    groups: Dict[str, set] = defaultdict(set)
    link_types: Dict[str, set] = defaultdict(set)
    text_clusters: List[Dict] = []
    seen_text_samples = set()
    bursts: List[Dict] = []

    for r in batch.results:
        for s in r.signals:
            if s.name == "coordination":
                key = tuple(sorted(s.evidence.get("group_account_ids", [])))
                groups[key].update(s.evidence.get("group_account_ids", []))
                link_types[key].update(s.evidence.get("link_types", []))
            elif s.name == "duplicate_text":
                sample = s.evidence.get("sample_text")
                if sample and sample not in seen_text_samples:
                    seen_text_samples.add(sample)
                    text_clusters.append(
                        {
                            "sample_text": sample,
                            "cluster_size": s.evidence.get("cluster_size"),
                            "distinct_accounts": s.evidence.get("distinct_accounts"),
                        }
                    )
            elif s.name == "timing_burst":
                bursts.append(
                    {
                        "window_start": s.evidence.get("window_start"),
                        "window_seconds": s.evidence.get("window_seconds"),
                        "events_in_window": s.evidence.get("events_in_window"),
                    }
                )

    coordinated_groups = [
        {"account_ids": sorted(accts), "size": len(accts), "link_types": sorted(link_types[key])}
        for key, accts in groups.items()
    ]
    # Deduplicate bursts by window.
    uniq_bursts = {(b["window_start"], b["events_in_window"]): b for b in bursts}

    amplified = bool(coordinated_groups) or len(text_clusters) > 0
    return {
        "question": "Is this page being attacked or artificially amplified?",
        "amplification_detected": amplified,
        "coordinated_groups": sorted(coordinated_groups, key=lambda g: -g["size"]),
        "repeated_text_clusters": sorted(
            text_clusters, key=lambda c: -(c.get("cluster_size") or 0)
        ),
        "timing_bursts": list(uniq_bursts.values()),
    }


# --- "Can I trust this influencer / page?" --------------------------------------

def authenticity_report(batch: BatchResult) -> Dict:
    """Overall authenticity score (0-100) with a confidence band."""
    if not batch.results:
        return {
            "question": "Can I trust this influencer/page?",
            "authenticity_score": None,
            "confidence_band": "no_data",
        }
    avg_suspicion = sum(r.score for r in batch.results) / len(batch.results)
    avg_conf = sum(r.confidence for r in batch.results) / len(batch.results)
    score = round(100.0 * (1.0 - avg_suspicion), 1)
    band = "high" if avg_conf >= 0.66 else "medium" if avg_conf >= 0.4 else "low"
    return {
        "question": "Can I trust this influencer/page?",
        "authenticity_score": score,  # 100 = fully authentic engagement
        "confidence_band": band,
        "based_on_comments": len(batch.results),
    }


# --- "Why did the model flag this?" ---------------------------------------------

def explain(result: CommentResult, llm: Optional[LLMClient] = None) -> Dict:
    """Structured + narrated evidence for a single scored comment."""
    llm = llm or NullLLM()
    evidence = [
        {"signal": s.name, "score": round(s.score, 2), **s.evidence} for s in result.signals
    ]
    narration = _narrate(result)
    enriched = llm.complete(
        _explain_prompt(result),
        system="You explain why a social-media comment was flagged. Be concise and factual.",
    )
    return {
        "question": "Why did the model flag this account/comment?",
        "comment_id": result.comment.id,
        "label": result.label.value,
        "score": round(result.score, 3),
        "confidence": round(result.confidence, 3),
        "evidence": evidence,
        "narration": enriched or narration,
    }


_REASON_TEXT = {
    "duplicate_or_templated_text": "the same or near-identical text appears across many accounts",
    "synchronized_timing_burst": "it was posted inside a synchronized burst of activity",
    "coordinated_behavior_cluster": "its author belongs to a group acting in a coordinated way",
    "weak_or_new_profile": "the author's profile is new or weak",
    "abnormal_follow_ratio": "the author follows far more accounts than follow it back",
}


def _narrate(result: CommentResult) -> str:
    if not result.signals:
        return "No suspicious signals fired; this comment looks organic."
    parts = []
    for s in result.signals:
        reason = s.evidence.get("reason", s.name)
        parts.append(_REASON_TEXT.get(reason, reason.replace("_", " ")))
    joined = "; ".join(dict.fromkeys(parts))  # dedupe, keep order
    return f"Flagged as {result.label.value} because {joined}."


def _explain_prompt(result: CommentResult) -> str:
    lines = [f'Comment: "{result.comment.text[:300]}"', f"Label: {result.label.value}", "Signals:"]
    for s in result.signals:
        lines.append(f"- {s.name}: {s.evidence}")
    lines.append("\nIn 1-2 sentences, explain to a non-expert why this was flagged.")
    return "\n".join(lines)


def full_report(batch: BatchResult) -> Dict:
    """All product outputs in one bundle."""
    return {
        "comments": comments_report(batch),
        "amplification": amplification_report(batch),
        "authenticity": authenticity_report(batch),
    }
