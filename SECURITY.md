# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Instead, use
GitHub's private reporting:

1. Go to the repository's **Security** tab → **Report a vulnerability**
   (GitHub Private Vulnerability Reporting), or
2. Open a regular issue asking a maintainer to set up a private channel — without
   posting any sensitive detail.

We aim to acknowledge reports within a few days. Since this is a community
project, please be patient and avoid public disclosure until a fix is available.

## Scope

SMBD is a local analysis tool. The most relevant security concerns are:

- **Secrets handling.** SMBD reads API keys only from environment variables
  (`YOUTUBE_API_KEY`, `X_BEARER_TOKEN`, `ANTHROPIC_API_KEY`) or arguments you
  pass at call time. It never writes them to disk and never commits them. The
  repository contains **no credentials** (CI/history are scanned). If you find a
  secret committed anywhere, report it.
- **Data sent off-device.** By default everything runs locally. The only network
  calls are (a) the provider you explicitly choose (YouTube/X/Instagram) and
  (b) the optional `--llm` enrichment, which sends the text of *ambiguous*
  comments to the AI provider you configure. Nothing else leaves your machine.
- **Dependency safety.** The core has zero runtime dependencies; optional extras
  pull well-known packages (`rich`, `networkx`, `anthropic`).

## Good practices for users

- Keep API keys in environment variables or a secret manager — never in code,
  config files committed to git, or screenshots.
- On GitHub, enable **Settings → Emails → "Keep my email private"** and
  **"Block command line pushes that expose my email"** before committing.
- Treat SMBD output as probabilistic evidence, not proof — see
  [docs/faq.md](docs/faq.md) for responsible use.
