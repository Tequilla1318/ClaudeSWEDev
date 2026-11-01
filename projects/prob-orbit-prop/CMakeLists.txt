cmake_minimum_required(VERSION 3.24)
project(prob_orbit_prop VERSION 0.1.0 LANGUAGES CXX)

# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------
option(POP_BUILD_PYTHON "Build the pybind11 extension module" OFF)
option(POP_BUILD_TESTS "Build the Catch2 C++ unit tests" OFF)
option(POP_WERROR "Treat compiler warnings as errors" OFF)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  # -O3, no -ffast-math: fast-math changes floating-point results, which would
  # corrupt the integrator accuracy comparison (design §3.6).
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# Warning flags for our own targets only (not third-party dependencies).
add_library(pop_warnings INTERFACE)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(pop_warnings INTERFACE -Wall -Wextra -Wpedantic -Wshadow -Wconversion)
  if(POP_WERROR)
    target_compile_options(pop_warnings INTERFACE -Werror)
  endif()
endif()

# ---------------------------------------------------------------------------
# Core library
# ---------------------------------------------------------------------------
add_library(pop_core STATIC cpp/src/version.cpp)
target_include_directories(pop_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/cpp/include)
target_compile_definitions(pop_core PRIVATE POP_VERSION="${PROJECT_VERSION}")
target_link_libraries(pop_core PRIVATE pop_warnings)

# ---------------------------------------------------------------------------
# Python extension (built by scikit-build-core via `pip install .`)
# ---------------------------------------------------------------------------
if(POP_BUILD_PYTHON)
  find_package(Python 3.11 REQUIRED COMPONENTS Interpreter Development.Module)
  find_package(pybind11 CONFIG REQUIRED)
  pybind11_add_module(_core MODULE cpp/python/bindings.cpp)
  target_link_libraries(_core PRIVATE pop_core pop_warnings)
  install(TARGETS _core LIBRARY DESTINATION prob_orbit_prop)
endif()

# ---------------------------------------------------------------------------
# C++ unit tests (Catch2, fetched from GitHub at a pinned tag)
# ---------------------------------------------------------------------------
if(POP_BUILD_TESTS)
  include(FetchContent)
  FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG v3.7.1
    GIT_SHALLOW TRUE)
  FetchContent_MakeAvailable(Catch2)

  enable_testing()
  add_executable(pop_tests cpp/tests/test_vec3.cpp cpp/tests/test_version.cpp)
  target_link_libraries(pop_tests PRIVATE pop_core pop_warnings Catch2::Catch2WithMain)
  list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
  include(Catch)
  catch_discover_tests(pop_tests)
endif()
