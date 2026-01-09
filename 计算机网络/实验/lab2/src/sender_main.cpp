#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <string>
#include <vector>

#include "congestion_control.h"
#include "rtp.h"
#include "timer.h"

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

struct SenderConfig {
    std::string receiver_ip;
    std::uint16_t receiver_port = 0;
    std::string input_file;
    std::string src_ip;
    std::uint32_t window_packets = 32; // 发送窗口大小（以数据包数计）
    std::uint32_t packet_size = 15000;
    std::chrono::milliseconds base_timeout{200};
    double simulated_loss = 0.0;
};

struct PacketState {
    rtp::Packet packet;
    std::chrono::steady_clock::time_point last_sent;
    bool acked = false;// 是否被确认
    bool retransmitted = false;// 是否已重传
};

#ifdef _WIN32
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

bool should_drop(double loss_rate, std::mt19937& rng) {
    if (loss_rate <= 0.0) {
        return false;
    }
    std::uniform_real_distribution<double> dist(0.0, 1.0);
    return dist(rng) < loss_rate;
}

bool send_packet(SocketHandle socket_handle, const sockaddr_in& addr, const rtp::Packet& packet,
                 double loss_rate, std::mt19937& rng) {
    const auto bytes = rtp::serialize(packet);
    if (should_drop(loss_rate, rng)) {
#ifdef RTP_VERBOSE_LOG
        std::cout << "[Sender] Simulated drop for packet seq=" << packet.header.seq << "\n";
#endif
        return true;  // pretend success
    }
#ifdef RTP_VERBOSE_LOG
    {
        char addrbuf[64] = {0};
        inet_ntop(AF_INET, &addr.sin_addr, addrbuf, sizeof(addrbuf));
        std::cout << "[Sender] sendto " << addrbuf << ":" << ntohs(addr.sin_port)
                  << " bytes=" << bytes.size() << " seq=" << packet.header.seq << " flags="
                  << rtp::flags_to_string(packet.header.flags) << "\n";
    }
#endif

    const int sent = sendto(socket_handle, reinterpret_cast<const char*>(bytes.data()),
                            static_cast<int>(bytes.size()), 0,
                            reinterpret_cast<const sockaddr*>(&addr), static_cast<int>(sizeof(addr)));
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
    return rtp::deserialize(buffer.data(), buffer.size(), packet);
}

/**
 * 执行与接收方的握手过程
 * param socket_handle UDP套接字
 * param receiver_addr 接收方地址
 * param config 发送方配置
 * param file_size 待发送文件大小
 * param initial_seq 输出参数，发送方初始序列号
 * param remote_initial_seq 输出参数，接收方初始序列号
 * param remote_window 输出参数，接收方窗口大小
 */
bool perform_handshake(SocketHandle socket_handle, const sockaddr_in& receiver_addr,
                       const SenderConfig& config, std::uint64_t file_size,
                       std::uint32_t& initial_seq, std::uint32_t& remote_initial_seq,
                       std::uint32_t& remote_window, std::mt19937& rng) {
    std::random_device rd;
    initial_seq = rd();
    remote_window = config.window_packets;

    rtp::HandshakePayload payload{rtp::PROTOCOL_VERSION, config.packet_size,
                                  config.window_packets, file_size};
    // 将原始文件名放入握手负载，接收端可据此恢复文件名
    try {
        payload.filename = std::filesystem::path(config.input_file).filename().string();
    } catch (...) {
        payload.filename = "";
    }

    rtp::Packet syn{};
    syn.header.seq = initial_seq;
    syn.header.ack = 0;
    syn.header.flags = rtp::FLAG_SYN;
    syn.header.window = rtp::clamp_window(config.window_packets);
    syn.header.length = static_cast<std::uint16_t>(sizeof(rtp::HandshakePayload));
    syn.payload = rtp::encode_handshake(payload);

    auto next_send_time = std::chrono::steady_clock::now();
    // 十秒钟握手超时
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);

    while (std::chrono::steady_clock::now() < deadline) {
        const auto now = std::chrono::steady_clock::now();
        // 第一次挥手
        if (now >= next_send_time) {
            if (!send_packet(socket_handle, receiver_addr, syn, config.simulated_loss, rng)) {
                std::perror("sendto");
                return false;
            }
#ifdef RTP_VERBOSE_LOG
            std::cout << "[Sender] SYN seq=" << syn.header.seq << "\n";
#endif
            next_send_time = now + std::chrono::milliseconds(500);
        }

        rtp::Packet response;
        sockaddr_in peer{};
        if (!receive_packet(socket_handle, response, peer, std::chrono::milliseconds(200))) {
            continue;
        }
        
        // 验证响应包
        if (!(response.header.flags & rtp::FLAG_SYN) || !(response.header.flags & rtp::FLAG_ACK)) {
            continue;
        }

        // 确认号必须是我们的初始序列号加一
        if (response.header.ack != initial_seq + 1) {
            continue;
        }

        rtp::HandshakePayload peer_payload{};
        if (!rtp::decode_handshake(response.payload, peer_payload)) {
            continue;
        }

        remote_initial_seq = response.header.seq;
        remote_window = peer_payload.window_size;
        
        // 发送最后一个ACK包报文
        rtp::Packet ack{};
        ack.header.seq = initial_seq + 1;
        ack.header.ack = remote_initial_seq + 1;
        ack.header.flags = rtp::FLAG_ACK;
        ack.header.window = rtp::clamp_window(config.window_packets);
        ack.header.length = 0;
        
        // 最后一个ACK包
        if (!send_packet(socket_handle, receiver_addr, ack, config.simulated_loss, rng)) {
            std::perror("sendto");
            return false;
        }
#ifdef RTP_VERBOSE_LOG
        std::cout << "[Sender] Handshake complete. Remote window=" << remote_window << "\n";
#endif
        return true;
    }

    std::cerr << "[Sender] Handshake timeout" << std::endl;
    return false;
}

/**
 * 分块加载文件
 */
std::vector<std::vector<std::uint8_t>> load_chunks(const std::string& file_path, std::size_t chunk_size) {
    std::ifstream input(file_path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("无法打开输入文件: " + file_path);
    }

    std::vector<std::vector<std::uint8_t>> chunks;
    std::vector<std::uint8_t> buffer(chunk_size);

    while (input) {
        input.read(reinterpret_cast<char*>(buffer.data()), static_cast<std::streamsize>(chunk_size));
        const auto read_bytes = input.gcount();
        if (read_bytes <= 0) {
            break;
        }
        chunks.emplace_back(buffer.begin(), buffer.begin() + read_bytes);
    }

    return chunks;
}

/**
 * 计算允许的发送窗口大小
 */
std::uint32_t allowed_window(const SenderConfig& config, double congestion_window,
                             std::uint32_t peer_window) {
    const auto cc_window = static_cast<std::uint32_t>(std::max(1.0, congestion_window));
    return std::max<std::uint32_t>(1, std::min({config.window_packets, peer_window, cc_window}));
}

}  // namespace

int main(int argc, char* argv[]) {
#ifdef _WIN32
    // Ensure console uses UTF-8 so Chinese literals print correctly
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
#endif
    if (argc < 6) {
        std::cerr << "用法: sender <receiver_ip> <receiver_port> <input_file> <window_packets> <packet_size> [timeout_ms] [--loss=0.0] [--src-ip=IP]\n";
        return 1;
    }

    SenderConfig config;
    config.receiver_ip = argv[1];
    config.receiver_port = static_cast<std::uint16_t>(std::stoi(argv[2]));
    config.input_file = argv[3];
    config.window_packets = static_cast<std::uint32_t>(std::stoi(argv[4]));
    config.packet_size = static_cast<std::uint32_t>(std::stoi(argv[5]));

    // 设置超时时间（位置参数）
    if (argc >= 7) {
        try { config.base_timeout = std::chrono::milliseconds(std::stoi(argv[6])); } catch(...) {}
    }

    // 解析可选标志（从 argv[7] 开始），支持 --loss= 和 --src-ip=
    for (int i = 7; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg.rfind("--loss=", 0) == 0) {
            try { config.simulated_loss = std::stod(arg.substr(7)); } catch(...) {}
        } else if (arg.rfind("--src-ip=", 0) == 0) {
            config.src_ip = arg.substr(9);
        }
    }

    if (config.packet_size == 0 || config.packet_size > rtp::MAX_PAYLOAD_SIZE) {
        std::cerr << "数据包大小必须在 1-" << rtp::MAX_PAYLOAD_SIZE << " 字节之间\n";
        return 1;
    }

    if (!std::filesystem::exists(config.input_file)) {
        std::cerr << "输入文件不存在: " << config.input_file << "\n";
        return 1;
    }

#ifdef _WIN32
    // ？？？
    WinsockInitializer winsock_guard;
#endif

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

    // struct sockaddr_in
    // {
    //   short sin_family;  // 地址族（AF_INET）
    //   u_short sin_port;  // 端口
    //   struct in_addr sin_addr; // IP地址
    //   char sin_zero[8]; // 填充字节，保持结构体大小一致
    // };

    sockaddr_in receiver_addr{};
    receiver_addr.sin_family = AF_INET;
    receiver_addr.sin_port = htons(config.receiver_port);
    // 检查IP地址是否合法，并填充sin_addr字段
    if (inet_pton(AF_INET, config.receiver_ip.c_str(), &receiver_addr.sin_addr) != 1) {
        std::cerr << "无效的接收方地址: " << config.receiver_ip << "\n";
        close_socket(socket_handle);
        return 1;
    }
    // 如果用户指定了源地址，绑定 socket 到该源地址（端口由系统选择）
    if (!config.src_ip.empty()) {
        sockaddr_in local{};
        local.sin_family = AF_INET;
        local.sin_port = htons(0); // 让系统选择端口
        if (inet_pton(AF_INET, config.src_ip.c_str(), &local.sin_addr) != 1) {
            std::cerr << "无效的源地址: " << config.src_ip << "\n";
            close_socket(socket_handle);
            return 1;
        }
        if (bind(socket_handle, reinterpret_cast<const sockaddr*>(&local), sizeof(local)) != 0) {
            std::perror("bind");
            close_socket(socket_handle);
            return 1;
        }
    }
    
    // 文件大小
    const std::uint64_t file_size = std::filesystem::file_size(config.input_file);
    
    // 随机数生成器
    std::mt19937 rng(std::random_device{}());

    std::uint32_t sender_isn = 0;
    std::uint32_t receiver_isn = 0;
    std::uint32_t receiver_window = config.window_packets;

    try {
      // 执行握手
        if (!perform_handshake(socket_handle, receiver_addr, config, file_size, sender_isn,
                               receiver_isn, receiver_window, rng)) {
            close_socket(socket_handle);
            return 1;
        }
    } catch (const std::exception& ex) {
        std::cerr << "握手失败: " << ex.what() << "\n";
        close_socket(socket_handle);
        return 1;
    }
    
    // 加载文件并分块
    const auto chunks = load_chunks(config.input_file, config.packet_size);
    const std::uint32_t total_packets = static_cast<std::uint32_t>(chunks.size());
    const std::uint64_t total_bytes = file_size;

    if (total_packets == 0) {
        std::cerr << "输入文件为空\n";
        close_socket(socket_handle);
        return 1;
    }

    const std::uint32_t data_seq_start = sender_isn + 1;
    const std::uint32_t fin_seq = data_seq_start + total_packets;// 最后一个FIN包的序列号
    std::uint32_t next_seq = data_seq_start;// 下一个要发送的数据包序列号
    std::uint32_t last_ack = data_seq_start;//上一个确认号

    std::map<std::uint32_t, PacketState> inflight;//正在传输的包
    RenoCongestionControl congestion;// 拥塞控制器
    RttEstimator rtt_estimator;
    const auto rto_base = config.base_timeout;

    Stopwatch stopwatch;
    stopwatch.start();

    bool fin_sent = false;// 是否发送了FIN包
    bool fin_acked = false;// 是否收到FIN包的确认
    std::uint64_t bytes_acked = 0;// 已确认的字节数

    // 开始传输数据包
    while (!fin_acked) {
      
        // 获取允许的发送窗口大小
        const std::uint32_t window = allowed_window(config, congestion.window_packets(), receiver_window);

        while (!fin_sent && next_seq < fin_seq && inflight.size() < window) {
            const auto index = next_seq - data_seq_start;
            rtp::Packet packet{};
            packet.header.seq = next_seq;
            packet.header.ack = last_ack;
            packet.header.flags = rtp::FLAG_DATA;
            packet.header.window = rtp::clamp_window(config.window_packets);
            packet.header.length = static_cast<std::uint16_t>(chunks[index].size());
            packet.payload = chunks[index];

            if (!send_packet(socket_handle, receiver_addr, packet, config.simulated_loss, rng)) {
                std::perror("sendto");
                close_socket(socket_handle);
                return 1;
            }

            inflight[next_seq] = PacketState{packet, std::chrono::steady_clock::now(), false, false};
            ++next_seq;
        }
        // 如果已经发送完所有数据包，且当前没有未确认的数据包，发送FIN包
        if (!fin_sent && inflight.empty() && next_seq >= fin_seq) {
            rtp::Packet fin{};
            fin.header.seq = fin_seq;
            fin.header.ack = last_ack;
            fin.header.flags = rtp::FLAG_FIN | rtp::FLAG_ACK;
            fin.header.window = rtp::clamp_window(config.window_packets);
            fin.header.length = 0;
            if (!send_packet(socket_handle, receiver_addr, fin, config.simulated_loss, rng)) {
                std::perror("sendto");
                close_socket(socket_handle);
                return 1;
            }
            inflight[fin_seq] = PacketState{fin, std::chrono::steady_clock::now(), false, false};
            fin_sent = true;
        }

        rtp::Packet ack_packet;
        sockaddr_in peer{};
        if (receive_packet(socket_handle, ack_packet, peer, std::chrono::milliseconds(50))) {
            if (!(ack_packet.header.flags & rtp::FLAG_ACK)) {
                continue;
            }

            // 如果对端在这个 ACK 包中携带了 FIN（即对端也要主动关闭），我们需要回复一个最终的 ACK
            // 以确认对端的 FIN。接收端通常会检查 ack == peer_fin_seq + 1。
            if (ack_packet.header.flags & rtp::FLAG_FIN) {
                rtp::Packet final_ack{};
                // 使用当前已确认的序号作为我们的 seq 字段（不重要，接收端只检查 ack）
                final_ack.header.seq = last_ack;
                // 确认对端的 FIN（对端的 FIN seq + 1）
                final_ack.header.ack = ack_packet.header.seq + 1;
                final_ack.header.flags = rtp::FLAG_ACK;
                final_ack.header.window = rtp::clamp_window(config.window_packets);
                final_ack.header.length = 0;
                // 发送响应 ACK，确保接收端能及时检测到并结束等待
                send_packet(socket_handle, receiver_addr, final_ack, config.simulated_loss, rng);
            }

            receiver_window = std::max<std::uint32_t>(1, ack_packet.header.window);
            const auto cumulative_ack = ack_packet.header.ack;
            const auto now = std::chrono::steady_clock::now();

            // 标记已确认的数据包，并更新RTT估计
            auto mark_acked = [&](std::uint32_t seq) {
                auto it = inflight.find(seq);
                if (it != inflight.end() && !it->second.acked) {
                    it->second.acked = true;
                    // 更新RTT估计
                    if (!it->second.retransmitted) {
                        const auto sample = std::chrono::duration_cast<std::chrono::milliseconds>(now - it->second.last_sent);
                        // 只用未重传包的RTT样本更新估计
                        rtt_estimator.update(sample);
                    }
                    bytes_acked += it->second.packet.header.length;
                }
            };

            if (cumulative_ack > last_ack) {// 收到新的ACK
                for (std::uint32_t seq = last_ack; seq < cumulative_ack; ++seq) {
                    mark_acked(seq);
                }

                std::vector<std::uint32_t> to_remove;
                for (const auto& [seq, state] : inflight) {
                    if (seq < cumulative_ack && state.acked) {
                        to_remove.push_back(seq);
                    }
                }
                for (auto seq : to_remove) {
                    inflight.erase(seq);
                }

                last_ack = cumulative_ack;
                congestion.on_new_ack();
                congestion.on_recovery_ack();
            } else if (cumulative_ack == last_ack) {
              // 收到重复ACK
                congestion.on_duplicate_ack();
            }
            
            // 处理SACK位图
            if (ack_packet.header.sack_bits) {
                for (std::uint32_t i = 0; i < rtp::MAX_SACK_BITS; ++i) {
                    if (ack_packet.header.sack_bits & (1u << i)) {
                        const auto seq = cumulative_ack + i + 1;
                        mark_acked(seq);
                    }
                }

                std::vector<std::uint32_t> to_remove;
                for (const auto& [seq, state] : inflight) {
                    if (state.acked) {
                        to_remove.push_back(seq);
                    }
                }
                for (auto seq : to_remove) {
                    inflight.erase(seq);
                }
            }
            
            // 需要快速重传并且有对应的未确认包
            if (congestion.should_trigger_fast_retransmit() && inflight.count(cumulative_ack) > 0) {
                auto& state = inflight[cumulative_ack];
                state.retransmitted = true;
                state.last_sent = std::chrono::steady_clock::now();
                send_packet(socket_handle, receiver_addr, state.packet, config.simulated_loss, rng);
                congestion.clear_fast_retransmit_flag();
            }
            
            // 如果所有数据包都已确认，且FIN包的确认号大于FIN包序列号，标记FIN为已确认
            if (fin_sent && cumulative_ack > fin_seq) {
                fin_acked = true;
                break;
            }
        }

        const auto now = std::chrono::steady_clock::now();
        const auto rto = rtt_estimator.current_rto() + config.base_timeout;
        bool timeout_triggered = false;
        for (auto& [seq, state] : inflight) {
            // 检测超时
            if (!state.acked && now - state.last_sent >= rto) {
                state.retransmitted = true;
                state.last_sent = now;
                send_packet(socket_handle, receiver_addr, state.packet, config.simulated_loss, rng);
                timeout_triggered = true;
            }                   
        }
        if (timeout_triggered) {
            congestion.on_timeout();
        }
    }

    stopwatch.stop();
    const double seconds = stopwatch.elapsed_seconds();
    const double throughput_mbps = (static_cast<double>(total_bytes) * 8.0) / (seconds * 1'000'000.0);

    std::cout << "传输完成: " << total_bytes << " 字节, 用时 " << seconds << " 秒, 平均吞吐率 "
              << throughput_mbps << " Mbps" << std::endl;

    close_socket(socket_handle);
    return 0;
}
