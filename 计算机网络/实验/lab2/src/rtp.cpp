#include "rtp.h"

#include "checksum.h"

#include <algorithm>
#include <array>
#include <cstring>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <iostream>


#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <intrin.h>
#else
#include <arpa/inet.h>
#endif

#if defined(__linux__)
#include <endian.h>
#elif defined(__APPLE__)
#include <libkern/OSByteOrder.h>
#endif

/**
 * RTP协议相关定义和工具函数的实现
 */

namespace rtp {

namespace {
constexpr std::size_t HEADER_SIZE = sizeof(PacketHeader);

std::uint64_t byteswap64(std::uint64_t value) {
#if defined(_WIN32)
    return _byteswap_uint64(value);
#elif defined(__GNUC__) || defined(__clang__)
    return __builtin_bswap64(value);
#else
    return ((value & 0x00000000000000FFULL) << 56) |
           ((value & 0x000000000000FF00ULL) << 40) |
           ((value & 0x0000000000FF0000ULL) << 24) |
           ((value & 0x00000000FF000000ULL) << 8) |
           ((value & 0x000000FF00000000ULL) >> 8) |
           ((value & 0x0000FF0000000000ULL) >> 24) |
           ((value & 0x00FF000000000000ULL) >> 40) |
           ((value & 0xFF00000000000000ULL) >> 56);
#endif
}

std::uint64_t host_to_network64(std::uint64_t value) {
#if defined(_WIN32)
    return byteswap64(value);
#elif defined(__APPLE__)
    return OSSwapHostToBigInt64(value);
#elif defined(__BYTE_ORDER__) && (__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__)
    return byteswap64(value);
#else
    return value;
#endif
}

std::uint64_t network_to_host64(std::uint64_t value) {
#if defined(_WIN32)
    return byteswap64(value);
#elif defined(__APPLE__)
    return OSSwapBigToHostInt64(value);
#elif defined(__BYTE_ORDER__) && (__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__)
    return byteswap64(value);
#else
    return value;
#endif
}

PacketHeader to_network(PacketHeader header) {
    header.seq = htonl(header.seq);
    header.ack = htonl(header.ack);
    header.sack_bits = htonl(header.sack_bits);
    header.window = htons(header.window);
    header.length = htons(header.length);
    header.flags = htons(header.flags);
    header.checksum = htons(header.checksum);
    return header;
}

PacketHeader to_host(PacketHeader header) {
    header.seq = ntohl(header.seq);
    header.ack = ntohl(header.ack);
    header.sack_bits = ntohl(header.sack_bits);
    header.window = ntohs(header.window);
    header.length = ntohs(header.length);
    header.flags = ntohs(header.flags);
    header.checksum = ntohs(header.checksum);
    return header;
}
}

std::vector<std::uint8_t> serialize(const Packet& packet) {
    PacketHeader header = packet.header;
    PacketHeader net_header = header;
    net_header.checksum = 0;

    std::vector<std::uint8_t> buffer(HEADER_SIZE + header.length);
    std::memcpy(buffer.data(), &to_network(net_header), HEADER_SIZE);
    if (header.length > 0 && !packet.payload.empty()) {
        std::memcpy(buffer.data() + HEADER_SIZE, packet.payload.data(), header.length);
    }

    const std::uint16_t checksum = compute_checksum(buffer.data(), buffer.size());
    reinterpret_cast<PacketHeader*>(buffer.data())->checksum = htons(checksum);
    return buffer;
}

bool deserialize(const std::uint8_t* buffer, std::size_t length, Packet& out_packet) {
    if (length < HEADER_SIZE) {
      #ifdef RTP_VERBOSE_LOG
          std::cout << "长度不足，无法解析包头" << std::endl;
      #endif
      return false;
    }

    if (!verify_checksum(buffer, length)) {
      #ifdef RTP_VERBOSE_LOG
          std::cout << "校验和验证失败" << std::endl;
      #endif
        return false;
    }

    PacketHeader header{};
    std::memcpy(&header, buffer, HEADER_SIZE);
    header = to_host(header);

    if (length < HEADER_SIZE + header.length) {
      #ifdef RTP_VERBOSE_LOG
          std::cout << "长度不足，无法解析完整包" << std::endl;
      #endif
        return false;
    }

    out_packet.header = header;
    out_packet.payload.assign(buffer + HEADER_SIZE, buffer + HEADER_SIZE + header.length);
    return true;
}

std::string flags_to_string(std::uint16_t flags) {
    std::ostringstream oss;
    if (flags & FLAG_SYN) oss << "SYN|";
    if (flags & FLAG_ACK) oss << "ACK|";
    if (flags & FLAG_FIN) oss << "FIN|";
    if (flags & FLAG_DATA) oss << "DATA|";
    if (flags & FLAG_RST) oss << "RST|";
    if (flags & FLAG_SACK) oss << "SACK|";
    std::string str = oss.str();
    if (!str.empty()) {
        str.pop_back();
    }
    return str;
}

bool is_flag_set(std::uint16_t flags, PacketFlags flag) {
    return (flags & static_cast<std::uint16_t>(flag)) != 0;
}

std::vector<std::uint8_t> encode_handshake(const HandshakePayload& payload) {
    HandshakePayload net = payload;
    net.version = htonl(net.version);
    net.chunk_size = htonl(net.chunk_size);
    net.window_size = htonl(net.window_size);
    net.file_size = host_to_network64(net.file_size);
    // 固定字段先编码
    const std::size_t fixed_sz = sizeof(std::uint32_t) * 3 + sizeof(std::uint64_t);
    const auto name_bytes = std::vector<std::uint8_t>(payload.filename.begin(), payload.filename.end());
    const std::uint16_t name_len = static_cast<std::uint16_t>(name_bytes.size());
    const std::size_t total = fixed_sz + sizeof(std::uint16_t) + name_len;
    std::vector<std::uint8_t> buffer(total);
    // 拷贝固定长度字段（version/chunk_size/window_size/file_size）
    std::memcpy(buffer.data(), &net.version, sizeof(std::uint32_t));
    std::memcpy(buffer.data() + 4, &net.chunk_size, sizeof(std::uint32_t));
    std::memcpy(buffer.data() + 8, &net.window_size, sizeof(std::uint32_t));
    std::memcpy(buffer.data() + 12, &net.file_size, sizeof(std::uint64_t));
    // 追加 filename 长度（网络序）和 name bytes（不含终止符）
    const std::uint16_t net_name_len = htons(name_len);
    std::memcpy(buffer.data() + fixed_sz, &net_name_len, sizeof(std::uint16_t));
    if (name_len > 0) {
        std::memcpy(buffer.data() + fixed_sz + sizeof(std::uint16_t), name_bytes.data(), name_len);
    }
    return buffer;
}

bool decode_handshake(const std::vector<std::uint8_t>& buffer, HandshakePayload& payload) {
    const std::size_t fixed_sz = sizeof(std::uint32_t) * 3 + sizeof(std::uint64_t);
    if (buffer.size() < fixed_sz + sizeof(std::uint16_t)) {
        return false;
    }

    HandshakePayload net{};
    // 读取固定字段
    std::memcpy(&net.version, buffer.data(), sizeof(std::uint32_t));
    std::memcpy(&net.chunk_size, buffer.data() + 4, sizeof(std::uint32_t));
    std::memcpy(&net.window_size, buffer.data() + 8, sizeof(std::uint32_t));
    std::memcpy(&net.file_size, buffer.data() + 12, sizeof(std::uint64_t));

    payload.version = ntohl(net.version);
    payload.chunk_size = ntohl(net.chunk_size);
    payload.window_size = ntohl(net.window_size);
    payload.file_size = network_to_host64(net.file_size);

    // 读取 filename 长度
    std::uint16_t net_name_len = 0;
    std::memcpy(&net_name_len, buffer.data() + fixed_sz, sizeof(std::uint16_t));
    const std::uint16_t name_len = ntohs(net_name_len);
    if (buffer.size() < fixed_sz + sizeof(std::uint16_t) + name_len) {
        return false;
    }
    if (name_len > 0) {
        payload.filename.assign(reinterpret_cast<const char*>(buffer.data() + fixed_sz + sizeof(std::uint16_t)),
                                reinterpret_cast<const char*>(buffer.data() + fixed_sz + sizeof(std::uint16_t) + name_len));
    } else {
        payload.filename.clear();
    }

    return true;
}

std::uint16_t clamp_window(std::uint32_t window) {
    return static_cast<std::uint16_t>(std::min<std::uint32_t>(window, 0xFFFF));
}

}  // namespace rtp
