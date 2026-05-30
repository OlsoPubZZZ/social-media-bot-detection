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

The UI is written in **plain language for non-technical users** — no jargon.

- **Two things to check** — *Comments on a post* or *Followers of an account*.
- **Data sources** — paste/upload a CSV or JSON, or pull from **YouTube**
  (video id) or **X** (tweet/user id).
- **Results** — "We checked N comments/followers," a friendly **donut** of
  **Real people vs Fake / bot / spam** (with counts and %), a one-line verdict,
  a plain-English warning if there's a coordinated bot campaign or bought-follower
  burst, and a "what looks suspicious" list with everyday reasons
  ("Brand-new account (only 9 days old)", "Follows 1,900 but only 3 follow back").
- **Optional AI explanation** — tick the box and paste an Anthropic key to get a
  short, plain-English written summary of the results (and a second opinion on
  borderline comments).

> Under the hood it's the same engine as the CLI — the labels are just mapped to
> plain buckets (genuine → *real people*; suspicious/spam/coordinated → *fake /
> bot / spam*; low-confidence → *not sure*).

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
