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
smbd comments examples/sample_comments.csv      # the % breakdown + top flagged
smbd page     examples/sample_comments.csv      # amplification + authenticity
smbd explain  examples/sample_comments.csv c6   # why comment c6 was flagged
smbd comments examples/sample_comments.csv --json   # machine-readable output
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
**coordination graph**, **account weakness**, **follow-ratio anomaly**.
Weights and thresholds live in [`smbd/config.py`](smbd/config.py) and can be
overridden with `--config cfg.json`.

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
- [ ] **M3** — Instagram Graph adapter (owned pages only — see note below)
- [ ] **M4** — follower analysis + richer coordination graph
- [ ] **M5** — YouTube & X adapters
- [ ] **M6** — optional scraper extra + web UI

### A note on Instagram

Instagram's Graph API only exposes comments/followers for pages **you own or
manage**. Analyzing an arbitrary third-party page through official channels is
not possible — for those, use the import provider with data you legitimately
have. The scraper extra (when added) carries ToS/legal risk and is opt-in.

## License

Apache-2.0. See [LICENSE](LICENSE). Contributions welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md).
