# Installation

SMBD is a Python package. It needs **Python 3.9 or newer** and nothing else for
the core engine.

## Quick install (from source)

```bash
git clone https://github.com/OlsoPubZZZ/social-media-bot-detection.git
cd social-media-bot-detection
pip install -e ".[cli]"
```

`-e` (editable) is recommended while SMBD is pre-1.0 so you can pull updates with
`git pull` without reinstalling. Drop `-e` for a normal install.

Verify it works:

```bash
smbd comments examples/sample_comments.csv
```

You should see a labelled breakdown table. If `smbd` isn't found, see
[Troubleshooting](#troubleshooting).

## Extras matrix

Install only what you need — the core stays dependency-free.

| Extra | Command | Adds | When you need it |
| --- | --- | --- | --- |
| _(none)_ | `pip install -e .` | the engine + library + CLI (plain text output) | always |
| `cli` | `pip install -e ".[cli]"` | `rich` — pretty colour tables | nicer CLI output |
| `llm` | `pip install -e ".[llm]"` | `anthropic` SDK | `--llm` AI enrichment |
| `graph` | `pip install -e ".[graph]"` | `networkx` | modularity community detection |
| `web` | `pip install -e ".[web]"` | `fastapi`, `uvicorn` | the local web app (`smbd serve`) |
| `browser` | `pip install -e ".[browser]"` | `playwright` | the experimental "Browse a page" reader¹ |
| `dev` | `pip install -e ".[dev]"` | `pytest`, `rich`, `networkx`, `fastapi`, … | running the test suite |

¹ The browser reader also needs a one-time browser download: `python -m playwright install chromium`.

Combine them with commas:

```bash
pip install -e ".[cli,llm,graph]"     # everything a user might want
pip install -e ".[cli,dev]"           # for contributors
```

> The CLI works **without** the `cli` extra — it just falls back to plain-text
> output instead of colour tables.

## A note on virtual environments

A virtualenv keeps SMBD's (few) dependencies isolated:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[cli]"
```

## Run the tests

```bash
pip install -e ".[cli,dev]"
pytest -q
```

All tests run **offline** with no credentials or API keys (network providers are
tested against recorded fixtures). One live LLM test is skipped unless you set
`SMBD_LIVE_LLM=1` and `ANTHROPIC_API_KEY`.

## API keys (optional)

Only needed for the online providers and AI enrichment. Set them as environment
variables; SMBD never stores them.

```bash
export YOUTUBE_API_KEY=AIza...        # YouTube provider
export X_BEARER_TOKEN=AAAA...         # X provider
export ANTHROPIC_API_KEY=sk-ant-...   # --llm enrichment
```

See **[providers.md](providers.md)** for how to obtain each one.

## Troubleshooting

**`smbd: command not found`** — the script installed to a directory not on your
`PATH` (common with `pip install --user`). Either activate a virtualenv (above)
or run the module form: `python -m smbd.cli comments ...`.

**`No module named smbd`** — you're not in the environment where you installed
it. Re-activate your virtualenv, or reinstall.

**Output is plain text, not colour tables** — install the `cli` extra
(`pip install -e ".[cli]"`). This is cosmetic only.

**`--llm` errors with "requires the 'anthropic' package"** — install the `llm`
extra and set `ANTHROPIC_API_KEY`.
