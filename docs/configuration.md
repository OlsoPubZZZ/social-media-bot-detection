# Configuration

Every detection weight and threshold lives in one place —
[`smbd/config.py`](../smbd/config.py) — so you can tune behavior without touching
detector logic. Override any subset with a JSON file via `--config`, or a
`Config` object from Python.

## Use a config file

```bash
smbd comments data.csv --config my_config.json
```

```jsonc
// my_config.json — only include what you want to change; the rest keep defaults
{
  "weights": { "account_weakness": 1.0, "ratio_anomaly": 0.9 },
  "extreme_follow_ratio": 10.0,
  "suspicious_at": 0.45
}
```

`weights` is **merged** into the defaults (you only list the ones you change);
all other keys replace the default value.

## From Python

```python
from smbd.config import Config
from smbd.scoring import analyze_comments

cfg = Config()
cfg.extreme_follow_ratio = 10.0
cfg.weights["coordination"] = 1.5
batch = analyze_comments(comments, config=cfg)

# or load a file:
cfg = Config.from_json("my_config.json")
```

## Reference

### Detector weights

How much each signal contributes to the aggregate suspicion score. Higher =
more influence.

| Key | Default |
| --- | --- |
| `duplicate_text` | 1.0 |
| `timing_burst` | 0.8 |
| `coordination` | 1.2 |
| `account_weakness` | 0.7 |
| `ratio_anomaly` | 0.6 |
| `follow_burst` | 1.1 |
| `llm_text_judgment` | 1.0 |

### Duplicate / templated text

| Key | Default | Meaning |
| --- | --- | --- |
| `duplicate_min_cluster` | 3 | Min accounts sharing (near-)identical text to form a cluster |
| `near_dup_max_hamming` | 6 | SimHash distance (of 64) below which two texts are "near-duplicate" |
| `duplicate_min_chars` | 4 | Ignore texts shorter than this (emoji-only, "nice", …) |

### Timing bursts (comments)

| Key | Default | Meaning |
| --- | --- | --- |
| `burst_window_seconds` | 60 | Sliding window size |
| `burst_rate_multiplier` | 4.0 | A window is a burst at ≥ this × the expected rate |
| `burst_min_events` | 5 | Minimum events in-window to count |

### Account weakness & follow ratio

| Key | Default | Meaning |
| --- | --- | --- |
| `new_account_days` | 30 | Accounts younger than this (vs. dataset's latest timestamp) are "new" |
| `extreme_follow_ratio` | 20.0 | following ÷ max(followers,1) at/above this is anomalous |
| `handle_digit_ratio` | 0.4 | Share of digits in a handle that reads as auto-generated |

### Coordination & community detection

| Key | Default | Meaning |
| --- | --- | --- |
| `coordination_min_group` | 3 | Min connected accounts to flag a coordinated group |
| `community_min_size` | 6 | Only run community detection on groups at least this big |

### Follower join-bursts

| Key | Default | Meaning |
| --- | --- | --- |
| `follow_burst_window_seconds` | 3600 | Join-burst window (wider than comments — mass-follows span minutes–hours) |
| `follow_burst_min_events` | 5 | Min follows in-window to count as a burst |

### Scoring thresholds

| Key | Default | Meaning |
| --- | --- | --- |
| `genuine_below` | 0.25 | Score below this → `genuine` |
| `suspicious_at` | 0.5 | Score at/above this → spam/coordinated/suspicious |
| `min_confidence_coverage` | 0.34 | Confidence below this → `low_confidence` regardless of score |

### LLM enrichment

| Key | Default | Meaning |
| --- | --- | --- |
| `llm_model` | `claude-opus-4-8` | Model for `--llm` (Haiku is far cheaper for this task) |
| `llm_max_items` | 25 | Max ambiguous comments sent to the LLM per run |
| `llm_max_tokens` | 2048 | Output token ceiling for the batched judge call |

## Tuning tips

- **Too many false positives?** Raise `genuine_below`/`suspicious_at`, or lower
  the weights of the signals doing the over-flagging. `extreme_follow_ratio` is
  often the lever for follower analysis.
- **Missing obvious rings?** Lower `coordination_min_group`, raise the
  `coordination` weight, or widen `near_dup_max_hamming` (more aggressive
  near-duplicate matching).
- **Different platform cadence?** Comment bursts on a fast-moving video differ
  from a slow forum — tune `burst_window_seconds` / `burst_rate_multiplier`.
- Share presets! A tuned `config.json` for a platform or use-case is a great
  contribution — see [CONTRIBUTING.md](../CONTRIBUTING.md).
