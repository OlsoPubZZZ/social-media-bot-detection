"""Headless-browser provider — OPT-IN, EXPERIMENTAL.

Renders a **public** web page in a headless browser (Playwright) and extracts the
visible text so the engine can analyze it. With an AI key, the text is turned
into structured comments by the model; without one, a simple line-based fallback
is used.

**What this is:** a generic public-page reader. **What this is NOT:** it does not
log in, enter or store credentials, bypass access controls, or use any
platform-specific scraping logic. It only sees what a logged-out visitor sees.

> ⚠ Automated browsing can violate a site's Terms of Service. Point it only at
> pages you are authorized to view, prefer your own content, and respect each
> platform's terms and robots rules. You are responsible for how you use it.

Requires the ``browser`` extra and a one-time browser download:

    pip install -e ".[browser]"
    python -m playwright install chromium
"""

from __future__ import annotations

import base64
from typing import Dict, List, Optional

from smbd.providers.base import Provider
from smbd.schema import Account, Comment

_INSTALL_HINT = (
    "The browser feature needs the 'browser' extra and a browser download:\n"
    "  pip install -e \".[browser]\"\n"
    "  python -m playwright install chromium"
)

_AI_EXTRACT_SYSTEM = (
    "You extract social-media comments from the visible text of a web page. "
    "Return ONLY a JSON array of objects like {\"handle\": <username or null>, "
    "\"text\": <the comment>}. Include only genuine user comments or replies — "
    "skip navigation, buttons, ads, captions, and boilerplate."
)


class BrowserProvider(Provider):
    name = "browser"

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 25000,
        max_chars: int = 20000,
        viewport=(1280, 900),
    ):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.max_chars = max_chars
        self.viewport = viewport

    # --- rendering ---

    def capture(self, url: str) -> Dict:
        """Render ``url`` and return ``{url, title, text, screenshot_b64}``."""
        if not str(url).lower().startswith(("http://", "https://")):
            raise ValueError("Enter a full URL starting with http:// or https://")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on the extra
            raise ImportError(_INSTALL_HINT) from exc

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            try:
                page = browser.new_page(
                    viewport={"width": self.viewport[0], "height": self.viewport[1]}
                )
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                page.wait_for_timeout(1200)  # let late content settle
                title = page.title()
                text = page.inner_text("body")[: self.max_chars]
                shot = page.screenshot(full_page=False)
            finally:
                browser.close()
        return {
            "url": url,
            "title": title,
            "text": text,
            "screenshot_b64": base64.b64encode(shot).decode("ascii"),
        }

    def fetch_comments(self, target: str) -> List[Comment]:
        """Provider interface: render the page and extract comments heuristically."""
        return self.comments_from_text(self.capture(target)["text"])

    # --- text -> comments ---

    @staticmethod
    def comments_from_text(
        text: str, *, min_len: int = 8, max_len: int = 400, limit: int = 300
    ) -> List[Comment]:
        """Fallback extraction (no AI): each distinct visible line becomes a comment."""
        out: List[Comment] = []
        seen = set()
        for line in (text or "").splitlines():
            line = line.strip()
            if not (min_len <= len(line) <= max_len) or line in seen:
                continue
            seen.add(line)
            idx = len(out)
            out.append(Comment(id=f"line_{idx}", account=Account(id=f"line_{idx}"), text=line))
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def ai_comments(text: str, llm, limit: int = 300) -> List[Comment]:
        """AI extraction: ask the model to pull structured comments from page text."""
        from smbd.llm.enrich import _parse_json_array

        reply = llm.complete("Page text:\n" + (text or "")[:8000], system=_AI_EXTRACT_SYSTEM)
        out: List[Comment] = []
        for item in _parse_json_array(reply):
            if not isinstance(item, dict):
                continue
            body = str(item.get("text", "")).strip()
            if not body:
                continue
            handle = item.get("handle") or None
            idx = len(out)
            out.append(
                Comment(
                    id=f"c{idx}",
                    account=Account(id=str(handle or f"c{idx}"), handle=handle),
                    text=body,
                )
            )
            if len(out) >= limit:
                break
        return out
