#include "timer.h"

#include <algorithm>
#include <cmath>

void Stopwatch::start() {
    running_ = true;
    start_ = std::chrono::steady_clock::now();
}

void Stopwatch::stop() {
    end_ = std::chrono::steady_clock::now();
    running_ = false;
}

void Stopwatch::reset() {
    running_ = false;
    start_ = {};
    end_ = {};
}

double Stopwatch::elapsed_seconds() const {
    auto end_time = running_ ? std::chrono::steady_clock::now() : end_;
    return std::chrono::duration<double>(end_time - start_).count();
}

double Stopwatch::elapsed_milliseconds() const {
    auto end_time = running_ ? std::chrono::steady_clock::now() : end_;
    return std::chrono::duration<double, std::milli>(end_time - start_).count();
}

RttEstimator::RttEstimator()
    : srtt_(std::chrono::milliseconds(200)), rttvar_(std::chrono::milliseconds(100)) {}

// 使用新的RTT样本更新估计值
void RttEstimator::update(std::chrono::milliseconds sample) {
    if (sample.count() <= 0) {
        return;
    }

    const double alpha = 1.0 / 8.0;
    const double beta = 1.0 / 4.0;

    auto sample_double = static_cast<double>(sample.count());
    auto srtt_double = static_cast<double>(srtt_.count());
    auto rttvar_double = static_cast<double>(rttvar_.count());

    rttvar_double = (1 - beta) * rttvar_double + beta * std::abs(srtt_double - sample_double);
    srtt_double = (1 - alpha) * srtt_double + alpha * sample_double;

    srtt_ = std::chrono::milliseconds(static_cast<int>(srtt_double));
    rttvar_ = std::chrono::milliseconds(static_cast<int>(rttvar_double));
}

std::chrono::milliseconds RttEstimator::current_rto() const {
    auto rto = srtt_ + std::max(std::chrono::milliseconds(50), 4 * rttvar_);
    return std::max(rto, std::chrono::milliseconds(100));
}
