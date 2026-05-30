"""SMBD command-line interface.

    smbd comments  <data.csv|json> [--json] [--config cfg.json]
    smbd followers <data.csv|json> [--json]      # follower quality + fake-likely
    smbd page      <data.csv|json> [--json]      # amplification + authenticity
    smbd explain   <data.csv|json> <comment_id>  # why a comment was flagged

Renders rich tables when the ``rich`` extra is installed, plain text otherwise.
Runs with no credentials and no AI key.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from smbd.config import Config
from smbd.followers import FollowerBatchResult, analyze_followers
from smbd.llm import enrich_batch, get_anthropic
from smbd.llm.base import LLMClient
from smbd.providers.importer import ImportProvider
from smbd.report import (
    amplification_report,
    authenticity_report,
    comments_report,
    explain,
    followers_report,
)
from smbd.scoring import BatchResult, analyze_comments

try:  # optional pretty output
    from rich.console import Console
    from rich.table import Table

    _RICH = True
    _console = Console()
except Exception:  # pragma: no cover - rich is optional
    _RICH = False
    _console = None

_LABEL_COLOR = {
    "genuine": "green",
    "suspicious": "yellow",
    "spam": "red",
    "coordinated": "magenta",
    "low_confidence": "dim",
}


def _config(args) -> Config:
    cfg = Config.from_json(args.config) if args.config else Config()
    if getattr(args, "llm_model", None):
        cfg.llm_model = args.llm_model
    if getattr(args, "llm_max_items", None):
        cfg.llm_max_items = args.llm_max_items
    return cfg


def _build_llm(args, config: Config) -> Optional[LLMClient]:
    """Construct an LLM client when --llm is set, else None."""
    if not getattr(args, "llm", False):
        return None
    try:
        return get_anthropic(model=config.llm_model, max_tokens=config.llm_max_tokens)
    except ImportError as exc:
        _err(str(exc))
        sys.exit(2)


def _provider(args):
    """Build the ingestion provider named by --provider (default: file import)."""
    if getattr(args, "provider", "import") == "youtube":
        from smbd.providers.youtube import YouTubeProvider

        return YouTubeProvider(
            api_key=getattr(args, "api_key", None),
            enrich_authors=getattr(args, "enrich_authors", False),
        )
    return ImportProvider()


def _load(target: str, config: Config, llm: Optional[LLMClient] = None, provider=None) -> BatchResult:
    provider = provider or ImportProvider()
    try:
        comments = provider.fetch_comments(target)
    except (RuntimeError, NotImplementedError) as exc:
        _err(str(exc))
        sys.exit(2)
    if not comments:
        _err(f"No comments found for {target!r}.")
        sys.exit(2)
    batch = analyze_comments(comments, config=config)
    if llm is not None:
        enrich_batch(batch, llm, config)
    return batch


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _print_breakdown(batch: BatchResult) -> None:
    rep = comments_report(batch)
    bd = rep["breakdown_pct"]
    if _RICH:
        table = Table(title="Are these comments real?", show_edge=True)
        table.add_column("Label")
        table.add_column("Share", justify="right")
        for label, pct in bd.items():
            color = _LABEL_COLOR.get(label, "white")
            table.add_row(f"[{color}]{label}[/{color}]", f"{pct:.1f}%")
        _console.print(table)
        _console.print(f"[bold]{rep['total_comments']}[/bold] comments analyzed")
        _console.print(rep["summary"])
    else:
        print("Are these comments real?")
        for label, pct in bd.items():
            print(f"  {label:<16} {pct:>5.1f}%")
        print(f"{rep['total_comments']} comments analyzed")
        print(rep["summary"])


def _print_flagged(batch: BatchResult, limit: int = 10) -> None:
    flagged = [r for r in batch.results if r.label.value not in ("genuine", "low_confidence")]
    flagged.sort(key=lambda r: -r.score)
    if not flagged:
        return
    if _RICH:
        table = Table(title=f"Top flagged comments (showing {min(limit, len(flagged))})")
        table.add_column("Score", justify="right")
        table.add_column("Label")
        table.add_column("Handle")
        table.add_column("Text", overflow="fold")
        for r in flagged[:limit]:
            color = _LABEL_COLOR.get(r.label.value, "white")
            table.add_row(
                f"{r.score:.2f}",
                f"[{color}]{r.label.value}[/{color}]",
                r.comment.account.handle or r.comment.account.id,
                r.comment.text[:80],
            )
        _console.print(table)
    else:
        print("\nTop flagged comments:")
        for r in flagged[:limit]:
            handle = r.comment.account.handle or r.comment.account.id
            print(f"  [{r.score:.2f}] {r.label.value:<12} @{handle}: {r.comment.text[:70]}")


def cmd_comments(args) -> int:
    cfg = _config(args)
    batch = _load(args.data, cfg, _build_llm(args, cfg), _provider(args))
    if args.json:
        _print_json({**comments_report(batch), "results": [r.to_dict() for r in batch.results]})
    else:
        _print_breakdown(batch)
        _print_flagged(batch)
    return 0


def cmd_followers(args) -> int:
    cfg = _config(args)
    followers = ImportProvider().fetch_followers(args.data)
    if not followers:
        _err(f"No followers found in {args.data!r} (need at least one account row).")
        return 2
    batch = analyze_followers(followers, config=cfg)
    rep = followers_report(batch)
    if args.json:
        _print_json(rep)
        return 0
    _print_followers(rep)
    return 0


def _print_followers(rep: dict) -> None:
    bd = rep["breakdown_pct"]
    clusters = rep["suspicious_clusters"]
    if _RICH:
        table = Table(title="Are these followers real people?", show_edge=True)
        table.add_column("Label")
        table.add_column("Share", justify="right")
        for label, pct in bd.items():
            color = _LABEL_COLOR.get(label, "white")
            table.add_row(f"[{color}]{label}[/{color}]", f"{pct:.1f}%")
        _console.print(table)
        _console.print(
            f"[bold]Follower quality:[/bold] {rep['follower_quality_score']}/100 "
            f"(confidence: {rep['confidence_band']})  |  "
            f"likely-fake: [red]{rep['likely_fake_pct']:.1f}%[/red] "
            f"({rep['likely_fake_count']}/{rep['total_followers']})"
        )
        if clusters:
            _console.print(
                f"⚠ {len(clusters)} coordinated join-burst cluster(s): "
                + ", ".join(f"{c['size']} accounts @ {c['window_start']}" for c in clusters[:5])
            )
        if rep["top_suspicious"]:
            t2 = Table(title=f"Most suspicious followers (showing {len(rep['top_suspicious'])})")
            t2.add_column("Score", justify="right")
            t2.add_column("Label")
            t2.add_column("Handle")
            t2.add_column("Created")
            t2.add_column("Avatar")
            t2.add_column("Reasons", overflow="fold")
            for f in rep["top_suspicious"]:
                color = _LABEL_COLOR.get(f["label"], "white")
                created = (f["account_created_at"] or "?")[:10]
                avatar = "no" if f["has_avatar"] is False else ("yes" if f["has_avatar"] else "?")
                t2.add_row(
                    f"{f['score']:.2f}",
                    f"[{color}]{f['label']}[/{color}]",
                    f["handle"] or f["account_id"],
                    created,
                    avatar,
                    ", ".join(f["reasons"]),
                )
            _console.print(t2)
        _console.print(rep["summary"])
    else:
        print("Are these followers real people?")
        for label, pct in bd.items():
            print(f"  {label:<16} {pct:>5.1f}%")
        print(
            f"Follower quality: {rep['follower_quality_score']}/100 "
            f"(confidence: {rep['confidence_band']}); likely-fake "
            f"{rep['likely_fake_pct']:.1f}% ({rep['likely_fake_count']}/{rep['total_followers']})"
        )
        for c in clusters[:5]:
            print(f"  cluster: {c['size']} accounts joined @ {c['window_start']}")
        print(rep["summary"])


def cmd_page(args) -> int:
    cfg = _config(args)
    batch = _load(args.data, cfg, _build_llm(args, cfg), _provider(args))
    amp = amplification_report(batch)
    auth = authenticity_report(batch)
    if args.json:
        _print_json({"amplification": amp, "authenticity": auth})
        return 0
    _print_breakdown(batch)
    print()
    if amp["amplification_detected"]:
        print(f"⚠ Amplification detected: {len(amp['coordinated_groups'])} coordinated group(s), "
              f"{len(amp['repeated_text_clusters'])} repeated-text cluster(s), "
              f"{len(amp['timing_bursts'])} timing burst(s).")
        for g in amp["coordinated_groups"][:5]:
            print(f"  • group of {g['size']} accounts via {', '.join(g['link_types'])}")
    else:
        print("No coordinated amplification detected.")
    print(
        f"\nAuthenticity score: {auth['authenticity_score']}/100 "
        f"(confidence: {auth['confidence_band']})"
    )
    return 0


def cmd_explain(args) -> int:
    cfg = _config(args)
    llm = _build_llm(args, cfg)
    batch = _load(args.data, cfg, llm, _provider(args))
    match = next((r for r in batch.results if r.comment.id == args.comment_id), None)
    if match is None:
        _err(f"comment id {args.comment_id!r} not found")
        return 2
    _print_json(explain(match, llm=llm))
    return 0


def _add_common(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--config", help="JSON config overriding detection weights/thresholds")
    sp.add_argument(
        "--provider",
        choices=["import", "youtube"],
        default="import",
        help="data source (default: import from file). 'youtube' treats the argument as a video id.",
    )
    sp.add_argument("--api-key", help="API key for online providers (or set YOUTUBE_API_KEY)")
    sp.add_argument(
        "--enrich-authors",
        action="store_true",
        help="(youtube) fetch each commenter's channel age + subscriber/video counts",
    )
    sp.add_argument(
        "--llm",
        action="store_true",
        help="enrich ambiguous comments with an LLM (needs ANTHROPIC_API_KEY and the 'llm' extra)",
    )
    sp.add_argument("--llm-model", help="LLM model id (default: claude-opus-4-8; haiku is cheaper)")
    sp.add_argument("--llm-max-items", type=int, help="max ambiguous comments to send to the LLM")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="smbd", description="Social Media Bot Detection Tool")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("comments", help="classify comments as genuine/suspicious/spam/...")
    c.add_argument("data", help="CSV or JSON file of comments")
    c.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    _add_common(c)
    c.set_defaults(func=cmd_comments)

    fo = sub.add_parser("followers", help="follower quality score + fake-likely estimate")
    fo.add_argument("data", help="CSV or JSON file of follower account rows")
    fo.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    fo.add_argument("--config", help="JSON config overriding detection weights/thresholds")
    fo.set_defaults(func=cmd_followers)

    pg = sub.add_parser("page", help="page-level amplification + authenticity report")
    pg.add_argument("data", help="CSV or JSON file of comments")
    pg.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    _add_common(pg)
    pg.set_defaults(func=cmd_page)

    e = sub.add_parser("explain", help="explain why a single comment was flagged")
    e.add_argument("data", help="CSV or JSON file of comments")
    e.add_argument("comment_id", help="id of the comment to explain")
    _add_common(e)
    e.set_defaults(func=cmd_explain)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
