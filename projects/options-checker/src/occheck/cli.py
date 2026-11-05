"""Command-line entry point for occheck."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from occheck import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="occheck",
        description="Tools that show traders where their money goes. Educational, not advice.",
    )
    parser.add_argument("--version", action="version", version=f"occheck {__version__}")
    parser.add_subparsers(dest="command")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
