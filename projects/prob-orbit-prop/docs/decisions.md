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
