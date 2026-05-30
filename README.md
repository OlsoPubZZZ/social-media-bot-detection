# SMBD — Social Media Bot Detection Tool

[![CI](https://github.com/OlsoPubZZZ/social-media-bot-detection/actions/workflows/tests.yml/badge.svg)](https://github.com/OlsoPubZZZ/social-media-bot-detection/actions/workflows/tests.yml)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/core%20deps-0-success)

**Find out how much of a page's engagement is real.** SMBD analyzes social media
comments and followers and tells you how much is **genuine** vs.
**fake / bot / spam / coordinated** — with **evidence for every flag**.

It runs with **no credentials** on any data you can export to a CSV/JSON, and
ships with adapters for **YouTube, X (Twitter), and Instagram**. An optional AI
key adds richer language analysis.

> Detection is **probabilistic**. SMBD reports *signals* and *confidence bands*,
> not verdicts. Treat results as evidence to review — never as proof that a
> specific person is a bot. See [Responsible use](docs/faq.md).

---

## What it answers

| You ask | SMBD returns |
| --- | --- |
| Are these comments real? | % genuine / suspicious / spam / coordinated / low-confidence |
| Are these followers real people? | follower quality score, likely-fake %, suspicious join-burst clusters, per-follower evidence |
| Is this page being amplified or attacked? | coordinated groups, repeated-text clusters, timing bursts, group cohesion |
| Can I trust this page/influencer? | authenticity score (0–100) + confidence band |
| Why was this flagged? | structured evidence + plain-English explanation per item |

## Install

```bash
git clone https://github.com/OlsoPubZZZ/social-media-bot-detection.git
cd social-media-bot-detection
pip install -e ".[cli]"      # the engine + pretty CLI tables
```

The core has **zero runtime dependencies**. Optional extras add features:
`llm` (AI enrichment), `graph` (community detection), `dev` (tests). Full matrix
in **[docs/installation.md](docs/installation.md)**.

## 60-second quickstart (no keys needed)

```bash
smbd comments  examples/sample_comments.csv     # % breakdown + top flagged
smbd followers examples/sample_followers.csv    # follower quality + fake-likely + clusters
smbd page      examples/sample_comments.csv     # amplification + authenticity
smbd explain   examples/sample_comments.csv c6  # why comment c6 was flagged
smbd comments  examples/sample_comments.csv --json   # machine-readable
```

### What you get

```
$ smbd comments examples/sample_comments.csv
 Are these comments real?
  genuine           46.7%
  coordinated       53.3%
  ...
15 comments analyzed
47% of comments look genuine; 53% show signs of spam, coordination, or
suspicious authorship; 0% lacked enough data to judge.

Top flagged comments:
  [1.00] coordinated  @grow_fast_77421: Check out my page for free followers...
  [1.00] coordinated  @boost_now_44521: DM me to grow your account fast 💯💯 link in bio
  ...
```

```
$ smbd explain examples/sample_comments.csv c6
label: coordinated | score: 1.0 | confidence: 1.0
evidence: duplicate_text, timing_burst, coordination, account_weakness, ratio_anomaly
"Flagged as coordinated because the same or near-identical text appears across
many accounts; it was posted inside a synchronized burst of activity; its author
belongs to a group acting in a coordinated way; the author's profile is new or
weak; the author follows far more accounts than follow it back."
```

→ Full walkthrough: **[docs/usage.md](docs/usage.md)** · Reading the output:
**[docs/output-reference.md](docs/output-reference.md)**

## Web UI

Prefer clicking to typing? There's a local web app — the "plug in your key and
go" experience over the same engine:

```bash
pip install -e ".[cli,web]"
smbd serve                      # → http://127.0.0.1:8000
```

Paste/upload data or pull from YouTube/X, see the breakdown and scores, and click
any flagged row for its evidence. It's **local and bring-your-own-key** — keys are
sent per request and never stored. Details: **[docs/web.md](docs/web.md)**.

## Platforms at a glance

| Source | Comments | Followers | What you need |
| --- | --- | --- | --- |
| **Import** (CSV/JSON) | ✅ | ✅ | nothing — any data you can export |
| **YouTube** | ✅ any public video | — (API hides subscribers) | free API key |
| **X (Twitter)** | ✅ replies | ✅ official follower list | paid bearer token |
| **Instagram** | ✅ your own media | — (API hides followers) | Graph API token (owned account) |

Per-platform setup, API keys, and limits: **[docs/providers.md](docs/providers.md)**.

> **The honest constraint:** getting follower-level data is harder than analyzing
> it. Instagram and YouTube don't expose follower profiles via their APIs; X
> does. For everything else, the engine runs on data you export or import — which
> is exactly why it's platform-agnostic.

## How it works

```
data → provider adapter → normalized schema → feature extractors
     → detectors (each emits a Signal + evidence) → scoring → reports
                                                  ↘ optional LLM enrichment
```

Signals: **duplicate/templated text**, **timing bursts**, **coordination graph**
(shared text / timing / URL edges + cohesion + optional community detection),
**account weakness** (age, avatar, bio, handle), **follow-ratio anomaly**, and
**coordinated follower join-bursts**. Each emits structured evidence; weights and
thresholds are tunable in [`smbd/config.py`](smbd/config.py) — see
**[docs/configuration.md](docs/configuration.md)**.

## Documentation

| Guide | What's in it |
| --- | --- |
| [Installation](docs/installation.md) | Python versions, extras matrix, troubleshooting |
| [Usage guide](docs/usage.md) | Every command, flags, input formats, examples |
| [Web UI](docs/web.md) | Running the local `smbd serve` app |
| [Providers & API keys](docs/providers.md) | YouTube / X / Instagram setup, limits, gotchas |
| [Output reference](docs/output-reference.md) | Labels, scores, confidence, every JSON field |
| [Configuration](docs/configuration.md) | Tuning weights and thresholds |
| [Library API](docs/library.md) | Using SMBD from Python |
| [Extending](docs/extending.md) | External providers + the scraper plugin interface |
| [FAQ & responsible use](docs/faq.md) | Accuracy, false positives, legality, limits |
| [Contributing](CONTRIBUTING.md) | Add a detector or a data source |
| [Security policy](SECURITY.md) | Reporting vulnerabilities, secrets handling |
| [Code of conduct](CODE_OF_CONDUCT.md) | Community standards |
| [Changelog](CHANGELOG.md) | Release history |

## Roadmap

- [x] **M1–M5** — core engine, comments/followers/amplification/authenticity,
  LLM enrichment, Instagram + YouTube + X adapters, community detection
- [x] **M6** — local web UI (`smbd serve`) + a documented scraper [plugin
  interface](docs/extending.md) (SMBD ships no scraper)

## Responsible use

SMBD is a **transparency tool**. Outputs are probabilistic signals with
confidence bands, not accusations. Official adapters only access data you're
authorized for; any scraping lives behind a clearly-marked opt-in extra. Don't
use SMBD to harass, deplatform, or make automated decisions about individuals.
See **[docs/faq.md](docs/faq.md)**.

## License

[Apache-2.0](LICENSE). Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
