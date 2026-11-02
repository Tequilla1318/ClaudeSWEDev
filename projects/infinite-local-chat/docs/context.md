# infinite-local-chat — context

Feedback last read: 2026-11-02

## State
- Design doc drafted (`docs/design.md`), PR open, awaiting owner approval. No code yet.

## What's next
- Owner answers the open questions in design §10.
- Then open M1 stories S1–S4 as issues and build S1 (scaffold + CI).

## Key facts for future sessions
- Target machine: owner's MacBook M1 Pro, 16 GB, macOS. Model: Qwen3.5-9B 4-bit GGUF via llama.cpp.
- "Infinite context" = no information lost within a conversation; fixed-size window + lossless
  SQLite store + hybrid retrieval. Not a bigger context window.
- Owner wants minimal setup: one-time install, then one terminal command opens a browser chat UI.
- The owner's computer is never accessed from sessions; the product is installed by the owner.

## Known issues / gotchas
- Qwen3.5-9B full-attention vs linear-attention layer ratio not verified; affects KV-cache size.
  Measure in S2.
- macOS-only code paths can't be tested on Linux CI (see design §10 Q2).
