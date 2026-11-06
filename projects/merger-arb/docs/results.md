# merger-arb — backtest results

Window 2011-11-01 to 2026-10-30, CAD 100,000 start, values in CAD after IBKR costs and tax.
Generated from `results.json` by the backtest; see the README for method and biases.

## Non-registered, about $100k other income

| Strategy | End value | Per year | Worst drop |
|---|---|---|---|
| Merger arb | $260,597 | +6.6% | -13% |
| Momentum long-short | $65,201 | -2.8% | -70% |
| S&P 500 (SPY) | $899,565 | +15.8% | -28% |
| TSX (XIC) | $388,464 | +9.5% | -37% |

## Non-registered, about $60k

| Strategy | End value | Per year | Worst drop |
|---|---|---|---|
| Merger arb | $263,404 | +6.7% | -13% |
| Momentum long-short | $65,320 | -2.8% | -70% |
| S&P 500 | $912,028 | +15.9% | -28% |
| TSX | $395,035 | +9.6% | -37% |

## Non-registered, top bracket

| Strategy | End value | Per year | Worst drop |
|---|---|---|---|
| Merger arb | $229,313 | +5.7% | -14% |
| Momentum long-short | $63,774 | -3.0% | -70% |
| S&P 500 | $754,668 | +14.4% | -28% |
| TSX | $315,290 | +8.0% | -37% |

## TFSA (momentum can't short in a TFSA: shown before tax)

| Strategy | End value | Per year | Worst drop |
|---|---|---|---|
| Merger arb (cash deals) | $300,676 | +7.6% | -13% |
| Momentum, before tax | $67,297 | -2.6% | -70% |
| S&P 500 | $1,082,119 | +17.2% | -28% |
| TSX | $445,536 | +10.5% | -37% |

## Taxed as business income, about $100k

| Strategy | End value | Per year | Worst drop |
|---|---|---|---|
| Merger arb | $222,672 | +5.5% | -15% |
| Momentum | $81,767 | -1.3% | -62% |

## Variants and references (before tax unless noted)

| Strategy | End value | Per year | Worst drop |
|---|---|---|---|
| Merger arb, TFSA, currency held constant | $214,741 | +5.2% | -3% |
| Merger arb, TFSA, 3% per deal | $242,336 | +6.1% | -14% |
| Merger arb, TFSA, 10% per deal | $380,439 | +9.3% | -13% |
| Momentum, currency held constant | $48,063 | -4.8% | -68% |
| S&P 500, TFSA, currency held constant | $772,843 | +14.6% | -34% |
| The Merger Fund (MERFX) | $231,286 | +5.8% | -12% |
| The Arbitrage Fund (ARBFX) | $208,922 | +5.0% | -13% |
| IQ Merger Arbitrage ETF (MNA) | $219,283 | +5.4% | -12% |
| Fama-French momentum factor (no costs) | $197,300 | +4.7% | -32% |

## Diagnostics

- Merger arb: 3,979 deal groups on EDGAR → 768 tradable ({'closed': 730, 'broke': 28, 'open': 10}); 749 traded, 28 broke, 95% profitable, median hold 46 days, 58% of the book in deals on average.
- Momentum: 83% of index members priced on average (lowest month 67%); 46% of equity traded per month; correlation with Fama-French Mom 0.90 over 178 months.
- Merger-arb drawdowns are understated: open deals are carried at cost (acquired companies' daily prices aren't published).
