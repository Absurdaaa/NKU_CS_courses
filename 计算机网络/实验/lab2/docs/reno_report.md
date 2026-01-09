# Reno 拥塞控制实现说明

本文档介绍了你在本项目中实现的 Reno 拥塞控制算法（类 `RenoCongestionControl`）的设计、实现细节、与发送器的集成方式、数学语义，以及测试与改进建议。可以把它作为实验报告或项目 README 的一部分。

## 概要

在 `include/congestion_control.h` 与 `src/congestion_control.cpp` 中实现了一个 TCP Reno 风格的拥塞控制模块，使用“包数（packets）”作为 cwnd 与 ssthresh 的度量单位。模块提供以下能力：

- 慢启动（Slow Start）
- 拥塞避免（Congestion Avoidance / AIMD）
- 快速重传与快速恢复（Fast Retransmit & Fast Recovery）
- 超时恢复（Timeout handling）

模块通过事件接口被发送端驱动：发送端在接收到不同类型的 ACK（新 ACK、重复 ACK、恢复 ACK）或在超时发生时调用相应接口来更新 cwnd/ssthresh 并触发必要的重传。

## 代码接口（概览）

- 类名：`RenoCongestionControl`
  - 构造函数：`RenoCongestionControl(double initial_cwnd_packets = 1.0, double initial_ssthresh_packets = 32.0)`
  - 事件方法：
    - `void on_new_ack()` — 收到新的累积 ACK 时调用
    - `void on_duplicate_ack()` — 收到重复 ACK（累积 ACK 未前进）时调用
    - `void on_recovery_ack()` — 在快速恢复阶段收到能退出恢复的 ACK 时调用
    - `void on_timeout()` — RTO 触发时调用
  - 状态查询与控制：
    - `double window_packets() const` — 返回当前 cwnd（至少 1.0）
    - `double ssthresh_packets() const` — 返回当前 ssthresh
    - `bool should_trigger_fast_retransmit() const` — 当检测到 3 次重复 ACK 时返回 true
    - `void clear_fast_retransmit_flag()` — 发送端在实际执行快速重传后调用以清除标志

## 实现细节

核心实现位于 `src/congestion_control.cpp` 中，主要行为如下：

1. 状态与成员

   - `enum State { SlowStart, CongestionAvoidance, FastRecovery }`
   - 成员变量：`double cwnd_`, `double ssthresh_`, `bool fast_retransmit_pending_`, `State state_`, `uint32_t duplicate_ack_count_`

2. `on_new_ack()`

   - 重置重复 ACK 计数 `duplicate_ack_count_ = 0`。
   - 如果处于 `FastRecovery`，切换为 `CongestionAvoidance` 并将 `cwnd_ = ssthresh_`。
   - 若处于 `SlowStart`：`cwnd_ += 1.0`（每收到一个新的 ACK 增一包），并在 `cwnd_ >= ssthresh_` 时切换到 `CongestionAvoidance`。
   - 若处于 `CongestionAvoidance`：`cwnd_ += 1.0 / cwnd_`（每收到一个 ACK 增加约 `1/cwnd`，等价于每 RTT 增加 ~1 包）。

3. `on_duplicate_ack()`

   - `duplicate_ack_count_++`。
   - 当 `duplicate_ack_count_ >= 3` 且当前不在 `FastRecovery`：
     - `ssthresh_ = max(2.0, cwnd_/2.0)`；
     - `cwnd_ = ssthresh_ + 3.0`；
     - `state_ = FastRecovery`；
     - `fast_retransmit_pending_ = true`（通知发送端应立即快速重传）。
   - 若已在 `FastRecovery`，对每个随后到达的重复 ACK 执行 `cwnd_ += 1.0`。

4. `on_recovery_ack()`

   - 若处于 `FastRecovery`，切回 `CongestionAvoidance` 并将 `cwnd_ = ssthresh_`。
   - 清零 `duplicate_ack_count_`。

5. `on_timeout()`

   - `ssthresh_ = max(2.0, cwnd_/2.0)`；
   - `cwnd_ = 1.0`；
   - `state_ = SlowStart`；
   - 清零重复 ACK 计数并清除快速重传挂起标志。

6. 辅助：`window_packets()` 返回 `max(1.0, cwnd_)`，用于发送端计算整数包窗口大小。

## 数学语义

- 慢启动：每收到一个新 ACK，cwnd 增加 1（包），等同于每 RTT 大约翻倍。
- 拥塞避免（AIMD）：每收到一个新 ACK，cwnd 增加 1/cwnd，等同于每 RTT 增加大约 1 包。
- 快速恢复：在 3 次重复 ACK 时，ssthresh ← cwnd/2，cwnd ← ssthresh + 3，然后进入快速恢复；每收到一个重复 ACK，cwnd += 1；当收到覆盖重传的数据的累计 ACK 时退出恢复并把 cwnd 设为 ssthresh。
- 超时：ssthresh ← cwnd/2，cwnd ← 1（回到慢启动）。

> 注意：实现中使用 `double` 来维护 cwnd/ ssthresh 的精度，但发送时会将其与接收方窗口与配置窗口做 `min` 并转换为整数包数发送。

## 与发送器的集成

- 在 `src/sender_main.cpp` 中创建并使用 `RenoCongestionControl congestion;`。
- 在主发送循环中使用：

```cpp
const std::uint32_t window = allowed_window(config, congestion.window_packets(), receiver_window);
```

其中 `allowed_window()` 会取发送端配置窗口、接收端通告窗口与拥塞控制返回的窗口的最小值。

- 在接收到 ACK 后根据是否为新 ACK / 重复 ACK 调用 `on_new_ack()` 或 `on_duplicate_ack()`；当检测到 `congestion.should_trigger_fast_retransmit()` 时，发送端会对相应的包进行快速重传并调用 `clear_fast_retransmit_flag()`。

- 在定期超时检查中，如果包的发送时间超过 RTO，发送端会重传并且调用 `congestion.on_timeout()`。

## 优点与局限

优点：

- 基于经典 Reno 的实现，逻辑清晰，适合作为实验与教学实现。
- 与发送端集成合理，支持快速重传/恢复与超时回退。

局限与改进方向：

1. 当前为标准 Reno：可考虑实现 NewReno 以更好地处理部分 ACK（Partial ACK）的情况。
2. 可以更好利用 SACK 信息优先重传真正丢失分片，减小不必要的重传。
3. RTO 与 ssthresh 的自适应策略可以改进（基于 RTT/bandwidth est.）以提高吞吐与稳定性。
4. 增加可观测性（导出状态/计数器、打印 cwnd 曲线）与测试覆盖（模拟重复 ACK / 超时序列的单元测试）。

## 测试建议

1. 单元测试：构造 ACK 序列模拟不同场景（正常 ACK、3 重复 ACK、连续重复 ACK、RTO）并断言 `cwnd`/`ssthresh` 的期望变化。
2. 端到端：在 `sender`/`receiver` 程序中使用 `--loss` 参数模拟丢包，观察吞吐率、cwnd 收敛行为与重传事件。
3. 参数扫描：调整初始 `ssthresh`、`base_timeout`、包大小，观察系统在不同网络条件下的表现。

## 建议的下一步（可选）

- 将 `RenoCongestionControl` 暴露更多观察接口（例如 `duplicate_ack_count()`、`state()`），便于调试与绘图。
- 在 `receiver_main.cpp` 中实现 FIN 的周期重传以增强连接关闭的鲁棒性（如果 ACK 丢失，可重传 FIN 直到收到最后 ACK 或超时）。
- 编写单元测试来模拟 ACK/丢包序列，验证拥塞控制器行为。

---

文件位置：`docs/reno_report.md`。

如果你需要我把这份报告合并到 `README.md` 的特定部分，或者生成一份英文版本/PPT 演示，我也可以继续处理。
