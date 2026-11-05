#include <catch2/catch_test_macros.hpp>

#include "pop/version.hpp"

TEST_CASE("version string is the CMake project version", "[version]") {
  CHECK(pop::version() == "0.1.0");
}

TEST_CASE("build info names the compiler and C++20", "[version]") {
  const std::string info = pop::build_info();
  CHECK_FALSE(info.empty());
  CHECK(info.find("C++ 2020") != std::string::npos);
}
