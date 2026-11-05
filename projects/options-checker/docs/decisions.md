# options-checker — decisions (append-only)

## 2026-11-05 — Tools that expose losses, not signals
- **Decision:** Build tools that measure where traders lose money (auditor, risk calculator,
  pre-trade checker, premium-selling backtester). No recommendations or trade signals.
- **Why:** Owner's goal is "making shovels for others". The research review finds losses come from
  measurable channels (costs, timing, IV overpayment, sizing, bias); skill is rare.
- **Rejected:** Signal generators / screeners that rank trades to take.

## 2026-11-05 — Free data only; static site first, localhost fallback; all trader levels
- **Decision:** Chosen by the owner.

## 2026-11-05 — Don't republish third-party data (proposed)
- **Decision:** Browser users drag in CSVs they download from Cboe/FRED; localhost downloads on the
  user's machine. CI uses trimmed fixtures.
- **Why:** Cboe and FRED send no CORS headers, and redistribution terms are unclear.
- **Rejected:** A scheduled job that republishes the data on the Pages site.

## 2026-11-05 — One Python core in the browser via Pyodide (proposed, pending owner)
- **Why:** Keeps one tested codebase (pytest/ruff, numpy/scipy) for web, CLI and localhost.
- **Rejected:** TypeScript front end with the math reimplemented (two codebases to keep in sync).
  Revisit if first-load size (~10–15 MB) proves too slow.

## 2026-11-05 — Synthetic SPX options for backtests, gated on PUT-index replication (proposed)
- **Why:** No free historical option chains. Black-Scholes on SPX + VIX + T-bills, validated by
  replicating Cboe's PUT index before trusting any rule results.
- **Rejected:** Paid chains (ORATS, Cboe DataShop) — owner chose free only.

## 2026-11-05 — Design approved; open questions resolved by default
- **Decision:** Owner approved the design ("Go for it. Build it"). Open questions without an
  explicit answer take the design's proposal: Pyodide; lottery thresholds < $0.50 and ≤ 7 DTE;
  pre-trade checker is **manual entry only** (no undocumented Cboe delayed-chain endpoint) until the
  owner says otherwise; synthetic Flex fixtures until a real export is provided.

## 2026-11-05 — Runtime dependency: numpy only
- **Decision:** `occheck` depends only on numpy at runtime. Normal CDF via `math.erf`, root finding
  hand-written; scipy is a dev dependency used to cross-check in tests.
- **Why:** Pyodide downloads every dependency on first page load; scipy adds tens of MB.
- **Rejected:** scipy at runtime (convenient, but heavy in the browser).

## 2026-11-05 — Assignments split into two round trips
- **Decision:** An assigned short put is one round trip (premium kept, closed at 0) and the
  stock is a separate round trip opened at the strike, as IBKR records it.
- **Why:** Matches the broker's records so totals reconcile; total P&L is identical to the
  "premium reduces cost basis" convention.
- **Rejected:** Folding premium into stock cost basis (wheel-style accounting) — could be a view
  option later.

## 2026-11-05 — Report-card thresholds (starting values)
- **Turnover:** Barber & Odean definition (half of traded notional / account value).
  watch > 0.8x (their average household), flag > 1.15x (their most active fifth).
- **Commissions:** share of gross profits; watch > 10%, flag > 25%. Judgment call, no source.
- **Lottery:** long options < $0.50 and ≤ 7 DTE; watch > 5%, flag > 25% of long premium. Judgment.
- **0DTE:** any = watch, > 25% of option trades = flag.
- **Disposition:** losers' median hold > 1.2x winners' = flag; needs ≥ 5 winners and ≥ 5 losers.
- **Concentration:** single loss > 5% of account = flag (forum rule of 5–10% per position).
- **Expectancy:** win rate ≥ 60% with negative expectancy = flag (short-vol skew pattern).
- **Why:** All in `audit.Thresholds` / `report.py` and shown on screen so users can judge them.
