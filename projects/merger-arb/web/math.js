// Merger-arb math. Mirrors src/mergerarb/core.py line for line; tests/test_js_parity.py
// checks the two agree. Keep both in sync.
const MA = (() => {
  const DAYS = 365;

  function validate(d) {
    if (!(d.target_price > 0)) throw new Error("Target price must be above zero.");
    if (!(d.days_to_close > 0)) throw new Error("Days to close must be above zero.");
    if (d.ratio < 0 || d.cash < 0) throw new Error("Cash and ratio can't be negative.");
    if (d.ratio > 0 && !(d.acquirer_price > 0))
      throw new Error("Enter the acquirer's price for a stock deal.");
    if (d.cash === 0 && d.ratio === 0) throw new Error("The offer needs cash, stock, or both.");
  }

  const dealValue = (d) => d.cash + d.ratio * d.acquirer_price;
  const borrowCost = (d, days = d.days_to_close) =>
    (d.borrow_fee_rate * d.ratio * d.acquirer_price * days) / DAYS;
  const carry = (d, days = d.days_to_close) =>
    d.target_dividends - d.ratio * d.acquirer_dividends - borrowCost(d, days) - d.trading_costs;

  function annualize(r, days) {
    if (r < -1) throw new Error("return below -100%");
    if (r === -1) return -1;
    return Math.pow(1 + r, DAYS / days) - 1;
  }

  const impliedProbability = (price, payoff, fallback) =>
    payoff === fallback ? NaN : (price - fallback) / (payoff - fallback);

  function analyze(d) {
    validate(d);
    const v = dealValue(d);
    const t = d.target_price;
    const s = v - t;
    const c = carry(d);
    const sn = s + c;
    const notes = [];
    if (s < 0)
      notes.push(
        "Negative spread: the target trades above the offer. The market may expect a higher bid, or a price is stale."
      );
    if (d.fallback_price >= t)
      notes.push(
        "The break price is at or above today's price, so a failed deal wouldn't lose money and the implied odds don't mean much."
      );
    if (d.ratio > 0)
      notes.push(
        `Stock deal: the offer's value moves with the acquirer. Shorting ${+d.ratio.toFixed(4)} acquirer shares per target share locks in the spread.`
      );
    const r = sn / t;
    return {
      deal_value: v,
      gross_spread: s,
      carry: c,
      borrow_cost: borrowCost(d),
      net_spread: sn,
      gross_return: s / t,
      net_return: r,
      annualized_net_return: r >= -1 ? annualize(r, d.days_to_close) : -1,
      loss_if_break: d.fallback_price - t,
      implied_probability: impliedProbability(t, v, d.fallback_price),
      breakeven_probability: impliedProbability(t, t + sn, d.fallback_price),
      hedge_shares_per_target: d.ratio,
      notes,
    };
  }

  function expectedReturn(d, q) {
    const a = analyze(d);
    return (q * a.net_spread + (1 - q) * a.loss_if_break) / d.target_price;
  }

  function delayTable(d, extras = [0, 90, 180, 365]) {
    return extras.map((x) => {
      const days = d.days_to_close + x;
      const r = (dealValue(d) - d.target_price + carry(d, days)) / d.target_price;
      return { days, net_return: r, annualized: r >= -1 ? annualize(r, days) : -1 };
    });
  }

  function positionSize(d, account, maxLoss) {
    const per = d.target_price - d.fallback_price;
    if (!(account > 0) || !(maxLoss > 0 && maxLoss <= 1) || !(per > 0)) return null;
    const shares = Math.floor((account * maxLoss) / per);
    return {
      target_shares: shares,
      acquirer_shares_short: Math.round(shares * d.ratio),
      capital: shares * d.target_price,
      loss_if_break: shares * per,
    };
  }

  return { analyze, expectedReturn, delayTable, positionSize, annualize, impliedProbability };
})();
if (typeof module !== "undefined") module.exports = MA;
