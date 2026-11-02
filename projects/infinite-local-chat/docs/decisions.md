# infinite-local-chat — decisions (append-only)

## 2026-11-02 — SQLite clone instead of running Polygres engines
- **Decision:** Hybrid retrieval (vector + full-text + graph) on SQLite (FTS5 + sqlite-vec),
  no database server. Chosen by the owner.
- **Why:** Polygres's managed service isn't taking new users; running Postgres with pgContext/pgGraph
  locally adds a background server and RAM on a 16 GB laptop, and more setup.
- **Rejected:** Local Postgres + pgContext/pgGraph (kept as an optional reference comparison, S12).

## 2026-11-02 — "Infinite context" = fixed window + lossless store
- **Decision:** Fixed token budget per turn (~8k prompt, 16k window cap); all messages stored
  verbatim; summaries and retrieval page earlier content back in.
- **Why:** Owner's definition is "never loses information in a conversation" with low token use.
  A 262k raw window doesn't fit in 16 GB and is slow to pre-fill on an M1 Pro.
- **Rejected:** Long raw context; KV-cache compression research (InfiniPot) — out of scope.

## 2026-11-02 — llama.cpp `llama-server` as runtime (proposed, pending approval)
- **Why:** Metal on Apple Silicon, GGUF, OpenAI-compatible API, `/tokenize`, prompt-prefix cache,
  KV-cache quantization, one Homebrew install.
- **Rejected:** Ollama (less control over cache/model files), MLX (second ecosystem, weaker
  embedding/server story), LM Studio (GUI, not scriptable enough).

## 2026-11-02 — Exact vector search, no ANN index (proposed)
- **Why:** Personal conversation stores are ~10⁴–10⁵ chunks; brute force is milliseconds with
  perfect recall. Revisit above ~500k chunks.

## 2026-11-02 — Browser UI launched from terminal
- **Decision:** `ilc` command starts servers and opens a local FastAPI + static HTML chat page.
  Owner chose browser UI started from the terminal.
- **Rejected:** Open WebUI (heavy install), terminal-only UI.
