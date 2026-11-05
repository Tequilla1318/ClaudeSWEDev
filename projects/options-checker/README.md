# options-checker

Free tools that show traders where their money actually goes: costs, overpaying for volatility,
bad timing, oversizing, and behavioral bias. Educational only — not financial advice.

See [docs/design.md](docs/design.md) and the
[research review](docs/research/stock-market-returns-review.md).

## Status
| Tool | Status |
| --- | --- |
| Black-Scholes core (`occheck.pricing`) | done (S2) |
| Trade-log auditor | Web page + CLI (S3–S6) |
| Risk-of-ruin calculator | Web page (S7) |
| Premium-selling backtester | Web page + rule engine (S8–S10); model [validation report](docs/validation/put-replication.md) |
| Pre-trade checker | Web page (S11) |

## Use it
**Online (after the Pages deploy runs):** https://tequilla1318.github.io/ClaudeSWEDev/options-checker/
— everything runs in your browser; files you open are never uploaded.
Demo with a sample file: `audit.html?sample`.

**On your own computer** (needs Python 3.11+):
```bash
pip install "git+https://github.com/Tequilla1318/ClaudeSWEDev#subdirectory=projects/options-checker"
occheck serve                      # opens http://127.0.0.1:3000/
occheck audit trades.csv --account-value 50000   # same report in the terminal
occheck download-data              # free Cboe/FRED histories -> ~/.cache/occheck
```

## Develop
```bash
cd projects/options-checker
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
occheck --version
```

Runtime dependency is **numpy only** so the package loads quickly in the browser (Pyodide).
scipy is a dev dependency used only to cross-check results in tests.

Browser smoke test (headless Chrome runs the real page through Pyodide):
```bash
occheck build-site /tmp/site && (cd /tmp/site && python -m http.server 8765 &)
cd webtest && npm ci && node smoke.mjs
# backtester too: run `occheck serve --no-browser` and
# SMOKE_BACKTEST=1 SITE_URL=http://127.0.0.1:3000/ node smoke.mjs
```
