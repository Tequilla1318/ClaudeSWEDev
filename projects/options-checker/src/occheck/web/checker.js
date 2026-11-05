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

const exp = new Date();
exp.setDate(exp.getDate() + 30);
$("expiry").value = iso(exp);
if (new URLSearchParams(location.search).has("run")) $("run").click();
else loadOccheck(status).catch(() => {});
