# FAQ & responsible use

## What is SMBD, in one line?

A transparency tool that estimates how much of a page's comments or followers are
fake/bot/coordinated, and **shows its evidence** for every flag.

## How accurate is it?

The detectors are **heuristics** — duplicate text, timing bursts, account-profile
weakness, follow-ratio anomalies, coordination graphs. On clear-cut cases (a
copy-paste spam ring, a batch of brand-new no-avatar accounts that all followed
within a minute) they're strong. On subtle cases they're uncertain, which is
exactly why every result carries a **confidence band** and ambiguous items can be
labelled `low_confidence`.

The default weights and thresholds are **calibrated on synthetic fixtures, not a
large labelled real-world dataset.** Treat the numbers as a well-reasoned
estimate, tune them for your context ([configuration.md](configuration.md)), and
verify before acting.

## Will it tell me "this account is definitely a bot"?

**No, by design.** SMBD reports *signals*, *scores*, and *confidence* — never a
verdict about a specific person. Even a high score means "these patterns are
consistent with inauthentic activity," not "this human is a bot." Use it to
prioritize review, not to make automated decisions about individuals.

## Why can't I just point it at any Instagram/TikTok page's followers?

Because the platforms don't let you. Instagram and YouTube's official APIs **do
not expose follower profiles**; X does (paid). This is a platform-policy reality,
not a SMBD limitation — and it's why the engine is decoupled from data ingestion
and works on imported data. See [providers.md](providers.md).

## Does it scrape?

No. SMBD ships with official-API adapters and a file importer only. Scraping
violates most platforms' terms, is fragile, and risks bans — it's planned solely
as a clearly-marked, **opt-in** extra (roadmap M6), never the default.

## What about false positives?

They happen — e.g. a fan account that follows thousands of pages, or a launch
where many genuine people comment near-simultaneously. Mitigations:

- The engine **abstains** on missing data instead of guessing.
- A single weak signal rarely crosses the `suspicious` threshold alone.
- `low_confidence` exists precisely to avoid over-committing on thin evidence.
- Always read the **evidence** (`smbd explain`) before treating a flag as real.

## Is this legal / privacy-safe to use?

You are responsible for how you obtain and use data. Use official adapters only
for data you're authorized to access, respect platform terms and rate limits, and
follow applicable privacy law (e.g. GDPR/CCPA) for any personal data you import.
SMBD stores nothing and sends nothing anywhere unless you explicitly enable
`--llm` (which sends only ambiguous comment text to your configured AI provider).

## Do I need an AI key?

No. The entire engine runs offline with zero credentials. An `ANTHROPIC_API_KEY`
only enables the optional `--llm` enrichment, which adds language nuance and
nicer explanations for borderline comments.

## Does it send my data anywhere?

Only if you opt in. Default and all official adapters run locally. With `--llm`,
the **text of ambiguous comments** (not your whole dataset) is sent to the AI
provider you configured, in a batched call. Nothing is persisted by SMBD.

## How do I make it better for my platform?

Tune a [config](configuration.md) and, ideally, contribute it back. New detectors
and providers are designed to be easy and isolated — see
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Responsible-use summary

- Outputs are **probabilistic evidence**, not proof or accusations.
- Don't use SMBD to harass, dox, mass-report, or auto-deplatform people.
- Disclose when you're presenting SMBD results, and show the confidence band.
- Respect platform terms and people's privacy.
