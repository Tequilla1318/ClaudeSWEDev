// Shows whether the server is in stub or live mode. Text only: never innerHTML.
fetch("/api/health")
  .then((r) => r.json())
  .then((data) => {
    document.getElementById("mode").textContent =
      data.mode === "stub" ? "stub (scripted replies, no API key)" : "live";
  })
  .catch(() => {
    document.getElementById("mode").textContent = "server not reachable";
  });
