# Providers & API keys

A **provider** is a data source. They all normalize into the same schema, so the
detection engine and reports are identical no matter where the data came from.

| Provider | `--provider` | Comments | Followers | Page metadata | Credential |
| --- | --- | --- | --- | --- | --- |
| Import | `import` (default) | ✅ | ✅ | — | none |
| YouTube | `youtube` | ✅ any public video | ❌ (API hides subscribers) | ✅ channel | free API key |
| X (Twitter) | `x` | ✅ replies | ✅ official list | ✅ user | paid bearer token |
| Instagram | _(library only)_ | ✅ your own media | ❌ (API hides followers) | ✅ counts | Graph API token |

> **Why followers are hard.** Of the major platforms, only **X** exposes a
> follower list with profiles through its official API. Instagram and YouTube
> deliberately don't. So for those, follower-quality analysis runs on data you
> **import** (an export you have, or — later — the opt-in scraper extra). This
> isn't a SMBD limitation; it's a platform-policy reality, and it's the reason
> the engine is decoupled from ingestion.

---

## Import (default — no credentials)

The zero-setup path: feed SMBD any CSV/JSON you legitimately have.

```bash
smbd comments  data/comments.csv
smbd followers data/followers.csv
```

Column/key reference and parsing rules: **[usage.md → Input formats](usage.md#input-formats)**.

From Python: `ImportProvider().fetch_comments(path)` /
`.fetch_followers(path)` — see [library.md](library.md).

---

## YouTube

YouTube's Data API v3 returns **public comments on any public video** — the
easiest way to analyze third-party content.

### Get a key

1. Create a project at <https://console.cloud.google.com/>.
2. Enable **YouTube Data API v3**.
3. Create an **API key** under *APIs & Services → Credentials*.
4. `export YOUTUBE_API_KEY=AIza...` (or pass `--api-key`).

### Use it

```bash
smbd comments <video_id> --provider youtube
smbd comments <video_id> --provider youtube --enrich-authors
smbd page     <channel_id> --provider youtube
```

The video id is the `v=` part of a watch URL
(`youtube.com/watch?v=dQw4w9WgXcQ` → `dQw4w9WgXcQ`).

`--enrich-authors` makes a second, **batched** call (`channels.list`, 50 ids at a
time) to fetch each commenter's **channel creation date, subscriber count, and
video count** — this is what lets the account-age and profile-weakness detectors
fire on YouTube comments. It costs extra quota, so it's opt-in.

### Limits & gotchas

- The API never exposes a channel's **subscriber identities** (only the
  authorized user's own subscriptions, with consent) → `fetch_followers` raises.
  Analyze followers via import instead.
- The free quota is generous for occasional analysis but finite; heavy use needs
  a quota increase.
- Comments come with an avatar URL (→ `has_avatar`) but no following count, so
  the follow-ratio signal abstains on YouTube data.

---

## X (Twitter)

X API v2. The **only** adapter that can fetch a real follower list with
profiles — so it's the one platform where the follower engine has an official
source.

### Get a token

1. Apply for access at <https://developer.x.com/> (a **paid** tier is required
   for meaningful read access).
2. Create an app and copy its **App-only Bearer Token**.
3. `export X_BEARER_TOKEN=AAAA...` (or pass `--api-key`).

### Use it

```bash
smbd comments  <tweet_id> --provider x      # replies in the conversation
smbd followers <user_id>  --provider x      # follower quality on official data
smbd page      <user_id>  --provider x      # account metadata (id or @username)
```

### Limits & gotchas

- X's API is **paid and rate-limited** — plan calls accordingly.
- Reply search (`conversation_id:`) on standard access covers roughly the
  **last 7 days**; older conversations need higher tiers.
- The followers endpoint gives **no "followed at" timestamp**, so the join-burst
  detector abstains on X follower data. Profile-weakness and follow-ratio signals
  still fire.
- Default-avatar accounts are detected (the placeholder `default_profile` image
  URL → `has_avatar: false`).

---

## Instagram

The official Graph API only works for accounts **you own or manage**, and even
then it exposes **comments on your own media** and your account's follower
**count** — but **never** a list of individual followers or any follower's
creation date, follower count, or profile photo.

So `InstagramProvider` supports `fetch_comments` and `fetch_page`;
`fetch_followers` raises with this explanation. There is currently no CLI flag —
use it from Python:

```python
from smbd.providers.instagram import InstagramProvider
from smbd.scoring import analyze_comments
from smbd.report import comments_report

ig = InstagramProvider(access_token="...")        # token for an account you manage
comments = ig.fetch_comments("<your-media-id>")   # comments on your own post
print(comments_report(analyze_comments(comments))["breakdown_pct"])
```

To analyze follower quality for an Instagram page, export/import the follower
data you have and use the import provider.

---

## A scraper?

A scraper would unlock follower/comment data for arbitrary third-party pages, but
scraping **violates most platforms' terms of service**, is fragile, and risks IP
or account bans. It is **not** part of SMBD today. It is planned only as a
clearly-marked, **opt-in** extra (roadmap M6) so the default install stays within
platform rules. Use official adapters and imports for anything you publish or rely
on.

---

## Writing your own provider

Subclass [`Provider`](../smbd/providers/base.py), map the platform payload into
the [normalized schema](../smbd/schema.py) (fill what you can, leave the rest
`None`), and put network providers behind an optional extra tested with recorded
fixtures. Full how-to in [CONTRIBUTING.md](../CONTRIBUTING.md).
