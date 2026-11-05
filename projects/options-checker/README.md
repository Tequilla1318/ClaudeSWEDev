# options-checker

Free tools that show traders where their money actually goes: costs, overpaying for volatility,
bad timing, oversizing, and behavioral bias. Educational only — not financial advice.

See [docs/design.md](docs/design.md) and the
[research review](docs/research/stock-market-returns-review.md).

## Status
| Tool | Status |
| --- | --- |
| Black-Scholes core (`occheck.pricing`) | done (S2) |
| Trade-log auditor | planned (S3–S6) |
| Risk-of-ruin calculator | planned (S7) |
| Premium-selling backtester | planned (S8–S10) |
| Pre-trade checker | planned (S11) |

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
