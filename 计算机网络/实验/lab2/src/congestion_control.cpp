#include "congestion_control.h"
/**
 * Reno拥塞控制算法的实现
 */

// 初始化
RenoCongestionControl::RenoCongestionControl(double initial_cwnd_packets, double initial_ssthresh_packets)
    : cwnd_(initial_cwnd_packets), ssthresh_(initial_ssthresh_packets) {}


// 处理新的ACK，收到一个新的确认
void RenoCongestionControl::on_new_ack() {
    duplicate_ack_count_ = 0;
    if (state_ == State::FastRecovery) {
        state_ = State::CongestionAvoidance;
        cwnd_ = ssthresh_;
    }

    if (state_ == State::SlowStart) {
        cwnd_ += 1.0;
        if (cwnd_ >= ssthresh_) {
            state_ = State::CongestionAvoidance;
        }
    } else {// 当状态为拥塞避免时
        cwnd_ += 1.0 / cwnd_;
    }
}

// 处理重复ACK
void RenoCongestionControl::on_duplicate_ack() {
    ++duplicate_ack_count_;
    if (state_ != State::FastRecovery && duplicate_ack_count_ >= 3) {
        ssthresh_ = std::max(2.0, cwnd_ / 2.0);
        cwnd_ = ssthresh_ + 3.0;
        state_ = State::FastRecovery;
        fast_retransmit_pending_ = true;
    } else if (state_ == State::FastRecovery) {
        cwnd_ += 1.0;
    }
}

// 处理恢复ACK，即在快速恢复期间收到的ACK
void RenoCongestionControl::on_recovery_ack() {
    if (state_ == State::FastRecovery) {
        state_ = State::CongestionAvoidance;
        cwnd_ = ssthresh_;
    }
    duplicate_ack_count_ = 0;
}

// 超时处理
void RenoCongestionControl::on_timeout() {
    ssthresh_ = std::max(2.0, cwnd_ / 2.0);
    cwnd_ = 1.0;
    state_ = State::SlowStart;
    duplicate_ack_count_ = 0;
    fast_retransmit_pending_ = false;
}

double RenoCongestionControl::window_packets() const {
    return std::max(1.0, cwnd_);
}

bool RenoCongestionControl::should_trigger_fast_retransmit() const {
    return fast_retransmit_pending_;
}

void RenoCongestionControl::clear_fast_retransmit_flag() {
    fast_retransmit_pending_ = false;
}
