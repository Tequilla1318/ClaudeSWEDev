# options-checker — context

Feedback last read: 2026-11-05

## State
- **Design doc in review** (`docs/design.md`). No code yet; implementation starts after approval.
- Research review behind the design: `docs/research/stock-market-returns-review.md`.

## What's next
- Owner answers design §8 open questions (Pages enabled? Pyodide OK? sample IBKR export? Cboe
  delayed-chain use? lottery thresholds).
- On approval: create epics/issues per milestone, then S1 (scaffold) and S2 (Black-Scholes core).

## Key facts for future sessions
- Goal: "shovels" — tools that expose where traders lose money (costs, IV overpayment, timing,
  sizing, bias). Not signals, not advice. Audience: traders at all levels.
- Owner constraints: free data only; static GitHub Pages site preferred, localhost fallback.
- Cboe daily CSVs (SPX, VIX, PUT, BXM) and FRED (DTB3, VIXCLS) are free but send **no CORS headers**
  (probed 2026-11-05), so the browser can't fetch them; users drag files in, or localhost downloads.
  We don't republish third-party data.
- Cboe URLs redirect `cdn.cboe.com` → `cdn-api.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv`.
- GitHub Pages: one site per repo; this project would publish under `/ClaudeSWEDev/options-checker/`.
  The repo's Pages API path is blocked from cloud sessions.

## Known issues / gotchas
- Shallow single-branch clones don't track pushed branches; add a fetch refspec or the stop hook
  reports "unpushed commits".
