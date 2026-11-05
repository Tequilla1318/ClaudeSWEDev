# merger-arb

Merger-arbitrage calculator: for a pending acquisition it shows the spread, the market-implied
odds that the deal closes, the annualized return if it closes on time, the loss if it breaks,
how delays hurt the return, and position sizing by break loss. Cash, stock and mixed deals.

Educational tool, not financial advice. It does not place trades or recommend deals.

## Layout
- `src/mergerarb/core.py` — the math (pure Python, no dependencies).
- `web/math.js` — the same math for the browser; `tests/test_js_parity.py` checks it matches Python.
- `web/page.html` + `web/build.py` — the single-file calculator page (`python web/build.py` writes
  `web/dist/index.html`, which is git-ignored).

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
Ignores the short leg's P&L when a stock deal breaks, competing bids, collars, CVRs, margin
interest and taxes; holds dividends fixed in the delay table.
