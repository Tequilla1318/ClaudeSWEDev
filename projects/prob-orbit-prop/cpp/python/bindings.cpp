/// \file bindings.cpp
/// pybind11 bindings for the C++ core. Exposed to Python as
/// `prob_orbit_prop._core`; the public Python API re-exports from
/// `prob_orbit_prop/__init__.py`.

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <array>
#include <stdexcept>

#include "pop/vec3.hpp"
#include "pop/version.hpp"

namespace py = pybind11;

namespace {

/// Convert a length-3 float64 NumPy array (or sequence) to pop::Vec3.
pop::Vec3 to_vec3(const py::array_t<double, py::array::c_style | py::array::forcecast>& a) {
  if (a.ndim() != 1 || a.shape(0) != 3) {
    throw std::invalid_argument("expected an array of shape (3,)");
  }
  const auto r = a.unchecked<1>();
  return {r(0), r(1), r(2)};
}

}  // namespace

PYBIND11_MODULE(_core, m) {
  m.doc() = "C++ core of prob-orbit-prop (EGM2008 gravity, integrators, ensembles).";

  m.def("version", &pop::version, "Version of the C++ core.");
  m.def("build_info", &pop::build_info, "Compiler and C++ standard used to build the core.");

  // Smoke-level round trip through the NumPy <-> Vec3 conversion that later
  // stories (force evaluation, propagation) rely on.
  m.def(
      "norm",
      [](const py::array_t<double, py::array::c_style | py::array::forcecast>& v) {
        return pop::norm(to_vec3(v));
      },
      py::arg("v"), "Euclidean norm of a length-3 vector (via pop::Vec3).");
  m.def(
      "cross",
      [](const py::array_t<double, py::array::c_style | py::array::forcecast>& a,
         const py::array_t<double, py::array::c_style | py::array::forcecast>& b) {
        return pop::cross(to_vec3(a), to_vec3(b)).to_array();
      },
      py::arg("a"), py::arg("b"), "Cross product a x b of two length-3 vectors.");
}
