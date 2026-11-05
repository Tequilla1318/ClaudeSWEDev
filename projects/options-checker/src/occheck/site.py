"""Build and serve the static web app.

The site is plain HTML/CSS/JS plus the ``occheck`` Python source. In the browser,
Pyodide (CPython compiled to WebAssembly) loads numpy, then writes the files listed in
``py/manifest.json`` into its virtual filesystem and imports ``occheck`` from there.
The same build is published to GitHub Pages and served by ``occheck serve``.
"""

from __future__ import annotations

import functools
import http.server
import json
import shutil
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

from occheck import data, quotes

PACKAGE_DIR = Path(__file__).resolve().parent
WEB_DIR = PACKAGE_DIR / "web"


def python_sources() -> list[Path]:
    """The package's .py files that the browser needs, relative to the package dir."""
    files = sorted(p.relative_to(PACKAGE_DIR) for p in PACKAGE_DIR.rglob("*.py"))
    return [p for p in files if p.parts[0] != "web" and "__pycache__" not in p.parts]


def build_site(out_dir: Path) -> Path:
    """Write the static site to ``out_dir`` (created or replaced). Returns ``out_dir``."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(WEB_DIR, out_dir)
    py_dir = out_dir / "py" / "occheck"
    manifest = []
    for rel in python_sources():
        dest = py_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PACKAGE_DIR / rel, dest)
        manifest.append("occheck/" + rel.as_posix())
    (out_dir / "py" / "manifest.json").write_text(json.dumps({"files": manifest}, indent=1))
    return out_dir


def local_data_file(kind: str, max_age_hours: float = 20.0, directory: Path | None = None) -> Path:
    """Path to a cached copy of ``kind``'s history, downloading it if missing or stale."""
    path = Path(directory or data.cache_dir()) / f"{kind}.csv"
    if not path.exists() or time.time() - path.stat().st_mtime > max_age_hours * 3600:
        path = data.download(kind, path.parent)
    return path


def quote_response(path: str) -> tuple[int, dict]:
    """Answer ``/quotes/ping``, ``/quotes/<SYM>.json`` or ``/quotes/<SYM>/<YYYY-MM-DD>.json``.

    Returns (HTTP status, JSON payload). Quotes are fetched from Cboe on this machine.
    """
    parts = path.split("?")[0].strip("/").split("/")[1:]
    if parts == ["ping"]:
        return 200, {"ok": True}
    try:
        if len(parts) == 1 and parts[0].endswith(".json"):
            return 200, quotes.summary(quotes.fetch_chain(parts[0][:-5]))
        if len(parts) == 2 and parts[1].endswith(".json"):
            from datetime import date

            chain = quotes.fetch_chain(parts[0])
            expiry = date.fromisoformat(parts[1][:-5])
            return 200, {
                "timestamp": chain.timestamp,
                "spot": chain.spot,
                "options": quotes.expiry_rows(chain, expiry),
            }
    except (quotes.QuoteError, ValueError) as exc:
        return 502, {"error": str(exc)}
    return 404, {"error": "unknown quotes path"}


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Static files, plus ``/data/<KIND>.csv`` fetched on this machine (localhost only)."""

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path.startswith("/data/") and self.path.endswith(".csv"):
            kind = self.path[len("/data/") : -len(".csv")].upper()
            if kind not in data.SOURCES:
                self.send_error(404, "unknown data file")
                return
            try:
                body = local_data_file(kind).read_bytes()
            except Exception as exc:  # network or parse failure: tell the page why
                self.send_error(502, f"could not download {kind}: {exc}")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/quotes/"):
            self._send_json(*quote_response(self.path))
            return
        super().do_GET()

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(port: int = 3000, open_browser: bool = True) -> None:  # pragma: no cover - blocking
    """Build the site into a temp dir and serve it on http://127.0.0.1:<port>/.

    Besides the static site, ``/data/<KIND>.csv`` serves free histories downloaded on
    this machine (see :mod:`occheck.data`), so the backtester can fill them in itself.
    """
    with tempfile.TemporaryDirectory(prefix="occheck-site-") as tmp:
        root = build_site(Path(tmp) / "site")
        handler = functools.partial(_Handler, directory=str(root))
        with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
            url = f"http://127.0.0.1:{httpd.server_address[1]}/"
            print(f"occheck: serving {url}  (Ctrl+C to stop)")
            if open_browser:
                threading.Timer(0.5, webbrowser.open, args=(url,)).start()
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\noccheck: stopped")
