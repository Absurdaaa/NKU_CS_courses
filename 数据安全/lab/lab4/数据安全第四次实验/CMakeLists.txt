cmake_minimum_required(VERSION 3.10)
project(libsnark_zkp_demo CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED LIBSNARK_SOURCE_DIR)
    message(FATAL_ERROR "Please configure with -DLIBSNARK_SOURCE_DIR=/absolute/path/to/libsnark")
endif()

if(NOT EXISTS "${LIBSNARK_SOURCE_DIR}/CMakeLists.txt")
    message(FATAL_ERROR "LIBSNARK_SOURCE_DIR does not point to a valid libsnark source tree")
endif()

add_subdirectory(${LIBSNARK_SOURCE_DIR} ${CMAKE_BINARY_DIR}/libsnark-build EXCLUDE_FROM_ALL)

add_executable(libsnark_zkp_demo libsnark_zkp_demo.cpp)
target_link_libraries(libsnark_zkp_demo snark)
