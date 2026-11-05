"""Command-line entry point for occheck."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from occheck import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="occheck",
        description="Tools that show traders where their money goes. Educational, not advice.",
    )
    parser.add_argument("--version", action="version", version=f"occheck {__version__}")
    sub = parser.add_subparsers(dest="command")
    audit = sub.add_parser("audit", help="report card for an IBKR Flex Trades CSV")
    audit.add_argument("csv", type=Path, help="path to the Flex Query CSV export")
    audit.add_argument("--account-value", type=float, default=None, help="account size, $")
    audit.add_argument("--json", action="store_true", help="print the report as JSON")
    serve = sub.add_parser("serve", help="run the web app on http://127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    dl = sub.add_parser("download-data", help="fetch free Cboe/FRED histories to a folder")
    dl.add_argument("kinds", nargs="*", help="SPX VIX PUT BXM DTB3 (default: all)")
    dl.add_argument("--dir", type=Path, default=None, help="default: ~/.cache/occheck")
    build = sub.add_parser("build-site", help="write the static web app to a folder")
    build.add_argument("out", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "audit":
        from occheck.brokers.ibkr_flex import FlexFormatError
        from occheck.report import render_text, report_from_csv

        try:
            report = report_from_csv(args.csv.read_text(), args.account_value)
        except (FlexFormatError, OSError) as exc:
            print(f"occheck: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(report, indent=2, default=str) if args.json else render_text(report))
    elif args.command == "serve":  # pragma: no cover - blocking server
        from occheck.site import serve

        serve(port=args.port, open_browser=not args.no_browser)
    elif args.command == "download-data":
        from occheck.data import SOURCES, download, load_csv

        for kind in [k.upper() for k in args.kinds] or list(SOURCES):
            path = download(kind, args.dir)
            series = load_csv(path.read_text())
            print(f"{kind}: {len(series)} days, {series.start} to {series.end} -> {path}")
    elif args.command == "build-site":
        from occheck.site import build_site

        print(f"occheck: wrote {build_site(args.out)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
