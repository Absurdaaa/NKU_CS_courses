#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <string>
#include <vector>
#include <sstream>
#include <iomanip>
#include <filesystem>

#include "rtp.h"
#include "timer.h"

// 是否windows平台
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
using SocketHandle = SOCKET;
#include <windows.h>
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
using SocketHandle = int;
#endif

namespace {

constexpr std::size_t HEADER_SIZE = sizeof(rtp::PacketHeader);

// 接收方的一些参数
struct ReceiverConfig {
    std::uint16_t listen_port = 0;
    std::string output_file;
    std::string listen_ip;
    std::string expected_peer_ip;
    std::uint32_t window_packets = 32;
    std::uint32_t packet_size = 1000;
    double simulated_loss = 0.0;
};

#ifdef _WIN32
// 确保Winsock在程序生命周期内正确初始化和清理
struct WinsockInitializer {
    WinsockInitializer() { WSAStartup(MAKEWORD(2, 2), &wsa_); }
    ~WinsockInitializer() { WSACleanup(); }
    WSADATA wsa_{};
};
#endif

void close_socket(SocketHandle socket_handle) {
#ifdef _WIN32
    if (socket_handle != INVALID_SOCKET) {
        closesocket(socket_handle);
    }
#else
    if (socket_handle >= 0) {
        close(socket_handle);
    }
#endif
}

// 随机丢包函数
bool should_drop(double rate, std::mt19937& rng) {
    if (rate <= 0.0) {
        return false;
    }
    std::uniform_real_distribution<double> dist(0.0, 1.0);
    return dist(rng) < rate;
}

// 发送包裹
bool send_packet(SocketHandle socket_handle, const sockaddr_in& addr, const rtp::Packet& packet,
                 double loss_rate, std::mt19937& rng) {
    // 
    if (should_drop(loss_rate, rng)) {
#ifdef RTP_VERBOSE_LOG
        std::cout << "[Receiver] Simulated drop when sending flags=" << rtp::flags_to_string(packet.header.flags)
                  << "\n";
#endif
        return true;
    }
    // 序列化报文
    const auto bytes = rtp::serialize(packet);
    const int sent = sendto(socket_handle, reinterpret_cast<const char*>(bytes.data()),
                            static_cast<int>(bytes.size()), 0,
                            reinterpret_cast<const sockaddr*>(&addr), sizeof(addr));
    return sent == static_cast<int>(bytes.size());
}

bool receive_packet(SocketHandle socket_handle, rtp::Packet& packet, sockaddr_in& peer_addr,
                    std::chrono::milliseconds timeout) {
    fd_set readfds;
    FD_ZERO(&readfds);
    FD_SET(socket_handle, &readfds);

    timeval tv{};
    tv.tv_sec = static_cast<long>(timeout.count() / 1000);
    tv.tv_usec = static_cast<long>((timeout.count() % 1000) * 1000);

    const int ready = select(static_cast<int>(socket_handle + 1), &readfds, nullptr, nullptr, &tv);
    if (ready <= 0) {
        return false;
    }

    socklen_t addr_len = sizeof(peer_addr);
    std::vector<std::uint8_t> buffer(HEADER_SIZE + rtp::MAX_PAYLOAD_SIZE);
    const int received = recvfrom(socket_handle, reinterpret_cast<char*>(buffer.data()),
                                  static_cast<int>(buffer.size()), 0,
                                  reinterpret_cast<sockaddr*>(&peer_addr), &addr_len);
    if (received <= 0) {
        return false;
    }

    buffer.resize(received);
#ifdef RTP_VERBOSE_LOG
    {
        char addrbuf[64] = {0};
        inet_ntop(AF_INET, &peer_addr.sin_addr, addrbuf, sizeof(addrbuf));
        std::cout << "[Receiver] recvfrom from " << addrbuf << ":" << ntohs(peer_addr.sin_port)
                  << " size=" << received << " bytes\n";
        // hex dump first 48 bytes
        std::size_t dump = std::min<std::size_t>(buffer.size(), 48);
        std::ostringstream oss;
        oss << std::hex << std::setfill('0');
        for (std::size_t i = 0; i < dump; ++i) {
            oss << std::setw(2) << static_cast<int>(buffer[i]) << ' ';
        }
        std::cout << "[Receiver] data: " << oss.str() << std::dec << std::endl;
    }
#endif

    if (!rtp::deserialize(buffer.data(), buffer.size(), packet)) {
#ifdef RTP_VERBOSE_LOG
        std::cout << "[Receiver] deserialize failed (checksum/format)\n";
#endif
        return false;
    }

    return true;
}

// 计算剩余窗口大小
std::uint32_t compute_free_window(std::uint32_t total_window, std::size_t buffered_packets) {
    if (buffered_packets >= total_window) {
        return 0;
    }
    return total_window - static_cast<std::uint32_t>(buffered_packets);
}

// 构建SACK位图
std::uint32_t build_sack_bits(std::uint32_t base_seq,
                              const std::map<std::uint32_t, std::vector<std::uint8_t>>& buffer) {
    std::uint32_t bits = 0;
    for (std::uint32_t i = 0; i < rtp::MAX_SACK_BITS; ++i) {
        const auto seq = base_seq + i + 1;
        if (buffer.find(seq) != buffer.end()) {
            bits |= (1u << i);
        }
    }
    return bits;
}

}  // namespace

int main(int argc, char* argv[]) {
#ifdef _WIN32
    // 确保控制台使用UTF-8编码以正确显示中文
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
#endif

    if (argc < 5) {
        std::cerr << "用法: receiver <listen_port> <output_file> <window_packets> <packet_size> [--loss=0.0] [--listen-ip=IP] [--peer-ip=IP]\n";
        return 1;
    }

    ReceiverConfig config;
    // 监听端口
    config.listen_port = static_cast<std::uint16_t>(std::stoi(argv[1]));
    // 输出文件路径
    config.output_file = argv[2];
    // 接收窗口大小（以数据包数计）
    config.window_packets = static_cast<std::uint32_t>(std::stoi(argv[3]));
    // 每个数据包的最大负载大小（字节数）
    config.packet_size = static_cast<std::uint32_t>(std::stoi(argv[4]));

    // 可选：模拟丢包率
    // parse optional flags (allow in any order after required ones)
    for (int i = 5; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg.rfind("--loss=", 0) == 0) {
            try { config.simulated_loss = std::stod(arg.substr(7)); } catch(...) {}
        } else if (arg.rfind("--listen-ip=", 0) == 0) {
            config.listen_ip = arg.substr(12);
        } else if (arg.rfind("--peer-ip=", 0) == 0) {
            config.expected_peer_ip = arg.substr(10);
        }
    }

    if (config.packet_size == 0 || config.packet_size > rtp::MAX_PAYLOAD_SIZE) {
        std::cerr << "数据包大小必须在 1-" << rtp::MAX_PAYLOAD_SIZE << " 字节之间\n";
        return 1;
    }

#ifdef _WIN32
    WinsockInitializer winsock_guard;
#endif
    // 创建UDP套接字
    SocketHandle socket_handle = socket(AF_INET, SOCK_DGRAM, 0);
    if (socket_handle
#ifdef _WIN32
        == INVALID_SOCKET
#else
        < 0
#endif
    ) {
        std::perror("socket");
        return 1;
    }
    
    // 初始化本地地址并绑定套接字
    sockaddr_in local{};
    local.sin_family = AF_INET;
    local.sin_port = htons(config.listen_port);
    if (!config.listen_ip.empty()) {
        if (inet_pton(AF_INET, config.listen_ip.c_str(), &local.sin_addr) != 1) {
            std::cerr << "无效的 listen IP: " << config.listen_ip << "\n";
            close_socket(socket_handle);
            return 1;
        }
    } else {
        local.sin_addr.s_addr = INADDR_ANY;
    }
    // 绑定套接字
    if (bind(socket_handle, reinterpret_cast<const sockaddr*>(&local), sizeof(local)) != 0) {
#ifdef _WIN32
        int wsaerr = WSAGetLastError();
        char addrbuf[64] = {0};
        inet_ntop(AF_INET, &local.sin_addr, addrbuf, sizeof(addrbuf));
        std::cerr << "bind failed for " << addrbuf << ": port " << ntohs(local.sin_port)
                  << ", WSAGetLastError=" << wsaerr << "\n";
#else
        std::perror("bind");
#endif
        close_socket(socket_handle);
        return 1;
    }

    // Output file will be determined after handshake; open a temporary stream later
    std::ofstream output;
    
    // 用于模拟丢包的随机数生成器
    std::mt19937 rng(std::random_device{}());

    // 握手阶段
    rtp::Packet packet;
    sockaddr_in client_addr{};

    std::cout << "等待客户端连接..." << std::endl;

    // Handshake: wait for SYN
    while (true) {
        if (!receive_packet(socket_handle, packet, client_addr, std::chrono::milliseconds(500))) {
            std::cout << "等待客户端连接..." << std::endl;
            continue;
        }
        // 如果接受到SYN包，跳出循环，检查握手载荷
        if (packet.header.flags & rtp::FLAG_SYN) {
            break;
        }
    }
    // 发送SYN-ACK响应
    rtp::HandshakePayload sender_payload{};
    if (!rtp::decode_handshake(packet.payload, sender_payload)) {
        std::cerr << "握手载荷无效\n";
        close_socket(socket_handle);
        return 1;
    }

    const std::uint32_t sender_isn = packet.header.seq;
    const std::uint64_t expected_file_size = sender_payload.file_size;

    std::random_device rd;
    const std::uint32_t receiver_isn = rd();

    rtp::HandshakePayload response_payload{rtp::PROTOCOL_VERSION, config.packet_size,
                                           config.window_packets, expected_file_size};

    rtp::Packet syn_ack{};
    syn_ack.header.seq = receiver_isn;
    syn_ack.header.ack = sender_isn + 1;
    syn_ack.header.flags = rtp::FLAG_SYN | rtp::FLAG_ACK;// 取|
    syn_ack.header.window = rtp::clamp_window(config.window_packets);
    syn_ack.header.length = sizeof(rtp::HandshakePayload);
    syn_ack.payload = rtp::encode_handshake(response_payload);

    if (!send_packet(socket_handle, client_addr, syn_ack, config.simulated_loss, rng)) {
        std::perror("sendto");
        close_socket(socket_handle);
        return 1;
    }

    // Wait for final ACK
    bool handshake_complete = false;
    const auto handshake_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (!handshake_complete && std::chrono::steady_clock::now() < handshake_deadline) {
        if (!receive_packet(socket_handle, packet, client_addr, std::chrono::milliseconds(200))) {
            continue;
        }
        if ((packet.header.flags & rtp::FLAG_ACK) && packet.header.ack == receiver_isn + 1) {
            handshake_complete = true;
            break;
        }
    }

    if (!handshake_complete) {
        std::cerr << "握手未完成" << std::endl;
        close_socket(socket_handle);
        return 1;
    }

    // 如果发送端在握手里包含文件名，则使用该文件名作为输出，否则使用命令行提供的路径
    std::string final_output_path = config.output_file;
    if (!sender_payload.filename.empty()) {
        final_output_path = sender_payload.filename;
    }

    output.open(final_output_path + ".part", std::ios::binary);
    if (!output) {
        std::cerr << "无法打开输出文件: " << final_output_path << ".part" << "\n";
        close_socket(socket_handle);
        return 1;
    }

    std::cout << "握手成功，开始接收数据 (预计 " << expected_file_size << " 字节), 保存为 " << final_output_path << "\n";
    
    // 数据接收阶段
    std::map<std::uint32_t, std::vector<std::uint8_t>> reorder_buffer;// 重排序缓冲区
    std::uint32_t expected_seq = sender_isn + 1;// 期望的下一个序列号
    std::uint64_t bytes_written = 0;

    Stopwatch stopwatch;
    bool stopwatch_started = false;

    auto flush_contiguous = [&]() {
        bool progressed = true;
        while (progressed) {// 连续滑动窗口
            progressed = false;
            auto it = reorder_buffer.find(expected_seq);
            if (it != reorder_buffer.end()) {
                output.write(reinterpret_cast<const char*>(it->second.data()),
                             static_cast<std::streamsize>(it->second.size()));
                bytes_written += it->second.size();
                reorder_buffer.erase(it);
                ++expected_seq;
                progressed = true;
            }
        }
    };

    bool fin_received = false;

    while (!fin_received) {
        if (!receive_packet(socket_handle, packet, client_addr, std::chrono::milliseconds(100))) {
            continue;
        }

        if (!stopwatch_started && (packet.header.flags & rtp::FLAG_DATA)) {
            stopwatch.start();
            stopwatch_started = true;
        }

        if (packet.header.flags & rtp::FLAG_DATA) {
            const auto seq = packet.header.seq;

            if (seq < expected_seq) {
                // 已经确认的数据包，直接发送当前状态的ACK
                // duplicate data, immediately ACK current state
            } 
            else if (seq >= expected_seq + config.window_packets) {
                // 超出窗口范围，丢弃
#ifdef RTP_VERBOSE_LOG
                std::cout << "[Receiver] Window full, dropping seq=" << seq << "\n";
#endif
            } else {
                reorder_buffer.emplace(seq, packet.payload);
                if (seq == expected_seq) {
                    flush_contiguous();
                }
            }

            rtp::Packet ack{};
            ack.header.seq = receiver_isn + 1;
            ack.header.ack = expected_seq;
            ack.header.flags = rtp::FLAG_ACK | rtp::FLAG_SACK;
            ack.header.window = rtp::clamp_window(compute_free_window(config.window_packets, reorder_buffer.size()));
            ack.header.sack_bits = build_sack_bits(expected_seq, reorder_buffer);
            ack.header.length = 0;
            
            // 每次收到一次数据包后都发送ACK
            send_packet(socket_handle, client_addr, ack, config.simulated_loss, rng);
            continue;
        }

        if (packet.header.flags & rtp::FLAG_FIN) {
            fin_received = true;
            expected_seq = std::max(expected_seq, packet.header.seq + 1);

            rtp::Packet ack{};
            ack.header.seq = receiver_isn + 1;
            ack.header.ack = expected_seq;
            ack.header.flags = rtp::FLAG_ACK;
            ack.header.window = rtp::clamp_window(compute_free_window(config.window_packets, reorder_buffer.size()));
            ack.header.length = 0;
            send_packet(socket_handle, client_addr, ack, config.simulated_loss, rng);

            rtp::Packet fin{};
            fin.header.seq = receiver_isn + 2;
            fin.header.ack = expected_seq;
            fin.header.flags = rtp::FLAG_FIN | rtp::FLAG_ACK;
            fin.header.window = rtp::clamp_window(compute_free_window(config.window_packets, reorder_buffer.size()));
            fin.header.length = 0;
            send_packet(socket_handle, client_addr, fin, config.simulated_loss, rng);
            break;
        }
    }

    // Wait for final ACK confirming our FIN
    auto shutdown_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (std::chrono::steady_clock::now() < shutdown_deadline) {
        if (!receive_packet(socket_handle, packet, client_addr, std::chrono::milliseconds(200))) {
            continue;
        }
        // 确认号应为 receiver_isn + 3
        if ((packet.header.flags & rtp::FLAG_ACK) && packet.header.ack == receiver_isn + 3) {
            break;
        }
    }

    stopwatch.stop();
    output.flush();

    // 关闭并原子重命名 .part 文件到最终文件名
    output.close();
    const std::string final_output_path_noext = std::string(final_output_path);
    const std::string part_path = final_output_path + ".part";
    try {
        std::filesystem::rename(part_path.c_str(), final_output_path);
    } catch (...) {
        std::cerr << "无法将临时文件重命名为最终文件: " << final_output_path << "\n";
    }

    std::cout << "接收完成: 写入 " << bytes_written << " 字节";
    if (stopwatch_started) {
        const double seconds = stopwatch.elapsed_seconds();
        const double throughput_mbps = (static_cast<double>(bytes_written) * 8.0) / (seconds * 1'000'000.0);
        std::cout << ", 用时 " << seconds << " 秒, 平均吞吐率 " << throughput_mbps << " Mbps";
    }
    std::cout << std::endl;

    close_socket(socket_handle);
    return 0;
}
