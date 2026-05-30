from datetime import datetime, timedelta

from smbd.features.text import (
    cluster_near_duplicates,
    hamming,
    normalize_text,
    simhash,
    url_count,
)
from smbd.features.temporal import detect_bursts
from smbd.features.account import follow_ratio, handle_looks_generated
from smbd.schema import Account


def test_normalize_text_strips_case_punct_accents():
    assert normalize_text("  Héllo,  WORLD!! ") == "hello world"


def test_url_count():
    assert url_count("visit www.spam.link now http://x.io") == 2


def test_simhash_near_identical_is_close():
    a = simhash("check out my page for free followers and likes")
    b = simhash("check out my page for free followers and likes!!")
    assert hamming(a, b) <= 6


def test_simhash_different_is_far():
    a = simhash("the sunset over the mountains was beautiful tonight")
    b = simhash("buy cheap followers and likes click this link now")
    assert hamming(a, b) > 6


def test_cluster_near_duplicates_groups_variants():
    texts = {
        "1": "Check out my page for free followers!!",
        "2": "Check out my page for free followers!",
        "3": "check out my page for free followers",
        "4": "totally unrelated organic comment here",
    }
    clusters = cluster_near_duplicates(texts, max_hamming=6, min_chars=4)
    assert any(set(c) >= {"1", "2", "3"} for c in clusters)
    # the unrelated one should not be in a multi-member cluster
    assert all("4" not in c for c in clusters)


def test_detect_bursts_finds_dense_window():
    base = datetime(2026, 1, 1, 0, 0, 0)
    # 6 events within 15s, then nothing for an hour
    ts = {f"x{i}": base + timedelta(seconds=i * 2) for i in range(6)}
    ts["far"] = base + timedelta(hours=1)
    bursts = detect_bursts(ts, window_seconds=60, rate_multiplier=4.0, min_events=5)
    assert bursts
    assert len(bursts[0]["ids"]) >= 5


def test_detect_bursts_abstains_when_sparse():
    base = datetime(2026, 1, 1)
    ts = {f"x{i}": base + timedelta(hours=i) for i in range(6)}
    assert detect_bursts(ts, window_seconds=60, min_events=5) == []


def test_follow_ratio_and_generated_handle():
    acct = Account(id="a", handle="user_100231", following_count=2500, followers_count=3)
    assert follow_ratio(acct) > 100
    assert handle_looks_generated("user_100231", 0.4)
    assert not handle_looks_generated("maria_lens", 0.4)
