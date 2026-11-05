"""Inline math.js into page.html to produce the single-file calculator (dist/index.html)."""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(deals: Path | None = None, out: Path | None = None) -> Path:
    """Write the single-file page and return its path.

    ``deals`` is a JSON snapshot from ``python -m mergerarb.scan``; without one
    the page still works as a plain calculator.
    """
    page = (HERE / "page.html").read_text()
    math_js = (HERE / "math.js").read_text()
    data = "null"
    if deals:
        # Keep "</script>" in filing text from ending the inline script early.
        data = json.dumps(json.loads(deals.read_text())).replace("</", "<\\/")
    out = out or HERE / "dist" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page.replace("/*MATH*/", math_js).replace("/*DEALS*/null", data))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deals", type=Path, help="deals.json from mergerarb.scan")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    print(build(a.deals, a.out))
