"""Web app tests — exercised via FastAPI's TestClient (offline). Skipped if the
`web` extra isn't installed."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from smbd.web.app import app  # noqa: E402

client = TestClient(app)

_GENUINE = (
    "text,handle,account_created_at,followers_count,following_count,has_avatar\n"
    '"love this, the colours are gorgeous",realjane,2018-04-01,820,310,true\n'
    '"been following for years, congrats",mike_t,2017-09-12,1400,600,true\n'
    '"where was this shot? stunning",dora.k,2019-02-20,540,300,true\n'
)
_RING = "".join(
    f'"Check out my page for free followers!! www.spam.link",user_{100000+i},2026-05-20,2,3000,false\n'
    for i in range(6)
)
_COMMENTS_CSV = _GENUINE + _RING

_FOLLOWERS_CSV = (
    "handle,account_created_at,followers_count,following_count,has_avatar,followed_at\n"
    "realfan,2018-01-01,500,300,true,2024-05-01T10:00:00\n"
    + "".join(
        f"grow_{40000+i},2026-05-20,2,4000,false,2026-05-29T03:00:0{i}\n" for i in range(6)
    )
)


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "SMBD" in r.text


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_analyze_comments_import():
    r = client.post("/api/analyze", json={"kind": "comments", "source": "import", "data": _COMMENTS_CSV})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "comments"
    assert "breakdown_pct" in body["report"]
    flagged = [x for x in body["results"] if x["label"] not in ("genuine", "low_confidence")]
    assert flagged, "the spam ring should produce flagged comments"
    assert all("narration" in x for x in body["results"])
    assert body["amplification"]["amplification_detected"] is True


def test_analyze_followers_import():
    r = client.post("/api/analyze", json={"kind": "followers", "source": "import", "data": _FOLLOWERS_CSV})
    assert r.status_code == 200
    rep = r.json()["report"]
    assert rep["follower_quality_score"] is not None
    assert rep["likely_fake_count"] >= 1


def test_analyze_page_import():
    r = client.post("/api/analyze", json={"kind": "page", "source": "import", "data": _COMMENTS_CSV})
    assert r.status_code == 200
    assert "authenticity" in r.json()


def test_empty_data_is_400():
    r = client.post("/api/analyze", json={"kind": "comments", "source": "import", "data": ""})
    assert r.status_code == 400
    assert "data" in r.json()["detail"].lower()


def test_llm_without_key_is_400():
    r = client.post("/api/analyze", json={
        "kind": "comments", "source": "import", "data": _COMMENTS_CSV,
        "options": {"llm": True},
    })
    assert r.status_code == 400
    assert "anthropic" in r.json()["detail"].lower()


def test_youtube_without_key_is_400():
    r = client.post("/api/analyze", json={
        "kind": "comments", "source": "youtube", "target": "vid123",
    })
    assert r.status_code == 400
    assert "api key" in r.json()["detail"].lower()


def test_instagram_source_without_token_is_400():
    r = client.post("/api/analyze", json={
        "kind": "comments", "source": "instagram", "target": "1784...",
    })
    assert r.status_code == 400
    assert "access token" in r.json()["detail"].lower()


def test_meta_comment_export_via_web():
    payload = '{"comments_media_comments": [{"string_map_data": {"Comment": {"value": "hey there friend", "timestamp": 1716949201}}}]}'
    r = client.post("/api/analyze", json={"kind": "comments", "source": "import", "data": payload})
    assert r.status_code == 200
    assert r.json()["report"]["total_comments"] == 1


def test_json_input_accepted():
    payload = '{"comments": [{"text": "nice", "handle": "a"}, {"text": "great", "handle": "b"}]}'
    r = client.post("/api/analyze", json={"kind": "comments", "source": "import", "data": payload, "fmt": "json"})
    assert r.status_code == 200
    assert r.json()["report"]["total_comments"] == 2
