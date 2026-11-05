# options-checker — context

Feedback last read: 2026-11-05 (PRs #45–#72, all comments)

## State
- v1 (design #45, stories S1–S11, PRs #62–#72) **merged** on 2026-11-05. Site live at
  https://tequilla1318.github.io/ClaudeSWEDev/options-checker/ (Pages deploy from main works).
- Owner feedback round 1 → epic #79, stories #73–#78 (S12–S17).
- S12 (#73, PR #80) in review: wheel cost-basis view (`roundtrips.wheel_view`), report default.
- S13 (#74, PR #82) in review: all cutoffs in `audit.Thresholds`, adjustable on audit.html; port 3000.
- S14 (#75, PR #83) in review: docs/research/thresholds.md; disposition flag 1.5x / watch 1.2x.
- S16 (#77, PR #84) in review: `occheck.quotes` + `/quotes/...`; checker prefill panel (local only).
- S17 (#78, PR #85) in review: `occheck.prices` (Odean PGR/PLR, realized vol, yfinance) + `/prices/...`.
- **S15 (#76) in review:** `occheck.backtest.skew` smile (ATM 0.9 x VIX + slope β=0.10 in z units),
  used by the rule engine; `scripts/validate_skew.py` → docs/validation/skew-calibration.md. All
  feedback-round stories built.
- Feedback-round PRs are stacked again (each branch cut from the previous).

## What's next
- Owner reviews PRs #80, #82–#86 (stacked, merge in order).

## Owner answers (2026-11-05)
- Pyodide approved. No real IBKR export will be shared (synthetic fixtures stay).
- Wheel cost-basis view wanted. Thresholds must be adjustable and backed by research with sources.
- 0.9 x VIX accepted if research supports it, with sources. Price-only SPX benchmark OK.
- Skew-model story: yes. Cboe delayed-quote prefill in localhost: yes. yfinance suggested.
- Localhost should use port 3000.

## Key facts for future sessions
- Goal: "shovels" — tools that expose where traders lose money (costs, IV overpayment, timing,
  sizing, bias). Not signals, not advice. Audience: traders at all levels.
- Owner constraints: free data only; static GitHub Pages site preferred, localhost fallback.
- Runtime deps: numpy only (fast Pyodide load). scipy is dev-only, for cross-checks in tests.
- Cboe daily CSVs (SPX, VIX, PUT, BXM) and FRED (DTB3, VIXCLS) are free but send **no CORS headers**
  (probed 2026-11-05), so the browser can't fetch them; users drag files in, or localhost downloads.
  We don't republish third-party data.
- Cboe URLs redirect `cdn.cboe.com` → `cdn-api.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv`.
- GitHub Pages: one site per repo; this project would publish under `/ClaudeSWEDev/options-checker/`.
  The repo's Pages API path is blocked from cloud sessions; owner must enable Pages (Source: Actions).

## Known issues / gotchas
- Today's SPX skew (β≈0.30, 2026-11-05) is ~3x the historical fit; PUTY (1990+) supports 0.05–0.15.
  Deriving ATM from VIX through the smile (or tying β to Cboe SKEW) failed the PUTY pre-2008 check.
- Cboe delayed chains: `cdn-api.cboe.com/api/global/delayed_quotes/options/<SYM>.json`, indexes
  prefixed `_` (e.g. `_SPX`); timestamps are UTC; SPX has ~30k contracts, so the endpoint serves
  a summary plus one expiry at a time; 5-minute in-memory cache.
- Synthetic options: ATM vol = 0.9 x VIX (VIX alone overstates put-selling CAGR by ~3.4 pts/yr).
  Cboe PUT daily history only complete from 2007-06; earlier years have a handful of points.
- FRED drops connections for a bare `occheck` User-Agent; `data.USER_AGENT` names the project
  and repo URL, which works. Live data test: `OCCHECK_LIVE=1 pytest tests/test_data_live.py`.
- Site loads Pyodide v314.0.7 (Python 3.14) + numpy from jsdelivr, then writes occheck's .py files
  (listed in `py/manifest.json`) into Pyodide's FS — no wheel build needed.
- Headless Chrome in sessions needs `--proxy-server=$HTTPS_PROXY --ignore-certificate-errors`
  (smoke.mjs adds these only when HTTPS_PROXY is set). `--virtual-time-budget` doesn't wait for
  network; use puppeteer (`webtest/`).
- Turnover needs account value from the user (Flex Trades has no equity); annualized over the
  file span with a 30-day minimum.
- Flex fixtures are synthetic (no real export yet). Option symbols follow IBKR's OCC-style
  `AAPL  250117C00190000`; expiry/assignment rows carry `Notes/Codes` Ep / A / Ex.
- `implied_vol` raises when an option has (numerically) no time value — vol is unidentifiable there.
- Shallow single-branch clones don't track pushed branches; add a fetch refspec or the stop hook
  reports "unpushed commits".
- `gh` needs `env -u GH_TOKEN` in sessions (the injected token is invalid); GraphQL is blocked.
