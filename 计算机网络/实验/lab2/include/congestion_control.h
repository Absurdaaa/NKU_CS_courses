#pragma once

#include <cstdint>
#include <algorithm>

class RenoCongestionControl {
public:
    RenoCongestionControl(double initial_cwnd_packets = 1.0, double initial_ssthresh_packets = 32.0);

    void on_new_ack();
    void on_duplicate_ack();
    void on_recovery_ack();
    void on_timeout();

    double window_packets() const;
    double ssthresh_packets() const { return ssthresh_; }

    bool should_trigger_fast_retransmit() const;
    void clear_fast_retransmit_flag();

private:
    enum class State {
                        SlowStart, // 慢启动
                        CongestionAvoidance, // 拥塞避免
                        FastRecovery // 快速恢复
                    };

    double cwnd_; // 拥塞窗口大小（以数据包数计）
    double ssthresh_; // 慢启动阈值（以数据包数计）
    mutable bool fast_retransmit_pending_ = false; // 快速重传标志
    State state_ = State::SlowStart; // 当前状态
    std::uint32_t duplicate_ack_count_ = 0; // 重复ACK计数
};
