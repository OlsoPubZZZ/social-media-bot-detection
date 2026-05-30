"""XProvider tests — all offline via an injected transport."""

import pytest

from smbd.followers import analyze_followers
from smbd.providers.x import XProvider, _has_avatar

_NORMAL_IMG = "https://pbs.twimg.com/profile_images/abc_normal.jpg"
_DEFAULT_IMG = "https://abs.twimg.com/sticky/default_profile_images/default_normal.png"


def _queue_transport(responses):
    calls = {"urls": []}
    it = iter(responses)

    def transport(url):
        calls["urls"].append(url)
        return next(it)

    transport.calls = calls
    return transport


def _user(uid, username, *, created="2015-01-01T00:00:00.000Z", followers=500, following=300,
          tweets=1200, img=_NORMAL_IMG, bio="hello", verified=False):
    return {
        "id": uid,
        "username": username,
        "name": username.title(),
        "created_at": created,
        "public_metrics": {"followers_count": followers, "following_count": following,
                           "tweet_count": tweets},
        "profile_image_url": img,
        "description": bio,
        "verified": verified,
    }


def test_has_avatar_detection():
    assert _has_avatar(_NORMAL_IMG) is True
    assert _has_avatar(_DEFAULT_IMG) is False
    assert _has_avatar(None) is None


def test_fetch_comments_joins_authors():
    resp = {
        "data": [
            {"id": "t1", "text": "great thread", "author_id": "u1",
             "created_at": "2026-05-01T10:00:00.000Z", "lang": "en", "conversation_id": "conv1"},
            {"id": "t2", "text": "follow me for free crypto", "author_id": "u2",
             "created_at": "2026-05-01T10:01:00.000Z", "lang": "en", "conversation_id": "conv1"},
        ],
        "includes": {"users": [
            _user("u1", "alice"),
            _user("u2", "crypto99", created="2026-05-20T00:00:00.000Z", followers=2,
                  following=4000, tweets=5, img=_DEFAULT_IMG, bio=""),
        ]},
        "meta": {"result_count": 2},
    }
    x = XProvider(transport=_queue_transport([resp]))
    comments = x.fetch_comments("conv1")
    assert len(comments) == 2
    assert comments[0].account.handle == "alice"
    assert comments[0].account.followers_count == 500
    assert comments[0].account.has_avatar is True
    assert comments[0].post_id == "conv1"
    assert comments[1].account.has_avatar is False          # default avatar
    assert comments[1].account.following_count == 4000


def test_fetch_comments_paginates():
    page1 = {"data": [{"id": "t1", "text": "a", "author_id": "u1", "conversation_id": "c"}],
             "includes": {"users": [_user("u1", "alice")]}, "meta": {"next_token": "NT"}}
    page2 = {"data": [{"id": "t2", "text": "b", "author_id": "u1", "conversation_id": "c"}],
             "includes": {"users": [_user("u1", "alice")]}, "meta": {"result_count": 1}}
    transport = _queue_transport([page1, page2])
    x = XProvider(bearer_token="t", transport=transport)
    comments = x.fetch_comments("c")
    assert [c.id for c in comments] == ["t1", "t2"]
    assert "next_token=NT" in transport.calls["urls"][1]


def test_fetch_followers_returns_profiles():
    resp = {"data": [_user("u1", "realfan"), _user("u2", "botacct", followers=1, following=5000)],
            "meta": {"result_count": 2}}
    x = XProvider(transport=_queue_transport([resp]))
    followers = x.fetch_followers("99")
    assert len(followers) == 2
    assert followers[0].account.handle == "realfan"
    assert followers[0].followed_at is None        # X gives no follow timestamp
    assert followers[1].account.following_count == 5000


def test_fetch_followers_paginates():
    page1 = {"data": [_user("u1", "a")], "meta": {"next_token": "PT"}}
    page2 = {"data": [_user("u2", "b")], "meta": {"result_count": 1}}
    transport = _queue_transport([page1, page2])
    x = XProvider(bearer_token="t", transport=transport)
    followers = x.fetch_followers("99")
    assert len(followers) == 2
    assert "pagination_token=PT" in transport.calls["urls"][1]


def test_x_followers_feed_the_follower_engine():
    # The payoff: X is the one platform with an official follower source.
    resp = {"data": [
        _user("u1", "realfan", created="2016-01-01T00:00:00.000Z", followers=800, following=400),
        _user("u2", "spam1", created="2026-05-20T00:00:00.000Z", followers=1, following=6000,
              tweets=0, img=_DEFAULT_IMG, bio=""),
    ], "meta": {"result_count": 2}}
    x = XProvider(transport=_queue_transport([resp]))
    batch = analyze_followers(x.fetch_followers("99"))
    assert batch.likely_fake()["count"] >= 1


def test_fetch_page_by_id_and_username():
    resp_id = {"data": _user("123", "brand", followers=100000)}
    x = XProvider(transport=_queue_transport([resp_id]))
    page = x.fetch_page("123")
    assert page.handle == "brand"
    assert page.owner.followers_count == 100000

    transport = _queue_transport([{"data": _user("123", "brand")}])
    XProvider(transport=transport).fetch_page("brand")
    assert "users/by/username/brand" in transport.calls["urls"][0]


def test_request_error_raises():
    err = {"status": 401, "title": "Unauthorized", "detail": "bad token"}
    with pytest.raises(RuntimeError, match="X API error"):
        XProvider(transport=_queue_transport([err])).fetch_comments("c")


def test_partial_errors_with_data_do_not_raise():
    resp = {"data": [{"id": "t1", "text": "ok", "author_id": "u1", "conversation_id": "c"}],
            "includes": {"users": [_user("u1", "alice")]},
            "errors": [{"detail": "one referenced tweet was unavailable"}],
            "meta": {"result_count": 1}}
    comments = XProvider(transport=_queue_transport([resp])).fetch_comments("c")
    assert len(comments) == 1


def test_live_call_without_token_errors():
    x = XProvider(bearer_token=None)
    x.bearer_token = None
    with pytest.raises(RuntimeError, match="bearer token"):
        x.fetch_comments("c")
