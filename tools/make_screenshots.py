#!/usr/bin/env python3
"""Render SMBD CLI output to crisp SVG 'terminal screenshots' for docs / social.

    python tools/make_screenshots.py     # writes docs/screenshots/cli-*.svg

Uses rich's record+save_svg so the images look exactly like the real CLI.
"""

from __future__ import annotations

import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from smbd.followers import analyze_followers
from smbd.providers.importer import ImportProvider
from smbd.report import (
    amplification_report,
    authenticity_report,
    comments_report,
    explain,
    followers_report,
)
from smbd.scoring import analyze_comments

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "screenshots")
COMMENTS = os.path.join(ROOT, "examples", "sample_comments.csv")
FOLLOWERS = os.path.join(ROOT, "examples", "sample_followers.csv")

COLOR = {
    "genuine": "green",
    "suspicious": "yellow",
    "spam": "red",
    "coordinated": "magenta",
    "low_confidence": "bright_black",
}


def _console() -> Console:
    return Console(record=True, width=98)


def _bar(pct: float, color: str, width: int = 28) -> Text:
    filled = round(pct / 100 * width)
    t = Text()
    t.append("█" * filled, style=color)
    t.append("░" * (width - filled), style="bright_black")
    return t


def _breakdown_table(breakdown: dict) -> Table:
    t = Table(show_edge=False, box=None, pad_edge=False)
    t.add_column("label", width=15)
    t.add_column("bar")
    t.add_column("pct", justify="right", width=7)
    for label, pct in breakdown.items():
        t.add_row(Text(label, style=COLOR.get(label, "white")), _bar(pct, COLOR.get(label, "white")),
                  f"{pct:.1f}%")
    return t


def comments_svg() -> None:
    batch = analyze_comments(ImportProvider().fetch_comments(COMMENTS))
    rep = comments_report(batch)
    c = _console()
    c.print(Text("$ smbd comments comments.csv", style="bold bright_cyan"))
    c.print()
    c.print(Text("Are these comments real?", style="bold"))
    c.print(_breakdown_table(rep["breakdown_pct"]))
    c.print()
    c.print(Text(rep["summary"], style="italic"))
    c.print()
    flagged = sorted((r for r in batch.results if r.label.value not in ("genuine", "low_confidence")),
                     key=lambda r: -r.score)[:5]
    t = Table(title="Top flagged comments", title_style="bold", title_justify="left")
    t.add_column("score", justify="right")
    t.add_column("label")
    t.add_column("handle")
    t.add_column("text", overflow="fold", max_width=44)
    for r in flagged:
        t.add_row(f"{r.score:.2f}", Text(r.label.value, style=COLOR[r.label.value]),
                  r.comment.account.handle or r.comment.account.id, r.comment.text[:60])
    c.print(t)
    c.save_svg(os.path.join(OUT, "cli-comments.svg"), title="SMBD · comments")


def followers_svg() -> None:
    batch = analyze_followers(ImportProvider().fetch_followers(FOLLOWERS))
    rep = followers_report(batch)
    c = _console()
    c.print(Text("$ smbd followers followers.csv", style="bold bright_cyan"))
    c.print()
    c.print(Text("Are these followers real people?", style="bold"))
    c.print(_breakdown_table(rep["breakdown_pct"]))
    c.print()
    q = rep["follower_quality_score"]
    line = Text()
    line.append("Follower quality: ", style="bold")
    line.append(f"{q}/100", style="bold red" if q < 60 else "bold green")
    line.append(f"   likely-fake: {rep['likely_fake_pct']:.0f}% "
                f"({rep['likely_fake_count']}/{rep['total_followers']})", style="red")
    c.print(line)
    if rep["suspicious_clusters"]:
        cl = rep["suspicious_clusters"][0]
        c.print(Text(f"⚠ coordinated join-burst: {cl['size']} accounts @ {cl['window_start']}",
                     style="yellow"))
    c.print()
    t = Table(title="Most suspicious followers", title_style="bold", title_justify="left")
    t.add_column("score", justify="right")
    t.add_column("handle")
    t.add_column("created")
    t.add_column("avatar")
    t.add_column("reasons", overflow="fold", max_width=38)
    for f in rep["top_suspicious"][:6]:
        t.add_row(f"{f['score']:.2f}", f["handle"] or f["account_id"],
                  (f["account_created_at"] or "?")[:10],
                  "no" if f["has_avatar"] is False else "yes",
                  ", ".join(f["reasons"]))
    c.print(t)
    c.save_svg(os.path.join(OUT, "cli-followers.svg"), title="SMBD · followers")


def page_svg() -> None:
    batch = analyze_comments(ImportProvider().fetch_comments(COMMENTS))
    amp = amplification_report(batch)
    auth = authenticity_report(batch)
    c = _console()
    c.print(Text("$ smbd page comments.csv", style="bold bright_cyan"))
    c.print()
    body = Text()
    body.append("⚠ Amplification detected\n\n", style="bold yellow")
    body.append(f"  coordinated groups   {len(amp['coordinated_groups'])}\n")
    body.append(f"  repeated-text clusters {len(amp['repeated_text_clusters'])}\n")
    body.append(f"  timing bursts        {len(amp['timing_bursts'])}\n")
    for g in amp["coordinated_groups"][:3]:
        body.append(f"\n  • group of {g['size']} accounts via {', '.join(g['link_types'])} "
                    f"(cohesion {g['cohesion']})", style="magenta")
    c.print(Panel(body, title="Is this page being amplified or attacked?", title_align="left",
                  border_style="yellow"))
    s = auth["authenticity_score"]
    line = Text()
    line.append("Authenticity score: ", style="bold")
    line.append(f"{s}/100", style="bold red" if s < 60 else "bold green")
    line.append(f"   (confidence: {auth['confidence_band']})", style="bright_black")
    c.print(line)
    c.save_svg(os.path.join(OUT, "cli-page.svg"), title="SMBD · page")


def explain_svg() -> None:
    batch = analyze_comments(ImportProvider().fetch_comments(COMMENTS))
    target = max(batch.results, key=lambda r: r.score)
    rep = explain(target)
    c = _console()
    c.print(Text(f"$ smbd explain comments.csv {target.comment.id}", style="bold bright_cyan"))
    c.print()
    head = Text()
    head.append("label: ", style="bold")
    head.append(rep["label"], style=COLOR[rep["label"]])
    head.append(f"    score: {rep['score']}    confidence: {rep['confidence']}", style="bright_black")
    c.print(head)
    c.print()
    c.print(Text("evidence", style="bold"))
    for e in rep["evidence"]:
        extra = {k: v for k, v in e.items() if k not in ("signal", "score", "reason")}
        bits = ", ".join(f"{k}={len(v) if isinstance(v, list) else v}" for k, v in list(extra.items())[:3])
        c.print(Text(f"  • {e['signal']} ({e['score']}) ", style="cyan").append(bits, style="bright_black"))
    c.print()
    c.print(Panel(Text(rep["narration"], style="italic"), title="Why was this flagged?",
                  title_align="left", border_style="cyan"))
    c.save_svg(os.path.join(OUT, "cli-explain.svg"), title="SMBD · explain")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    comments_svg()
    followers_svg()
    page_svg()
    explain_svg()
    print("wrote:", ", ".join(sorted(os.listdir(OUT))))


if __name__ == "__main__":
    main()
