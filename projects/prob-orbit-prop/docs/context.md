# Context — prob-orbit-prop

Feedback last read: 2026-11-01T21:00Z (PRs #2, #4, #5 merged; only comment was the owner's answers on #2, applied)

## Branch model
**Side project: lives on `project/prob-orbit-prop`; never merged to `main`** (owner, 2026-11-01).
Cut story branches from `project/prob-orbit-prop` and open PRs against it. To pick up repo-wide changes
(CI, CLAUDE.md) merge `origin/main` into the project branch via a `chore/` PR.

## Current state
- Design approved (PR #2 merged into the project branch). Backlog: epic #22, stories #8–#21 (design §6 order).
- **Story 1 / #8 (scaffold) — in review.** C++20 core library `pop_core` (`pop::Vec3`, version/build info),
  pybind11 module `prob_orbit_prop._core`, Catch2 tests (CTest), pytest, black + ruff, clang-format (Google,
  100 cols), project CI workflow `.github/workflows/prob-orbit-prop.yml` (C++ build/test/format). No physics yet.

## v1 scope in one line
LEO 400 km / 51.6°, EGM2008 70×70, 7 days, N = 20,000 (stopping rule, §3.5.1); integrators RK4, RK4+Richardson,
DOPRI5, DOP853, Verlet, Yoshida 4/6; headline = integrator error vs ensemble spread.

## Next
- Story 2 / #9: EGM2008 coefficients from ICGEM (icgem.gfz.de is reachable), truncate to 120×120, commit with provenance.
- Then #10 (gravity), #11 (frames + ForceModel).

## How to build/test here
See README "Build and test". Use a venv; pip needs the proxy workaround below.

## Known issues / gotchas
- **PyPI**: `pypi.org` is on the proxy's bypass list but doesn't resolve directly. Route pip through the proxy:
  `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 pip install ...`.
- **EGM2008 source**: icgem.gfz.de works; earth-info.nga.mil times out (owner enabled network egress 2026-11-01).
- **"Run workflow" button not possible yet**: GitHub only shows `workflow_dispatch` for workflows on the default
  branch (`main`), and this project never merges to main. Asked the owner (story 1 PR) how to proceed.
- pybind11 is a build-time dependency only (pip's isolated build). To build the module with plain CMake, install
  pybind11 in the venv and pass `-Dpybind11_DIR=$(python -m pybind11 --cmakedir)`.
- Python is formatted with **black** (`[tool.black]` makes shared CI run `black --check`); ruff lints only.
- `perf` is not installed and perf_event_paranoid=2 in the cloud VM; revisit in story 13/14.
- `gh pr create` fails (GraphQL blocked): use `env -u GH_TOKEN gh api repos/Tequilla1318/ClaudeSWEDev/pulls -X POST ...`.
- The local clone is shallow and only fetches `main` by default; add a fetch refspec per branch you work on.
- Drag is out of v1; M5 on its own branch(es) behind `ForceModel::velocity_dependent()`.
