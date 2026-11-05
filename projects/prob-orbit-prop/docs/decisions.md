# Decisions — prob-orbit-prop

Append-only. Format: date — decision — why — alternatives rejected.

- 2026-11-01 — (proposed) C++20 core with pybind11 bindings; Python for orchestration/stats/plots —
  Google Benchmark and perf need native code; interpreter overhead would mask integrator differences —
  rejected: pure Python + Numba.
- 2026-11-01 — (proposed) Implement integrators from scratch; cross-check DOP853 against SciPy —
  comparing integrators is the point of the project — rejected: wrapping SciPy/Boost.Odeint only.
- 2026-11-01 — (proposed) Common random numbers across integrators — differences in the propagated
  distribution are then attributable to the integrator alone and paired errors are available —
  rejected: independent ensembles per integrator (sampling noise would swamp small integrator effects).
- 2026-11-01 — (proposed) Drag deferred to M5 behind `ForceModel::velocity_dependent()`; symplectic
  integrators refuse velocity-dependent forces — keeps v1 pure-gravity while making drag a drop-in —
  rejected: adding drag in v1.
- 2026-11-01 — Owner approved C++20 + pybind11 core; Python formatted with black (ruff for lint only) —
  owner requirement — rejected: ruff format.
- 2026-11-01 — v1 scope: LEO only, EGM2008 70×70, 7-day horizon; Gauss–Jackson/Kepler-split deferred —
  owner choice; keeps compute affordable on a 2-vCPU VM — rejected: four regimes × three horizons in v1.
- 2026-11-01 — Headline metric = integrator error / ensemble spread — owner choice — rejected: Pc as headline.
- 2026-11-01 — N = 20,000 default, batches of 5,000, stop when headline and covariance SE < 1 %, cap 1e5
  (see design §3.5.1) — owner asked for more precision than 1e4; 2e4 halves tail-probability noise vs 1e4
  while the reference ensemble stays ~8–14 h on 2 vCPUs (estimate, to be measured in story 10) —
  rejected: 1e5 fixed (~40–70 h), 1e4 fixed (owner wanted more precision).
- 2026-11-01 — Truncated EGM2008 table (≤ 120×120) committed with provenance + SHA-256 — owner approved;
  tests run offline — rejected: download at test time.
- 2026-11-01 — Side project on long-lived branch `project/prob-orbit-prop`, never merged to `main`; story PRs
  target that branch — owner instruction — rejected: merging the project into main.
- 2026-11-01 — Build: scikit-build-core + CMake ≥ 3.24 + pybind11; static `pop_core` library linked into the
  extension and the Catch2 tests; Release by default, no `-ffast-math` — one build serves pip, CTest and later
  Google Benchmark — rejected: setuptools + pybind11 setup helpers (no clean path to CTest/benchmarks).
- 2026-11-01 — Catch2 v3.7.1 via CMake FetchContent from GitHub (pinned tag) — GitHub is reachable from the
  cloud session and CI; no system package needed — rejected: GoogleTest (heavier; either would do).
- 2026-11-01 — C++ CI in a project-specific workflow `.github/workflows/prob-orbit-prop.yml` on the project
  branch (clang-format, `-Werror` build, CTest); Python stays in the shared `ci.yml` — keeps main's CI untouched
  — rejected: adding a CMake step to the shared workflow on main.
- 2026-11-01 — clang-format: Google style, 100-column limit — owner had no preference; Google is a common
  default and 100 columns fits template-heavy numeric code — rejected: LLVM style.
