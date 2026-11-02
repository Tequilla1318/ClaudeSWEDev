# infinite-local-chat — design doc

Status: **draft, awaiting owner approval** · Author: Claude · Date: 2026-11-02

## 1. Goal

A local chat assistant for the owner's MacBook (M1 Pro, 16 GB unified memory, macOS) that:

1. **Starts with one command.** Type `ilc` in a terminal → model server comes up (or is reused) →
   browser opens on a chat page. No manual model setup after a one-time install.
2. **Never loses information in a conversation** ("infinite context"), however long it runs.
3. **Uses a small, flat number of tokens per turn**, so it stays fast and fits in 16 GB.

Model: **Qwen3.5-9B** (Apache-2.0, released Feb 2026), 4-bit GGUF.

### What "infinite context" means here
Not a bigger context window. The model sees a **fixed-size window** each turn; everything else
lives in a **lossless store** on disk and is paged back in when relevant. This is the MemGPT idea
(context window as RAM, external store as disk) combined with Polygres-style hybrid retrieval
(vector + full-text + graph, fused). Every message is kept verbatim forever; summaries are an
index into it, never a replacement for it.

## 2. Scope

**In scope (v1)**
- macOS on Apple Silicon only. One user, local only (binds to `127.0.0.1`).
- One-time installer + `ilc` launcher; model download on first run.
- Browser chat UI with streaming, multiple conversations, conversation list.
- Memory layer: lossless message store, rolling summaries, hybrid retrieval, context assembler
  with a fixed token budget.
- OpenAI-compatible endpoint (`/v1/chat/completions`) so other tools (editors, scripts) can use the
  same memory-backed model.
- Evaluation harness that measures memory quality against a published benchmark.

**Out of scope (v1)**
- Linux/Windows, multiple users, remote access, auth.
- Uploading large documents or codebases (possible later; the store would support it).
- Fine-tuning, KV-cache compression research (InfiniPot-style), anything needing a GPU server.
- Images (Qwen3.5 is multimodal; text only for v1).

## 3. Key constraints and numbers

| Item | Estimate | Source / note |
|---|---|---|
| Weights, Qwen3.5-9B 4-bit GGUF | ~5.1–5.5 GB | Size of a published IQ4_NL quant; Q4_K_M is similar |
| KV cache, 16k-token window | ≤ ~1 GB (f16), ~0.5 GB (q8_0) | 32 layers, 4 KV heads, head_dim 256; only the full-attention layers (about half or fewer, the rest are Gated DeltaNet linear attention with fixed-size state) hold KV. Layer ratio **unverified**; measured in S2 |
| Embedding model (~0.3–0.6B, 8-bit) | ~0.3–0.6 GB | Candidate chosen in S7 |
| App + SQLite | < 0.3 GB | |
| **Total** | **~7–8 GB** | Leaves room for macOS, a browser and normal apps |

The model supports a 262k native context, but on 16 GB that is not affordable, and prefill on an
M1 Pro is the real latency cost. So the window is **capped at 16k tokens** and the prompt budget
per turn at **~8k tokens** (configurable).

## 4. Approach

### 4.1 Runtime: llama.cpp `llama-server` (Metal)
- Installed via Homebrew (`brew install llama.cpp`). Runs GGUF on the M1 GPU through Metal,
  exposes an OpenAI-compatible HTTP API, a `/tokenize` endpoint, and prompt-prefix caching.
- Two processes: one for chat (Qwen3.5-9B), one small `--embeddings` server.
- Alternatives considered: **Ollama** (easiest install, but less control over KV-cache type,
  slot/prefix caching and model files; we would still need our own memory layer), **MLX**
  (fast on Apple Silicon, but a second ecosystem and weaker embedding/server story),
  **LM Studio** (GUI app, not scriptable enough). Recorded in `decisions.md`.
- **Idle shutdown:** servers stop after N minutes idle (default 30) to give RAM back; next
  message restarts them (~5–15 s cold start, to be measured).
- **Thinking mode off by default.** Qwen3.5 thinks by default, which burns tokens; a per-message
  toggle turns it on.

### 4.2 Memory: SQLite only, no database server
One file, `~/.ilc/memory.db`:

- `messages` — every turn verbatim (id, conversation, role, text, timestamp, token count).
- `chunks` — retrieval units (a message, or a user+assistant pair), with:
  - **FTS5** index (BM25 full-text),
  - **sqlite-vec** table (embedding vectors, exact search).
- `summaries` — hierarchical: level-1 summary per block of ~20 turns, level-2 summary of
  summaries, each pointing to the message ids it covers.
- `entities`, `relations` — the graph (M3): `(subject, predicate, object, source_message_id)`.
- `core_memory` — a short, model-maintained list of standing facts (names, preferences, goals),
  capped at ~500 tokens.

Why exact vector search instead of HNSW (what pgContext/Polygres use): a personal conversation
store is tens of thousands of chunks, not millions. Brute force at that size is a few
milliseconds and has perfect recall, so an ANN index adds complexity for no gain. Revisit if the
store passes ~500k chunks.

### 4.3 Retrieval: hybrid, fused, bounded
For each new user message:
1. Full-text (FTS5 BM25) top 20 and vector top 20 over chunks of this conversation.
2. Fuse with **reciprocal-rank fusion** (RRF, k=60) — the same method pgContext uses.
3. (M3) Graph expansion: entities in the query → 1-hop facts → their source chunks join the pool.
4. Drop chunks already in the recent window; take the top chunks that fit the retrieval budget.

Retrieval never grows with history: the budget is fixed, so "RAG blowing up" cannot happen.

### 4.4 Context assembly (fixed budget, cache-friendly order)

```
[system prompt]            ~300  tokens   stable
[core memory]              ≤500           changes rarely
[conversation summary]     ≤1000          changes only on compaction
[recent turns, verbatim]   ≤4000          append-only between compactions
[recalled from earlier]    ≤2000          changes every turn
[current user message]
```

The order is deliberate: everything above "recalled" only grows by appending between
compactions, so llama.cpp's prompt cache reuses it and each turn only pre-fills the recalled
block plus the new message. This keeps latency and tokens per turn low.

**Compaction:** when recent turns exceed their budget, the oldest ~20 turns move out of the
window, get a level-1 summary (background, after the reply is sent), and stay searchable verbatim.

### 4.5 Background "memory writer"
After each reply, off the critical path: embed new chunks, update summaries when due, update core
memory, and (M3) extract entity/relation triples. If the laptop is busy, this work queues.

### 4.6 UI and launcher
- **FastAPI** app on `127.0.0.1:8765`: serves one static HTML/JS chat page (no build step, no
  Node), streams via server-sent events, exposes `/v1/chat/completions`.
- A "memory" side panel per answer shows which earlier messages were recalled (for trust and
  debugging).
- `ilc` command: ensure servers are up → start the app → open the browser. `ilc stop`,
  `ilc status`, `ilc doctor` (checks RAM, disk, Homebrew, Metal).
- **Install:** `brew install llama.cpp` + `uv tool install` of this package from GitHub, wrapped
  in one `install.sh`. First `ilc` run downloads the GGUFs from Hugging Face (resumable,
  checksum-verified).

## 5. Architecture

```
 browser ──HTTP/SSE──▶ ilc app (FastAPI, Python)
                         │  ├─ conversation API + /v1/chat/completions
                         │  ├─ context assembler (token budget)
                         │  ├─ retriever (FTS5 + sqlite-vec + RRF [+ graph])
                         │  └─ memory writer (background queue)
                         │            │
                         │       ~/.ilc/memory.db (SQLite, single file)
                         ▼
               llama-server :8080 (Qwen3.5-9B, Metal)    llama-server :8081 (embeddings)
```

Package layout: `src/ilc/{cli.py, server/, memory/, retrieval/, assembler.py, llm_client.py}`.
Stack: Python 3.11+, FastAPI, httpx, sqlite3 + sqlite-vec, pytest, ruff.

**Build vs reuse:** inference (llama.cpp), storage (SQLite, FTS5, sqlite-vec) and the web
framework are existing libraries. The memory layer (assembler, compaction, hybrid retrieval,
graph) is written here, because that is the point of the project and no off-the-shelf piece
fits a 16 GB laptop without a database server. Mem0/Letta-style frameworks were considered but
pull in a server or a hosted backend.

## 5a. References

- MemGPT: Packer et al., *MemGPT: Towards LLMs as Operating Systems*, 2023 (memory paging idea).
- Polygres / pgContext (Evokoa): HNSW + Postgres full-text fused with RRF; Apache-2.0
  (github.com/Evokoa/pgContext). Our retrieval mirrors its fusion step.
- Cormack, Clarke, Büttcher, *Reciprocal Rank Fusion outperforms Condorcet and individual rank
  learning methods*, SIGIR 2009 (RRF, k=60).
- Maharana et al., *Evaluating Very Long-Term Conversational Memory of LLM Agents* (LoCoMo), 2024.
- Qwen3.5-9B model card (Qwen, Feb 2026): 262k native context, hybrid Gated DeltaNet + attention.
- sqlite-vec (Alex Garcia) and SQLite FTS5 for the hybrid index.

## 6. Validation (how we know memory works)

Retrieval quality is ours to prove, since we are not using a benchmarked engine:

- **Reference benchmark: LoCoMo** (very long multi-session conversations with QA, and each
  question annotated with the evidence turns). Downloaded at test time, not committed.
- **Metric 1, retrieval recall@k:** fraction of questions whose evidence turns are in what the
  assembler puts in the window. Deterministic, cheap, runs in CI on a subset.
- **Metric 2, QA accuracy:** answers from Qwen3.5-9B (run in a cloud session on CPU, slow but
  fine for a subset), scored against gold answers.
- **Baselines:** (a) recent-window only (what a normal chat does after truncation),
  (b) vector-only RAG, (c) full text in context where it fits. Our system should beat (a) and (b)
  at the same token budget. Graph retrieval (M3) is kept **only if** it measurably helps.
- Optional: run the same chunks through pgContext (Docker) as an external reference for the
  retrieval stage.

## 7. Milestones and stories

**M1 — Boot and chat (no memory yet)**
- **S1** Scaffold: `pyproject.toml`, `ilc` CLI skeleton, config file, CI green.
- **S2** Model manager: download GGUFs (resumable, checksum), start/stop/health-check
  `llama-server` with Metal and q8 KV cache, idle shutdown; measure RAM and cold-start time.
- **S3** Chat app: FastAPI + static chat page, SSE streaming, conversations stored verbatim in
  SQLite, conversation list, thinking-mode toggle.
- **S4** Installer + launcher: `install.sh`, `ilc` opens the browser, `ilc doctor`; macOS smoke
  test (see open question 2).

**M2 — Infinite conversation memory**
- **S5** Context assembler with token budget (token counts via `/tokenize`), cache-friendly order.
- **S6** Compaction: hierarchical summaries in the background writer.
- **S7** Hybrid retrieval: embeddings server, FTS5 + sqlite-vec + RRF, recall panel in UI.
- **S8** Evaluation harness: LoCoMo recall@k + QA subset, baselines (a)–(c), results in docs.
- **S9** Core memory + OpenAI-compatible `/v1/chat/completions` for other tools.

**M3 — Graph memory (Polygres-style)**
- **S10** Triple extraction in the memory writer, `entities`/`relations` tables.
- **S11** Graph-expanded retrieval; keep or drop based on S8 harness results.
- **S12** (optional) pgContext comparison on the same corpus.

After M1 the owner can already use it daily; M2 delivers the "never forgets" behavior.

## 8. Testing strategy

- Unit tests with a **fake LLM/embedding client** (deterministic) for assembler, retrieval,
  compaction, RRF, budgets.
- Integration tests in the cloud session against real `llama-server` on CPU with a tiny GGUF
  model, so CI stays fast; Qwen3.5-9B only for the S8 evaluation runs.
- macOS-specific parts (Metal flags, browser opening, installer) can't run on Linux CI: covered
  by a macOS GitHub Actions job if available (open question 2), otherwise flagged as tested only
  by the owner's first install.

## 9. Risks

- **9B quality.** Summaries and triple extraction by a 9B model will sometimes be wrong. Mitigated
  by keeping verbatim text as the source of truth; summaries only steer retrieval.
- **Latency on M1 Pro.** Prefill of several thousand tokens per turn may take seconds;
  mitigated by the cache-friendly order. Measured in S2/S5.
- **Retrieval misses.** If a needed detail isn't recalled, the model won't know it. The recall
  panel makes misses visible; S8 quantifies them.
- **Dependency drift.** llama.cpp moves fast; pin a tested version in the installer.

## 10. Open questions for the owner

1. **Running on your Mac.** CLAUDE.md says never ask you to run code locally, but this product
   only works on your laptop. Proposal: all development and testing happen in cloud sessions; you
   run `install.sh` once and then use `ilc` like any app. OK? (If yes, I'll add a note to the
   project README rather than changing CLAUDE.md.)
2. **macOS CI.** Is ClaudeSWEDev public? GitHub's macOS runners are free for public repos and
   cost minutes on private ones. Without them, Mac-only paths are untested until your first install.
3. **Memory across conversations.** Default: each conversation has its own lossless memory, plus
   one shared core-memory list (your name, preferences) used by all chats. Want fully separate
   chats, or one shared memory across everything?
4. **Command name** `ilc` — fine, or prefer something else?
