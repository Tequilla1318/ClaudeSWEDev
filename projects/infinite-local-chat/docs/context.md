# infinite-local-chat — context

Feedback last read: 2026-11-02

## State
- Design approved and merged (PR #38). Backlog: epic #43 (M1 boot and chat), stories #39–#42.
- **S1 (#39) in review:** package scaffold, `ilc` CLI (`doctor` and `config` work; `start`/`stop`/
  `status` are stubs), config with validated token budgets, 46 tests.

## What's next
- S2 (#40): model manager — pick exact GGUF files (chat + embedding), download, run `llama-server`,
  idle shutdown, measure RAM and cold start.
- Then S3 (#41) chat app, S4 (#42) installer + launcher + macOS CI.

## Key facts for future sessions
- Target machine: owner's MacBook M1 Pro, 16 GB, macOS. Model: Qwen3.5-9B 4-bit GGUF via llama.cpp.
- "Infinite context" = no information lost within a conversation; fixed-size window + lossless
  SQLite store + hybrid retrieval. Not a bigger context window.
- Owner wants minimal setup: one-time install, then `ilc` opens a browser chat UI.
- The owner's computer is never accessed from sessions; the owner installs and runs the product.
- Repo is public, so macOS GitHub Actions runners are available (used from S4).
- `ILC_HOME` overrides the data dir (`~/.ilc`); tests rely on it to stay isolated.

## Known issues / gotchas
- Qwen3.5-9B full-attention vs linear-attention layer ratio not verified; affects KV-cache size.
  Measure in S2.
- Budget validation reserves `user_message` (1000 tokens); a longer pasted message will need
  truncation or chunking rule in S5.
