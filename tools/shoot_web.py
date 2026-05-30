#!/usr/bin/env python3
"""Capture web-UI screenshots to docs/screenshots/web-*.png with Playwright.

Setup (one-time):
    pip install -e ".[web,browser]"
    python -m playwright install chromium

Run:
    python tools/shoot_web.py

Launches `smbd serve` on a temp port, drives the UI with the bundled example
datasets, and writes retina PNGs. Pure screenshotting of our own local app — no
external sites involved.
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "screenshots")
EXAMPLES = os.path.join(ROOT, "examples")
PORT = 8211
BASE = f"http://127.0.0.1:{PORT}"


def _read(name: str) -> str:
    with open(os.path.join(EXAMPLES, name), encoding="utf-8") as fh:
        return fh.read()


def _wait_ready(timeout: float = 25.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("smbd serve didn't become ready")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    comments_csv = _read("sample_comments.csv")
    followers_csv = _read("sample_followers.csv")

    server = subprocess.Popen(
        ["smbd", "serve", "--port", str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_ready()
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1180, "height": 1024}, device_scale_factor=2)

            # 1) Landing
            page.goto(BASE, wait_until="networkidle")
            page.screenshot(path=os.path.join(OUT, "web-landing.png"))

            # 2) Comments result
            page.fill("#data", comments_csv)
            page.click("#run")
            page.wait_for_selector(".checked", timeout=15000)
            page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(OUT, "web-comments.png"))

            # 3) Followers result
            page.click('[data-kind="followers"]')
            page.fill("#data", followers_csv)
            page.click("#run")
            page.wait_for_selector(".checked", timeout=15000)
            page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(OUT, "web-followers.png"))

            browser.close()
        print("wrote:", ", ".join(["web-landing.png", "web-comments.png", "web-followers.png"]))
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    main()
