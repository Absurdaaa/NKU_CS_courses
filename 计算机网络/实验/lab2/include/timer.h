#pragma once

#include <chrono>
/**
 * 计时器
 */
class Stopwatch {
public:
    // 开始计时
    void start();
    // 停止计时
    void stop();
    // 重置计时器
    void reset();
    // 获取经过的秒数
    double elapsed_seconds() const;
    // 获取经过的毫秒数
    double elapsed_milliseconds() const;

private:
    std::chrono::steady_clock::time_point start_{};
    std::chrono::steady_clock::time_point end_{};
    bool running_ = false;
};

/**
 * 往返时间估计器
 */
class RttEstimator {
public:
    RttEstimator();

    void update(std::chrono::milliseconds sample);
    std::chrono::milliseconds current_rto() const;

private:
    std::chrono::milliseconds srtt_;
    std::chrono::milliseconds rttvar_;
};
