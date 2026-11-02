# Decisions: local-llm-fallback

- 2026-11-02 — Reuse an existing open-source coding agent instead of writing one. Why: faster, maintained by others; the eval harness picks among candidates. Rejected: custom agent loop.
- 2026-11-02 — Model and agent are chosen by an eval harness at migration time, not fixed in the design. Why: open models change monthly.
- 2026-11-02 — Trigger local work through a self-hosted GitHub Actions runner. Why: reuses the existing GitHub workflow and keeps jobs isolated in containers. Rejected: a polling daemon on the server.
- 2026-11-02 — Parked: design merged to main, implementation deferred until hardware is bought. Kept on main (not a side branch) because the later stories change repo-wide workflows, which must live on the default branch.
