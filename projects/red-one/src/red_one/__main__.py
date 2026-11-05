"""Entry point: `python -m red_one` or `red-one` starts the server on localhost only."""

from __future__ import annotations

import argparse

import uvicorn

from red_one.web.app import create_app, is_stub_mode

DEFAULT_HOST = "127.0.0.1"  # never 0.0.0.0: reach it only through private port forwarding
DEFAULT_PORT = 8765


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and run the server."""
    parser = argparse.ArgumentParser(prog="red-one", description="Run the Red One chat room.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    mode = "STUB (no ANTHROPIC_API_KEY; scripted replies)" if is_stub_mode() else "LIVE"
    print(f"Red One starting on http://{DEFAULT_HOST}:{args.port}  mode: {mode}")
    print(f"In Codespaces: open the PORTS tab; port {args.port} must show Visibility: Private.")
    uvicorn.run(create_app(), host=DEFAULT_HOST, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
