# prob-orbit-prop

Probabilistic orbit propagation under EGM2008 gravity, and how the choice of numerical
integrator (RK4, RK4 + Richardson, DOPRI5, DOP853, symplectic methods) changes the propagated
probability distribution — and what each costs (Google Benchmark, `perf`).

**Side project:** lives on branch `project/prob-orbit-prop` and is never merged to `main`.
Design: [`docs/design.md`](docs/design.md) · Status: [`docs/context.md`](docs/context.md) ·
Decisions: [`docs/decisions.md`](docs/decisions.md) · Backlog: epic #22.

## Status
Story 1 (scaffold) — C++20 core + pybind11 extension + tests + CI. No physics yet.

## Layout
```
CMakeLists.txt        C++ build (core library, pybind11 module, Catch2 tests)
pyproject.toml        Python package (scikit-build-core); black + ruff config
cpp/include/pop/      C++ headers (pop::Vec3, version)
cpp/src/              C++ sources
cpp/python/           pybind11 bindings -> prob_orbit_prop._core
cpp/tests/            Catch2 unit tests
src/prob_orbit_prop/  Python package
tests/                pytest
```

## Build and test (cloud session / CI)
```bash
# Python package + extension, then Python tests
pip install -e ".[dev]"
pytest

# C++ unit tests
cmake -S . -B build/cpp -G Ninja -DPOP_BUILD_TESTS=ON -DPOP_WERROR=ON
cmake --build build/cpp
ctest --test-dir build/cpp --output-on-failure

# Formatting and lint
black --check . && ruff check .
clang-format --dry-run --Werror cpp/**/*.hpp cpp/**/*.cpp
```
In this cloud environment PyPI is only reachable through the proxy, so prefix pip with
`NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1` (see `docs/context.md`).

Build flags: C++20, Release (`-O3`), **no `-ffast-math`** (it changes floating-point results and
would corrupt the accuracy comparison).
