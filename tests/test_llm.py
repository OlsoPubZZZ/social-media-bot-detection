"""LLM enrichment tests — all offline via a FakeLLM, plus one gated live smoke test."""

import json
import os
from datetime import datetime, timedelta

import pytest

from smbd.llm.base import LLMClient, NullLLM
from smbd.llm.enrich import enrich_batch, select_ambiguous, _parse_json_array
from smbd.scoring import analyze_comments
from smbd.schema import Account, Comment, Label

_REF = datetime(2026, 5, 29)


class FakeLLM(LLMClient):
    """Records prompts and returns a canned classification for every input id."""

    name = "fake"
    model = "fake-model-1"

    def __init__(self, verdicts=None, narration="LLM says: looks scripted."):
        self.verdicts = verdicts or {}
        self.narration = narration
        self.calls = []
        self.last_ids = []

    def complete(self, prompt, *, system=None):
        self.calls.append({"prompt": prompt, "system": system})
        # Narration calls (explain) don't include the "Comments to classify" header.
        if "Comments to classify" not in prompt:
            return self.narration
        payload = json.loads(prompt.split("Comments to classify:\n", 1)[1])
        self.last_ids = [row["id"] for row in payload]
        out = []
        for row in payload:
            v = self.verdicts.get(
                row["id"],
                {"classification": "spam", "suspicion": 0.9, "rationale": "templated"},
            )
            out.append({"id": row["id"], **v})
        return json.dumps(out)


def _ambiguous_comment(cid):
    """A comment that lands in the low-confidence band: a new account with an
    empty bio (mild suspicion) but no duplicate text or burst. Unique tokens per
    id keep the duplicate-text detector from clustering them; spread timestamps
    keep the burst detector quiet."""
    acct = Account(id=f"a_{cid}", handle=f"u{cid}", bio="", created_at=_REF - timedelta(days=5))
    minutes = int(cid) if cid.isdigit() else 0
    return Comment(
        id=cid,
        account=acct,
        text=f"alpha{cid} beta{cid} gamma{cid} musing",
        created_at=_REF - timedelta(minutes=minutes),
    )


# --- parsing ---

def test_parse_plain_array():
    assert _parse_json_array('[{"id": "x"}]') == [{"id": "x"}]


def test_parse_fenced_array():
    txt = "Sure!\n```json\n[{\"id\": \"x\"}]\n```\nDone."
    assert _parse_json_array(txt) == [{"id": "x"}]


def test_parse_garbage_returns_empty():
    assert _parse_json_array("no json here") == []
    assert _parse_json_array("") == []


# --- routing / cost control ---

def test_null_llm_is_noop(genuine_comments):
    batch = analyze_comments(genuine_comments)
    before = [(r.label, r.score) for r in batch.results]
    enrich_batch(batch, NullLLM())
    after = [(r.label, r.score) for r in batch.results]
    assert before == after


def test_clear_cases_are_not_sent(mixed_comments):
    batch = analyze_comments(mixed_comments)
    llm = FakeLLM()
    enrich_batch(batch, llm)
    by_id = {r.comment.id: r for r in batch.results}
    # Clear spam ring and clear-genuine comments should be excluded from the LLM call.
    for cid in ("b0", "g0"):
        assert cid not in llm.last_ids


def test_ambiguous_comment_gets_judged_and_rescored():
    comments = [_ambiguous_comment(str(i)) for i in range(3)]
    batch = analyze_comments(comments)
    # Precondition: these are borderline/low-confidence, not already flagged.
    assert all(r.label in (Label.LOW_CONFIDENCE, Label.SUSPICIOUS, Label.GENUINE) for r in batch.results)

    llm = FakeLLM(verdicts={"0": {"classification": "spam", "suspicion": 0.95, "rationale": "ad"}})
    enrich_batch(batch, llm)

    judged = next(r for r in batch.results if r.comment.id == "0")
    names = {s.name for s in judged.signals}
    assert "llm_text_judgment" in names
    assert judged.label == Label.SPAM
    assert judged.score > 0.5


def test_genuine_verdict_does_not_escalate():
    # A "genuine" verdict adds ~no suspicion (noisy-OR only accumulates), so it
    # must not push a borderline comment into a flagged label.
    comments = [_ambiguous_comment("solo")]
    batch = analyze_comments(comments)
    base = batch.results[0].score
    llm = FakeLLM(verdicts={"solo": {"classification": "genuine", "suspicion": 0.05, "rationale": "real"}})
    enrich_batch(batch, llm)
    r = batch.results[0]
    assert r.label not in (Label.SPAM, Label.COORDINATED)
    assert r.score <= base + 0.05


def test_max_items_caps_the_batch():
    comments = [_ambiguous_comment(str(i)) for i in range(40)]
    batch = analyze_comments(comments)
    batch.config.llm_max_items = 10
    selected = select_ambiguous(batch, batch.config)
    assert len(selected) == 10


def test_malformed_reply_degrades_gracefully():
    comments = [_ambiguous_comment("z")]
    batch = analyze_comments(comments)

    class BrokenLLM(FakeLLM):
        def complete(self, prompt, *, system=None):
            return "the model rambled and returned no json"

    before = [(r.label, r.score) for r in batch.results]
    enrich_batch(batch, BrokenLLM())
    after = [(r.label, r.score) for r in batch.results]
    assert before == after  # no signal added, no crash


def test_system_prompt_is_sent_for_caching():
    comments = [_ambiguous_comment("c")]
    batch = analyze_comments(comments)
    llm = FakeLLM()
    enrich_batch(batch, llm)
    judge_call = next(c for c in llm.calls if "Comments to classify" in c["prompt"])
    assert judge_call["system"]  # stable system prompt present (enables prefix caching)


# --- live smoke test (opt-in) ---

@pytest.mark.skipif(
    not os.getenv("SMBD_LIVE_LLM"), reason="set SMBD_LIVE_LLM=1 and ANTHROPIC_API_KEY to run"
)
def test_live_anthropic_roundtrip():
    from smbd.llm import get_anthropic

    comments = [_ambiguous_comment(str(i)) for i in range(3)]
    batch = analyze_comments(comments)
    llm = get_anthropic(model=os.getenv("SMBD_LIVE_MODEL", "claude-haiku-4-5"))
    enrich_batch(batch, llm)
    assert any(
        any(s.name == "llm_text_judgment" for s in r.signals) for r in batch.results
    )
