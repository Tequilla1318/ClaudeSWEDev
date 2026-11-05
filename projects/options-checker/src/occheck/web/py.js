// Loads Pyodide, numpy and the occheck Python package into the page.
// Nothing is sent anywhere: files are read locally and passed to Python in memory.
const PYODIDE_VERSION = "v314.0.7";
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VERSION}/full/`;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error(`Could not load ${src}`));
    document.head.appendChild(s);
  });
}

let ready = null;

/** Returns a Pyodide instance with `occheck` importable. Loads once per page. */
export function loadOccheck(onStatus = () => {}) {
  if (ready) return ready;
  ready = (async () => {
    onStatus("Loading Python (first visit downloads about 10 MB, then it's cached)…");
    await loadScript(PYODIDE_URL + "pyodide.js");
    const pyodide = await globalThis.loadPyodide({ indexURL: PYODIDE_URL });
    onStatus("Loading numpy…");
    await pyodide.loadPackage("numpy");
    onStatus("Loading occheck…");
    const base = new URL("py/", document.baseURI);
    const manifest = await (await fetch(new URL("manifest.json", base))).json();
    for (const rel of manifest.files) {
      const text = await (await fetch(new URL(rel, base))).text();
      const path = "/home/pyodide/" + rel;
      pyodide.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
      pyodide.FS.writeFile(path, text);
    }
    pyodide.runPython("import occheck");
    onStatus("");
    return pyodide;
  })();
  ready.catch(() => { ready = null; });
  return ready;
}
