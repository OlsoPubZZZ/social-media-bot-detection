"""Shared synthetic fixtures: a copy-paste bot ring and a genuine comment set.

No real user data ever lives in the repo — everything here is fabricated.
"""

from datetime import datetime, timedelta

import pytest

from smbd.schema import Account, Comment

REF = datetime(2026, 5, 29, 3, 0, 0)


def make_comment(cid, text, *, account=None, dt=None, **acct_kw):
    if account is None:
        defaults = dict(
            id=f"acct_{cid}",
            handle=f"user_{cid}",
            created_at=datetime(2018, 1, 1),
            followers_count=500,
            following_count=300,
            post_count=200,
            has_avatar=True,
        )
        defaults.update(acct_kw)
        account = Account(**defaults)
    return Comment(id=cid, account=account, text=text, created_at=dt)


@pytest.fixture
def genuine_comments():
    base = datetime(2026, 5, 28, 9, 0, 0)
    texts = [
        "Loved this, the colors are gorgeous",
        "Been following for years, congrats!",
        "Where was this taken? looks amazing",
        "This helped me a lot, thank you",
        "Not sure I agree but interesting take",
        "Great content as always",
    ]
    out = []
    for i, t in enumerate(texts):
        out.append(
            make_comment(
                f"g{i}",
                t,
                dt=base + timedelta(hours=i * 3),
                id=f"genuine_{i}",
                handle=f"realperson{i}",
                followers_count=600 + i * 50,
                following_count=300,
            )
        )
    return out


@pytest.fixture
def bot_ring():
    """Five fresh accounts posting near-identical spam within seconds."""
    out = []
    text = "Check out my page for free followers and likes!! www.freefollowers.link"
    for i in range(5):
        acct = Account(
            id=f"bot_{i}",
            handle=f"user_{100000 + i}",
            created_at=REF - timedelta(days=8),  # new account
            followers_count=3,
            following_count=2500,  # extreme follow ratio
            post_count=0,
            has_avatar=False,
        )
        # vary text trivially so we exercise near-dup, not just exact match
        variant = text if i % 2 == 0 else text.replace("!!", "!")
        out.append(
            make_comment(f"b{i}", variant, account=acct, dt=REF + timedelta(seconds=i * 3))
        )
    return out


@pytest.fixture
def mixed_comments(genuine_comments, bot_ring):
    return genuine_comments + bot_ring
