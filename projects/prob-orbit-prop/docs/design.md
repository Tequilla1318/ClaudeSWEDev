# Design: Probabilistic orbit propagation under EGM2008 gravity — integrator comparison

Status: **revised after owner review 2026-11-01** (owner answered §8; approval = merging this PR)
Project dir: `projects/prob-orbit-prop/`

## 1. Goal

Propagate an *uncertain* Earth-orbit state (a probability distribution, not a single point) under
a high-fidelity EGM2008 spherical-harmonic gravity field, and measure:

1. **How the propagated probability distribution changes with the numerical integrator**
   (RK4, RK4 + Richardson extrapolation, DOPRI5, DOP853, symplectic methods, …), at matched cost
   and at matched tolerance.
2. **Efficiency vs accuracy** of each integrator, measured with Google Benchmark
   (micro/macro benchmarks) and Linux `perf` (hardware counters, hotspots), summarised as
   work-precision diagrams.

The force model is pure gravity in v1, but is built behind an interface so that **atmospheric
drag can be added later** (separate story/branch, see M5) without touching integrators or the UQ layer.

### Motivation (from the two reference videos in the project)
- *Brain Truffle — orbital propagation trick*: swapping the update order turns explicit Euler into
  symplectic Euler; it preserves phase-space area (Poincaré invariants / Liouville) and so has bounded
  long-term energy error instead of secular drift. Wisdom–Holman splitting (Kepler drift + perturbation
  kick) builds on this.
- *Probabilistic orbital propagation*: propagate phase-space probability clouds instead of single rays;
  numerical error and interpolation can masquerade as physical diffusion of the probability. This
  project asks the quantitative version of that question for Earth orbits: **when does integrator error
  materially change the propagated probability, and what does it cost to avoid that?**

## 2. Scope

**In scope (v1)**
- EGM2008 gravity, configurable truncation (degree/order up to 120; **v1 runs at 70×70**), tide-free coefficients.
- **v1 scenario: LEO only** (400 km, i = 51.6°), **7-day horizon**. Other regimes stay configurable but are not run in v1.
- Simple Earth-orientation model: uniform rotation about the z-axis (Earth Rotation Angle), GCRF ≈ inertial.
- Integrators implemented from scratch in C++ (the comparison *is* the point), cross-checked against SciPy.
- Monte Carlo ensembles from a Gaussian initial covariance, plus linearised (STM) and unscented-transform
  propagation as cheap comparators.
- Distribution-comparison metrics, event probabilities, phase-space-volume diagnostics.
- Google Benchmark suite, `perf` profiling scripts, work-precision plots, a written results report.

**Out of scope (v1), designed for later**
- Atmospheric drag (interface + hook only; implementation in M5).
- Third bodies (Sun/Moon), SRP, solid/ocean tides, relativity.
- Full IERS precession–nutation / polar motion (frame interface allows swapping it in).
- Grid/PDE (Fokker–Planck) density propagation — the second video shows why it suffers numerical diffusion;
  we only *bin* Monte Carlo particles for visualisation.
- Orbit determination / filtering.

## 3. Approach

### 3.1 Dynamics
Inertial-frame equations of motion `r'' = a_grav(t, r)`, with
`a_grav = R(t)^T · ∇U_ECEF(R(t) r)`, where `R(t)` is rotation by ERA(t) and `U` is the EGM2008 potential

    U(r,φ,λ) = GM/r · Σ_{n=0}^{N} (a/r)^n Σ_{m=0}^{n} P̄_nm(sin φ) (C̄_nm cos mλ + S̄_nm sin mλ)

- Constants: GM = 3.986004415e14 m³/s², a = 6378136.3 m (EGM2008 defining values).
- Gradient via the Cunningham / Montenbruck–Gill V_nm, W_nm recursion in fully-normalised form
  (no singularity at the poles). For degree > ~200 Holmes–Featherstone would be needed; we cap at 120.
- The force depends on position (and time) only ⇒ the flow is Hamiltonian and symplectic, so
  symplectic integrators retain their structure. In the Earth-fixed frame the **Jacobi integral**
  `½|v_ecef|² − ½|ω×r|² − U` is conserved (uniform rotation), which is our main conservation diagnostic.
  Drag will break this (expected and documented when M5 lands).

### 3.2 Force-model interface (drag-ready)
```cpp
struct ForceModel {
  virtual Vec3 accel(double t, const Vec3& r, const Vec3& v) const = 0;
  virtual bool velocity_dependent() const = 0;   // false for gravity, true for drag
  virtual ~ForceModel() = default;
};
class CompositeForce : public ForceModel { /* sum of components */ };
// v1: PointMassGravity, SphericalHarmonicGravity(EGM2008, n_max, m_max)
// M5: DragForce(std::shared_ptr<Atmosphere>, ballistic_coeff), Atmosphere = {Exponential, NRLMSISE-00?}
```
Integrators only see `CompositeForce`. Symplectic/splitting integrators assert `!velocity_dependent()`
(or fall back to a documented non-symplectic variant) so adding drag can't silently produce wrong
"symplectic" results.

### 3.3 Integrators (all C++, common `Integrator` interface, count force evaluations)
| ID | Method | Order | Step control | Notes |
|---|---|---|---|---|
| `rk4` | Classic Runge–Kutta | 4 | fixed | baseline |
| `rk4r` | RK4 + Richardson extrapolation (step doubling) | 4 (5 extrapolated) | adaptive | error = (y_h/2 − y_h)/15; local extrapolation optional (flag) |
| `dopri5` | Dormand–Prince 5(4) | 5 | adaptive, PI control | |
| `dop853` | Dormand–Prince 8(5,3), Hairer coefficients | 8 | adaptive | dense output; cross-checked vs `scipy.integrate.DOP853` |
| `verlet` | Störmer–Verlet / leapfrog (kick-drift-kick) | 2 | fixed | symplectic; = the "flipped lines" of the video, symmetrised |
| `yoshida4/6` | Yoshida composition of Verlet | 4 / 6 | fixed | symplectic |
| `rkn` (stretch) | Runge–Kutta–Nyström 12(10) or Gauss–Jackson 8 | high | adaptive / fixed | industry-standard comparators |
| `wh` (stretch) | Kepler-drift + harmonic-kick splitting (Wisdom–Holman style) | 2 | fixed | the 1991 idea from the video, applied to J2+ perturbations |

Adaptive methods are swept over tolerances (1e-6 … 1e-13); fixed-step methods over steps-per-orbit.
That gives each method a curve, not a point, on the work-precision plane.

### 3.4 Reference ("truth") solution
- Primary: `dop853` at rtol = atol-scaled 1e-14, verified by self-convergence (halving tolerance changes
  the result by < 1 mm over the test horizon).
- Independent cross-check: SciPy `DOP853` on the same force model (via Python bindings) and, if available
  in the environment, an independent propagator (Orekit or heyoka) for a small set of trajectories.

### 3.5 Probabilistic propagation
- **Initial distribution**: Gaussian in RTN about a nominal state (e.g. σ_pos = 100 m, σ_vel = 0.1 m/s,
  configurable full 6×6 covariance). Optional heavier-tailed / along-track-dominated variants.
- **Monte Carlo**: N particles (1e3–1e5), batch-propagated in C++ with OpenMP across particles.
  **Common random numbers**: every integrator propagates the *same* particles, so differences are
  attributable to the integrator alone, and per-particle (paired) errors are available.
- **Cheap comparators**: linearised covariance via the state-transition matrix (variational equations
  integrated alongside the state) and the unscented transform (13 sigma points).
- **What "the probabilities change" means — metrics**, each computed against the reference ensemble:
  1. Paired per-particle position error, and its ratio to the ensemble spread (σ along-track/radial/cross).
     This ratio is the headline: < ~0.01 ⇒ integrator error irrelevant to the distribution.
  2. Moment differences: mean shift (in units of σ), covariance difference (Förstner/Frobenius),
     Gaussian KL divergence.
  3. Non-parametric distances: sliced 2-Wasserstein and energy distance on 6-D clouds; 1-D marginal KS tests.
  4. Event probabilities with bootstrap CIs: P(particle inside a target box at t_f) and a
     conjunction-style probability of passing within d of a reference trajectory.
  5. Structure diagnostics (the video's point): Jacobi-integral drift per particle, and
     `|det Φ − 1|` (phase-space volume) from the STM for each integrator.
- **Headline result (owner choice)**: integrator error vs ensemble spread — metric (1) — reported over time
  for each integrator and cost level. The other metrics are supporting evidence.
- **Scenario (v1)**: LEO 400 km, i = 51.6°, 70×70 field, 7 days (~111 orbits). SSO/MEO/Molniya and 1/30-day
  horizons are deferred.

### 3.5.1 Ensemble size N — default 20,000, with a sequential stopping rule
Owner asked for more precision than the originally proposed N = 1e4, with a defence:
- **Headline ratio.** The spread σ is estimated with relative standard error ≈ 1/√(2N): 0.7 % at 1e4,
  **0.5 % at 2e4**, 0.2 % at 1e5. The numerator is a *paired* difference against the reference using the
  same particles, so its sampling noise is far smaller (integrator error is strongly correlated across a
  100 m cloud). Across integrators the ratio spans orders of magnitude, so ±0.5 % is ample.
- **Supporting metrics.** Correlation entries: SE ≈ (1−ρ²)/√N ≈ 0.007 at 2e4. A tail event with p = 0.05:
  relative SE ≈ √((1−p)/(Np)) ≈ 3 % at 2e4 (vs 4 % at 1e4); p = 0.01: ≈ 7 %.
- **Cost is the binding constraint.** Pre-implementation estimate: a 70×70 acceleration ≈ 10–20 µs; the
  DOP853 reference at tight tolerance ≈ 2–3×10⁵ evaluations per particle over 7 days ⇒ ~3–5 s per particle.
  On the current 2-vCPU cloud VM that is ~8–14 h for a 2e4 reference ensemble and ~40–70 h for 1e5. 1e5 is
  not affordable here; 2e4 is, if the reference ensemble is computed once and cached.
- **Rule:** propagate in batches of 5,000 (common seeds) and stop once the headline ratio's bootstrap SE
  < 1 % and the covariance-diagonal SE < 1 %; default target 2e4, hard cap 1e5. The achieved SE is reported
  with every result. Story 10 measures the real per-particle cost and records the final N in decisions.md.

### 3.6 Performance measurement
- **Google Benchmark** (C++): `BM_Accel/<degree>` (force evaluation vs truncation), `BM_Step/<integrator>`,
  `BM_Propagate/<integrator>/<tol-or-step>` with user counters for force evaluations and achieved error,
  `BM_Ensemble/<integrator>/<N>/<threads>`. JSON output, median of repetitions, CPU time.
- **perf**: `perf stat` (cycles, instructions, IPC, cache and branch misses) per benchmark; `perf record`
  + flame graphs for hotspots (expected: Legendre recursion and trig). Scripts in `bench/perf/`.
  Fallback to software events if the VM doesn't expose hardware counters (recorded in the report).
- **Work-precision diagrams**: final-position error vs (a) force evaluations (machine-independent) and
  (b) wall time (machine-dependent), per integrator and scenario; plus "distribution-error vs cost"
  using metric (1) above.
- Single-thread numbers are the primary comparison; multithread scaling is reported separately.
  Build: `-O3`, no `-ffast-math` (it changes results). CPU model and compiler recorded with every run.

## 4. Architecture

```
projects/prob-orbit-prop/
  pyproject.toml            # scikit-build-core + pybind11; [tool.black] + ruff lint config; pip install -e .[dev]
  CMakeLists.txt
  cpp/
    include/pop/            # vec, frames, force (ForceModel, EGM2008), integrators, ensemble, stm
    src/
    tests/                  # Catch2 (or GoogleTest) unit tests
  bench/
    gbench/                 # Google Benchmark executables
    perf/                   # perf stat / record scripts, flamegraph helpers
  data/egm2008/             # truncated coefficient table + provenance (source URL, SHA-256, truncation)
  src/prob_orbit_prop/      # Python: bindings wrapper, sampling, metrics, experiments, plotting
  tests/                    # pytest: validation against references, metric tests
  experiments/              # experiment configs (YAML) → results/*.parquet + figures
  docs/ design.md context.md decisions.md results.md
```
Data flow: experiment config → Python samples ensemble → C++ batch propagator (per integrator,
same particles) → arrays back to NumPy → metrics/plots → `docs/results.md`.

**Language decision (needs approval, deviates from the Python default):** core numerics in **C++20**
with pybind11 bindings; Python for orchestration, statistics, plots and validation. Reasons: Google
Benchmark and `perf` measure native code meaningfully, whereas in pure Python interpreter overhead would
dominate and mask the differences between integrators; a 1e5-particle × 30-day × 70×70-field ensemble
is also infeasible in pure Python. Rejected: pure Python + Numba (no Google Benchmark, `perf` sees the JIT
poorly). C++ deps (Eigen optional, Google Benchmark, Catch2, pybind11) fetched via CMake FetchContent from
GitHub, pinned by tag.

## 5. Validation plan (Definition of Done requires a reference)
| What | Reference |
|---|---|
| Point-mass propagation | Analytic Kepler solution (all integrators, relative error vs step/tol) |
| Integrator order | Empirical convergence slope on Kepler and on J2 problem matches theoretical order |
| J2-only dynamics | Analytic secular RAAN/argument-of-perigee rates (Vallado) within averaging tolerance |
| EGM2008 acceleration | Independent evaluation (pyshtools if installable, else values from ICGEM calculation service at fixed test points) to ~1e-12 relative; also finite-difference of potential |
| Conservation | Jacobi integral drift: bounded for symplectic, secular for non-symplectic (qualitative test + thresholds) |
| DOP853 implementation | Matches SciPy DOP853 at same tolerances |
| STM | Finite-difference Jacobian of the flow map |
| Monte Carlo metrics | Unit tests on synthetic distributions with known distances (e.g. two Gaussians) |

## 6. Milestones and user stories
Each story = one issue, one branch (`feat/prob-orbit-prop-<desc>`), one PR (< ~400 lines).

**M0 — Design** (this PR)

**M1 — Foundation and gravity**
1. *Scaffold*: CMake + scikit-build-core + pybind11 skeleton, Catch2 + pytest, CI builds the extension and runs both test suites.
2. *EGM2008 data*: coefficient loader (ICGEM `.gfc` / NGA format), truncated table committed with provenance and checksum.
3. *Spherical-harmonic gravity*: V/W recursion, point-mass and J2 special cases, validated per §5.
4. *Frames + force interface*: ERA rotation, `ForceModel`/`CompositeForce`, `velocity_dependent()` contract, drag hook stub.

**M2 — Integrators**
5. RK4 and RK4 + Richardson (adaptive), with evaluation counting.
6. DOPRI5 and DOP853 (dense output), cross-checked vs SciPy.
7. Symplectic: Verlet, Yoshida 4/6; Jacobi-integral diagnostics.
8. Reference solution + convergence-order test suite.

**M3 — Probabilistic propagation**
10. Ensemble sampler (RTN covariance) + OpenMP batch propagator with common random numbers.
11. STM via variational equations + unscented transform.
12. Metrics module (§3.5) with tests; experiment runner (YAML configs → results files).

**M4 — Performance and report**
13. Google Benchmark suite (§3.6), JSON outputs.
14. `perf` scripts + work-precision and distribution-error-vs-cost plots.
15. Results report `docs/results.md` (+ published HTML report if useful).

**Later (not v1)** — Gauss–Jackson or RKN 12(10); Kepler-split (Wisdom–Holman-style) integrator; SSO/MEO/Molniya; 1- and 30-day horizons.

**M5 — Drag (later, separate branch/PRs)**
16. `Atmosphere` interface + exponential model; `DragForce` with ballistic coefficient; tests vs analytic decay rate.
17. Re-run M3/M4 experiments with drag; document loss of symplecticity.

## 7. Risks
- **Environment network**: in the design session PyPI (DNS) and earth-info.nga.mil (proxy 403) were
  unreachable; GitHub via git was reachable. Building needs PyPI (pybind11, scikit-build-core) in the
  cloud session, and the EGM2008 file needs one download. See open questions.
- **perf in a VM/container**: hardware PMU counters may be unavailable (perf_event_paranoid=2, `perf`
  not installed). GitHub-hosted runners have the same issue. Mitigation: software events + Google
  Benchmark timing; document what was measurable.
- **Benchmark noise**: shared 2-vCPU cloud VMs. Mitigation: repetitions, medians, report variance; lean on
  force-evaluation counts as the machine-independent cost metric.
- **Truth quality**: double precision caps achievable accuracy (~1e-13 relative); comparisons below that
  floor are meaningless and will be flagged.
- **Simplified Earth orientation**: uniform rotation is not real GCRF↔ITRF; fine for an integrator
  comparison (all methods see the same field), not for operational accuracy claims.

## 8. Owner answers (2026-11-01)
1. C++20 core + pybind11: **approved**. Python is formatted with **black** (owner requirement); `ruff check`
   still lints. C++ formatting: clang-format, Google style (proposal).
2. Committing a truncated EGM2008 table (≤ 120×120): **approved**. Owner will enable PyPI and the NGA/ICGEM
   host in the network settings; story 2 is blocked until then.
3. Headline: **integrator error vs ensemble spread**.
4. **70×70, LEO only, 7 days**; N chosen and defended in §3.5.1 (20,000 with a stopping rule).
5. Gauss–Jackson / Kepler-split: **later**.

No blocking questions remain. Story 10 may revise N once real cost is measured (§3.5.1).

## 9. References
- Pavlis, N. K., Holmes, S. A., Kenyon, S. C., Factor, J. K. (2012). *The development and evaluation of the
  Earth Gravitational Model 2008 (EGM2008)*. JGR 117, B04406.
- Montenbruck, O., Gill, E. (2000). *Satellite Orbits*, §3.2 (V/W recursion), §4 (integrators).
- Hairer, E., Nørsett, S. P., Wanner, G. (1993). *Solving ODEs I* — DOPRI5, DOP853, Richardson extrapolation.
- Hairer, E., Lubich, C., Wanner, G. (2006). *Geometric Numerical Integration* — symplectic methods, Poincaré invariants.
- Yoshida, H. (1990). Construction of higher order symplectic integrators. Phys. Lett. A 150.
- Wisdom, J., Holman, M. (1991). Symplectic maps for the N-body problem. AJ 102.
- Vallado, D. A. *Fundamentals of Astrodynamics and Applications* — J2 secular rates, RTN frames.
- Julier, S., Uhlmann, J. (2004). Unscented filtering and nonlinear estimation. Proc. IEEE.
- Project docs: "Brain truffle Orbital Prop Algo computational trick", "Probabalistic Orbital Propagation" (video transcripts).
