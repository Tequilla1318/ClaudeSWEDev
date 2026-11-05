# options-checker — design doc

Status: **draft, awaiting owner approval** · Author: Claude · Date: 2026-11-05

## 1. Goal

Free, open tools that show traders, from beginners to experienced premium sellers, **where their
money actually goes**. The goal is to make visible the losses the research measures: costs, overpaying
for volatility, bad timing, oversizing and behavioral bias. It is **not** to generate signals or
tell anyone what to trade.

The evidence behind this framing is in
[`research/stock-market-returns-review.md`](research/stock-market-returns-review.md). In short:
fewer than 1% of day traders show persistent skill. The rest lose through measurable, avoidable
channels, and a tool can measure each of those channels.

Hard constraints from the owner:
- **Free data only.** No paid feeds, no API keys.
- **Runs as a static GitHub Pages site** if possible; otherwise a localhost app the user downloads.
- **Audience:** traders at every level. Every number on screen gets a plain-language explanation and
  a link to the research behind it.

Every page states that this is an educational tool, not financial advice.

## 2. Scope

**In scope (v1).** Four tools sharing one Python core:

| Tool | What it answers | Data it needs | Where it runs |
| --- | --- | --- | --- |
| **Trade-log auditor** (headline) | "What is my trading actually costing me, and which known biases show up in my trades?" | The user's own IBKR Flex CSV export | Browser (GitHub Pages) |
| **Position-size and risk-of-ruin calculator** | "How likely is this sizing to blow up my account?" | User inputs only | Browser |
| **Pre-trade option checker** | "Is this option trade expensive before I even pick a direction?" | User-entered quote; optional delayed chain in localhost mode | Browser; live data in localhost mode only |
| **Premium-selling backtester** | "What would the r/thetagang rules have done through 2008, 2018, 2020 and 2022, net of costs?" | Free Cboe index histories (SPX, VIX, PUT, BXM) + FRED T-bill rates | Browser with user-supplied CSVs, or localhost with auto-download |

**Out of scope (v1)**
- Placing trades, broker API connections, storing credentials (including IBKR Flex Web Service tokens).
- Recommendations, signals, screeners that rank trades to take.
- Backtests on individual stocks' options. There is no free historical single-name option data.
- Brokers other than IBKR (the parser is pluggable, so others can be added later).
- User accounts or a server: nothing a user uploads ever leaves their browser.

**Backlog (post-v1):** a backtest honesty checker (deflated Sharpe ratio, number of trials), other
broker CSV formats, and an earnings-calendar overlay for the auditor.

## 3. Approach

### 3.1 One Python core, two shells
All math lives in one pure-Python package, `occheck` (numpy/scipy, no I/O in the core). It is
tested with pytest in CI like every other project in this repo. Two thin shells use it:

1. **Static web app (GitHub Pages).** An HTML/JS page loads **Pyodide** (CPython compiled to
   WebAssembly, which ships numpy and scipy) and installs the `occheck` wheel in the browser. Files the
   user drops in are read locally by JavaScript and handed to Python. There is no backend, and no
   data leaves the browser.
2. **Localhost (`occheck serve`).** It serves the same static site from `127.0.0.1`, plus a small local
   endpoint that can download free data (Cboe, FRED) on the user's own machine. This removes the
   browser CORS limit (§3.3) without the project republishing anyone's data.

This keeps the repo's Python/pytest/ruff defaults. The same code runs in both places, so a bug fixed
once is fixed everywhere.

### 3.2 Trade-log auditor (milestone 2, the headline)
Input is an IBKR Flex Query CSV containing trades, with stocks and options. IBKR lets users export
this from the web portal, so no token is needed. The pipeline:

1. **Parse** the CSV into a normalized `Trade` model: symbol, asset class, side, quantity,
   multiplier, price, commission, fees, open/close flag, and for options the right, strike and
   expiry.
2. **Match** opens to closes FIFO into round trips, handling expiries, assignments and exercises.
3. **Report card** metrics, each tied to a finding in the research review:

| Metric | Definition | Research link |
| --- | --- | --- |
| Cost drag | (commissions + fees) / gross P&L, and per trade | French 2008 |
| Turnover | Traded notional / average equity, annualized | Barber & Odean 2000 |
| Expectancy vs win rate | Mean P&L per trade next to hit rate; flags "high win rate, negative expectancy" | thetagang / short-vol skew |
| Disposition (holding-time) | Median days held, winners vs losers | Odean 1998 |
| Disposition (PGR − PLR) | Odean's proportion of gains realized minus proportion of losses realized. Needs daily prices for open positions, so localhost mode only | Odean 1998 |
| Lottery share | % of option premium spent on long, cheap (< $0.50), short-dated (≤ 7 DTE) OTM options; 0DTE share | Bali et al. 2011; Beckmeyer et al. 2023 |
| Buyer vs seller split | P&L and premium split by long vs short options | Bryzgalova et al. 2023; de Silva et al. |
| Concentration | Largest single-position loss as % of account | March 2020 lessons |

The thresholds (< $0.50, ≤ 7 DTE) are starting values, recorded in `decisions.md` and shown on screen.

### 3.3 Data: free, and not republished
Probing the free sources from a session on 2026-11-05 showed:

- **Cboe** serves free daily CSVs for SPX (since 1975), VIX (since 1990), PUT (since 1991) and BXM
  (since 2002), plus a delayed option-chain JSON. **None of them send CORS headers**, so a GitHub
  Pages page cannot fetch them directly.
- **FRED** (T-bill rates `DTB3`/`DGS3MO`, VIX `VIXCLS`) has no CORS headers either.

Two options remain: republish their data on our Pages site (terms unclear, risky), or have the user's
machine fetch it. The design takes the second:
- **Browser:** the user downloads the CSVs from Cboe/FRED (one link each, shown on the page) and drags
  them in. The page checks the file headers and tells the user what's missing.
- **Localhost:** `occheck serve` downloads them on the user's machine on request and caches them locally.
- **CI tests** use small, hand-trimmed fixture files.

### 3.4 Premium-selling backtester (milestone 4)
There is no free historical SPX option-chain data. The backtester therefore **prices synthetic
options** with Black-Scholes:

- Underlying: SPX close.
- Volatility: VIX scaled to each option's moneyness by a simple skew model, with the skew
  parameter documented.
- Risk-free rate: 3-month T-bill.
- Costs: a configurable bid-ask spread as % of premium.

This is a real approximation, and it **gets checked against a reference before any rule results are
trusted**. Cboe's PUT index is exactly a mechanical, cash-secured monthly ATM SPX put-writing strategy
with published history. Step one replicates the PUT methodology synthetically and reports tracking
error against the real PUT index. Only then are the forum rules (delta targets, DTE, 50% take-profit,
21-DTE roll, sizing) layered on. Results report CAGR, max drawdown, worst month, and a per-stress-period
table (2008, Feb 2018, Mar 2020, 2022) next to buy-and-hold SPX.

Single-stock wheels can't be backtested on free data; the page says so plainly.

### 3.5 Pre-trade checker and risk calculator
- **Pre-trade checker.** The user enters bid, ask, IV, strike, expiry and an optional earnings date. The
  checker shows the spread as % of mid, break-even, the expected move implied by IV, and IV vs. recent
  realized volatility when price history is available. It flags cases matching the "Losing is Optional"
  pattern, such as a wide spread with an earnings event inside the expiry. Localhost mode can prefill
  from Cboe's delayed chain (subject to open question Q4).
- **Risk-of-ruin calculator.** Inputs are win rate, average win, average loss and fraction of account
  risked per trade. It runs a Monte Carlo of equity paths, then shows probability of a 50% drawdown and
  of ruin, the median path, and the full-Kelly fraction for comparison.

## 4. Validation (repo Definition of Done)

| Component | Reference | Pass criterion |
| --- | --- | --- |
| Black-Scholes price and Greeks | Hull, *Options, Futures and Other Derivatives*: S=42, K=40, r=10%, σ=20%, T=0.5 → call 4.76, put 0.81; put-call parity; finite-difference Greeks | Prices within 0.01; parity to 1e-10; Greeks within 1e-4 of finite differences |
| Implied-vol solver | Round trip: price at σ, solve back | \|σ̂ − σ\| < 1e-6 across a grid of strikes and expiries |
| Round-trip matching and P&L | Hand-built fixture trade logs with known answers, including assignment, expiry and partial fills | Exact match |
| Disposition PGR/PLR | Worked example built from Odean (1998)'s definitions | Exact match |
| Risk of ruin | Closed-form gambler's ruin for the fixed-bet case | Monte Carlo within 3 standard errors |
| Synthetic put-write | Cboe PUT index history | Tracking error and CAGR difference reported in the PR. Target: monthly-return correlation ≥ 0.9 and CAGR within 1.5 points/yr. If it misses, the PR says so and why before any rule results are trusted. |

## 5. Architecture

```
projects/options-checker/
├── pyproject.toml            # occheck package; numpy, scipy; dev: pytest, ruff
├── src/occheck/
│   ├── pricing.py            # Black-Scholes, Greeks, IV solver
│   ├── trades.py             # Trade model, FIFO round-trip matcher
│   ├── brokers/ibkr_flex.py  # CSV parser -> Trade (pluggable per broker)
│   ├── audit.py              # report-card metrics
│   ├── risk.py               # risk of ruin, Kelly
│   ├── backtest/             # synthetic chain, PUT replication, rule engine
│   ├── data.py               # validate user-supplied CSVs; local download (localhost only)
│   └── cli.py                # `occheck serve`, `occheck audit <csv>`
├── web/                      # static site: index.html, per-tool pages, JS glue, Pyodide loader
├── tests/                    # pytest + fixtures (trimmed CSVs, synthetic trade logs)
└── docs/ design.md · context.md · decisions.md · research/
```

**Deploy.** A new workflow, `.github/workflows/pages-options-checker.yml`, runs on pushes to `main` that
touch this project. It builds the `occheck` wheel, copies `web/`, and publishes to
`https://tequilla1318.github.io/ClaudeSWEDev/options-checker/`. GitHub allows **one Pages site per
repo**. This workflow publishes under a subpath so other projects can add their own later, but they
would need to share the one deploy job.

**Performance.** Pyodide plus numpy/scipy download about 10–15 MB on first load, then the browser caches
it. The page shows a loading bar. If that feels too slow in practice, the fallback is to port only
the auditor to plain JavaScript. That isn't planned.

## 6. Milestones and stories

Each story is one branch and one PR, targeting under ~400 changed lines.

**M1 — Core and pricing**
- **S1** Scaffold: `pyproject.toml`, `occheck` package, README, CI picks it up, `occheck --version`.
- **S2** Black-Scholes pricer, Greeks and IV solver, with validation against Hull and parity (§4).

**M2 — Trade-log auditor (Python)**
- **S3** IBKR Flex CSV parser to the `Trade` model. Fixtures are synthetic exports in IBKR's documented
  column layout.
- **S4** FIFO round-trip matcher, including expiry, assignment and exercise, plus P&L, cost drag and
  turnover.
- **S5** Bias metrics: holding-time disposition, lottery share, 0DTE share, buyer/seller split,
  concentration. Output is a JSON report card with plain-language text per metric.

**M3 — Web app on GitHub Pages**
- **S6** Static site plus Pyodide loader. The auditor page accepts a dropped CSV and renders the report
  card. Adds `occheck serve` and the Pages deploy workflow.
- **S7** Risk-of-ruin and position-size calculator page, with Monte Carlo validated against the closed form.

**M4 — Premium-selling backtester**
- **S8** Data loaders and validators for Cboe SPX/VIX/PUT/BXM and FRED T-bills, the drag-in flow on the
  web, and auto-download in localhost mode.
- **S9** Synthetic put-write replication of the PUT index, with a tracking-error report. This is a
  validation gate.
- **S10** Rule engine (delta, DTE, take-profit, roll, sizing, spread cost), a stress-period table, and a
  backtester web page.

**M5 — Pre-trade checker**
- **S11** Manual-entry checker page with spread, break-even, expected move and event flags. Localhost
  delayed-chain prefill depends on Q4.

After approval, each story becomes a GitHub issue under an epic per milestone.

## 7. Risks and limitations

- **Synthetic option prices aren't real fills.** VIX describes 30-day ATM SPX volatility; deep OTM
  strikes and other tenors rely on the skew model. S9's comparison with the PUT index measures the error
  rather than assuming it away.
- **IBKR Flex layouts vary** with the fields each user selects. The parser will need a documented
  "required columns" list and clear errors. Without a real export (Q3) the fixtures are synthetic, and
  the first real file may surface surprises.
- **Some metrics need price history** that the trade log doesn't contain: PGR/PLR, and IV vs realized for
  single names. The browser version omits these and says why. Localhost mode can fill them in.
- **Data terms.** Cboe and FRED terms on reuse were not reviewed in depth. Not republishing their data
  sidesteps most of this, but Q4 covers the delayed-chain endpoint, which is unofficial.
- **Pyodide first-load size** (§5).
- **Not advice.** Labels and copy describe what happened or what is likely; they never say what to
  do.

## 8. Open questions for the owner

1. **Enable GitHub Pages.** In repo Settings → Pages, set Source to "GitHub Actions". Sessions can't
   change repo settings. This is only needed by S6.
2. **Stack.** I propose Python in the browser via Pyodide (§3.1), so we keep one tested codebase. The
   alternative is a TypeScript front end with the math rewritten in TS: faster load, but two
   codebases. OK with Pyodide?
3. **A real IBKR Flex export.** Can you provide an anonymized or paper-trading export (Flex Query, Trades
   section, CSV)? It would replace guesswork in S3. Synthetic fixtures work otherwise.
4. **Cboe delayed option-chain endpoint.** It's free and works server-side, but it isn't a documented
   public API. Is localhost-only use for prefilling the checker acceptable, or should the checker stay
   manual-entry only?
5. **Thresholds.** Lottery share uses < $0.50 premium and ≤ 7 DTE. Keep these, or do you have your own
   definition?

## 9. References

- Research review: [`research/stock-market-returns-review.md`](research/stock-market-returns-review.md),
  with all sources.
- Hull, J. *Options, Futures and Other Derivatives* (Black-Scholes worked example; Greeks).
- Odean, T. (1998). Are investors reluctant to realize their losses? *Journal of Finance* 53(5)
  (PGR/PLR definitions).
- Cboe S&P 500 PutWrite Index (PUT) methodology and daily history: cdn-api.cboe.com daily_prices CSVs.
- FRED: 3-month Treasury bill rates (`DTB3`), VIX (`VIXCLS`).
- Pyodide: https://pyodide.org (CPython + numpy/scipy in WebAssembly).
