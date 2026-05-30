from smbd.scoring import analyze_comments
from smbd.schema import Label


def test_bot_ring_is_flagged_not_genuine(bot_ring):
    batch = analyze_comments(bot_ring)
    labels = {r.label for r in batch.results}
    # Every bot comment should be flagged (spam or coordinated), none genuine.
    assert Label.GENUINE not in labels
    assert labels & {Label.SPAM, Label.COORDINATED}


def test_genuine_comments_score_low(genuine_comments):
    batch = analyze_comments(genuine_comments)
    for r in batch.results:
        assert r.score < 0.25
        assert r.label in (Label.GENUINE, Label.LOW_CONFIDENCE)


def test_breakdown_sums_to_about_100(mixed_comments):
    batch = analyze_comments(mixed_comments)
    bd = batch.breakdown()
    assert abs(sum(bd.values()) - 100.0) < 0.5
    # mixed set must contain both genuine and flagged buckets
    assert bd[Label.GENUINE.value] > 0
    assert bd[Label.SPAM.value] + bd[Label.COORDINATED.value] > 0


def test_mixed_separates_bots_from_humans(mixed_comments):
    batch = analyze_comments(mixed_comments)
    by_id = {r.comment.id: r for r in batch.results}
    assert by_id["b0"].label in (Label.SPAM, Label.COORDINATED)
    assert by_id["g0"].label in (Label.GENUINE, Label.LOW_CONFIDENCE)


def test_confidence_present(mixed_comments):
    batch = analyze_comments(mixed_comments)
    assert all(0.0 <= r.confidence <= 1.0 for r in batch.results)
