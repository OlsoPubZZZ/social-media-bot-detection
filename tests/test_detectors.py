from smbd.config import DEFAULT_CONFIG
from smbd.detectors import (
    AccountWeaknessDetector,
    CoordinationDetector,
    DuplicateTextDetector,
    RatioAnomalyDetector,
    TimingBurstDetector,
)


def _all_signals(produced):
    return [s for sigs in produced.values() for s in sigs]


def test_duplicate_text_flags_ring(bot_ring):
    produced = DuplicateTextDetector(DEFAULT_CONFIG).analyze(bot_ring)
    assert len(produced) == len(bot_ring)
    sig = _all_signals(produced)[0]
    assert sig.evidence["distinct_accounts"] >= 3
    assert sig.evidence["reason"] == "duplicate_or_templated_text"


def test_duplicate_text_ignores_genuine(genuine_comments):
    produced = DuplicateTextDetector(DEFAULT_CONFIG).analyze(genuine_comments)
    assert produced == {}


def test_timing_burst_flags_ring(mixed_comments, bot_ring):
    # Bursts need a baseline of normal activity to contrast against, so we
    # analyze the ring alongside the spread-out genuine comments.
    produced = TimingBurstDetector(DEFAULT_CONFIG).analyze(mixed_comments)
    assert produced
    assert _all_signals(produced)[0].evidence["reason"] == "synchronized_timing_burst"
    # Every flagged comment in this fixture should be one of the ring members.
    ring_ids = {c.id for c in bot_ring}
    assert set(produced) <= ring_ids


def test_timing_burst_abstains_without_timestamps(bot_ring):
    for c in bot_ring:
        c.created_at = None
    assert TimingBurstDetector(DEFAULT_CONFIG).analyze(bot_ring) == {}


def test_coordination_flags_ring(bot_ring):
    produced = CoordinationDetector(DEFAULT_CONFIG).analyze(bot_ring)
    assert produced
    sig = _all_signals(produced)[0]
    assert sig.evidence["group_size"] >= 3
    assert "shared_text" in sig.evidence["link_types"]


def test_coordination_ignores_genuine(genuine_comments):
    assert CoordinationDetector(DEFAULT_CONFIG).analyze(genuine_comments) == {}


def test_account_weakness_flags_new_generated_profiles(bot_ring):
    produced = AccountWeaknessDetector(DEFAULT_CONFIG).analyze(bot_ring)
    assert len(produced) == len(bot_ring)
    attrs = _all_signals(produced)[0].evidence["attributes"]
    assert any(a.startswith("new_account") for a in attrs)
    assert "auto_generated_handle" in attrs
    assert "no_avatar" in attrs


def test_account_weakness_abstains_on_strong_profiles(genuine_comments):
    assert AccountWeaknessDetector(DEFAULT_CONFIG).analyze(genuine_comments) == {}


def test_ratio_anomaly_flags_ring(bot_ring):
    produced = RatioAnomalyDetector(DEFAULT_CONFIG).analyze(bot_ring)
    assert len(produced) == len(bot_ring)
    assert _all_signals(produced)[0].evidence["reason"] == "abnormal_follow_ratio"


def test_ratio_anomaly_abstains_when_counts_missing(bot_ring):
    for c in bot_ring:
        c.account.followers_count = None
        c.account.following_count = None
    assert RatioAnomalyDetector(DEFAULT_CONFIG).analyze(bot_ring) == {}
