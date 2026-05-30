"""Follower analysis tests — genuine vs fake-ring separation, clusters, import."""

import os
from datetime import datetime, timedelta

import pytest

from smbd.followers import analyze_followers
from smbd.providers.importer import ImportProvider
from smbd.report import followers_report
from smbd.schema import Account, Follower, Label

_REF = datetime(2026, 5, 29)
EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_followers.csv")


def _genuine(i):
    return Follower(
        account=Account(
            id=f"g{i}",
            handle=f"real_person_{i}",
            created_at=_REF - timedelta(days=900 + i),
            followers_count=500 + i * 50,
            following_count=300,
            post_count=120,
            bio="a normal human bio",
            has_avatar=True,
        ),
        followed_at=_REF - timedelta(days=200 + i * 30),  # spread out, no burst
    )


def _fake(i):
    return Follower(
        account=Account(
            id=f"b{i}",
            handle=f"grow_fast_{40000 + i}",  # generated-looking
            created_at=_REF - timedelta(days=9),  # brand new
            followers_count=3,
            following_count=3000,  # huge ratio
            post_count=0,
            bio="",
            has_avatar=False,
        ),
        followed_at=_REF + timedelta(seconds=5 * i),  # tight join burst
    )


@pytest.fixture
def mixed_followers():
    return [_genuine(i) for i in range(7)] + [_fake(i) for i in range(8)]


def test_genuine_followers_are_clean():
    batch = analyze_followers([_genuine(i) for i in range(7)])
    assert all(r.label == Label.GENUINE for r in batch.results)
    assert batch.quality_score() > 90


def test_fake_ring_is_flagged(mixed_followers):
    batch = analyze_followers(mixed_followers)
    by_id = {r.follower.account.id: r for r in batch.results}
    for i in range(8):
        assert by_id[f"b{i}"].label in (Label.COORDINATED, Label.SUSPICIOUS, Label.SPAM)
    for i in range(7):
        assert by_id[f"g{i}"].label == Label.GENUINE


def test_likely_fake_estimate(mixed_followers):
    batch = analyze_followers(mixed_followers)
    fake = batch.likely_fake()
    assert fake["count"] == 8
    assert 45 <= fake["pct"] <= 60  # 8/15
    assert batch.quality_score() < 70


def test_join_burst_forms_a_cluster(mixed_followers):
    batch = analyze_followers(mixed_followers)
    clusters = batch.suspicious_clusters()
    assert len(clusters) == 1
    assert clusters[0]["size"] == 8


def test_no_profile_data_abstains():
    # Only a handle, nothing else known -> no signals -> not flagged.
    followers = [Follower(account=Account(id=f"x{i}", handle=f"person{i}")) for i in range(5)]
    batch = analyze_followers(followers)
    assert all(r.label == Label.GENUINE for r in batch.results)
    assert all(not r.signals for r in batch.results)


def test_report_shape_and_evidence(mixed_followers):
    rep = followers_report(analyze_followers(mixed_followers))
    assert rep["total_followers"] == 15
    assert rep["likely_fake_count"] == 8
    assert rep["follower_quality_score"] is not None
    # Top suspicious entries surface the profile facts the user cares about.
    top = rep["top_suspicious"][0]
    assert top["has_avatar"] is False
    assert top["account_created_at"] is not None
    assert any("weak_or_new_profile" in r or "follow" in r or "ratio" in r for r in top["reasons"])


# --- import path (the realistic way follower data arrives) ---

def test_import_followers_from_csv_end_to_end():
    followers = ImportProvider().fetch_followers(os.path.abspath(EXAMPLE))
    assert len(followers) == 15
    batch = analyze_followers(followers)
    # The 8-account ring should be flagged and form one cluster.
    assert batch.likely_fake()["count"] == 8
    assert len(batch.suspicious_clusters()) == 1
    # Genuine handles stay clean.
    by_id = {r.follower.account.id: r for r in batch.results}
    assert by_id["f1"].label == Label.GENUINE
