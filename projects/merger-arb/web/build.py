"""Inline math.js into page.html to produce the single-file calculator (dist/index.html)."""

from pathlib import Path

HERE = Path(__file__).resolve().parent


def build() -> Path:
    """Write dist/index.html and return its path."""
    page = (HERE / "page.html").read_text()
    math_js = (HERE / "math.js").read_text()
    out = HERE / "dist" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page.replace("/*MATH*/", math_js))
    return out


if __name__ == "__main__":
    print(build())
