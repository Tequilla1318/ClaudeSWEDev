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
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
