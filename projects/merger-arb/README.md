# merger-arb

Merger-arbitrage calculator: for a pending acquisition it shows the spread, the market-implied
odds that the deal closes, the annualized return if it closes on time, the loss if it breaks,
how delays hurt the return, and position sizing by break loss. Cash, stock and mixed deals.

Educational tool, not financial advice. It does not place trades or recommend deals.

## Layout
- `src/mergerarb/core.py` — the math (pure Python, no dependencies).
- `src/mergerarb/scan.py` — finds pending deals on SEC EDGAR and prices them.
- `src/mergerarb/extract.py` — reads cash price, exchange ratio and expected close from filing text.
- `src/mergerarb/sources.py` — EDGAR and daily-price access, with rate limiting and a disk cache.
- `web/math.js` — the same math for the browser; `tests/test_js_parity.py` checks it matches Python.
- `web/page.html` + `web/build.py` — the single-file calculator page (`python web/build.py` writes
  `web/dist/index.html`, which is git-ignored).

## Deal scanner
```
export SEC_USER_AGENT="Your Name you@example.com"   # the SEC rejects requests without a contact
python -m mergerarb.scan --out deals.json
python web/build.py --deals deals.json             # page with the deal list embedded
```
1. Searches EDGAR full-text search for tender offers (SC TO-T, last 120 days) and merger proxies
   (DEFM14A 270 days, PREM14A 200 days). Skips amendments and SPACs (SIC 6770).
2. Keeps one filing per target (tender > definitive proxy > preliminary proxy).
3. From the target's EDGAR history: drops deals whose target filed a Form 25/15 after the deal
   filing (closed), dates the announcement from the latest 8-K item 1.01, flags a later item 1.02
   (termination).
4. Extracts terms from the filing text (plus the Offer to Purchase exhibit for tender offers).
5. Prices target and acquirer from Yahoo Finance's free chart endpoint; the close before the
   announcement is the default break price.

Anything ambiguous goes to a "needs review" list with the reason instead of being guessed:
no terms found, cash/stock elections, unmatched acquirer ticker, price far from the offer, stale
prices. About a third of recent merger proxies land there (many are not acquisitions at all).

## 15-year backtest (Ontario investor, IBKR)
```
export SEC_USER_AGENT="Your Name you@example.com"
python -m mergerarb.backtest.collect --out deals_hist.jsonl     # ~40 min, cached
python -m mergerarb.backtest.run --deals deals_hist.jsonl --out results.json
python -m mergerarb.backtest.export results.json dash/          # CSVs for the results dashboard
```
- `backtest/collect.py` — every SC TO-T, PREM14A and DEFM14A from 2011-11 to 2026-10, grouped per
  target. Entry price is the closing price the filing states for its latest practicable date
  (never a live price, so selection doesn't depend on how the deal ended). Outcome from the
  target's filing history: Form 25/15 or 8-K item 5.01 = closed; 8-K item 1.02 within 540 days
  with no change in control = broke (exit at the market price after, else the filing's unaffected
  price); a target with no ticker that stopped filing = closed; still listed a year on = broke.
- `backtest/sim.py` — 5% of the book per deal, spread 0–40%, price ≥ $1; IBKR Fixed commissions,
  SEC/FINRA fees, 0.05% slippage, 0.5% borrow on shorts; idle USD earns T-bill − 0.5% over $10k.
  Tax in CAD: deal gains at trade-date FX, FX gains on the USD pool when converted (average
  cost), capital losses carried forward; or everything as business income.
- `backtest/bench.py` — SPY and XIC buy-and-hold with dividend withholding, dividend tax and
  capital-gains tax on the final sale.
- Cross-check: MERFX, ARBFX and MNA total returns over the same window.
- `backtest/momentum.py` — long-short 12-1 momentum on point-in-time S&P 500 members
  (github.com/fja05680/sp500): top and bottom 10% equal-weighted, each side 100% of equity,
  monthly. Checked against the Fama-French momentum factor (`--members`, `--umd` on the runner).
  Yahoo has no prices for delisted or renamed members (about 17% of members on average).
- Rates: 2026 Ontario combined (Richter), applied to all years; 50% inclusion.

Biases to keep in mind: positions are carried at cost (acquired companies' daily prices are gone),
so the book's drawdowns are understated; deals that broke before any proxy was filed are missing;
higher competing bids and CVRs aren't credited; dividends on held targets are ignored.

## Key formulas
- Deal value `V = cash + ratio × acquirer_price`; gross spread `S = V − target_price`.
- Net spread adds carry: target dividends − ratio × acquirer dividends − borrow fee − trading costs.
- Market-implied odds `p = (target − break) / (V − break)`; break-even odds use the net payoff.

## Validation
- Analytic case from the source video: $15 offer, $14 price, $10 break price gives p = 0.8.
- Implied odds re-price the target exactly for random inputs.
- Stock-deal hedge (long 1 target, short `ratio` acquirer) earns the same spread for any acquirer
  price at close.

## Run
```
pip install -e '.[dev]'
pytest && ruff check .
```

## Known limits
- Term extraction is regex over free text. Every deal carries the sentences it was read from, and
  the page links to the filing; check before relying on a number.
- Close dates are guesses (30 days for tenders, 120 for definitive proxies) when the filing
  doesn't state one in a form the scanner reads; those rows are marked.
- Yahoo's chart endpoint is free but unofficial and may change or rate-limit.
- Collars, CVRs, ticking fees and elections are flagged, not valued.
- Ignores the short leg's P&L when a stock deal breaks, competing bids, collars, CVRs, margin
  interest and taxes; holds dividends fixed in the delay table.
