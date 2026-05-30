"""FastAPI app exposing the SMBD engine to the local web UI.

Keys are bring-your-own: the browser sends them per request, the server uses
them for that one call and never persists or logs them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from smbd.config import Config
from smbd.followers import analyze_followers
from smbd.providers.importer import ImportProvider
from smbd.report import (
    amplification_report,
    authenticity_report,
    comments_report,
    followers_report,
    _narrate,
)
from smbd.scoring import analyze_comments

_STATIC = Path(__file__).parent / "static"


class AnalyzeRequest(BaseModel):
    kind: str = "comments"                       # comments | followers | page
    source: str = "import"                       # import | youtube | x
    data: Optional[str] = None                   # pasted CSV/JSON (import)
    target: Optional[str] = None                 # video / tweet / user id (online)
    fmt: Optional[str] = None                    # csv | json | auto
    keys: Dict[str, str] = Field(default_factory=dict)      # anthropic/youtube/x — not stored
    options: Dict[str, Any] = Field(default_factory=dict)   # llm, llm_model, enrich_authors


# --- input parsing --------------------------------------------------------------

def _looks_json(data: str, fmt: Optional[str]) -> bool:
    if fmt == "json":
        return True
    if fmt == "csv":
        return False
    s = (data or "").lstrip()
    return s.startswith("[") or s.startswith("{")


def _parse_comments(data: str, fmt: Optional[str]):
    ip = ImportProvider()
    return ip.from_json(data) if _looks_json(data, fmt) else ip.from_csv(data)


def _parse_followers(data: str, fmt: Optional[str]):
    ip = ImportProvider()
    return ip.followers_from_json(data) if _looks_json(data, fmt) else ip.followers_from_csv(data)


# --- loading via the chosen source ----------------------------------------------

def _load_comments(req: AnalyzeRequest):
    keys, opts = req.keys, req.options
    if req.source == "import":
        if not (req.data or "").strip():
            raise ValueError("Paste or upload some comment data first.")
        comments = _parse_comments(req.data, req.fmt)
    elif req.source == "youtube":
        from smbd.providers.youtube import YouTubeProvider

        if not (req.target or "").strip():
            raise ValueError("Enter a YouTube video id.")
        provider = YouTubeProvider(
            api_key=keys.get("youtube") or None,
            enrich_authors=bool(opts.get("enrich_authors")),
        )
        comments = provider.fetch_comments(req.target.strip())
    elif req.source == "x":
        from smbd.providers.x import XProvider

        if not (req.target or "").strip():
            raise ValueError("Enter a tweet id.")
        comments = XProvider(bearer_token=keys.get("x") or None).fetch_comments(req.target.strip())
    else:
        raise ValueError(f"Unknown source {req.source!r}.")
    if not comments:
        raise ValueError("No comments found in the input.")
    return comments


def _load_followers(req: AnalyzeRequest):
    if req.source == "import":
        if not (req.data or "").strip():
            raise ValueError("Paste or upload some follower data first.")
        followers = _parse_followers(req.data, req.fmt)
    elif req.source == "x":
        from smbd.providers.x import XProvider

        if not (req.target or "").strip():
            raise ValueError("Enter an X user id.")
        followers = XProvider(bearer_token=req.keys.get("x") or None).fetch_followers(req.target.strip())
    else:
        raise ValueError("Followers are available from the 'import' or 'x' source only.")
    if not followers:
        raise ValueError("No followers found in the input.")
    return followers


# --- analysis -------------------------------------------------------------------

_AI_SYSTEM = (
    "You explain social-media authenticity results to a NON-technical person in "
    "plain, friendly language. No jargon, no bullet points, no markdown. 2-3 short "
    "sentences: say what the numbers mean and whether the engagement looks trustworthy."
)


def _ai_summary(prompt: str, llm) -> str:
    try:
        return llm.complete(prompt, system=_AI_SYSTEM).strip()
    except Exception as exc:  # never let the AI step break the core result
        return f"(AI explanation unavailable: {exc})"


def _browse(req: AnalyzeRequest, llm):
    """Render a public page in a headless browser and extract comments from it."""
    url = (req.target or "").strip()
    if not url:
        raise ValueError("Enter the full address (URL) of the page to check.")
    from smbd.providers.browser import BrowserProvider

    bp = BrowserProvider()
    try:
        cap = bp.capture(url)
    except ImportError as exc:
        raise ValueError(str(exc))
    except ValueError:
        raise
    except Exception as exc:  # Playwright timeout/navigation errors → friendly message
        raise ValueError(f"Couldn't open that page: {exc}")
    comments = (
        BrowserProvider.ai_comments(cap["text"], llm)
        if llm is not None
        else BrowserProvider.comments_from_text(cap["text"])
    )
    if not comments:
        raise ValueError("Couldn't find readable comments on that page.")
    capture = {
        "title": cap["title"],
        "url": cap["url"],
        "screenshot_b64": cap["screenshot_b64"],
        "extracted": len(comments),
    }
    return comments, capture


def _run(req: AnalyzeRequest) -> Dict[str, Any]:
    cfg = Config()
    opts = req.options or {}
    if opts.get("llm_model"):
        cfg.llm_model = str(opts["llm_model"])

    # Build the LLM once (used for enrichment and/or the plain-English summary).
    llm = None
    if opts.get("llm"):
        key = req.keys.get("anthropic")
        if not key:
            raise ValueError("AI explanation is on — paste your Anthropic API key, or turn it off.")
        from smbd.llm import get_anthropic

        llm = get_anthropic(model=cfg.llm_model, api_key=key, max_tokens=cfg.llm_max_tokens)

    if req.kind == "followers":
        batch = analyze_followers(_load_followers(req), cfg)
        rep = followers_report(batch)
        out: Dict[str, Any] = {"kind": "followers", "report": rep}
        if llm is not None:
            b, total = rep["breakdown_pct"], rep["total_followers"]
            out["ai_summary"] = _ai_summary(
                f"We checked {total} followers of an account. About "
                f"{b['genuine']:.0f}% look like real people and {rep['likely_fake_pct']:.0f}% "
                f"look fake or low-quality. Coordinated 'bought-follower' bursts found: "
                f"{len(rep['suspicious_clusters'])}.",
                llm,
            )
        return out

    capture = None
    if req.kind == "browser":
        comments, capture = _browse(req, llm)
    else:
        comments = _load_comments(req)
    batch = analyze_comments(comments, cfg)
    if llm is not None:
        from smbd.llm import enrich_batch

        enrich_batch(batch, llm, cfg)

    if req.kind == "page":
        return {
            "kind": "page",
            "amplification": amplification_report(batch),
            "authenticity": authenticity_report(batch),
        }

    rep = comments_report(batch)
    amp = amplification_report(batch)
    results: List[Dict[str, Any]] = []
    for r in batch.results:
        d = r.to_dict()
        d["narration"] = _narrate(r)
        results.append(d)
    out = {
        "kind": "comments",
        "report": rep,
        "authenticity": authenticity_report(batch),
        "amplification": amp,
        "results": results,
    }
    if capture is not None:
        out["capture"] = capture
    if llm is not None:
        b = rep["breakdown_pct"]
        fake = b["suspicious"] + b["spam"] + b["coordinated"]
        out["ai_summary"] = _ai_summary(
            f"We checked {rep['total_comments']} comments on a post. About "
            f"{b['genuine']:.0f}% look like real people and {fake:.0f}% look like "
            f"spam, bots, or coordinated activity. Coordinated bot groups found: "
            f"{len(amp['coordinated_groups'])}.",
            llm,
        )
    return out


def create_app() -> FastAPI:
    app = FastAPI(title="SMBD", description="Social Media Bot Detection — local web UI")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    @app.get("/api/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/analyze")
    def analyze(req: AnalyzeRequest) -> Dict[str, Any]:
        try:
            return _run(req)
        except (RuntimeError, NotImplementedError, ValueError, ImportError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    if _STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
    return app


app = create_app()
