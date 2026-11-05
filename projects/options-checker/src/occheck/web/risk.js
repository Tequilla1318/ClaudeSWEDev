import { loadOccheck } from "./py.js";

const $ = (id) => document.getElementById(id);
const status = (msg, isError = false) => {
  $("status").textContent = msg;
  $("status").classList.toggle("error", isError);
};
const pct = (x) => (x * 100).toFixed(1) + "%";
const SVG = "http://www.w3.org/2000/svg";

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function svgEl(tag, attrs) {
  const n = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}

function drawFan(band, xs) {
  const svg = $("chart");
  const W = 700, H = 300, L = 44, R = 12, T = 10, B = 28;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.replaceChildren();
  const n = xs[xs.length - 1];
  // Log scale: a 50% loss and a 100% gain are the same distance from 1x.
  const floor = 0.125;
  const lo = Math.max(floor, Math.min(0.5, ...band[5]));
  const hi = Math.max(2, ...band[95]);
  const ly = (v) => Math.log2(Math.max(v, floor));
  const x = (i) => L + (xs[i] / n) * (W - L - R);
  const y = (v) => T + (1 - (ly(v) - ly(lo)) / (ly(hi) - ly(lo))) * (H - T - B);
  const area = (a, b) => {
    const top = b.map((v, i) => `${x(i)},${y(v)}`);
    const bot = a.map((v, i) => `${x(i)},${y(v)}`).reverse();
    return `M${top.join("L")}L${bot.join("L")}Z`;
  };
  for (const t of [0.125, 0.25, 0.5, 1, 2, 4, 8, 16, 32].filter((t) => t >= lo && t <= hi)) {
    svg.append(svgEl("line", { x1: L, x2: W - R, y1: y(t), y2: y(t), class: t === 1 ? "axis-start" : "grid" }));
    const lab = svgEl("text", { x: L - 6, y: y(t) + 4, "text-anchor": "end", class: "tick" });
    lab.textContent = t + "x";
    svg.append(lab);
  }
  const xl = svgEl("text", { x: W - R, y: H - 6, "text-anchor": "end", class: "tick" });
  xl.textContent = `trade ${n}`;
  svg.append(xl);
  svg.append(svgEl("path", { d: area(band[5], band[95]), class: "band-outer" }));
  svg.append(svgEl("path", { d: area(band[25], band[75]), class: "band-inner" }));
  svg.append(svgEl("polyline", { points: band[50].map((v, i) => `${x(i)},${y(v)}`).join(" "), class: "median" }));
}

function row(status, title, display, why) {
  const li = el("li");
  li.append(el("span", `stamp ${status}`, { flag: "Flag", watch: "Watch", ok: "OK", info: "Info" }[status]));
  const body = el("div");
  body.append(el("h3", null, title), el("p", "display", display), el("p", "why", why));
  li.append(body);
  return li;
}

function render(r) {
  const f = r.final_percentiles;
  $("headline").replaceChildren(
    el("span", "net", pct(r.prob_drawdown)),
    document.createTextNode(`of simulated runs fell ${r.drawdown_pct}% or more from a peak at some point in ${r.trades} trades`),
  );
  drawFan(r.band, r.band_x);
  const kellyText = r.kelly > 0
    ? `Kelly fraction ${pct(r.kelly)}; you risk ${r.risk_vs_kelly.toFixed(2)}x Kelly`
    : "Negative edge: no amount of risk per trade grows the account on average";
  const rows = [
    row(r.edge > 0 ? "ok" : "flag", "Edge per trade",
      `${r.edge >= 0 ? "+" : ""}${(r.edge * 100).toFixed(1)}% of the amount risked, on average (payoff ratio ${r.payoff.toFixed(2)})`,
      "Win rate alone says nothing. A 60% win rate loses money if the average loss is more than 1.5 times the average win."),
    row(r.kelly <= 0 ? "flag" : r.risk_vs_kelly > 1 ? "flag" : r.risk_vs_kelly > 0.5 ? "watch" : "ok",
      "Risk per trade vs Kelly", kellyText,
      "The Kelly fraction maximizes long-run growth if your numbers are exactly right. Above it, growth falls and drawdowns get much deeper. Many practitioners use half Kelly or less because the inputs are only estimates."),
    row(r.prob_ruin > 0.05 ? "flag" : r.prob_ruin > 0.01 ? "watch" : "ok", "Runs that lost 80% or more",
      pct(r.prob_ruin), "An 80% loss needs a 400% gain to get back to even."),
    row("info", "Where runs ended",
      `Median ${f[50].toFixed(2)}x; bad run (5th percentile) ${f[5].toFixed(2)}x; good run (95th) ${f[95].toFixed(2)}x`,
      "The median is a typical outcome. The 5th percentile is what 1 in 20 runs did, or worse."),
  ];
  $("ledger").replaceChildren(...rows);
  $("result").hidden = false;
}

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("run").disabled = true;
  try {
    const py = await loadOccheck(status);
    status("Simulating…");
    const args = ["win", "avgwin", "avgloss", "risk", "trades", "dd"].map((id) => parseFloat($(id).value));
    if (args.some((v) => !Number.isFinite(v) || v <= 0)) {
      status("Fill in every field with a positive number.", true);
      return;
    }
    py.globals.set("args", py.toPy(args));
    const out = py.runPython(`
import json
from occheck.risk import risk_report
w, aw, al, rk, n, dd = args
try:
    _r = json.dumps({"ok": risk_report(w, aw, al, rk, int(n), dd)})
except ValueError as exc:
    _r = json.dumps({"error": str(exc)})
_r`);
    const res = JSON.parse(out);
    if (res.error) { status(res.error, true); return; }
    status("");
    render(res.ok);
  } catch (err) {
    status("Something failed while loading or running the simulation: " + err.message, true);
  } finally {
    $("run").disabled = false;
  }
});
if (new URLSearchParams(location.search).has("run")) $("run").click();
else loadOccheck(status).catch(() => {});
