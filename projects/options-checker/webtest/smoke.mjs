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
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  headless: true,
  args,
});
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
} catch (err) {
  fail(err.message);
} finally {
  await browser.close();
}
