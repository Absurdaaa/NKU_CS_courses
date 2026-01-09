#pragma once

#include <cstddef>
#include <cstdint>

std::uint16_t compute_checksum(const std::uint8_t* data, std::size_t length);
bool verify_checksum(const std::uint8_t* data, std::size_t length);
