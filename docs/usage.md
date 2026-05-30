# Usage guide

SMBD has four commands. All of them read data, run the detection engine, and
print a report (human-readable by default, `--json` for machines).

```
smbd comments  <data>           # "Are these comments real?"
smbd followers <data>           # "Are these followers real people?"
smbd page      <data>           # "Is this page amplified/attacked?" + trust score
smbd explain   <data> <id>      # "Why was this one flagged?"
```

`<data>` is a file path by default, or a video/tweet/user id when you pass
`--provider youtube|x`. See [providers.md](providers.md).

---

## `smbd comments`

Classifies every comment as genuine / suspicious / spam / coordinated /
low-confidence and lists the worst offenders.

```bash
smbd comments examples/sample_comments.csv
smbd comments examples/sample_comments.csv --json
```

```
 Are these comments real?
  genuine           46.7%
  suspicious         0.0%
  spam               0.0%
  coordinated       53.3%
  low_confidence     0.0%
15 comments analyzed
47% of comments look genuine; 53% show signs of spam, coordination, or
suspicious authorship; 0% lacked enough data to judge.

Top flagged comments:
  [1.00] coordinated  @grow_fast_77421: Check out my page for free followers...
  [1.00] coordinated  @boost_now_44521: DM me to grow your account fast 💯💯 link in bio
```

**Flags:** `--json`, `--config`, `--provider`, `--api-key`, `--enrich-authors`,
and the LLM flags (below).

## `smbd followers`

Scores each follower's account and reports a quality score (0–100), a
likely-fake estimate, and suspicious **join-burst clusters** (accounts that
started following within a tight window — a hallmark of purchased followers).

```bash
smbd followers examples/sample_followers.csv
smbd followers examples/sample_followers.csv --json
smbd followers <user_id> --provider x      # official follower data from X
```

```
 Are these followers real people?
  genuine           46.7%
  coordinated       53.3%
Follower quality: 47.3/100 (confidence: high)  |  likely-fake: 53.3% (8/15)
⚠ 1 coordinated join-burst cluster(s): 8 accounts @ 2026-05-29T03:00:01
 Most suspicious followers (showing 8)
  Score  Label        Handle        Created     Avatar  Reasons
  0.99   coordinated  user8830192   2026-05-20  no      abnormal_follow_ratio,
                                                        coordinated_follow_burst,
                                                        weak_or_new_profile
```

Per-follower signals: **new/weak profile** (account age, missing avatar, empty
bio, no posts, auto-generated handle), **abnormal follow ratio**, and
**coordinated join-burst** membership.

**Analyze your own Instagram/Facebook network:** download your data from the
platform (*Settings → Download Your Information* → **JSON**) and pass the file
straight in — SMBD auto-detects the export format:

```bash
smbd followers ~/instagram_export/followers_1.json   # or facebook friends.json
```

Instagram exports include the **time you were followed**, so coordinated
bought-follower bursts show up. (Exports don't include each follower's age,
avatar, or counts — Meta doesn't provide those — so only the handle-pattern and
join-burst signals fire. There's no legitimate way to get a *third party's*
follower list; see [providers.md](providers.md).)

**Flags:** `--json`, `--config`, `--provider {import,x}`, `--api-key`.

## `smbd page`

The page-level view: amplification (coordinated groups, repeated-text clusters,
timing bursts, cohesion) plus an overall authenticity score.

```bash
smbd page examples/sample_comments.csv
smbd page examples/sample_comments.csv --json
smbd page <channel_id> --provider youtube
```

```
⚠ Amplification detected: 1 coordinated group(s), 2 repeated-text cluster(s),
  1 timing burst(s).
  • group of 8 accounts via shared_burst, shared_text, shared_url

Authenticity score: 46.0/100 (confidence: high)
```

## `smbd explain`

Full evidence for a single item, always as JSON. Pass the comment id (the `id`
column, or the `c0`, `c1`… fallback ids).

```bash
smbd explain examples/sample_comments.csv c6
smbd explain examples/sample_comments.csv c6 --llm   # AI-written narration
```

```json
{
  "label": "coordinated",
  "score": 1.0,
  "confidence": 1.0,
  "evidence": [
    {"signal": "duplicate_text", "score": 0.9, "cluster_size": 5, ...},
    {"signal": "ratio_anomaly", "score": 1.0, "following": 1900, "followers": 3, ...}
  ],
  "narration": "Flagged as coordinated because the same or near-identical text
                appears across many accounts; ..."
}
```

Every field is documented in **[output-reference.md](output-reference.md)**.

---

## Input formats

Any **CSV or JSON** works. For comments, the only required field is `text`; for
followers, just an account identifier. Richer columns unlock more signals.

### Comment columns / keys

```
comment_id, text, created_at, likes, parent_id, post_id, lang,
account_id, handle, display_name, account_created_at,
followers_count, following_count, post_count, bio, has_avatar,
is_verified, external_url
```

### Follower columns / keys

The same account fields as above, plus `followed_at` (when they started
following — enables join-burst detection).

Alternatively, feed a **Facebook/Instagram "Download Your Information" JSON**
file as-is — SMBD recognizes the Instagram (`relationships_followers` /
`relationships_following`) and Facebook (`friends_v2` / `followers_v2`) shapes
and maps each entry's handle/name + follow timestamp automatically.

### Formats and parsing

- **CSV:** a header row with any subset of the names above.
- **JSON:** a top-level array of objects, an object with a `"comments"` /
  `"followers"` key, **or** a Facebook/Instagram export file (auto-detected).
- **Timestamps** (`created_at`, `account_created_at`, `followed_at`): ISO-8601
  (`2026-05-01T12:00:00`, trailing `Z` ok) or epoch seconds.
- **Booleans** (`has_avatar`, `is_verified`): `true/false`, `1/0`, `yes/no`.
- **Missing data → the detector abstains.** No `created_at` means the
  account-age and burst signals simply don't fire for that row — SMBD never
  guesses.

Minimal CSV example:

```csv
text,handle,account_created_at,followers_count,following_count,has_avatar
"love this!",realjane,2018-04-01,820,310,true
"DM me for free followers bit.ly/x",grow_4821,2026-05-20,2,4000,false
```

---

## Optional flags (all commands that read comments)

| Flag | Effect |
| --- | --- |
| `--json` | Emit machine-readable JSON instead of tables |
| `--config cfg.json` | Override detection weights/thresholds ([configuration.md](configuration.md)) |
| `--provider {import,youtube,x}` | Choose the data source (default `import`) |
| `--api-key KEY` | API key / bearer token (or use env vars) |
| `--enrich-authors` | (YouTube) fetch each commenter's channel age + subscriber counts |
| `--llm` | Send ambiguous comments to an AI model for a second opinion |
| `--llm-model MODEL` | Override the model (default `claude-opus-4-8`; Haiku is cheaper) |
| `--llm-max-items N` | Cap how many ambiguous comments are sent to the LLM |

## LLM enrichment (optional)

With the `llm` extra and an `ANTHROPIC_API_KEY`, `--llm` sends only the
**ambiguous** comments (borderline / low-confidence / suspicious) to an AI model
in one batched, prompt-cached call — clear-genuine and clear-spam comments are
never sent, so cost stays low. The model's judgment becomes an
`llm_text_judgment` signal and the comment is re-scored.

```bash
pip install -e ".[cli,llm]"
export ANTHROPIC_API_KEY=sk-ant-...
smbd comments examples/sample_comments.csv --llm
smbd comments examples/sample_comments.csv --llm --llm-model claude-haiku-4-5
```

The engine runs fully without any of this — the LLM only adds language nuance and
nicer explanations.

---

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `2` | Bad input, missing data, missing API key, or a provider error (message on stderr) |
