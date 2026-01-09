#pragma once

#include <cstdint>
#include <vector>
#include <string>
#include <chrono>
#include <optional>

/**
 * RTP协议相关定义和工具函数
 */

namespace rtp {

constexpr std::uint32_t PROTOCOL_VERSION = 1;
constexpr std::size_t MAX_PAYLOAD_SIZE = 15000; // 最大负载大小（字节）
constexpr std::chrono::milliseconds DEFAULT_RTO{200};
constexpr std::uint32_t MAX_SACK_BITS = 32;

// 信息标志位枚举
enum PacketFlags : std::uint16_t {
    FLAG_SYN = 1 << 0, // 0000000000000001
    FLAG_ACK = 1 << 1, // 0000000000000010
    FLAG_FIN = 1 << 2, // 0000000000000100
    FLAG_DATA = 1 << 3,// 0000000000001000
    FLAG_RST = 1 << 4, // 0000000000010000
    FLAG_SACK = 1 << 5 // 0000000000100000
};

// 数据包头结构体
struct PacketHeader {
    std::uint32_t seq; // 包的序列号
    std::uint32_t ack; // 确认号（下一个期望收到的序列号）
    std::uint32_t sack_bits; // SACK位图
    std::uint16_t window;   // 接收窗口大小（以数据包数计）
    std::uint16_t length;   // 负载长度（字节数）
    std::uint16_t flags;    // 标志位
    std::uint16_t checksum; // 校验和
};

struct Packet {
    // 数据包头
    PacketHeader header{};
    // 负载数据
    std::vector<std::uint8_t> payload;
};

// 握手载荷结构体
struct HandshakePayload {
    std::uint32_t version;  // 协议版本
    std::uint32_t chunk_size;// 每个数据包的最大负载大小
    std::uint32_t window_size;// 接收窗口大小（以数据包数计）
    std::uint64_t file_size;// 预期传输的文件大小（字节）
        // 可选：发送端原始文件名（UTF-8），用于接收端恢复原始文件名
        // 该字段在编码时以 "uint16_t name_len + name_bytes" 追加到固定字段之后
        std::string filename;
};

struct SackSummary {
    std::uint32_t cumulative_ack; // 累计确认号（下一个期望收到的序列号）
    std::uint32_t sack_bits;      // bit i => packet cumulative_ack + i + 1 received，位图表示SACK信息，用来指示哪些数据包已被接收
};

// 序列化
std::vector<std::uint8_t> serialize(const Packet& packet);
// 反序列化
bool deserialize(const std::uint8_t* buffer, std::size_t length, Packet& out_packet);
// 标志位转字符串（调试用）
std::string flags_to_string(std::uint16_t flags);
// 检查标志位是否被设置
bool is_flag_set(std::uint16_t flags, PacketFlags flag);

// 握手载荷编码和解码
std::vector<std::uint8_t> encode_handshake(const HandshakePayload& payload);
bool decode_handshake(const std::vector<std::uint8_t>& buffer, HandshakePayload& payload);

// 窗口大小限制在16位范围内
std::uint16_t clamp_window(std::uint32_t window);

}  // namespace rtp
