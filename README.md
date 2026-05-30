# SMBD — Social Media Bot Detection Tool

Analyze social media engagement — comments, followers, amplification — and find
out how much is **genuine** vs. **fake / bot / coordinated**, with
human-readable **evidence for every flag**.

The detection engine is **platform-agnostic** and runs with **no credentials
and no AI key**. You feed it data (a CSV/JSON export, an API pull, pasted rows)
and it returns scored, explained results. An optional AI key adds richer
language analysis and natural-language explanations.

> ⚠️ Detection is **probabilistic**. SMBD reports *signals* and *confidence*, not
> verdicts. Treat outputs as evidence to review, never as proof that a specific
> person is a bot.

## What it answers

| You ask | SMBD returns |
| --- | --- |
| Are these comments real? | % genuine / suspicious / spam / coordinated / low-confidence |
| Are these followers real people? | follower quality score, likely-fake estimate, suspicious join-burst clusters, per-follower evidence (account age, avatar, follow ratio) |
| Is this page being amplified or attacked? | coordinated groups, repeated-text clusters, timing bursts |
| Can I trust this page/influencer? | authenticity score (0–100) + confidence band |
| Why was this flagged? | structured evidence + plain-English narration per item |

## Install

```bash
pip install -e ".[cli,dev]"     # editable install with CLI table output + tests
```

Core has **zero runtime dependencies**; `rich` (the `cli` extra) only makes
output prettier.

## Quick start (no keys needed)

```bash
smbd comments  examples/sample_comments.csv      # the % breakdown + top flagged
smbd followers examples/sample_followers.csv      # follower quality + fake-likely + clusters
smbd page      examples/sample_comments.csv       # amplification + authenticity
smbd explain   examples/sample_comments.csv c6    # why comment c6 was flagged
smbd comments  examples/sample_comments.csv --json   # machine-readable output
```

### As a library

```python
from smbd.providers.importer import ImportProvider
from smbd.scoring import analyze_comments
from smbd.report import comments_report, amplification_report

comments = ImportProvider().fetch_comments("examples/sample_comments.csv")
batch = analyze_comments(comments)

print(comments_report(batch)["breakdown_pct"])
print(amplification_report(batch)["coordinated_groups"])
```

## Input format

Any CSV/JSON with a `text` column is enough; richer columns unlock more signals.
Recognized fields (all optional except `text`):

```
comment_id, text, created_at, likes, parent_id, post_id, lang,
account_id, handle, display_name, account_created_at,
followers_count, following_count, post_count, bio, has_avatar,
is_verified, external_url
```

Detectors **abstain** on missing data rather than guess (no `created_at` → the
account-age and burst signals simply don't fire for that item).

## How it works

```
data → provider adapter → normalized schema → feature extractors
     → detectors (each emits a Signal + evidence) → scoring → reports
                                                  ↘ optional LLM enrichment
```

Detectors in v1: **duplicate/templated text**, **timing bursts**,
**coordination graph**, **account weakness**, **follow-ratio anomaly**, and
(for followers) **coordinated join-bursts**.
Weights and thresholds live in [`smbd/config.py`](smbd/config.py) and can be
overridden with `--config cfg.json`.

## Analyzing followers

`smbd followers <data>` scores each follower's account and reports a quality
score, a likely-fake estimate, and suspicious **join-burst clusters** (accounts
that all started following within a tight window — a hallmark of purchased
followers):

```bash
smbd followers examples/sample_followers.csv          # human-readable
smbd followers examples/sample_followers.csv --json   # machine-readable
```

Per-follower signals: **new/weak profile** (account age, missing avatar, empty
bio, no posts, auto-generated handle), **abnormal follow ratio**, and
**coordinated join-burst** membership. Follower rows accept the same account
columns as comments, plus `followed_at`.

```python
from smbd.providers.importer import ImportProvider
from smbd.followers import analyze_followers
from smbd.report import followers_report

followers = ImportProvider().fetch_followers("examples/sample_followers.csv")
print(followers_report(analyze_followers(followers))["summary"])
```

> **Where does follower data come from?** Instagram's official API does **not**
> expose individual followers or their profiles (creation date, follower count,
> avatar). So follower analysis runs on data you legitimately have (export/import)
> or the optional scraper plugin — not the official Instagram adapter. See below.

## Optional: LLM enrichment

Install the extra and set a key, then add `--llm` to any command:

```bash
pip install -e ".[cli,llm]"
export ANTHROPIC_API_KEY=sk-ant-...
smbd comments examples/sample_comments.csv --llm
smbd comments examples/sample_comments.csv --llm --llm-model claude-haiku-4-5   # cheaper
smbd explain  examples/sample_comments.csv c6 --llm                            # LLM-narrated evidence
```

Only **ambiguous** comments (borderline scores / low-confidence / suspicious) are
sent to the model, in one batched, prompt-cached call — clear-genuine and
clear-spam comments never are, so cost stays low. The judgment becomes an
`llm_text_judgment` signal and the comment is re-scored. The default model is
`claude-opus-4-8`; `--llm-model claude-haiku-4-5` is far cheaper for this task.
The engine runs fully without any of this.

## Roadmap

- [x] **M1** — core engine, CSV/JSON import, comments + amplification + authenticity, CLI
- [x] **M2** — optional LLM enrichment (ambiguous-text judgments, richer `explain`)
- [x] **M3** — follower analysis engine + Instagram Graph adapter (comments/page metadata)
- [ ] **M4** — richer coordination graph (community detection) + YouTube adapter
- [ ] **M5** — X adapter
- [ ] **M6** — optional scraper extra + web UI

### A note on Instagram

The official Instagram Graph API only works for accounts **you own or manage**,
and even then it exposes **comments on your own media** and your account's
**follower count** — but **never a list of individual followers** or any
follower's creation date, follower count, or profile photo. Instagram withholds
follower-level profiles by design.

So `InstagramProvider` ([`smbd/providers/instagram.py`](smbd/providers/instagram.py))
supports `fetch_comments` and `fetch_page` (counts); `fetch_followers` raises
with this explanation. To actually analyze follower *quality*, feed
`smbd.followers.analyze_followers` data you legitimately have via the import
provider, or (later) the opt-in scraper plugin, which carries ToS/legal risk.

```python
from smbd.providers.instagram import InstagramProvider
from smbd.scoring import analyze_comments

ig = InstagramProvider(access_token="...")        # token for an account you manage
comments = ig.fetch_comments("<your-media-id>")   # comments on your own post
batch = analyze_comments(comments)
```

## License

Apache-2.0. See [LICENSE](LICENSE). Contributions welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md).
