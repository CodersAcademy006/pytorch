# Minimal cross toolchain file, deliberately mirroring the CMAKE_SYSTEM_NAME /
# CMAKE_SYSTEM_PROCESSOR=riscv64 pair that .ci/pytorch/build.sh sets via env
# vars for the real PyTorch cross-build, so this smoke exercises the same
# CMake cross-compilation code path at a fraction of the cost.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR riscv64)

if(NOT DEFINED RISCV_GCC_SUFFIX)
  set(RISCV_GCC_SUFFIX "-14")
endif()

set(CMAKE_C_COMPILER "riscv64-linux-gnu-gcc${RISCV_GCC_SUFFIX}")
set(CMAKE_CXX_COMPILER "riscv64-linux-gnu-g++${RISCV_GCC_SUFFIX}")

set(CMAKE_FIND_ROOT_PATH /usr/riscv64-linux-gnu)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
