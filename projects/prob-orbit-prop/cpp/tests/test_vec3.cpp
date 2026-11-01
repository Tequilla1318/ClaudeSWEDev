#include <catch2/catch_test_macros.hpp>
#include <catch2/matchers/catch_matchers_floating_point.hpp>

#include "pop/vec3.hpp"

using Catch::Matchers::WithinRel;
using pop::Vec3;

TEST_CASE("Vec3 arithmetic", "[vec3]") {
  const Vec3 a{1.0, 2.0, 3.0};
  const Vec3 b{-4.0, 0.5, 2.0};

  CHECK(a + b == Vec3{-3.0, 2.5, 5.0});
  CHECK(a - b == Vec3{5.0, 1.5, 1.0});
  CHECK(-a == Vec3{-1.0, -2.0, -3.0});
  CHECK(2.0 * a == Vec3{2.0, 4.0, 6.0});
  CHECK(a * 2.0 == 2.0 * a);
  CHECK(a / 2.0 == Vec3{0.5, 1.0, 1.5});
  CHECK(a[0] == 1.0);
  CHECK(a[1] == 2.0);
  CHECK(a[2] == 3.0);
}

TEST_CASE("Vec3 products obey their algebraic identities", "[vec3]") {
  const Vec3 a{1.0, 2.0, 3.0};
  const Vec3 b{-4.0, 0.5, 2.0};
  const Vec3 c = pop::cross(a, b);

  CHECK(pop::dot(a, b) == 3.0);  // -4 + 1 + 6
  CHECK(c == Vec3{2.5, -14.0, 8.5});
  // a × b is orthogonal to both factors.
  CHECK(pop::dot(c, a) == 0.0);
  CHECK(pop::dot(c, b) == 0.0);
  // Unit basis: x × y = z.
  CHECK(pop::cross(Vec3{1, 0, 0}, Vec3{0, 1, 0}) == Vec3{0, 0, 1});
}

TEST_CASE("Vec3 norm", "[vec3]") {
  CHECK(pop::norm(Vec3{3.0, 4.0, 12.0}) == 13.0);
  CHECK(pop::norm2(Vec3{3.0, 4.0, 12.0}) == 169.0);
  // Orbit-scale magnitude: |r| for a 400 km LEO position.
  const double r = 6'778'137.0;
  CHECK_THAT(pop::norm(Vec3{r / std::sqrt(3.0), r / std::sqrt(3.0), r / std::sqrt(3.0)}),
             WithinRel(r, 1e-15));
}

TEST_CASE("Vec3 operations are usable at compile time", "[vec3]") {
  constexpr Vec3 a{1.0, 2.0, 3.0};
  constexpr double d = pop::dot(a, a);
  STATIC_REQUIRE(d == 14.0);
  STATIC_REQUIRE(pop::cross(a, a) == Vec3{});
}
