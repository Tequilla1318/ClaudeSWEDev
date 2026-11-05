# options-checker — context

Feedback last read: 2026-11-05

## State
- Design approved by the owner in chat on 2026-11-05 ("Go for it. Build it"); design PR #45.
- Backlog: epics #48 (M1), #52 (M2), #55 (M3), #59 (M4), #61 (M5); stories #46–#60.
- **S1 (#46) in review:** `occheck` package scaffold, CLI with `--version`.
- Story PRs are **stacked** (each branch cut from the previous); merge in order, starting with #45.

## What's next
- S2 (#47): Black-Scholes, Greeks, IV solver with Hull/parity/scipy validation.

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
- Shallow single-branch clones don't track pushed branches; add a fetch refspec or the stop hook
  reports "unpushed commits".
- `gh` needs `env -u GH_TOKEN` in sessions (the injected token is invalid); GraphQL is blocked.
