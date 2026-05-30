"""LLM enrichment — judge ambiguous comments and re-score them.

The deterministic engine settles most comments on its own. Enrichment routes
only the *borderline* ones (low-confidence, suspicious, or mid-band scores) to
the LLM, in a single batched call, then folds the judgment back in as an
``llm_text_judgment`` signal and re-scores. Clear-genuine and clear-spam
comments are never sent — that's the cost-control lever.

The LLM contract is just ``complete()`` returning text, so this works with any
provider. We ask for JSON and parse defensively (no structured-output
dependency), keeping enrichment provider-agnostic.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from smbd.config import Config, DEFAULT_CONFIG
from smbd.llm.base import LLMClient, NullLLM
from smbd.schema import Label, Signal
from smbd.scoring import BatchResult, CommentResult, rescore

_SYSTEM = (
    "You are a social-media authenticity analyst. For each comment you are given, "
    "judge whether it reads as genuine human engagement or as spam / generic copy-paste "
    "praise / scripted or coordinated inauthentic text. Be calibrated and conservative: "
    "ordinary short positive comments from real people are genuine, not spam. "
    "Reply with ONLY a JSON array, one object per input comment, each of the form: "
    '{"id": "<id>", "classification": "genuine|spam|generic_praise|scripted|coordinated", '
    '"suspicion": <float 0..1>, "rationale": "<short reason>"}.'
)

# classification -> (label hint, is-suspicious-enough-to-count)
_LABEL_HINT = {
    "genuine": None,
    "spam": Label.SPAM,
    "generic_praise": Label.SUSPICIOUS,
    "scripted": Label.SUSPICIOUS,
    "coordinated": Label.COORDINATED,
}


def select_ambiguous(batch: BatchResult, config: Config) -> List[CommentResult]:
    """Comments worth a (paid) LLM opinion, most-uncertain first, capped."""
    picked: Dict[str, CommentResult] = {}
    for r in batch.results:
        is_borderline = config.genuine_below <= r.score < config.suspicious_at
        if r.label in (Label.LOW_CONFIDENCE, Label.SUSPICIOUS) or is_borderline:
            picked[r.comment.id] = r
    ordered = sorted(picked.values(), key=lambda r: abs(r.score - 0.5))
    return ordered[: config.llm_max_items]


def _build_prompt(results: List[CommentResult]) -> str:
    payload = [{"id": r.comment.id, "text": r.comment.text[:500]} for r in results]
    return "Comments to classify:\n" + json.dumps(payload, ensure_ascii=False)


def _parse_json_array(text: str) -> List[dict]:
    """Extract a JSON array from a model reply, tolerating prose/markdown fences."""
    if not text:
        return []
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def judge(results: List[CommentResult], llm: LLMClient) -> Dict[str, dict]:
    """Ask the LLM to classify a batch; return {comment_id: judgment dict}."""
    if not results:
        return {}
    reply = llm.complete(_build_prompt(results), system=_SYSTEM)
    out: Dict[str, dict] = {}
    for item in _parse_json_array(reply):
        if isinstance(item, dict) and "id" in item:
            out[str(item["id"])] = item
    return out


def enrich_batch(
    batch: BatchResult,
    llm: Optional[LLMClient],
    config: Optional[Config] = None,
) -> BatchResult:
    """Route ambiguous comments through the LLM, add a signal, and re-score them.

    Returns the same ``batch`` (mutated). A no-op when ``llm`` is missing or a
    :class:`~smbd.llm.base.NullLLM`, or when the model reply can't be parsed.
    """
    cfg = config or batch.config or DEFAULT_CONFIG
    if llm is None or isinstance(llm, NullLLM):
        return batch

    targets = select_ambiguous(batch, cfg)
    if not targets:
        return batch

    judgments = judge(targets, llm)
    weight = cfg.weights.get("llm_text_judgment", 1.0)
    by_id = {r.comment.id: r for r in batch.results}

    for cid, verdict in judgments.items():
        result = by_id.get(cid)
        if result is None:
            continue
        classification = str(verdict.get("classification", "genuine")).lower()
        try:
            suspicion = float(verdict.get("suspicion", 0.0))
        except (TypeError, ValueError):
            suspicion = 0.0
        suspicion = max(0.0, min(1.0, suspicion))

        result.signals.append(
            Signal(
                name="llm_text_judgment",
                score=suspicion,
                weight=weight,
                evidence={
                    "reason": "llm_language_judgment",
                    "classification": classification,
                    "rationale": str(verdict.get("rationale", ""))[:300],
                    "model": getattr(llm, "model", llm.name),
                },
                label_hint=_LABEL_HINT.get(classification),
            )
        )
        rescore(result, cfg, batch.n_detectors)

    return batch
