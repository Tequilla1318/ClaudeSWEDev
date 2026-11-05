import { loadOccheck } from "./py.js";

const $ = (id) => document.getElementById(id);
const status = (msg, isError = false) => {
  $("status").textContent = msg;
  $("status").classList.toggle("error", isError);
};
const STAMP = { flag: "Flag", watch: "Watch", ok: "OK", info: "Info", na: "No data" };
const iso = (d) => d.toISOString().slice(0, 10);

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function render(out) {
  const s = out.summary;
  const money = (x) => "$" + x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  $("headline").replaceChildren(
    el("span", "net", `${s.side === "buy" ? "Pay" : "Collect"} ${money(s.premium_total)}`),
    document.createTextNode(`at the ${s.side === "buy" ? "ask" : "bid"}, ${s.days} day(s) to expiry. Most you can lose: ${s.max_loss}.`),
  );
  $("ledger").replaceChildren(...out.items.map((m) => {
    const li = el("li");
    li.append(el("span", `stamp ${m.status}`, STAMP[m.status] ?? m.status));
    const body = el("div");
    const src = el("p", "src");
    const a = el("a", null, m.research.label);
    a.href = m.research.url;
    a.rel = "noopener";
    src.append("Research: ", a);
    body.append(el("h3", null, m.title), el("p", "display", m.display), el("p", "why", m.explanation), src);
    li.append(body);
    return li;
  }));
  $("disclaimer").textContent = out.disclaimer;
  $("result").hidden = false;
}

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("run").disabled = true;
  try {
    const py = await loadOccheck(status);
    const fields = { today: iso(new Date()) };
    for (const id of ["side", "right", "contracts", "spot", "strike", "expiry", "bid", "ask", "event", "rv", "rate"]) {
      fields[id] = $(id).value;
    }
    if (!fields.expiry) { status("Choose an expiry date.", true); return; }
    py.globals.set("form_json", JSON.stringify(fields));
    const out = JSON.parse(py.runPython(`
import json
from occheck.pretrade import check_from_form
try:
    _r = json.dumps({"ok": check_from_form(json.loads(form_json))})
except ValueError as exc:
    _r = json.dumps({"error": str(exc)})
_r`));
    if (out.error) { status(out.error.charAt(0).toUpperCase() + out.error.slice(1) + ".", true); return; }
    status("");
    render(out.ok);
  } catch (err) {
    status("Something failed while loading or running the checker: " + err.message, true);
  } finally {
    $("run").disabled = false;
  }
});

// --- Delayed-quote prefill: only when served by `occheck serve` on this computer. ---
let chainRows = [];
const qStatus = (msg) => { $("q-status").textContent = msg; };

async function loadSymbol() {
  const sym = $("q-symbol").value.trim();
  if (!sym) { qStatus("Type a symbol first."); return; }
  qStatus(`Loading ${sym.toUpperCase()} from Cboe…`);
  const r = await fetch(`quotes/${encodeURIComponent(sym)}.json`);
  const s = await r.json();
  if (!r.ok) { qStatus(s.error || "Quotes unavailable."); return; }
  $("spot").value = Math.round(s.spot * 100) / 100;
  $("q-expiry").replaceChildren(...s.expiries.map((e) => { const o = el("option", null, e); o.value = e; return o; }));
  $("q-expiry").disabled = false;
  qStatus(`${s.symbol || sym.toUpperCase()} at ${s.spot}, Cboe delayed quote as of ${s.timestamp} UTC (about 15 minutes old).`);
  fetch(`prices/${encodeURIComponent(sym)}.json`).then((r) => r.json()).then((p) => {
    if (p.realized_vol) {
      $("rv").value = (p.realized_vol * 100).toFixed(1);
      $("q-status").textContent += ` Realized vol over the last 21 trading days: ${(p.realized_vol * 100).toFixed(1)}% (Yahoo Finance).`;
    }
  }).catch(() => {});
  const soon = s.expiries.find((e) => (new Date(e) - new Date()) / 864e5 >= 25) || s.expiries[0];
  $("q-expiry").value = soon;
  await loadExpiry();
}

async function loadExpiry() {
  const sym = $("q-symbol").value.trim(), exp = $("q-expiry").value;
  const r = await fetch(`quotes/${encodeURIComponent(sym)}/${exp}.json`);
  const s = await r.json();
  if (!r.ok) { qStatus(s.error || "Quotes unavailable."); return; }
  chainRows = s.options;
  const spot = s.spot;
  $("q-contract").replaceChildren(...chainRows.map((o, i) => {
    const opt = el("option", null, `${o.right === "C" ? "Call" : "Put"} ${o.strike} — bid ${o.bid.toFixed(2)} / ask ${o.ask.toFixed(2)}`);
    opt.value = String(i);
    return opt;
  }));
  // Default to the call nearest the money.
  let best = 0;
  chainRows.forEach((o, i) => { if (o.right === "C" && Math.abs(o.strike - spot) < Math.abs(chainRows[best].strike - spot)) best = i; });
  $("q-contract").value = String(best);
  $("q-contract").disabled = false;
  $("expiry").value = exp;
  fillContract();
}

function fillContract() {
  const o = chainRows[Number($("q-contract").value)];
  if (!o) return;
  $("right").value = o.right;
  $("strike").value = o.strike;
  $("bid").value = o.bid;
  $("ask").value = o.ask;
}

$("q-load").addEventListener("click", () => loadSymbol().catch((e) => qStatus("Quotes failed: " + e.message)));
$("q-symbol").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); $("q-load").click(); } });
$("q-expiry").addEventListener("change", () => loadExpiry().catch((e) => qStatus("Quotes failed: " + e.message)));
$("q-contract").addEventListener("change", fillContract);
fetch("quotes/ping").then((r) => { if (r.ok) $("prefill").hidden = false; }).catch(() => {});

const exp = new Date();
exp.setDate(exp.getDate() + 30);
$("expiry").value = iso(exp);
if (new URLSearchParams(location.search).has("run")) $("run").click();
else loadOccheck(status).catch(() => {});
