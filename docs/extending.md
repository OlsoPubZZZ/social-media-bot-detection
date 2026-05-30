# Extending SMBD — providers & the scraper plugin interface

SMBD is built so the two most valuable contributions — **new data sources**
(providers) and **new signals** (detectors) — are easy and isolated. This page
covers loading *external* providers, including the **scraper plugin interface**.

For in-repo contributions (detectors, official providers), see
[CONTRIBUTING.md](../CONTRIBUTING.md).

## On scrapers — read this first

> **SMBD intentionally ships no scraper.** Scraping social platforms generally
> **violates their Terms of Service**, is legally risky (Instagram in particular
> has pursued scrapers), breaks whenever the site changes, and can get IPs or
> accounts banned. The official adapters (`youtube`, `x`, `instagram`) and the
> file `import` provider cover legitimate, authorized access.

What SMBD *does* provide is a clean **plugin interface** so that someone who has
decided — at their own risk and responsibility — to use scraped or otherwise
externally-acquired data can feed it through the same engine, **without that code
living in this repository**. If you build one, keep it in your own separate,
clearly-licensed, ToS-aware package.

## The provider contract

Any data source is a subclass of [`Provider`](../smbd/providers/base.py):

```python
from smbd.providers.base import Provider
from smbd.schema import Account, Comment, Follower

class MySource(Provider):
    name = "mysource"

    def fetch_comments(self, target: str) -> list[Comment]:
        ...   # map your payload into normalized Comment objects

    def fetch_followers(self, target: str) -> list[Follower]:   # optional
        ...
```

Map the platform payload into the [normalized schema](../smbd/schema.py) — fill
what you can, leave the rest `None`. Detectors **abstain** on missing fields, so
partial data still works. That's the entire contract.

## Plugging it in

Two ways to use an external provider with the SMBD CLI:

### 1. Dotted path (no registration)

```bash
smbd comments <target> --provider my_pkg.source:MySource
smbd followers <user> --provider my_pkg.source:MySource --api-key ...
```

### 2. Entry point (installable name)

In your package's `pyproject.toml`:

```toml
[project.entry-points."smbd.providers"]
mysource = "my_pkg.source:MySource"
```

After `pip install` of your package:

```bash
smbd comments <target> --provider mysource
```

SMBD discovers it via the `smbd.providers` entry-point group (see
[`smbd/providers/registry.py`](../smbd/providers/registry.py)). If `--api-key` is
given, SMBD tries `MySource(api_key=...)`, otherwise `MySource()` — so read your
own credentials from the environment if you prefer.

From Python you can also just import and use it directly — it's an ordinary
`Provider`:

```python
from smbd.scoring import analyze_comments
from my_pkg.source import MySource

batch = analyze_comments(MySource().fetch_comments("..."))
```

## Adding a detector (new signal)

New detectors live in-repo and are easy to add — see
[CONTRIBUTING.md](../CONTRIBUTING.md). The rules: subclass `Detector`, emit a
`Signal` with structured **evidence**, **abstain** on missing data, register a
default weight, and add a test that fires on the bot fixture and abstains on the
genuine one.
