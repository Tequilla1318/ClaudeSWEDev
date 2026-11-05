# Where the report-card thresholds come from

As of 2026-11-05. Every cut-off is a field of `occheck.audit.Thresholds` and can be changed on the
auditor page under "Adjust what gets flagged".

A threshold is **research-anchored** when a published number sets it. It is a **judgment call**
when the research shows a pattern costs money but gives no cut-off. Judgment calls are marked so
nobody mistakes them for findings.

## Summary

| Field | Default | Basis | Type |
| --- | --- | --- | --- |
| `turnover_watch` | 0.8x a year | Average household turnover, about 80% a year (Barber & Odean 2000) | research-anchored |
| `turnover_flag` | 1.15x a year | Most active fifth: at least 9.6% a month. They earned 10.0% net against 17.1% for the market (Barber & Odean 2000) | research-anchored |
| `commission_watch` | 10% of gross profits | Costs are the largest single loss channel. Commissions were 32% of Taiwan individuals' trading losses (Barber, Lee, Liu & Odean 2009). No paper gives a "share of profits" cut-off | judgment call |
| `commission_flag` | 25% of gross profits | As above | judgment call |
| `lottery_max_premium` | $0.50 | Cheap, short-dated, out-of-the-money options carry the most skew. Higher-skew options earn lower returns, by 10–50% a week across portfolios (Boyer & Vorkink 2014). Retail favours cheap weekly options (Bryzgalova et al. 2023). The $0.50 line itself is not from a paper | judgment call, pattern research-backed |
| `lottery_max_dte` | 7 days | Weekly options are the retail favourite, with 12.6% average spreads (Bryzgalova et al. 2023) | judgment call, pattern research-backed |
| `lottery_watch` | 5% of long premium | A small lottery share is common. No cut-off in the literature | judgment call |
| `lottery_flag` | 25% of long premium | As above | judgment call |
| `zero_dte_flag` | 25% of option trades | Any 0DTE trading is a "watch". Retail lost about $350k a day on SPX 0DTE (Beckmeyer, Branger & Gayda 2023) | judgment call, pattern research-backed |
| `disposition_ratio_watch` | 1.2x | A clear tilt toward holding losers longer than winners (a ratio of 1.0 means no tilt) | judgment call |
| `disposition_ratio_flag` | 1.5x | The size of the effect in the research. Odean's investors sold winners about 1.5x as readily as losers (PGR 14.8% vs PLR 9.8%). Professional futures traders held losers about 1.6x as long as winners (268 vs 166 seconds; Garvey & Murphy 2004) | research-anchored |
| `high_win_rate` | 60% | Flags "wins most trades but loses money": the short-volatility payoff shape. Systematic put selling wins about 78–84% of trades in this project's backtests. The 60% line is a judgment call | judgment call |
| `concentration_flag` | 5% of account in one loss | The forum position-size rule of 5–10% per trade (r/thetagang wheel guide). Underdiversified individual portfolios are the norm, and they bear unrewarded risk (Goetzmann & Kumar 2008) | judgment call (practitioner rule) |
| `min_samples` | 5 trades | Smallest sample where a pattern is worth showing. A statistical judgment call, not a test | judgment call |

## Notes on the changes this review made

- **Disposition:** the flag moved from 1.2x to **1.5x**, the effect size two independent studies
  found. 1.2x is now the "watch" level. Before this, a modest tilt was flagged as if it matched
  the research.
- **Turnover** uses Barber & Odean's own definition: half of traded notional over account value,
  the average of buy and sell turnover. That keeps their numbers comparable.
- Everything else is unchanged and now labelled for what it is.

## The 0.9 x VIX constant in the backtester

The backtester prices options at volatility = VIX x 0.9. Two sources support a ratio of about 0.9:

- **Why VIX sits above at-the-money vol.** VIX is computed from out-of-the-money puts and calls
  across many strikes, each weighted by 1/K² (Cboe VIX methodology). That makes VIX² a 30-day
  variance-swap rate, not an at-the-money implied vol. Carr & Wu (2006) find the new VIX averages
  **about 2 vol points above** the bias-corrected at-the-money measure (VXOA). They attribute the
  gap to Jensen's inequality and the variance of volatility, which the steep put skew amplifies.
  At a typical VIX of 18–22, 2 points is a ratio of 0.89–0.91.
- **Fit to the real index.** Fitted on 2007–2016, the ratio that best matches the Cboe PutWrite
  index is 0.90. It holds out of sample on 2017–2026: +0.92 points a year of CAGR and 0.978
  monthly correlation. Details: [put-replication.md](../validation/put-replication.md).

A fixed ratio is still an average. The gap widens when the skew steepens, so the backtester's
caveats stay.

## Sources

- [Barber & Odean (2000), Trading Is Hazardous to Your Wealth](https://faculty.haas.berkeley.edu/odean/papers/returns/returns.html)
- [Barber, Lee, Liu & Odean (2009), Just How Much Do Individual Investors Lose by Trading?](https://scispace.com/pdf/just-how-much-do-individual-investors-lose-by-trading-1mpuvvflu9.pdf)
- [Odean (1998), Are Investors Reluctant to Realize Their Losses?, PGR/PLR values via Wikipedia's summary](https://en.wikipedia.org/wiki/Disposition_effect)
- [Garvey & Murphy (2004), Are Professional Traders Too Slow to Realize Their Losses?](https://ideas.repec.org/a/taf/ufajxx/v60y2004i4p35-43.html)
- [Boyer & Vorkink (2014), Stock Options as Lotteries](https://ideas.repec.org/a/bla/jfinan/v69y2014i4p1485-1527.html)
- [Bryzgalova, Pavlova & Sikorskaya (2023), Retail Trading in Options](https://academicnewsletter.sufe.edu.cn/info/359005)
- [Beckmeyer, Branger & Gayda (2023), 0DTE retail losses, via Neudata](https://neudata.co/literature-reviews/zero-day-to-expiry-options-a-losing-bet-for-retail-traders)
- [Goetzmann & Kumar (2008), Equity Portfolio Diversification](https://www.nber.org/papers/w8686.pdf)
- [r/thetagang, The Wheel Strategy: An In-Depth Overview](https://lr.eu.psf.lt/r/thetagang/comments/1e6g9v2/the_wheel_strategy_an_indepth_overview)
- [Carr & Wu (2006), A Tale of Two Indices](https://engineering.nyu.edu/sites/default/files/2021-03/carrwutaleoftwoindices.pdf)
- [Cboe VIX methodology](https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf)

Several figures come from abstracts or summaries rather than the full papers, as noted above.
