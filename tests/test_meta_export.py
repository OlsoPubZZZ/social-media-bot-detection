"""Meta ('Download Your Information') export import tests — Instagram & Facebook."""

import json

from smbd.followers import analyze_followers
from smbd.providers.importer import ImportProvider
from smbd.scoring import analyze_comments

# ~2020-01-01 and ~2024-05-29 in epoch seconds.
T_OLD, T_NEW = 1577836800, 1716949201


def _ig(username, ts):
    return {"string_list_data": [{"href": f"https://instagram.com/{username}",
                                   "value": username, "timestamp": ts}]}


def test_instagram_followers_export():
    payload = json.dumps({"relationships_followers": [_ig("realfan", T_OLD), _ig("grow_99210", T_NEW)]})
    followers = ImportProvider().followers_from_json(payload)
    assert len(followers) == 2
    assert followers[0].account.handle == "realfan"
    assert followers[0].followed_at.year == 2020          # timestamp parsed
    assert followers[1].account.handle == "grow_99210"


def test_instagram_bare_list_form():
    payload = json.dumps([_ig("alice", T_OLD), _ig("bob", T_NEW)])
    followers = ImportProvider().followers_from_json(payload)
    assert [f.account.handle for f in followers] == ["alice", "bob"]


def test_facebook_friends_export():
    payload = json.dumps({"friends_v2": [
        {"name": "Jane Doe", "timestamp": T_OLD},
        {"name": "John Smith", "timestamp": T_NEW},
    ]})
    followers = ImportProvider().followers_from_json(payload)
    assert len(followers) == 2
    assert followers[0].account.display_name == "Jane Doe"
    assert followers[0].followed_at.year == 2020


def test_normal_rows_json_still_works():
    # A plain followers array must NOT be mistaken for a Meta export.
    payload = json.dumps({"followers": [{"handle": "someone", "followers_count": 100}]})
    followers = ImportProvider().followers_from_json(payload)
    assert len(followers) == 1 and followers[0].account.handle == "someone"


def test_instagram_comments_export():
    payload = json.dumps({"comments_media_comments": [
        {"string_map_data": {"Comment": {"value": "love this!", "timestamp": T_OLD},
                             "Media Owner": {"value": "some_creator"}}},
        {"string_map_data": {"Comment": {"value": "first", "timestamp": T_NEW}}},
    ]})
    comments = ImportProvider().from_json(payload)
    assert [c.text for c in comments] == ["love this!", "first"]
    assert comments[0].created_at.year == 2020
    assert comments[0].post_id == "some_creator"
    assert comments[0].account.id == "you"          # exports = your own comments


def test_instagram_comments_bare_list():
    payload = json.dumps([{"string_map_data": {"Comment": {"value": "hi", "timestamp": T_OLD}}}])
    assert [c.text for c in ImportProvider().from_json(payload)] == ["hi"]


def test_facebook_comments_export():
    payload = json.dumps({"comments_v2": [
        {"timestamp": T_OLD, "data": [{"comment": {"comment": "nice post", "author": "Jane Doe"}}]},
    ]})
    comments = ImportProvider().from_json(payload)
    assert comments[0].text == "nice post"
    assert comments[0].account.display_name == "Jane Doe"
    # Runs through the engine (single author -> no bot signals).
    assert analyze_comments(comments).results[0].label.value in ("genuine", "low_confidence")


def test_normal_comment_rows_json_still_works():
    payload = json.dumps({"comments": [{"text": "hello", "handle": "a"}]})
    comments = ImportProvider().from_json(payload)
    assert len(comments) == 1 and comments[0].text == "hello"


def test_export_feeds_the_engine():
    # Realistic shape: genuine follows spread over time (the baseline) + a batch
    # of generated-handle accounts that all followed within minutes (the spike).
    month = 2_592_000
    genuine = [_ig(name, 1_640_995_200 + i * month)
               for i, name in enumerate(["realfan", "mike_t", "dora_k", "sam_lee",
                                          "priya_r", "tom_h", "lena_w"])]
    fakes = [_ig(f"grow_{40000 + i}", T_NEW + i * 30) for i in range(8)]
    payload = json.dumps({"relationships_followers": genuine + fakes})
    batch = analyze_followers(ImportProvider().followers_from_json(payload))
    assert batch.likely_fake()["count"] >= 1
    assert len(batch.suspicious_clusters()) >= 1   # join-burst detected from timestamps
