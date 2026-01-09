cmake_minimum_required(VERSION 3.20)
project(ReliableUDP LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(ENABLE_LOGGING "Enable verbose logging" ON)

if(MSVC)
    add_compile_options(/utf-8)
endif()

add_library(rtp_core
    src/rtp.cpp
    src/checksum.cpp
    src/congestion_control.cpp
    src/timer.cpp
)

target_include_directories(rtp_core
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

if(WIN32)
    target_link_libraries(rtp_core PUBLIC ws2_32)
    target_compile_definitions(rtp_core PUBLIC _WINSOCK_DEPRECATED_NO_WARNINGS NOMINMAX)
endif()

if(ENABLE_LOGGING)
    # target_compile_definitions(rtp_core PUBLIC RTP_VERBOSE_LOG)
    target_compile_definitions(rtp_core PUBLIC)
endif()

add_executable(sender src/sender_main.cpp)
target_link_libraries(sender PRIVATE rtp_core)

add_executable(receiver src/receiver_main.cpp)
target_link_libraries(receiver PRIVATE rtp_core)
