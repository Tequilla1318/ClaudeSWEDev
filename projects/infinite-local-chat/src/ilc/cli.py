"""``ilc`` command-line entry point.

``ilc`` with no subcommand means ``ilc start``. Only ``doctor`` and ``config`` work in S1;
``start``, ``stop`` and ``status`` are wired up in S2-S4.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import asdict

from ilc import __version__
from ilc.config import ConfigError, load_config
from ilc.doctor import Status, format_report, gather, run_checks

NOT_YET = {
    "start": "S2-S4 (model manager, chat app, launcher)",
    "stop": "S2 (model manager)",
    "status": "S2 (model manager)",
}


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``ilc``."""
    parser = argparse.ArgumentParser(
        prog="ilc", description="Local chat with lossless conversation memory."
    )
    parser.add_argument("--version", action="version", version=f"ilc {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("start", help="start the model servers and open the chat in your browser")
    sub.add_parser("stop", help="stop the model servers and the chat app")
    sub.add_parser("status", help="show what is running")
    sub.add_parser("doctor", help="check that this machine can run ilc")
    sub.add_parser("config", help="print the effective configuration")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``ilc`` command and return its exit code."""
    args = build_parser().parse_args(argv)
    command = args.command or "start"

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"ilc: config error: {exc}", file=sys.stderr)
        return 2

    if command == "doctor":
        checks = run_checks(gather(config.data_dir))
        print(format_report(checks))
        return 1 if any(c.status is Status.FAIL for c in checks) else 0

    if command == "config":
        for section, values in asdict(config).items():
            print(f"{section} = {values}")
        print(f"budget.prompt_total = {config.budget.prompt_total}")
        return 0

    print(f"ilc {command}: not implemented yet, arrives in {NOT_YET[command]}", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
