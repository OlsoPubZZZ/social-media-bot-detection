"""YouTubeProvider tests — all offline via an injected transport."""

import pytest

from smbd.providers.youtube import YouTubeProvider


def _queue_transport(responses):
    calls = {"urls": []}
    it = iter(responses)

    def transport(url):
        calls["urls"].append(url)
        return next(it)

    transport.calls = calls
    return transport


def _thread(cid, text, *, author="Real Person", channel="UC123", img="https://img", likes=0,
            published="2026-05-01T10:00:00Z"):
    snip = {
        "textOriginal": text,
        "authorDisplayName": author,
        "authorChannelId": {"value": channel},
        "likeCount": likes,
        "publishedAt": published,
    }
    if img is not None:
        snip["authorProfileImageUrl"] = img
    return {"snippet": {"topLevelComment": {"id": cid, "snippet": snip}}}


def test_fetch_comments_single_page():
    page = {"items": [
        _thread("c1", "first!", author="alice", likes=5),
        _thread("c2", "DM me free subs", author="spammer", channel="UC999", img=None),
    ]}
    yt = YouTubeProvider(transport=_queue_transport([page]))
    comments = yt.fetch_comments("vid42")
    assert [c.id for c in comments] == ["c1", "c2"]
    assert comments[0].account.handle == "alice"
    assert comments[0].account.has_avatar is True
    assert comments[0].likes == 5
    assert comments[0].post_id == "vid42"
    assert comments[0].created_at is not None
    assert comments[1].account.has_avatar is False  # no profile image
    assert comments[1].account.id == "UC999"


def test_fetch_comments_paginates():
    page1 = {"items": [_thread("c1", "a")], "nextPageToken": "TOK"}
    page2 = {"items": [_thread("c2", "b")]}
    transport = _queue_transport([page1, page2])
    yt = YouTubeProvider(api_key="k", transport=transport)
    comments = yt.fetch_comments("v1")
    assert [c.id for c in comments] == ["c1", "c2"]
    assert "pageToken=TOK" in transport.calls["urls"][1]


def test_enrich_authors_fills_channel_stats():
    threads = {"items": [_thread("c1", "hi", channel="UC123")]}
    channels = {"items": [{
        "id": "UC123",
        "snippet": {"publishedAt": "2015-06-01T00:00:00Z"},
        "statistics": {"subscriberCount": "5400", "videoCount": "120", "hiddenSubscriberCount": False},
    }]}
    yt = YouTubeProvider(transport=_queue_transport([threads, channels]), enrich_authors=True)
    comment = yt.fetch_comments("v1")[0]
    assert comment.account.followers_count == 5400
    assert comment.account.post_count == 120
    assert comment.account.created_at.year == 2015


def test_enrich_respects_hidden_subscriber_count():
    threads = {"items": [_thread("c1", "hi", channel="UC123")]}
    channels = {"items": [{
        "id": "UC123",
        "snippet": {"publishedAt": "2015-06-01T00:00:00Z"},
        "statistics": {"videoCount": "120", "hiddenSubscriberCount": True},
    }]}
    yt = YouTubeProvider(transport=_queue_transport([threads, channels]), enrich_authors=True)
    comment = yt.fetch_comments("v1")[0]
    assert comment.account.followers_count is None
    assert comment.account.post_count == 120


def test_fetch_page_metadata():
    resp = {"items": [{
        "id": "UCchan",
        "snippet": {"title": "Cool Channel", "publishedAt": "2012-01-01T00:00:00Z"},
        "statistics": {"subscriberCount": "1000000", "videoCount": "450", "hiddenSubscriberCount": False},
    }]}
    yt = YouTubeProvider(transport=_queue_transport([resp]))
    page = yt.fetch_page("UCchan")
    assert page.handle == "Cool Channel"
    assert page.owner.followers_count == 1000000
    assert page.owner.post_count == 450
    assert page.owner.created_at.year == 2012


def test_api_error_raises():
    err = {"error": {"message": "API key not valid", "code": 400}}
    yt = YouTubeProvider(transport=_queue_transport([err]))
    with pytest.raises(RuntimeError, match="YouTube API error"):
        yt.fetch_comments("v1")


def test_followers_unsupported_is_explicit():
    yt = YouTubeProvider(transport=_queue_transport([]))
    with pytest.raises(NotImplementedError, match="subscriber identities"):
        yt.fetch_followers("UCchan")


def test_live_call_without_key_errors():
    yt = YouTubeProvider(api_key=None)
    yt.api_key = None  # ensure env didn't supply one
    with pytest.raises(RuntimeError, match="API key"):
        yt.fetch_comments("v1")
