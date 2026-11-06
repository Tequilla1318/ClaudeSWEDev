# merger-arb — decisions

Append-only. Date · decision · why · alternatives rejected.

- 2026-11-05 · Skip the design-doc PR and build directly. · Owner asked ("don't worry about a
  PR, just make the thing"). · Design-first workflow from CLAUDE.md.
- 2026-11-05 · The tool computes and shows; it never places trades or ranks deals to buy. ·
  Owner asked to "trade using that"; order placement and advice are out of scope. · Broker API
  integration.
- 2026-11-05 · SEC contact comes from the `SEC_USER_AGENT` environment variable, never the repo.
  · The SEC requires a contact email; the owner chose the AI-workflow account email for
  requests to sec.gov only. · Hard-coding it; a placeholder address.
- 2026-11-05 · Free prices from Yahoo Finance's chart endpoint. · Same free-data rule as
  options-checker; reachable from cloud sessions. · Paid feeds (Norgate, EODdata) that include
  delisted symbols.
- 2026-11-05 · Backtest entry price comes only from the filing text. · Using a live price as a
  fallback would add broken deals (still listed) but not closed ones (delisted), biasing the
  sample toward losses. · Yahoo fallback at the filing date.
- 2026-11-05 · Outcome rules: Form 25/15 or 8-K 5.01 = closed; 8-K 1.02 within 540 days without
  a completion = broke; a target with no ticker that stopped filing = closed; still listed a year
  on = broke; anything else dropped as unknown. · Cross-checked against known deals (Annie's,
  Capri, First Horizon, Lattice, Jos. A. Bank). · Treating any unresolved deal as a break.
- 2026-11-05 · Book rules: 5% of the book per deal, spread 0–40%, price ≥ $1; 3% and 10%
  variants reported. · Common diversified-arb sizing; >40% spreads are almost all misreads. ·
  Kelly sizing; no spread cap.
- 2026-11-05 · Tax: 2026 Ontario combined rates for every year; 50% inclusion; capital-gains and
  business-income treatments both shown; FX gains on the USD pool realized at average cost. ·
  Owner asked for Toronto taxes at three income levels; CRA can treat active trading as business
  income. · Historical rates per year.
- 2026-11-05 · Momentum: 12-1 signal on point-in-time S&P 500 members, top/bottom 10% equal
  weight, each side 100% of equity, monthly; checked against Fama-French Mom. · The video's
  version in its standard academic form; owner picked long-short US stocks. · Long-only, ETF
  rotation, crypto (offered, not chosen).
