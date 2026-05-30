"""End-to-end: CSV import -> analyze -> reports, plus the CLI entry point."""

import json
import os

from smbd.cli import main
from smbd.providers.importer import ImportProvider
from smbd.report import amplification_report, authenticity_report, comments_report, explain
from smbd.scoring import analyze_comments

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_comments.csv")


def test_import_sample_csv():
    comments = ImportProvider().fetch_comments(EXAMPLE)
    assert len(comments) == 15
    assert all(c.text for c in comments)


def test_sample_breakdown_flags_spam_ring():
    comments = ImportProvider().fetch_comments(EXAMPLE)
    batch = analyze_comments(comments)
    bd = comments_report(batch)["breakdown_pct"]
    assert bd["genuine"] > 0
    assert bd["spam"] + bd["coordinated"] > 0
    # the 8 spam/promo accounts should not be called genuine
    by_id = {r.comment.id: r for r in batch.results}
    assert by_id["c6"].label.value in ("spam", "coordinated", "suspicious")
    assert by_id["c1"].label.value in ("genuine", "low_confidence")


def test_amplification_and_authenticity_reports():
    comments = ImportProvider().fetch_comments(EXAMPLE)
    batch = analyze_comments(comments)
    amp = amplification_report(batch)
    assert amp["amplification_detected"] is True
    assert amp["coordinated_groups"]
    auth = authenticity_report(batch)
    assert 0 <= auth["authenticity_score"] <= 100


def test_explain_returns_evidence_and_narration():
    comments = ImportProvider().fetch_comments(EXAMPLE)
    batch = analyze_comments(comments)
    spam = next(r for r in batch.results if r.comment.id == "c6")
    out = explain(spam)
    assert out["evidence"]
    assert isinstance(out["narration"], str) and out["narration"]


def test_csv_roundtrip_from_string():
    csv_text = "text,handle\n\"hello there\",alice\n\"hi\",bob\n"
    comments = ImportProvider().from_csv(csv_text)
    assert len(comments) == 2


def test_cli_comments_runs(capsys):
    rc = main(["comments", EXAMPLE])
    assert rc == 0
    out = capsys.readouterr().out
    assert "comments analyzed" in out


def test_cli_comments_json(capsys):
    rc = main(["comments", EXAMPLE, "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_comments"] == 15
    assert "breakdown_pct" in payload


def test_cli_page_json(capsys):
    rc = main(["page", EXAMPLE, "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "amplification" in payload and "authenticity" in payload
