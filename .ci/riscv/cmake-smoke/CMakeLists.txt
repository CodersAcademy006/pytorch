cmake_minimum_required(VERSION 3.18)
project(riscv_toolchain_smoke CXX)
add_executable(toolchain_smoke ${CMAKE_CURRENT_SOURCE_DIR}/../toolchain_smoke.cpp)
