# What Actually Determines Returns in the Stock Market — Research Review

As of 2026-11-05. Exported from the Claude Doc: https://claude.ai/artifact/2pLaagwkkjY9D3ks4eF2b7

## Summary

Most people who make money in stocks do it by owning the market cheaply and holding it. Most people who lose money do it through costs, bad timing, oversized bets, and paying too much for options. Six factors explain most of the outcome:

1. **Costs.** Fees, spreads and taxes take about 0.67% a year from investors as a group. For options buyers they are far larger: spreads run 12–20% of the price.
2. **Behavior.** Investors trade too much, time their buying and selling badly (about 1.2 points a year), sell winners and hold losers, and chase lottery-like payoffs.
3. **Skew.** About 4% of stocks created all the market's net wealth. Concentrated pickers usually miss them, and 79% of professional large-cap funds trailed the index in 2025.
4. **Risk premia.** The equity premium, factor tilts and the volatility risk premium are the real, persistent sources of return. They are pay for bearing risk, and they shrink once published.
5. **Side of the options trade.** Option sellers are paid the volatility risk premium of about 4 points. Retail buyers mostly pay it and lose. Sellers carry the crash risk.
6. **Sizing and survival.** Blowups come from leverage and concentration more than from the strategy chosen.

Only a tiny, persistent minority shows real trading skill: fewer than 1% of Taiwan's day traders. That makes the most useful shovels the ones that measure and expose losses, not ones that promise signals.

## How individual traders actually do

The more often individuals trade, the worse they do. Three large datasets, from three countries, agree on this.

| Study | Sample | Finding |
| --- | --- | --- |
| [Barber & Odean (2000), Journal of Finance](https://faculty.haas.berkeley.edu/odean/papers/returns/returns.html) | 60,000+ US households at a discount broker, 1991–1996 | The 20% who traded most earned 10.0% a year net. The market earned 17.1% (gross). |
| [Barber, Lee, Liu & Odean (2014), Journal of Financial Markets](https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html) | All Taiwan day traders, 1992–2006 | Fewer than 1% earned reliable profits after fees. Past winners did keep winning the next year. |
| [Chague, De-Losso & Giovannetti (2019)](https://ideas.repec.org/p/fgv/eesptd/525.html) | Every Brazilian who day-traded equity futures for 300+ days, 2013–2015 | 97% lost money. Only 0.4% earned more than a bank teller's pay (about US$54 a day). |

The Taiwan result matters for tool-building. Skill exists in a tiny minority, and it persists. For everyone else, trading activity mostly turns into fees and losses.

## Costs and the behavior gap

Investors lose about 1 to 2 points a year before they make a single bad pick: half to fees and trading costs, half to bad timing.

- **Costs.** In aggregate, US investors spent 0.67% of total market value every year (1980–2006) on fees, expenses and trading costs in search of better returns. Since everyone together holds the market, that spending is a pure loss for the group as a whole ([French 2008, Journal of Finance](https://ideas.repec.org/a/bla/jfinan/v63y2008i4p1537-1573.html)).
- **Timing.** From 2016 to 2025, the average dollar in US funds earned 8.7% a year. The funds themselves returned 9.9%. The roughly 1.2-point difference comes from buying after gains and selling after drops ([Morningstar Mind the Gap 2026, via WealthManagement](https://wealthmanagement.com/investing-strategies/investors-miss-out-on-12-of-fund-returns-over-decade)).
- **Where the gap is biggest.** It was 0.4 points for broad US equity funds, 1.2 for sector funds, 1.6 for alternatives, and about 14 for crypto ETFs. The more exciting the product, the worse investors time it.

Taxes come on top of all this. Frequent trading turns long-term gains into short-term gains. In Canada it can also get you treated as a business trader, which taxes profits as income, even inside a TFSA.

## Market structure: a few huge winners, and the pros can't find them either

Stock returns are extremely skewed. Across nearly 26,000 US stocks from 1926 to 2016, just 4.3% of them (1,092 companies) produced all the stock market's wealth creation above Treasury bills. Most stocks, about 58%, did worse than T-bills over their lifetimes ([Bessembinder 2018, Journal of Financial Economics](https://blogs.wpcarey.asu.edu/20180917-do-stocks-outperform-treasury-bills)).

Two things follow from this:

- A concentrated portfolio usually misses the few big winners, so its typical result trails the index even when its average result does not.
- Picking winners is hard even for professionals. In 2025, 79% of active large-cap US funds trailed the S&P 500, the fourth-worst year in SPIVA's 25-year history ([InvestmentNews on SPIVA US Year-End 2025](https://investmentnews.com/equities/active-managers-stumble-again-in-2025-as-large-caps-dominate/265541)). Over 15 years, more than 70% of active funds lagged their benchmark in 38 of 39 categories (SPIVA US Mid-Year 2022).

Owning the whole haystack is the default that the evidence keeps confirming.

## Factor premia: real, but smaller after everyone knows

Systematic tilts do earn extra return over decades. These include value, momentum, profitability and quality, low volatility, and small size. But the extra return shrinks once a factor is published, and many of the published "anomalies" are noise.

- **Decay.** Across 97 published predictors, returns were 26% lower out of sample and 58% lower after publication. The gap suggests about a third of each edge gets traded away once people know about it ([McLean & Pontiff 2016, Journal of Finance](https://academicnewsletter.sufe.edu.cn/info/359722)).
- **The factor zoo.** Researchers have tested hundreds of factors. That much testing guarantees some flukes, so Harvey, Liu and Zhu argue a new factor should clear a t-statistic of 3.0, not the usual 2.0. They conclude most claimed findings are probably false ([NBER w20592](https://www.nber.org/papers/w20592)).
- **The counterpoint.** Jensen, Kelly and Pedersen find that most factors do replicate, including out of sample across 93 countries, and they group into 13 themes ([NBER w28432](https://www.nber.org/papers/w28432)).

The takeaway for a tool: any backtested edge should be reported with how many variants were tried, its out-of-sample performance, and what it earns after costs. Most retail backtests skip all three.

## Options: retail buyers pay the volatility premium; sellers collect it

The structural edge in options sits with the seller. Implied volatility has averaged well above the volatility that actually materialized. Retail traders mostly buy, and they pay that premium plus wide spreads.

**The volatility risk premium.** From 1990 to 2018, the VIX averaged 19.3%. Actual S&P 500 volatility averaged 15.1%, so sellers were paid a 4.2-point premium. The Cboe PutWrite index (PUT), which sells cash-secured S&P puts each month, gained 1,835% from 1986 to 2018. Its volatility was 9.95% a year, against 14.93% for the S&P 500 ([Bondarenko study, Cboe](https://www.cboe.com/insights/posts/white-paper-shows-volatility-risk-premium-facilitated-higher-risk-adjusted-returns-for-put-index/)). AQR found that much of a covered call's risk is uncompensated equity exposure. Hedging that exposure keeps the returns but lowers the risk ([Israelov & Nielsen 2015, FAJ](https://www.aqr.com/insights/research/journal-article/covered-calls-uncovered)).

**What retail option traders experience:**

| Study | Finding |
| --- | --- |
| [Bryzgalova, Pavlova & Sikorskaya (2023), Journal of Finance](https://academicnewsletter.sufe.edu.cn/info/359005) | Retail is now more than 60% of US options volume. Traders favor cheap weekly options, whose average bid-ask spread is 12.6%. They lose money on average. |
| [de Silva, Smith & So, "Losing is Optional"](https://quantpedia.com/how-retail-losses-money-in-option-trading/) | Around earnings, retail loses 5–9% on average, and 10–14% when big moves are expected. That is about $1.5B moved to market makers. Retail overpays for volatility, crosses spreads of about 20% of the option price, and holds losing positions too long. |
| [Beckmeyer, Branger & Gayda (2023), 0DTE](https://neudata.co/literature-reviews/zero-day-to-expiry-options-a-losing-bet-for-retail-traders) | Retail lost about $350k a day on same-day SPX options after daily expirations began in 2022. 0DTE made up more than 75% of retail SPX volume. |

The catch for sellers: the premium is pay for bearing crash risk. A short-volatility book loses money when volatility spikes, as in 2008, February 2018, and March 2020. A tool that shows sellers their worst historical drawdown is as valuable as one that shows buyers their expected loss.

## Behavioral biases that cost money

Three biases show up in nearly every dataset. Each one has a measured price tag.

| Bias | What people do | Measured cost |
| --- | --- | --- |
| Overconfidence | Trade too often. Men trade 45% more than women. | Men's risk-adjusted returns were 1.4 points a year lower than women's. Single men's were 2.3 points lower than single women's ([Barber & Odean 2001, QJE](https://faculty.haas.berkeley.edu/odean/papers/gender/gender.html)). |
| Disposition effect | Sell winners too early and hold losers too long. | Later returns didn't justify the pattern, and it lowers after-tax returns ([Odean 1998, Journal of Finance](https://academicnewsletter.sufe.edu.cn/info/361849)). In options it shows up as holding losers after earnings. |
| Lottery preference | Pay up for stocks and options with big upside spikes. | Stocks with the biggest recent one-day jumps trailed the least spiky by more than 1% a month ([Bali, Cakici & Whitelaw 2011, JFE](https://academicnewsletter.sufe.edu.cn/info/356984)). Cheap out-of-the-money weeklies are the options version. |

These biases are detectable from a trade log. A tool can flag them automatically: turnover, how long winners are held versus losers, and how much of the book sits in lottery-like positions.

## What Reddit and the forums say

The communities have each converged on a philosophy. The experienced posters' rules line up closely with the research: size small, avoid events, mind the spread, and expect the crash.

| Community | Core belief | What the evidence says |
| --- | --- | --- |
| r/wallstreetbets | High-conviction bets, often short-dated options, plus "due diligence" (DD) posts | Before GameStop (January 2021), WSB DD posts did predict returns. Afterwards, that predictive power disappeared as posts shifted to attention-grabbing stocks ([Bradley et al. 2024, Review of Financial Studies](https://academicnewsletter.sufe.edu.cn/info/351572)). |
| r/thetagang, r/Optionswheel | Sell premium: cash-secured puts, covered calls, the wheel | Consistent with the volatility risk premium in the Options section. The main risks the community names are assignment in a falling market, correlated positions, and lagging buy-and-hold in bull markets. |
| r/Bogleheads | Own low-cost index funds, trade rarely, ignore noise | Consistent with the cost, timing and SPIVA findings (approximate, from general knowledge; their wiki wasn't checked for this doc). |
| r/options | Education: Greeks, IV crush, liquidity | IV crush and wide spreads are the mechanisms behind the measured retail losses. |

**Rules of thumb that keep recurring** in r/thetagang's wheel guides ([wheel overview thread](https://lr.eu.psf.lt/r/thetagang/comments/1e6g9v2/the_wheel_strategy_an_indepth_overview)):

- Only sell puts on stocks you would hold. Don't chase high IV.
- Around 0.30 delta, open at 45–60 DTE, close at 50% profit, manage at 21 DTE.
- Keep positions to 5–10% of capital each. Keep spare buying power. Avoid holding through earnings.
- Don't sell covered calls below your cost basis. Watch for many positions in one sector getting assigned together.

**Lessons from the March 2020 crash** ([r/Optionswheel post-mortem](https://redlib.ssps.io/r/Optionswheel/comments/lp22xe/how_the_wheel_worked_in_march_during_the_crash)). The poster who held about 50% cash got through with modest losses. They took assignment on some names, rolled others, and switched to defined-risk spreads. Commenters agreed that overcommitted, concentrated accounts were the ones hurt.

These rules are folk wisdom, not tested results. Most have never been backtested net of costs across crash periods. That gap is a natural first project for a tool.

## Implications: which shovels people need

The best tools wouldn't predict prices. They would make the measured losses visible before or after a trade: costs, overpaying for volatility, bad timing, oversizing, and biased behavior.

| Tool | Loss it targets | Evidence above | Data it needs | Effort |
| --- | --- | --- | --- | --- |
| Trade-log auditor: upload an IBKR Flex report, get a report card | Overtrading, disposition effect, lottery positions, fee drag, timing gap vs buy-and-hold | Barber & Odean; Odean; Bali et al.; Morningstar | Only the user's own statement, no market data | Low–medium |
| Pre-trade option checker | Wide spreads, overpaying for IV before events, IV crush | de Silva et al.; Bryzgalova et al.; Bondarenko | Live or delayed option chains plus earnings dates | Medium |
| Forum-rule backtester: wheel, CSPs and covered calls with the r/thetagang rules | Folk rules never tested net of costs or through crashes | Volatility risk premium; Israelov & Nielsen; thetagang rules | Historical option chains (paid or limited free sets) | High |
| Position-size and risk-of-ruin calculator | Oversizing and margin liquidation | March 2020 lessons; short-vol blowups | None (user inputs) | Low |
| Backtest honesty checker | Data mining and decay after publication | McLean & Pontiff; Harvey et al. | The user's backtest results | Low–medium |

The trade-log auditor stands out as a first project. It needs no market-data subscription, its math is checkable against the papers' definitions, and each finding maps to a measured cost. The forum-rule backtester is the most impressive, but historical option data is its bottleneck.

**Open questions for the owner:**

- Which user is the target: yourself, r/thetagang-style sellers, or beginners?
- Is a paid historical options dataset acceptable (for example ORATS or Cboe DataShop), or free sources only?
- CLI, web app, or both?

## Sources

Pages opened for this review:

- [Barber & Odean 2000, The Common Stock Investment Performance of Individual Investors](https://faculty.haas.berkeley.edu/odean/papers/returns/returns.html)
- [Barber, Lee, Liu & Odean 2014, The cross-section of speculator skill (Taiwan day traders)](https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html)
- [Chague, De-Losso & Giovannetti 2019, Day Trading for a Living?](https://ideas.repec.org/p/fgv/eesptd/525.html)
- [French 2008, The Cost of Active Investing](https://ideas.repec.org/a/bla/jfinan/v63y2008i4p1537-1573.html)
- [Morningstar Mind the Gap 2026, via WealthManagement](https://wealthmanagement.com/investing-strategies/investors-miss-out-on-12-of-fund-returns-over-decade)
- [Bessembinder 2018, Do Stocks Outperform Treasury Bills?](https://blogs.wpcarey.asu.edu/20180917-do-stocks-outperform-treasury-bills)
- [InvestmentNews on SPIVA US Year-End 2025](https://investmentnews.com/equities/active-managers-stumble-again-in-2025-as-large-caps-dominate/265541)
- [SPIVA US overview page (15-year category figure)](https://spglobal.com/spdji/en/spiva/article/spiva-us)
- [McLean & Pontiff 2016, Does Academic Research Destroy Stock Return Predictability?](https://academicnewsletter.sufe.edu.cn/info/359722)
- [Harvey, Liu & Zhu, …and the Cross-Section of Expected Returns](https://www.nber.org/papers/w20592)
- [Jensen, Kelly & Pedersen, Is There a Replication Crisis in Finance?](https://www.nber.org/papers/w28432)
- [Cboe on the Bondarenko PUT index study](https://www.cboe.com/insights/posts/white-paper-shows-volatility-risk-premium-facilitated-higher-risk-adjusted-returns-for-put-index/)
- [Israelov & Nielsen 2015, Covered Calls Uncovered](https://www.aqr.com/insights/research/journal-article/covered-calls-uncovered)
- [Bryzgalova, Pavlova & Sikorskaya 2023, Retail Trading in Options and the Rise of the Big Three Wholesalers](https://academicnewsletter.sufe.edu.cn/info/359005)
- [Quantpedia on de Silva, Smith & So, Losing is Optional](https://quantpedia.com/how-retail-losses-money-in-option-trading/)
- [Neudata on 0DTE retail losses (Beckmeyer, Branger & Gayda)](https://neudata.co/literature-reviews/zero-day-to-expiry-options-a-losing-bet-for-retail-traders)
- [Barber & Odean 2001, Boys Will Be Boys](https://faculty.haas.berkeley.edu/odean/papers/gender/gender.html)
- [Odean 1998, Are Investors Reluctant to Realize Their Losses?](https://academicnewsletter.sufe.edu.cn/info/361849)
- [Bali, Cakici & Whitelaw 2011, Maxing Out](https://academicnewsletter.sufe.edu.cn/info/356984)
- [Bradley, Hanousek, Jame & Xiao 2024, Place Your Bets?](https://academicnewsletter.sufe.edu.cn/info/351572)
- [r/thetagang, The Wheel Strategy: An In-Depth Overview](https://lr.eu.psf.lt/r/thetagang/comments/1e6g9v2/the_wheel_strategy_an_indepth_overview)
- [r/Optionswheel, How the wheel worked in March during the crash](https://redlib.ssps.io/r/Optionswheel/comments/lp22xe/how_the_wheel_worked_in_march_during_the_crash)

Several figures come from each paper's abstract or a secondary summary, not the full text. Check the primary paper before quoting a number in the design doc.
