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
import webbrowser
from pathlib import Path

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


def serve(port: int = 8765, open_browser: bool = True) -> None:  # pragma: no cover - blocking
    """Build the site into a temp dir and serve it on http://127.0.0.1:<port>/."""
    with tempfile.TemporaryDirectory(prefix="occheck-site-") as tmp:
        root = build_site(Path(tmp) / "site")
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
        with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
            url = f"http://127.0.0.1:{httpd.server_address[1]}/"
            print(f"occheck: serving {url}  (Ctrl+C to stop)")
            if open_browser:
                threading.Timer(0.5, webbrowser.open, args=(url,)).start()
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\noccheck: stopped")
