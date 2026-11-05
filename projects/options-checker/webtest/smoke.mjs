// Browser smoke test: loads the built site in headless Chrome, runs the sample report
// through Pyodide, and checks the rendered report card.
// Usage: SITE_URL=http://127.0.0.1:8765/ CHROME=/usr/bin/google-chrome node smoke.mjs [shot.png]
import puppeteer from "puppeteer-core";

const site = process.env.SITE_URL ?? "http://127.0.0.1:8765/";
const args = ["--no-sandbox", "--disable-gpu"];
if (process.env.HTTPS_PROXY) {
  // Cloud dev sessions route through a TLS-inspecting proxy; CI does not set this.
  args.push(`--proxy-server=${process.env.HTTPS_PROXY}`, "--proxy-bypass-list=127.0.0.1;localhost",
    "--ignore-certificate-errors");
}
// CI runners sometimes take longer than puppeteer's default 30 s to start Chrome; allow
// 90 s and retry once before failing.
async function launch() {
  const opts = { executablePath: process.env.CHROME ?? "/usr/bin/google-chrome", headless: true, args, timeout: 90_000 };
  try {
    return await puppeteer.launch(opts);
  } catch (err) {
    console.error("Chrome did not start, retrying once:", err.message);
    return puppeteer.launch(opts);
  }
}
const browser = await launch();
const fail = (msg) => { console.error("SMOKE FAIL:", msg); process.exitCode = 1; };
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 900, height: 1200 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(site + "audit.html?sample", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#report:not([hidden])", { timeout: 180_000 });
  const stamps = await page.$$eval(".ledger .stamp", (els) => els.map((e) => e.textContent));
  const net = await page.$eval(".summary .net", (e) => e.textContent);
  console.log("net:", net, "stamps:", stamps.join(", "));
  if (stamps.length !== 8) fail(`expected 8 metrics, got ${stamps.length}`);
  if (net !== "$1,442.45") fail(`expected net $1,442.45, got ${net}`);
  if (errors.length) fail("page errors: " + errors.join("; "));
  if (process.argv[2]) await page.screenshot({ path: process.argv[2], fullPage: true });

  // Risk calculator: default inputs (75% wins, $100 / $250, 10% risked).
  await page.goto(site + "risk.html?run", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#result:not([hidden])", { timeout: 180_000 });
  const riskRows = await page.$$eval("#ledger .display", (els) => els.map((e) => e.textContent));
  const bands = await page.$$eval("#chart path", (els) => els.length);
  console.log("risk:", riskRows[1]);
  if (riskRows.length !== 4) fail(`expected 4 risk rows, got ${riskRows.length}`);
  if (!riskRows[1].includes("Kelly fraction 12.5%")) fail("Kelly fraction should be 12.5%");
  if (bands !== 2) fail(`expected 2 chart bands, got ${bands}`);
  if (process.argv[3]) await page.screenshot({ path: process.argv[3], fullPage: true });

  // Backtester: needs the /data endpoint of `occheck serve` (not available on static hosting).
  if (process.env.SMOKE_BACKTEST) {
    await page.goto(site + "backtest.html?run", { waitUntil: "domcontentloaded" });
    await page.waitForSelector("#result:not([hidden])", { timeout: 240_000 });
    const stressRows = await page.$$eval("#stress-table tbody tr", (els) => els.length);
    const headline = await page.$eval("#headline .net", (e) => e.textContent);
    console.log("backtest:", headline, "stress rows:", stressRows);
    if (stressRows < 5) fail(`expected >= 5 stress periods, got ${stressRows}`);
    if (process.argv[4]) await page.screenshot({ path: process.argv[4], fullPage: true });
  }
  if (errors.length) fail("page errors: " + errors.join("; "));
} catch (err) {
  fail(err.message);
} finally {
  await browser.close();
}
