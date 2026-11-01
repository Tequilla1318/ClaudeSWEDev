# Context — prob-orbit-prop

Feedback last read: 2026-11-01T20:35Z (owner comment on PR #2 read and applied; PR #2 was closed unmerged)

## Current state
- Design in `design.md`, revised with the owner's answers (PR #2). **Nothing implemented yet.**
  Merging PR #2 = design approved.

## v1 scope in one line
LEO 400 km / 51.6°, EGM2008 70×70, 7 days, N = 20,000 (stopping rule, §3.5.1); integrators RK4, RK4+Richardson,
DOPRI5, DOP853, Verlet, Yoshida 4/6; headline = integrator error vs ensemble spread.

## Next
- After merge: create GitHub issues for the stories in design.md §6, then story 1 (scaffold).
- Story 2 (EGM2008 data) is blocked until the owner enables PyPI + earth-info.nga.mil / icgem in network settings.

## Known issues / gotchas
- Python formatting is **black** (owner requirement), not `ruff format`; CI must run `black --check` for
  this project (see the separate chore PR that teaches CI about `[tool.black]`).
- Design session (2026-11-01): PyPI unreachable (DNS), earth-info.nga.mil blocked (403), `perf` not
  installed, perf_event_paranoid=2. `gh pr create` fails (GraphQL blocked) — use
  `env -u GH_TOKEN gh api repos/Tequilla1318/ClaudeSWEDev/pulls -X POST ...` (REST works).
- Drag is out of v1; M5 on its own branch(es) behind `ForceModel::velocity_dependent()`.
