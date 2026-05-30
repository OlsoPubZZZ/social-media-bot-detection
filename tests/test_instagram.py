"""InstagramProvider tests — all offline via an injected transport."""

import pytest

from smbd.providers.instagram import InstagramProvider, _parse_ig_time


def _queue_transport(responses):
    """Return a transport callable that yields queued responses in order."""
    calls = {"urls": []}
    it = iter(responses)

    def transport(url):
        calls["urls"].append(url)
        return next(it)

    transport.calls = calls
    return transport


def test_parse_ig_time_offset_without_colon():
    dt = _parse_ig_time("2026-05-01T10:00:00+0000")
    assert dt is not None and dt.year == 2026 and dt.hour == 10


def test_fetch_comments_single_page():
    page = {
        "data": [
            {"id": "1", "text": "love this", "timestamp": "2026-05-01T10:00:00+0000",
             "username": "alice", "like_count": 3},
            {"id": "2", "text": "DM me for free followers", "timestamp": "2026-05-01T10:00:05+0000",
             "from": {"id": "u99", "username": "spammer"}, "like_count": 0},
        ]
    }
    ig = InstagramProvider(transport=_queue_transport([page]))
    comments = ig.fetch_comments("media_123")
    assert len(comments) == 2
    assert comments[0].account.handle == "alice"
    assert comments[0].likes == 3
    assert comments[0].post_id == "media_123"
    assert comments[1].account.id == "u99"  # from.id used when present
    assert comments[0].created_at is not None


def test_fetch_comments_paginates():
    page1 = {"data": [{"id": "1", "text": "a"}], "paging": {"next": "https://next-page"}}
    page2 = {"data": [{"id": "2", "text": "b"}]}
    transport = _queue_transport([page1, page2])
    ig = InstagramProvider(transport=transport)
    comments = ig.fetch_comments("m1")
    assert [c.id for c in comments] == ["1", "2"]
    assert transport.calls["urls"][1] == "https://next-page"  # followed paging.next


def test_fetch_page_metadata():
    resp = {"id": "ig1", "username": "brand", "followers_count": 10000,
            "follows_count": 120, "media_count": 87}
    ig = InstagramProvider(transport=_queue_transport([resp]))
    page = ig.fetch_page("ig1")
    assert page.handle == "brand"
    assert page.owner.followers_count == 10000
    assert page.owner.following_count == 120
    assert page.owner.post_count == 87


def test_api_error_raises():
    err = {"error": {"message": "Invalid OAuth access token", "code": 190}}
    ig = InstagramProvider(transport=_queue_transport([err]))
    with pytest.raises(RuntimeError, match="Instagram API error"):
        ig.fetch_comments("m1")


def test_followers_unsupported_is_explicit():
    ig = InstagramProvider(transport=_queue_transport([]))
    with pytest.raises(NotImplementedError, match="does not expose individual followers"):
        ig.fetch_followers("ig1")


def test_live_call_without_token_errors():
    # No transport injected -> would hit HTTP -> must refuse without a token.
    ig = InstagramProvider(access_token=None)
    ig.access_token = None  # ensure env didn't supply one
    with pytest.raises(RuntimeError, match="access token"):
        ig.fetch_comments("m1")
