# Output reference

How to read what SMBD gives you. Add `--json` to any command for the
machine-readable form.

## Labels

Every comment and follower gets one label:

| Label | Meaning |
| --- | --- |
| `genuine` | No meaningful suspicion signals fired. Looks like organic activity. |
| `suspicious` | Enough signal to flag, but not clearly spam or coordinated. |
| `spam` | Strongest signal points to spam/promo (templated text, generic praise). |
| `coordinated` | Belongs to a group acting together (shared text/timing/links, or a join-burst). |
| `low_confidence` | A score landed in the middle **and** there wasn't enough evidence to commit — judge manually. |

## Score & confidence

- **`score`** — aggregate suspicion in `0.0–1.0` (a weighted "noisy-OR" of all
  signals; higher = more suspicious). Thresholds: `< 0.25` → genuine,
  `≥ 0.5` → spam/coordinated/suspicious, in between → suspicious.
- **`confidence`** — `0.0–1.0`, how much evidence backed the call. Rises with the
  number of distinct signal families that weighed in and with how extreme the
  score is. Below ~`0.34` the item is labelled `low_confidence` regardless of
  score.
- **`confidence_band`** (page/follower level) — `high` (≥ 0.66), `medium`
  (≥ 0.4), or `low`, averaged across items.

Both thresholds live in [`smbd/config.py`](../smbd/config.py) and are tunable —
see [configuration.md](configuration.md).

## `smbd comments` (JSON)

```jsonc
{
  "question": "Are these comments real?",
  "total_comments": 15,
  "breakdown_pct": { "genuine": 46.7, "suspicious": 0.0, "spam": 0.0,
                     "coordinated": 53.3, "low_confidence": 0.0 },
  "summary": "47% of comments look genuine; 53% show signs of ...",
  "results": [
    {
      "comment_id": "c6", "account_id": "...", "handle": "grow_fast_77421",
      "text": "...", "score": 1.0, "label": "coordinated", "confidence": 1.0,
      "signals": [ /* see "Signals & evidence" below */ ]
    }
  ]
}
```

## `smbd followers` (JSON)

```jsonc
{
  "question": "Are these followers real people?",
  "total_followers": 15,
  "follower_quality_score": 47.3,        // 0-100, 100 = all look real
  "confidence_band": "high",
  "likely_fake_count": 8,
  "likely_fake_pct": 53.3,               // labelled suspicious/spam/coordinated
  "breakdown_pct": { ... },
  "suspicious_clusters": [
    { "window_start": "2026-05-29T03:00:01", "window_end": "...",
      "size": 8, "account_ids": ["b1", "b2", ...] }   // a join-burst
  ],
  "top_suspicious": [
    { "handle": "user8830192", "account_id": "b1", "label": "coordinated",
      "score": 0.99, "account_created_at": "2026-05-20T00:00:00",
      "followers_count": 3, "has_avatar": false,
      "reasons": ["abnormal_follow_ratio", "coordinated_follow_burst",
                  "weak_or_new_profile"] }
  ],
  "summary": "Follower quality 47/100. About 53% ..."
}
```

## `smbd page` (JSON)

```jsonc
{
  "amplification": {
    "question": "Is this page being attacked or artificially amplified?",
    "amplification_detected": true,
    "coordinated_groups": [
      { "account_ids": [...], "size": 8,
        "link_types": ["shared_burst", "shared_text", "shared_url"],
        "cohesion": 0.32 }              // realized/possible edges in the group
    ],
    "repeated_text_clusters": [
      { "sample_text": "...", "cluster_size": 5, "distinct_accounts": 5 }
    ],
    "timing_bursts": [
      { "window_start": "...", "window_seconds": 20.0, "events_in_window": 8 }
    ]
  },
  "authenticity": {
    "question": "Can I trust this influencer/page?",
    "authenticity_score": 46.0,         // 0-100, 100 = fully authentic
    "confidence_band": "high",
    "based_on_comments": 15
  }
}
```

`cohesion` distinguishes a tight clique (everyone linked to everyone, ~1.0) from
a loose chain. With the `[graph]` extra, large groups also carry a
`subcommunity_count` (distinct sub-rings).

## `smbd explain` (always JSON)

```jsonc
{
  "question": "Why did the model flag this account/comment?",
  "comment_id": "c6", "label": "coordinated", "score": 1.0, "confidence": 1.0,
  "evidence": [ /* the signals below, flattened */ ],
  "narration": "Flagged as coordinated because the same or near-identical text
                appears across many accounts; ..."
}
```

## Signals & evidence

Each detector emits a `Signal` with a `score`, a `weight`, and an `evidence`
dict. The evidence is the *why* — here's what each signal carries:

| Signal | `reason` | Key evidence fields |
| --- | --- | --- |
| `duplicate_text` | `duplicate_or_templated_text` | `cluster_size`, `distinct_accounts`, `sample_text`, `sibling_comment_ids` |
| `timing_burst` | `synchronized_timing_burst` | `window_start`, `window_end`, `window_seconds`, `events_in_window` |
| `coordination` | `coordinated_behavior_cluster` | `group_size`, `link_types`, `cohesion`, `group_account_ids`, `subcommunity_count`* |
| `account_weakness` | `weak_or_new_profile` | `attributes` (e.g. `new_account(9d)`, `no_avatar`, `empty_bio`, `auto_generated_handle`), `handle` |
| `ratio_anomaly` | `abnormal_follow_ratio` | `following`, `followers`, `ratio`, `threshold` |
| `follow_burst` | `coordinated_follow_burst` | `window_start`, `window_end`, `cluster_size`, `member_account_ids` |
| `llm_text_judgment` | `llm_language_judgment` | `classification`, `rationale`, `model` |

\* `subcommunity_count` only appears for large groups when the `[graph]` extra is
installed.

`link_types` on a coordination signal tell you *how* the accounts are connected:
`shared_text` (near-duplicate wording), `shared_burst` (posted in the same timing
window), `shared_url` (posted the same link, even with different wording).
