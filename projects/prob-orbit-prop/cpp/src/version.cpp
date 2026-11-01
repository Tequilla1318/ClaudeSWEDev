#include "pop/version.hpp"

#ifndef POP_VERSION
#error "POP_VERSION must be defined by the build system"
#endif

namespace pop {

std::string version() { return POP_VERSION; }

std::string build_info() {
  std::string compiler;
#if defined(__clang__)
  compiler = "clang " __clang_version__;
#elif defined(__GNUC__)
  compiler = "gcc " __VERSION__;
#elif defined(_MSC_VER)
  compiler = "msvc " + std::to_string(_MSC_VER);
#else
  compiler = "unknown";
#endif
  return compiler + "; C++ " + std::to_string(__cplusplus);
}

}  // namespace pop
