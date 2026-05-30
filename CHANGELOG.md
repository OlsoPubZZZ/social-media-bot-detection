# Changelog

All notable changes to SMBD are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/) once it reaches 1.0.

## [Unreleased]

### Added
- **Meta data-export import**: drop your Instagram (`followers_1.json` /
  `following.json`) or Facebook (`friends_v2` / `followers_v2`) "Download Your
  Information" JSON straight into the Followers tab — it auto-detects the format
  and maps handles + follow timestamps (so bought-follower bursts surface). The
  legitimate way to analyze your own network; SMBD does not scrape login-walled
  follower lists.
- **Plain-language web UI** for non-technical users: "We checked N comments/
  followers", a friendly donut of *real people vs fake/bot/spam*, everyday
  reasons instead of signal names, and an optional **AI explanation** card.
- **"Browse a page" workflow** (experimental, opt-in `browser` extra): a
  headless-browser (Playwright) reader that renders a **public** page, extracts
  the visible text (AI-assisted when a key is provided), and runs it through the
  engine — shown with a screenshot of what was read. It does **not** log in,
  store credentials, bypass access controls, or scrape platform-specific data.
  Plus `BrowserProvider` in `smbd.providers.browser`.

- **Local web UI** (`smbd serve`, the `web` extra): a FastAPI app + dependency-free
  HTML/JS frontend over the engine. Bring-your-own-key, local-first — keys are
  sent per request and never stored. Comments / followers / page tabs, with
  click-to-expand evidence. See `docs/web.md`.
- **Provider plugin interface** (`smbd.providers.registry`): load external
  providers via an `smbd.providers` entry point or a `package.module:Class`
  path (`--provider`). This is the **scraper plugin interface** — SMBD ships no
  scraper; see `docs/extending.md`.
- Full documentation set under `docs/` (installation, usage, web, providers,
  output reference, configuration, library API, extending, FAQ), CHANGELOG,
  SECURITY, CODE_OF_CONDUCT, issue/PR templates, and a CI workflow.

## [0.5.0] — 2026-05-30

### Added
- **X (Twitter) provider** (`smbd.providers.x`): comments (conversation replies),
  the official **follower list with profiles**, and page/user metadata. The only
  adapter that can feed the follower engine an official follower source.
- **Community detection** (`smbd.community`): splits large coordinated groups into
  sub-rings via networkx modularity (optional `[graph]` extra), with a stdlib
  connected-components fallback. Surfaced as `subcommunity_count`.
- `--provider x` on `comments`/`page`/`followers`.

### Changed
- Bumped to 0.5.0; added the `[graph]` extra; removed the unused
  `instagram`/`requests` extra (providers use stdlib `urllib`).

## [0.4.0] — 2026-05-30

### Added
- **YouTube provider** (`smbd.providers.youtube`): comments on any public video,
  with optional `--enrich-authors` to fetch commenter channel age/subscriber/video
  counts. Channel metadata via `fetch_page`.
- Coordination graph: **shared-URL edges** (link accounts posting the same link
  with different wording) and a per-group **cohesion** score.
- `--provider youtube` on the CLI.

## [0.3.0] — 2026-05-30

### Added
- **Follower analysis engine** (`smbd.followers`): follower quality score,
  likely-fake estimate, and suspicious **join-burst clusters**, with per-follower
  evidence (account age, avatar, follow ratio).
- **Instagram provider** (`smbd.providers.instagram`): comments on owned media and
  page metadata via the Graph API. `fetch_followers` raises with an explanation —
  the API does not expose follower profiles.
- `ImportProvider.fetch_followers` (CSV/JSON) and the `smbd followers` command.

## [0.2.0] — 2026-05-29

### Added
- **Optional LLM enrichment** (`smbd.llm`): a provider-agnostic client (Anthropic
  default) that routes only **ambiguous** comments to a batched, prompt-cached
  judge and re-scores them. AI-written narration for `smbd explain`. Gated behind
  `--llm` and the `llm` extra; the engine runs fully without it.

## [0.1.0] — 2026-05-29

### Added
- Core engine: normalized schema, pluggable provider interface, CSV/JSON importer.
- Detectors: duplicate/templated text, timing bursts, coordination graph, account
  weakness, follow-ratio anomaly — each emitting structured evidence.
- Weighted noisy-OR scoring with calibrated labels and confidence bands.
- Reports: comments breakdown, page amplification, authenticity score, and
  per-item `explain`.
- CLI (`smbd comments | page | explain`) and a synthetic example dataset.

[Unreleased]: https://github.com/OlsoPubZZZ/social-media-bot-detection/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/OlsoPubZZZ/social-media-bot-detection/releases/tag/v0.5.0
