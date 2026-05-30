# Library API

SMBD is a library first and a CLI second. Everything the CLI does is a thin
wrapper over these calls.

## The shape of it

```
provider.fetch_*()  ->  list[Comment | Follower]   (normalized schema)
analyze_*()         ->  BatchResult | FollowerBatchResult
report functions    ->  plain dicts (JSON-ready)
```

## Comments

```python
from smbd.providers.importer import ImportProvider
from smbd.scoring import analyze_comments
from smbd.report import comments_report, amplification_report, authenticity_report, explain

comments = ImportProvider().fetch_comments("examples/sample_comments.csv")
batch = analyze_comments(comments)            # -> BatchResult

comments_report(batch)        # % breakdown + summary
amplification_report(batch)   # coordinated groups, clusters, bursts
authenticity_report(batch)    # 0-100 score + confidence band

# per-comment results
for r in batch.results:
    print(r.comment.id, r.label.value, round(r.score, 2), r.confidence)

# explain a single one (optionally with an LLM for nicer narration)
explain(batch.results[5])
```

`analyze_comments(comments, config=None, detector_classes=None)` — pass a
[`Config`](configuration.md) to tune, or a custom detector list to subset/extend.

## Followers

```python
from smbd.providers.importer import ImportProvider
from smbd.followers import analyze_followers
from smbd.report import followers_report

followers = ImportProvider().fetch_followers("examples/sample_followers.csv")
batch = analyze_followers(followers)          # -> FollowerBatchResult

batch.quality_score()         # 0-100
batch.likely_fake()           # {"count": int, "pct": float}
batch.suspicious_clusters()   # join-burst clusters
followers_report(batch)       # the full report dict
```

## Building rows in memory (no files)

You don't need a file — construct rows or schema objects directly.

```python
from smbd.providers.importer import ImportProvider
from smbd.scoring import analyze_comments

rows = [
    {"text": "love this!", "handle": "realjane", "account_created_at": "2018-04-01",
     "followers_count": 820, "following_count": 310, "has_avatar": "true"},
    {"text": "DM me free followers bit.ly/x", "handle": "grow_4821",
     "account_created_at": "2026-05-20", "followers_count": 2,
     "following_count": 4000, "has_avatar": "false"},
]
batch = analyze_comments(ImportProvider().from_rows(rows))
```

Or build [schema](../smbd/schema.py) objects yourself:

```python
from smbd.schema import Account, Comment
from smbd.scoring import analyze_comments

c = Comment(id="1", account=Account(id="u1", handle="alice"), text="great post")
batch = analyze_comments([c])
```

## Online providers

Same interface, different source. All take an injectable `transport=` for
testing.

```python
from smbd.providers.youtube import YouTubeProvider
from smbd.providers.x import XProvider
from smbd.providers.instagram import InstagramProvider

yt = YouTubeProvider(api_key="AIza...", enrich_authors=True)
comments = yt.fetch_comments("<video_id>")

x = XProvider(bearer_token="AAAA...")
followers = x.fetch_followers("<user_id>")    # official follower list

ig = InstagramProvider(access_token="...")
comments = ig.fetch_comments("<your_media_id>")
```

See [providers.md](providers.md) for credentials and limits.

## LLM enrichment

```python
from smbd.llm import get_anthropic, enrich_batch
from smbd.scoring import analyze_comments

batch = analyze_comments(comments)
llm = get_anthropic(model="claude-haiku-4-5")   # needs the `llm` extra + ANTHROPIC_API_KEY
enrich_batch(batch, llm)                         # re-scores only the ambiguous comments
```

`enrich_batch` is a no-op with a `NullLLM` or `None`, so it's safe to call
unconditionally. To plug in a different model vendor, implement the tiny
[`LLMClient`](../smbd/llm/base.py) interface (one method: `complete`).

## Key types

| Type | Module | Notes |
| --- | --- | --- |
| `Account`, `Comment`, `Follower`, `Page`, `Signal` | `smbd.schema` | dataclasses; `.to_dict()` is JSON-ready |
| `Label` | `smbd.schema` | enum: `GENUINE`, `SUSPICIOUS`, `SPAM`, `COORDINATED`, `LOW_CONFIDENCE` |
| `Config` | `smbd.config` | weights + thresholds; `Config.from_json(path)` |
| `BatchResult`, `CommentResult` | `smbd.scoring` | `.breakdown()`, `.to_dict()` |
| `FollowerBatchResult`, `FollowerResult` | `smbd.followers` | `.quality_score()`, `.likely_fake()`, `.suspicious_clusters()` |
| `Provider` | `smbd.providers.base` | base class for data sources |
| `Detector` | `smbd.detectors.base` | base class for signals |

Field meanings: [output-reference.md](output-reference.md).
