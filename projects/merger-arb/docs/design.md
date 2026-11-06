# merger-arb — design (as built)

Status: **built ahead of a design review at the owner's request** ("don't worry about a PR, just
make the thing"). This records the design as it stands so it can be reviewed with the code.
Author: Claude · 2026-11-05

## Goal
Tools for the market-neutral strategies in the "uncorrelated returns" video: a merger-arbitrage
calculator and live deal list, and a 15-year backtest of merger arb and long-short momentum for
an Ontario investor trading at IBKR, compared with buying index funds. Educational, not advice;
nothing here places trades.

## Scope
In: spread / implied-odds / carry calculator (cash, stock, mixed deals); live pending-deal
scanner from SEC EDGAR; historical deal collector; portfolio simulators with IBKR costs and
Canadian tax (TFSA vs non-registered, three income levels, capital gains vs business income);
index-fund and fund benchmarks; results dashboard.
Out: order placement or broker connections; deal recommendations; paid data.

## Approach
- **Math core** (`core.py`): deal value `V = cash + ratio·A`, spread, carry (dividends, borrow,
  costs), implied odds `p = (T − F)/(V − F)`, break-even odds, compounding, delay table, sizing
  by break loss. Mirrored in `web/math.js`; a parity test checks they agree.
- **Live scanner** (`scan.py`, `extract.py`, `sources.py`): EDGAR full-text search for SC TO-T,
  DEFM14A and PREM14A; regex extraction of cash, exchange ratio and close date with evidence
  snippets; target filing history for closed / terminated deals; Yahoo daily prices.
- **Historical collector** (`backtest/collect.py`, `history.py`): the same filings for
  2011-11 to 2026-10; entry price = the closing price the filing states for its latest
  practicable date (never a live price, so the sample doesn't depend on the outcome); outcome
  from the target's filing history.
- **Simulators** (`backtest/sim.py`, `momentum.py`, `bench.py`): described in the README.
- **Results**: `backtest/run.py` → `results.json` → `backtest/export.py` → CSVs for a
  claude.ai Dashboard artifact.

## References
- Mitchell & Pulvino (2001), "Characteristics of Risk and Return in Risk Arbitrage" (why merger
  arb looks like selling insurance).
- Jegadeesh & Titman (1993) and the Fama-French momentum factor (12-1 signal).
- IBKR Canada Fixed pricing and interest pages; Richter 2026 Ontario tax tables (linked in
  `backtest/costs.py`).

## Open questions
See `decisions.md` for the calls made without the owner; the PR lists the ones worth a look.
