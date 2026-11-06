# merger-arb — context

Feedback last read: 2026-11-05 (new project; no PRs or issues yet)

## Built
- Calculator page (spread, implied odds, carry, delay table, sizing) and a live deal list from
  SEC EDGAR, published as a claude.ai artifact ("Merger Arb Desk").
- 15-year backtest: merger arb (768 tradable deals) and long-short S&P 500 momentum, with IBKR
  costs and 2026 Ontario tax, against SPY and XIC buy-and-hold, MERFX/ARBFX/MNA and the
  Fama-French momentum factor. Results in `docs/results.md` and a claude.ai Dashboard artifact
  ("Merger Arb & Momentum vs Index Funds").

## How to run
`SEC_USER_AGENT="Name email"` is required for every EDGAR call (the SEC rejects requests
without a contact). The owner's contact is kept out of the repo; set it in the session.
Commands are in the README. A cold historical collection takes ~40 minutes; cached reruns ~8.

## Next
- Optional: refresh the deal list on a schedule (weekdays after close) and republish.
- Optional: publish the calculator to GitHub Pages like options-checker.
- Improve term extraction for stock deals (only 11 tradable stock deals; most proxies put
  prices in tables the regexes miss).

## Known issues / gotchas
- Yahoo has no history for delisted or renamed tickers: acquired targets can't be marked to
  market (positions carried at cost, drawdowns understated), and about 17% of past S&P 500
  members can't be ranked in the momentum test.
- About 11 broken deals can't be priced from market data and use the filing's unaffected
  price; a few of those were really topping bids (Warner Bros. Discovery 2026, Jos. A. Bank
  2014), so merger-arb results are slightly understated.
- Term extraction is regex over free text; ~40% of filings yield no entry price and ~30% no
  terms (many proxies aren't acquisitions at all).
- `ruff` picks up a repo-level config with extra rules (C4, SIM, DTZ, S…); run it from the
  project folder.
