#include "checksum.h"

#include <cstddef>
#include <cstdint>
#include <iostream>
#include <iomanip>
/**
 * 这个文件放的是计算和验证16位校验和的函数实现
 */
namespace {
  /**
   * 检查和计算的最终步骤：将高16位加到低16位，取反得到最终的16位校验和
   */
std::uint16_t finalize(std::uint32_t sum) {
    while (sum >> 16) {
        sum = (sum & 0xFFFF) + (sum >> 16);
    }
    return static_cast<std::uint16_t>(~sum);
}
}
/**
 * 计算数据块的16位校验和
 * param data 指向数据块的指针
 * param length 数据块的长度（字节数，这里是八字节一个长度）
 */
std::uint16_t compute_checksum(const std::uint8_t* data, std::size_t length) {
    std::uint32_t sum = 0;
    std::size_t i = 0;
    // 按字节组合为16位大端值，避免未对齐访问
    while (i + 1 < length) {
        std::uint16_t word = (static_cast<std::uint16_t>(data[i]) << 8) | static_cast<std::uint16_t>(data[i + 1]);
        sum += word;
        i += 2;
    }
    if (i < length) {
        // 奇数字节，作为高字节处理
        std::uint16_t word = static_cast<std::uint16_t>(data[i]) << 8;
        sum += word;
    }

    return finalize(sum);
}

/**
 * 验证数据块的16位校验和是否正确
 */
bool verify_checksum(const std::uint8_t* data, std::size_t length) {
    std::uint16_t sum = compute_checksum(data, length);
#ifdef RTP_VERBOSE_LOG
    std::cout << "[Checksum] computed finalize(sum)=0x" << std::hex << std::setw(4) << std::setfill('0') << sum << std::dec << " length=" << length << "\n";
#endif
    return sum == 0;
}
