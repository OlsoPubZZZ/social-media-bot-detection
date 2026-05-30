# Web UI

SMBD ships a small local web app — the "plug in your key and go" experience over
the same engine the CLI uses.

## Run it

```bash
pip install -e ".[cli,web]"
smbd serve                       # → http://127.0.0.1:8000
smbd serve --host 0.0.0.0 --port 9000
```

Open the printed URL in your browser.

## What it does

- **Three tabs** — Comments, Followers, Page — mirroring the CLI commands.
- **Data sources** — paste/upload a CSV or JSON, or pull from **YouTube**
  (video id) or **X** (tweet/user id).
- **Results** — the genuine/suspicious/spam/coordinated breakdown, an
  authenticity or follower-quality score, amplification warnings and join-burst
  clusters, and a flagged table. **Click any flagged row** to expand its
  evidence and plain-English explanation.
- **Optional AI enrichment** — tick the box and paste an Anthropic key to send
  ambiguous comments to a model for a second opinion.

## Keys & privacy

The app is **bring-your-own-key and local-first**:

- It binds to `127.0.0.1` by default — only your machine can reach it.
- Any keys you enter (Anthropic / YouTube / X) are sent to the local backend
  **per request** and used only for that call. **Nothing is stored or logged.**
- Don't expose it to the public internet with real keys in the browser. If you
  must bind to `0.0.0.0`, put it behind your own auth/proxy.

## How it's built

A thin [FastAPI](https://fastapi.tiangolo.com/) app
([`smbd/web/app.py`](../smbd/web/app.py)) with a single `POST /api/analyze`
endpoint and a dependency-free HTML/JS frontend in `smbd/web/static/`. The
backend just calls the same library functions documented in
[library.md](library.md), so anything the UI shows, you can script.

Interactive API docs are available at `/docs` while the server runs.
