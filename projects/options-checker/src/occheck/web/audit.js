import { loadOccheck } from "./py.js";

const $ = (id) => document.getElementById(id);
const status = (msg, isError = false) => {
  $("status").textContent = msg;
  $("status").classList.toggle("error", isError);
};
const STAMP = { flag: "Flag", watch: "Watch", ok: "OK", info: "Info", na: "No data" };

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function render(report) {
  const s = report.summary;
  const money = (x) => (x < 0 ? "-$" : "$") + Math.abs(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  $("summary").replaceChildren(
    el("span", "net", money(s.net_pnl)),
    document.createTextNode(`net realized P&L from ${s.round_trips} closed trades (${s.trades} executions)`),
  );
  $("ledger").replaceChildren(...report.metrics.map((m) => {
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
  $("notes").replaceChildren(...report.warnings.map((w) => el("p", null, "Note: " + w)));
  $("disclaimer").textContent = report.disclaimer;
  $("report").hidden = false;
  $("report").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

async function run(text) {
  $("run").disabled = true;
  try {
    const py = await loadOccheck(status);
    const acct = parseFloat($("account").value);
    py.globals.set("csv_text", text);
    py.globals.set("account_value", Number.isFinite(acct) && acct > 0 ? acct : null);
    const out = py.runPython(`
import json
from occheck.brokers.ibkr_flex import FlexFormatError
from occheck.report import report_from_csv
try:
    _r = json.dumps({"ok": report_from_csv(csv_text, account_value)}, default=str)
except FlexFormatError as exc:
    _r = json.dumps({"error": str(exc)})
_r`);
    const res = JSON.parse(out);
    if (res.error) {
      status("This file can't be read: " + res.error + ".", true);
      return;
    }
    status("");
    render(res.ok);
  } catch (err) {
    status("Something failed while loading or running the report: " + err.message, true);
  } finally {
    $("run").disabled = false;
  }
}

async function runFile(file) {
  if (!file) { status("Choose a CSV file first.", true); return; }
  run(await file.text());
}

$("form").addEventListener("submit", (e) => { e.preventDefault(); runFile($("file").files[0]); });
$("sample").addEventListener("click", async () => run(await (await fetch("sample-trades.csv")).text()));
const form = $("form");
["dragenter", "dragover"].forEach((t) => form.addEventListener(t, (e) => { e.preventDefault(); form.classList.add("dragover"); }));
["dragleave", "drop"].forEach((t) => form.addEventListener(t, (e) => { e.preventDefault(); form.classList.remove("dragover"); }));
form.addEventListener("drop", (e) => runFile(e.dataTransfer.files[0]));
if (new URLSearchParams(location.search).has("sample")) {
  $("sample").click(); // shareable demo link: audit.html?sample
} else {
  loadOccheck(status).catch(() => {}); // warm up while the user finds their file
}
