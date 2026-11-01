# Context — prob-orbit-prop

## Current state
- Design proposed in `design.md` (PR: design doc). **Nothing implemented yet.** Waiting for owner approval.

## Next
- After approval: create GitHub issues for the stories in design.md §6, then start M1 story 1 (scaffold).

## Known issues / gotchas
- Design session (2026-11-01): PyPI unreachable (DNS), earth-info.nga.mil blocked by proxy (403),
  `perf` not installed and perf_event_paranoid=2, `gh` token invalid. GitHub over git works.
  Check these again at the start of the next session (design.md §7, §8).
- Drag is intentionally out of v1; it comes in M5 on its own branch(es) behind the `ForceModel` interface.
