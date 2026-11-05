import { loadOccheck } from "./py.js";

const $ = (id) => document.getElementById(id);
const status = (msg, isError = false) => {
  $("status").textContent = msg;
  $("status").classList.toggle("error", isError);
};
const pct = (x, d = 1) => (x === null || x === undefined ? "n/a" : (x * 100).toFixed(d) + "%");
const SVG = "http://www.w3.org/2000/svg";

const NEEDED = {
  SPX: { label: "S&P 500 index history (Cboe)", url: "https://cdn.cboe.com/api/global/us_indices/daily_prices/SPX_History.csv" },
  VIX: { label: "VIX history (Cboe)", url: "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv" },
  DTB3: { label: "3-month T-bill rate (FRED)", url: "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3" },
};
const files = {};

const PRESETS = {
  forum: { delta: 0.3, dte: 45, tp: 50, manage: 21, lev: 1, cost: 3, monthly: false },
  put: { delta: "", dte: 30, tp: "", manage: "", lev: 1, cost: 0, monthly: true },
  far: { delta: 0.16, dte: 45, tp: "", manage: "", lev: 1, cost: 3, monthly: false },
  levered: { delta: 0.3, dte: 45, tp: 50, manage: 21, lev: 2, cost: 3, monthly: false },
};

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function kindOf(text) {
  const h = text.replace(/^﻿/, "").split(/\r?\n/, 1)[0].toUpperCase().split(",").map((s) => s.trim());
  if (h[0] === "DATE" && h[1] === "OPEN" && h.includes("CLOSE")) return "VIX";
  if (h.length === 2 && (h[0] === "DATE" || h[0] === "OBSERVATION_DATE")) return h[1];
  return null;
}

function renderFiles() {
  $("files").replaceChildren(...Object.entries(NEEDED).map(([k, info]) => {
    const li = el("li");
    li.append(el("span", files[k] ? "have" : "need", files[k] ? "Loaded" : "Needed"));
    const a = el("a", null, info.label);
    a.href = info.url;
    a.rel = "noopener";
    li.append(a);
    return li;
  }));
  $("run").disabled = !Object.keys(NEEDED).every((k) => files[k]);
}

async function addFiles(list) {
  const unknown = [];
  for (const f of list) {
    const text = await f.text();
    const k = kindOf(text);
    if (k && NEEDED[k]) files[k] = text;
    else unknown.push(f.name);
  }
  renderFiles();
  if (unknown.length) status(`Not one of the needed files: ${unknown.join(", ")}.`, true);
  else status("");
}

async function tryLocalData() {
  // Under `occheck serve`, the local server downloads these on this machine.
  try {
    const got = await Promise.all(Object.keys(NEEDED).map(async (k) => {
      const r = await fetch(`data/${k}.csv`);
      if (!r.ok) throw new Error(String(r.status));
      return [k, await r.text()];
    }));
    for (const [k, t] of got) files[k] = t;
    $("data-intro").textContent = "Downloaded on this computer by occheck serve. You can also drop newer files here.";
  } catch {
    /* static hosting: the user drops the files */
  }
  renderFiles();
}

function applyPreset(name) {
  const p = PRESETS[name];
  $("delta").value = p.delta; $("dte").value = p.dte; $("tp").value = p.tp;
  $("manage").value = p.manage; $("lev").value = p.lev; $("cost").value = p.cost;
  $("monthly").checked = p.monthly;
}

function svgEl(tag, attrs) {
  const n = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}

function drawChart(c) {
  const svg = $("chart");
  const W = 700, H = 300, L = 44, R = 12, T = 10, B = 24;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.replaceChildren();
  const all = c.strategy.concat(c.spx).filter((v) => v > 0);
  const lo = Math.log2(Math.min(...all)), hi = Math.log2(Math.max(...all));
  const n = c.dates.length - 1;
  const x = (i) => L + (i / n) * (W - L - R);
  const y = (v) => T + (1 - (Math.log2(Math.max(v, 1e-6)) - lo) / (hi - lo || 1)) * (H - T - B);
  for (let t = Math.floor(lo); t <= Math.ceil(hi); t++) {
    const v = 2 ** t;
    svg.append(svgEl("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: v === 1 ? "axis-start" : "grid" }));
    const lab = svgEl("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end", class: "tick" });
    lab.textContent = (v >= 1 ? v : v.toFixed(2)) + "x";
    svg.append(lab);
  }
  let prev = "";
  c.dates.forEach((d, i) => {
    const yr = d.slice(0, 4);
    if (yr !== prev && Number(yr) % 5 === 0) {
      const lab = svgEl("text", { x: x(i), y: H - 6, "text-anchor": "middle", class: "tick" });
      lab.textContent = yr;
      svg.append(lab);
    }
    prev = yr;
  });
  const line = (vals, cls) => svgEl("polyline", { points: vals.map((v, i) => `${x(i)},${y(v)}`).join(" "), class: cls });
  svg.append(line(c.spx, "bench"), line(c.strategy, "strategy"));
}

function table(id, head, rows) {
  const t = $(id);
  const thead = el("thead"), tr = el("tr");
  head.forEach((h) => tr.append(el("th", null, h)));
  thead.append(tr);
  const tbody = el("tbody");
  rows.forEach((r) => {
    const row = el("tr");
    r.forEach((cell) => {
      const td = el("td", cell.cls ?? null, cell.text ?? cell);
      row.append(td);
    });
    tbody.append(row);
  });
  t.replaceChildren(thead, tbody);
}

function render(r) {
  const s = r.strategy, b = r.spx;
  $("headline").replaceChildren(
    el("span", "net", r.wiped_out ? "Account wiped out" : pct(s.cagr) + " a year"),
    document.createTextNode(` from ${r.start} to ${r.end}, against ${pct(b.cagr)} a year for the S&P 500 index (price only), with a worst drop of ${pct(s.max_drawdown)} against ${pct(b.max_drawdown)}.`),
  );
  drawChart(r.chart);
  table("headline-table", ["", "Strategy", "S&P 500 (price)"], [
    ["Return a year", pct(s.cagr), pct(b.cagr)],
    ["Worst drop from a peak", pct(s.max_drawdown), pct(b.max_drawdown)],
    ["Worst month", pct(s.worst_month), pct(b.worst_month)],
  ]);
  table("stress-table", ["Period", "Strategy", "Worst drop inside", "S&P 500"], r.stress.map((p) => [
    `${p.name} (${p.from} to ${p.to})`,
    { text: pct(p.strategy), cls: p.strategy < p.spx ? "worse" : null },
    pct(p.strategy_drawdown),
    pct(p.spx),
  ]));
  const t = r.trades;
  const reasons = Object.entries(t.close_reasons).map(([k, v]) => `${v} ${k}`).join(", ");
  $("trades").textContent = `${t.count} trades; ${pct(t.win_rate, 0)} made money. Average trade ${pct(t.avg_pnl, 2)} of the account, best ${pct(t.best, 1)}, worst ${pct(t.worst, 1)}. Closed by: ${reasons}.`;
  $("result").hidden = false;
}

$("preset").addEventListener("change", (e) => applyPreset(e.target.value));
$("datafiles").addEventListener("change", (e) => addFiles(e.target.files));
const zone = $("datazone");
["dragenter", "dragover"].forEach((t) => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.add("dragover"); }));
["dragleave", "drop"].forEach((t) => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.remove("dragover"); }));
zone.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("run").disabled = true;
  try {
    const py = await loadOccheck(status);
    status("Backtesting 35 years of trades…");
    const num = (id) => ($(id).value === "" ? null : parseFloat($(id).value));
    const args = {
      delta: num("delta"), dte: Math.round(num("dte") ?? 45),
      take_profit: num("tp") === null ? null : num("tp") / 100,
      manage_dte: num("manage") === null ? null : Math.round(num("manage")),
      leverage: num("lev") ?? 1, cost_frac: (num("cost") ?? 0) / 100, monthly: $("monthly").checked,
    };
    py.globals.set("texts", py.toPy([files.SPX, files.VIX, files.DTB3]));
    py.globals.set("rule_json", JSON.stringify(args));
    await new Promise((r) => setTimeout(r, 20)); // let the status paint before Python blocks
    const out = py.runPython(`
import json
from occheck.backtest.rules import backtest_report
try:
    _r = json.dumps({"ok": backtest_report(*texts, **json.loads(rule_json))})
except ValueError as exc:
    _r = json.dumps({"error": str(exc)})
_r`);
    const res = JSON.parse(out);
    if (res.error) { status(res.error, true); return; }
    status("");
    render(res.ok);
  } catch (err) {
    status("Something failed while running the backtest: " + err.message, true);
  } finally {
    $("run").disabled = false;
  }
});

applyPreset("forum");
renderFiles();
tryLocalData().then(() => {
  if (new URLSearchParams(location.search).has("run") && !$("run").disabled) $("run").click();
});
loadOccheck(status).catch(() => {});
