# Context: local-llm-fallback

Feedback last read: 2026-11-02

## State
- **Parked.** Design doc on main; no code until the owner buys the home server and un-parks it.
- Depends on PR #6 (wake-on-merge workflow), which S2 generalizes.

## Next
- When un-parked: resolve open questions in design §10, then S1 (move rules to AGENTS.md).

## Gotchas
- Self-hosted runners must not run on a public repo's fork PRs; make the repo private first.
- Cloud sessions can't fetch model weights or use a GPU; real-model tests run on the home server.
