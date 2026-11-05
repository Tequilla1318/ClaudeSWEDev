#pragma once
/// \file vec3.hpp
/// Minimal 3-vector used throughout the propagator (positions, velocities,
/// accelerations). Header-only, constexpr, no dynamic allocation, so it adds no
/// overhead in the force-model and integrator hot loops.

#include <array>
#include <cmath>
#include <cstddef>

namespace pop {

/// Cartesian 3-vector of doubles. Components are SI units by convention
/// (m, m/s, m/s^2) unless a function documents otherwise.
struct Vec3 {
  double x = 0.0;
  double y = 0.0;
  double z = 0.0;

  constexpr Vec3() = default;
  constexpr Vec3(double x_, double y_, double z_) : x(x_), y(y_), z(z_) {}

  /// Component access by index (0 = x, 1 = y, 2 = z). No bounds check.
  [[nodiscard]] constexpr double operator[](std::size_t i) const {
    return i == 0 ? x : (i == 1 ? y : z);
  }

  constexpr Vec3& operator+=(const Vec3& o) {
    x += o.x;
    y += o.y;
    z += o.z;
    return *this;
  }
  constexpr Vec3& operator-=(const Vec3& o) {
    x -= o.x;
    y -= o.y;
    z -= o.z;
    return *this;
  }
  constexpr Vec3& operator*=(double s) {
    x *= s;
    y *= s;
    z *= s;
    return *this;
  }

  /// Convert to a std::array (used by the Python bindings).
  [[nodiscard]] constexpr std::array<double, 3> to_array() const { return {x, y, z}; }
};

[[nodiscard]] constexpr Vec3 operator+(Vec3 a, const Vec3& b) { return a += b; }
[[nodiscard]] constexpr Vec3 operator-(Vec3 a, const Vec3& b) { return a -= b; }
[[nodiscard]] constexpr Vec3 operator-(const Vec3& a) { return {-a.x, -a.y, -a.z}; }
[[nodiscard]] constexpr Vec3 operator*(Vec3 a, double s) { return a *= s; }
[[nodiscard]] constexpr Vec3 operator*(double s, Vec3 a) { return a *= s; }
[[nodiscard]] constexpr Vec3 operator/(const Vec3& a, double s) {
  return {a.x / s, a.y / s, a.z / s};
}
[[nodiscard]] constexpr bool operator==(const Vec3& a, const Vec3& b) {
  return a.x == b.x && a.y == b.y && a.z == b.z;
}

/// Dot product.
[[nodiscard]] constexpr double dot(const Vec3& a, const Vec3& b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

/// Cross product a × b (right-handed).
[[nodiscard]] constexpr Vec3 cross(const Vec3& a, const Vec3& b) {
  return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x};
}

/// Squared Euclidean norm.
[[nodiscard]] constexpr double norm2(const Vec3& a) { return dot(a, a); }

/// Euclidean norm. Uses std::hypot to avoid overflow/underflow for extreme
/// magnitudes (irrelevant for orbits, but costs nothing to get right).
[[nodiscard]] inline double norm(const Vec3& a) { return std::hypot(a.x, a.y, a.z); }

}  // namespace pop
