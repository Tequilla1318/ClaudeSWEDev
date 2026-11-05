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
