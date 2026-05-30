"""BrowserProvider tests — the text→comments logic (no live browser needed).

`smbd.providers.browser` imports Playwright lazily, so these run in CI without
the `browser` extra. Live page rendering is exercised manually / behind a flag.
"""

import json

from smbd.providers.browser import BrowserProvider


def test_comments_from_text_extracts_distinct_lines():
    text = "Nav\nHome\nlove this post so much\nlove this post so much\n" \
           "this is a totally different comment here\nx\n" + "y" * 500
    comments = BrowserProvider.comments_from_text(text)
    bodies = [c.text for c in comments]
    assert "love this post so much" in bodies
    assert "this is a totally different comment here" in bodies
    assert bodies.count("love this post so much") == 1   # de-duplicated
    assert "x" not in bodies                              # too short
    assert all(len(b) <= 400 for b in bodies)            # too-long line dropped


def test_comments_from_text_respects_limit():
    text = "\n".join(f"comment number {i} here" for i in range(50))
    assert len(BrowserProvider.comments_from_text(text, limit=10)) == 10


class _FakeLLM:
    name = "fake"
    model = "fake-1"

    def __init__(self, reply):
        self._reply = reply

    def complete(self, prompt, *, system=None):
        return self._reply


def test_ai_comments_parses_model_json():
    reply = json.dumps([
        {"handle": "alice", "text": "great video!"},
        {"handle": None, "text": "first"},
        {"text": ""},                       # dropped (empty)
        "garbage",                          # dropped (not a dict)
    ])
    comments = BrowserProvider.ai_comments("<page text>", _FakeLLM(reply))
    assert [c.text for c in comments] == ["great video!", "first"]
    assert comments[0].account.handle == "alice"


def test_ai_comments_handles_unparseable_reply():
    assert BrowserProvider.ai_comments("x", _FakeLLM("the model said no json")) == []


def test_login_wall_detected():
    fb = "Log in\nCreate new account\nForgotten password?\nLog in or sign up to see more"
    assert BrowserProvider.looks_like_login_wall(fb, title="Facebook") is True


def test_normal_page_not_a_login_wall():
    page = "Great video!\nThis helped me so much\nFirst!\nWhere was this filmed?"
    assert BrowserProvider.looks_like_login_wall(page, title="Cool Post") is False
    # A lone "Sign in" button shouldn't trip it.
    assert BrowserProvider.looks_like_login_wall("Sign in\nawesome content here") is False
