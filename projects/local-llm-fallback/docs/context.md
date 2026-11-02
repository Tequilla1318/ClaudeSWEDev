# Context: local-llm-fallback

Feedback last read: 2026-11-02

## State
- Design doc drafted (`docs/design.md`), awaiting owner approval. No code yet.
- Depends on PR #6 (wake-on-merge workflow), which S2 generalizes.

## Next
- After approval: S1 (move rules to AGENTS.md, CLAUDE.md imports it).

## Gotchas
- Self-hosted runners must not run on a public repo's fork PRs; make the repo private first.
- Cloud sessions can't fetch model weights or use a GPU; real-model tests run on the home server.
