# RttEstimator（往返时间估计器）说明文档

该文档描述了项目中 `RttEstimator` 类的目的、算法实现细节、与发送端的集成方式、测试建议以及可能的改进方向。该说明适合作为实验报告的一部分或放入 `docs/` 目录供团队参考。

## 概要

`RttEstimator` 用来估计数据包从发送到收到确认（ACK）的往返时间（RTT），并基于 RTT 的估计和方差计算重传超时（RTO）。正确的 RTO 能避免过早重传（引入额外负载）或迟迟不重传（延长丢包恢复时间）。

在本项目中，发送端在收到对某个原始未重传包的 ACK 时，会把样本 RTT 提交给 `RttEstimator::update()`；发送端在判断是否超时时会调用 `RttEstimator::current_rto()` 来获得当前建议的 RTO 值。

## 设计目标

- 以稳定且标准化的方式估计 RTT（使用 EWMA），能够对抖动进行平滑处理。
- 估计 RTT 的同时估计 RTT 的方差（rttvar），用于计算保守的 RTO（通常 RTO = srtt + 4 * rttvar）。
- 对首次样本和随后的样本采取不同初始化逻辑，遵循 Jacobson/Karels 以及 RFC 6298 的指导。
- 提供合理的最小/最大 RTO 边界以避免极端值。

## 算法细节（推荐实现）

常用的 RTT 更新规则（Jacobson/Karels）：

- 参数：α = 1/8（0.125），β = 1/4（0.25）
- 初始样本（如果尚无 srtt）：
  - srtt = sample
  - rttvar = sample / 2
- 后续样本：
  - rttvar = (1 - β) * rttvar + β * |srtt - sample|
  - srtt = (1 - α) * srtt + α * sample
- RTO 计算：
  - RTO = srtt + max(4 * rttvar, G)
  - 其中 G 是时钟粒度（可设为 1ms 或更大的值）

参考：RFC 6298（默认 RTO 初始值和退避策略）以及原始 Jacobson/Karels 论文。

## 建议的 C++ 实现要点

- 在 `include/timer.h` 中 `RttEstimator` 已声明两个私有成员：`srtt_` 与 `rttvar_`（以毫秒为单位）。
- 推荐在实现文件（`src/timer.cpp`）中提供如下行为：
  - 构造函数初始化 `srtt_` 和 `rttvar_` 为 0。
  - `update(sample)` 接受 `std::chrono::milliseconds`，按上面公式更新 `srtt_` 和 `rttvar_`。
  - `current_rto()` 返回 `std::chrono::milliseconds`，在无样本时返回一个合理的默认值（例如 1000ms 或 500ms，实验环境可调整）。
  - 对计算结果施加上下限（例如最小 200ms，最大 60s），避免过短/过长的 RTO。

下面是一个可直接放入 `src/timer.cpp` 的参考实现片段：

```cpp
RttEstimator::RttEstimator()
    : srtt_(0), rttvar_(0) {}

void RttEstimator::update(std::chrono::milliseconds sample) {
    const double alpha = 1.0 / 8.0;
    const double beta = 1.0 / 4.0;

    if (srtt_.count() == 0) {
        srtt_ = sample;
        rttvar_ = sample / 2;
        return;
    }

    // 计算差值的绝对值
    auto diff = sample > srtt_ ? sample - srtt_ : srtt_ - sample;
    // rttvar = (1 - beta) * rttvar + beta * diff
    rttvar_ = std::chrono::milliseconds(static_cast<long>(
        (1.0 - beta) * rttvar_.count() + beta * diff.count()));
    // srtt = (1 - alpha) * srtt + alpha * sample
    srtt_ = std::chrono::milliseconds(static_cast<long>(
        (1.0 - alpha) * srtt_.count() + alpha * sample.count()));
}

std::chrono::milliseconds RttEstimator::current_rto() const {
    if (srtt_.count() == 0) {
        return std::chrono::milliseconds(1000); // 初始 RTO，可调整
    }
    auto rto = srtt_ + std::chrono::milliseconds(std::max<long>(4 * rttvar_.count(), 1));
    const auto min_rto = std::chrono::milliseconds(200);
    const auto max_rto = std::chrono::seconds(60);
    if (rto < min_rto) rto = min_rto;
    if (rto > max_rto) rto = max_rto;
    return rto;
}
```

注意：本项目的发送端还把 `current_rto()` 的返回值与 `config.base_timeout` 相加（见 `sender_main.cpp`），这是一种更保守的超时策略，允许在动态 RTO 基础上再加上一个固定的安全量。

## 集成与使用建议

- 仅在未发生重传的包上采样：如果某个包被重传过，则其 ACK 到达时间不一定对应原始传输路径，不能直接作为 RTT 样本。你的发送器在标记 `retransmitted` 后避免使用这些样本，这点实现正确。
- 初始 RTO 的选取：RFC 6298 建议初始 RTO 为 1s。实验中如果 RTT 较小（局域网），也可以用 200-500ms，但需谨慎以免造成过早重传。
- 当出现多次超时（RTO 重试）时，通常需要指数回退（RTO *= 2）；本项目中发送端的超时处理可以按需实现指数退避逻辑。

## 测试建议

1. 单元测试：模拟一系列 RTT 样本（例如 50ms、60ms、120ms、80ms），调用 `update()` 并检查 `srtt_` 与 `rttvar_` 的期望变化。
2. 集成测试：在 `sender`/`receiver` 程序中注入网络延时与丢包，观察 RTO 随时间的动态调整，确认超时触发与快速重传行为合理。

## 可选改进

- 将初始 RTO、最小/最大 RTO 以及 α/β 暴露为配置参数以便调优。
- 实现 RTO 指数退避（当连续超时发生时，RTO *= 2）。
- 记录并导出 srtt/rttvar/rto 时间序列，便于离线分析与可视化。

---

文件位置：`docs/rtt_estimator.md`

如果你希望我把参考实现直接写入 `src/timer.cpp`，并在本地编译或运行基本测试，请回复“实现并测试”，我会继续修改并运行构建命令（需要你允许我执行构建）。
