#pragma once
/// \file version.hpp
/// Library version and build information.

#include <string>

namespace pop {

/// Semantic version of the C++ core, e.g. "0.1.0" (set by CMake from project()).
[[nodiscard]] std::string version();

/// Compiler identification and C++ standard the core was built with. Recorded
/// alongside every benchmark run so results stay reproducible (design §3.6).
[[nodiscard]] std::string build_info();

}  // namespace pop
