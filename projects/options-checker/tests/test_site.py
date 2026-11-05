import json

from occheck.cli import main
from occheck.site import build_site, python_sources


def test_python_sources_excludes_web_and_cache():
    names = {p.as_posix() for p in python_sources()}
    assert {"__init__.py", "report.py", "brokers/ibkr_flex.py"} <= names
    assert not any(n.startswith("web/") or "__pycache__" in n for n in names)


def test_build_site(tmp_path):
    out = build_site(tmp_path / "site")
    for f in (
        "index.html",
        "audit.html",
        "audit.js",
        "risk.html",
        "risk.js",
        "py.js",
        "style.css",
        "sample-trades.csv",
    ):
        assert (out / f).is_file(), f
    manifest = json.loads((out / "py" / "manifest.json").read_text())
    assert "occheck/report.py" in manifest["files"]
    for rel in manifest["files"]:
        assert (out / "py" / rel).is_file()
    build_site(out)  # rebuilding over an existing folder works


def test_pages_link_local_assets_only(tmp_path):
    out = build_site(tmp_path / "site")
    for page in ("index.html", "audit.html", "risk.html", "backtest.html", "checker.html"):
        html = (out / page).read_text()
        assert 'lang="en"' in html and 'name="viewport"' in html
        assert "not financial advice" in html


def test_cli_build_site(tmp_path, capsys):
    assert main(["build-site", str(tmp_path / "s")]) == 0
    assert (tmp_path / "s" / "audit.html").exists()
