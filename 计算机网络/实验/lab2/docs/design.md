# 实验 2：自定义可靠传输协议设计与实现说明

## 1. 目标概述

本项目基于 UDP 套接字在用户空间实现了一个**面向连接的单向可靠数据传输协议**，支持如下能力：

- 三次握手 / 四次挥手的连接管理，带异常重传与超时控制。
- 16 bit 反码求和校验，实现端到端差错检测。
- 流水线发送与**选择确认 (Selective ACK)**，保证乱序场景下的高吞吐。
- 固定大小的发送 / 接收滑动窗口，实现基于窗口的流量控制。
- TCP RENO 拥塞控制（慢启动、拥塞避免、快速重传 / 恢复、超时回退）。
- 统计整个文件传输的耗时与平均吞吐率，便于对不同窗口、丢包率进行对比实验。

## 2. 报文格式

### 2.1 RTP 自定义头部

| 字段 | 位宽 | 含义 |
| --- | --- | --- |
| `seq` | 32 | 本端发送的包序号（以报文为粒度） |
| `ack` | 32 | 对端期望收到的下一个序号（累计确认） |
| `sack_bits` | 32 | 选择确认位图，bit *i* 表示 `ack + i + 1` 已收到 |
| `window` | 16 | 本端可用接收窗口（单位：报文个数） |
| `length` | 16 | 负载字节数 |
| `flags` | 16 | SYN / ACK / FIN / DATA / RST / SACK |
| `checksum` | 16 | 对头部 + 负载求得的 1 补码校验和 |

最大载荷 `MAX_PAYLOAD_SIZE = 1200`，保证在典型的以太网 MTU 下不会被分片。

### 2.2 握手负载

握手阶段附带结构化字段：

| 字段 | 位宽 | 含义 |
| --- | --- | --- |
| `version` | 32 | 协议版本，当前为 1 |
| `chunk_size` | 32 | 建议数据段大小（字节） |
| `window_size` | 32 | 发送方期望的窗口大小（报文） |
| `file_size` | 64 | 即将传输文件的总字节数 |

双方在三次握手过程中交换该结构体，从而对齐窗口和分段配置。

## 3. 连接管理状态机

- **握手**：
  1. 发送方随机初始化序号 `ISN_s`，发送 `SYN(ISN_s)` 并附带握手负载。
  2. 接收方收到 SYN 后生成 `ISN_r`，回复 `SYN+ACK(ISN_r, ACK=ISN_s+1)`。
  3. 发送方回 `ACK(ACK=ISN_r+1)`，进入数据发送态。
  4. 全过程带 500 ms 超时与 10 s 总时限，超时自动重传上一握手段。

- **挥手**：
  1. 发送方在全部数据确认后发送 `FIN`，并等待 `ACK`。
  2. 接收方收到 `FIN` 后，先回 `ACK`，再发送自有 `FIN` 完成半关闭。
  3. 发送方对接收方的 `FIN` 进行 `ACK`，随后释放资源。

> 若握手 / 挥手阶段超时，程序将打印错误并优雅退出，防止端口资源泄露。

## 4. 差错检测

- 头部 + 负载一并执行 16 bit 反码求和校验，接收端校验失败直接丢弃。
- 校验实现位于 `checksum.{h,cpp}`，即可复用到其他实验。

## 5. 可靠性与选择确认

- 序号按“报文”为粒度单调递增。
- 发送端维护 `std::map` 形式的**未确认报文表**，记录最近一次发送时间以及是否曾重传。
- 接收端维护乱序缓冲 `map<seq, payload>`；当 `expected_seq` 的报文到达后立即写文件，并持续向前滑动，直到出现缺口。
- 每个 ACK 报文都携带：
  - `ack`：下一个期望序号。
  - `sack_bits`：对 `ack+1` 起的 32 个报文的接收位图。
  - `window`：剩余可用缓存大小（接收窗口）。
- 发送端根据 `ack` 批量确认 `< ack` 的报文，并根据位图补充确认乱序报文，避免多余重传。

## 6. 流量控制

- CLI 参数 `window_packets` 设定发送 / 接收窗口的上限，实验时可自由调整。
- 接收端在 ACK 中广告剩余窗口，发送端取三者最小值：`min(config_window, peer_window, cwnd)`，同时满足实验“同大小固定窗口”的要求。

## 7. 拥塞控制（RENO）

`RenoCongestionControl` 负责维护 cwnd、ssthresh 以及状态（慢启动 / 拥塞避免 / 快恢复）：

- **慢启动**：每收到一个新 ACK，`cwnd += 1`，直至 `cwnd >= ssthresh`。
- **拥塞避免**：按 `cwnd += 1 / cwnd` 线性增长。
- **快速重传 / 恢复**：3 个重复 ACK 触发，`ssthresh = cwnd / 2`，`cwnd = ssthresh + 3` 并立即重传丢包段。
- **超时**：`cwnd` 退回 1，`ssthresh = cwnd / 2`，重新进入慢启动。

RTT 采用 Jacobson/Karels 平滑估计，`RttEstimator` 同时维护 `SRTT` 与 `RTTVAR`，超时阈值为 `SRTT + max(50 ms, 4*RTTVAR)`，并叠加用户可配置的基础超时。

## 8. 代码结构

```
├─ include/
│  ├─ rtp.h                // 报文格式、常量、序列化辅助
│  ├─ checksum.h           // 校验和接口
│  ├─ congestion_control.h // Reno cwnd 管理
│  └─ timer.h              // 秒表与 RTT 估计
├─ src/
│  ├─ rtp.cpp              // 序列化 / 反序列化与握手 Payload 编解码
│  ├─ checksum.cpp         // 16 bit 反码校验实现
│  ├─ congestion_control.cpp
│  ├─ timer.cpp
│  ├─ sender_main.cpp      // 发送端应用：握手、流水线、统计
│  └─ receiver_main.cpp    // 接收端应用：乱序缓存、选择确认、写文件
└─ docs/
   └─ design.md            // 本文档
```

## 9. 运行与实验建议

1. **编译**：
   ```
   cmake -S . -B build
   cmake --build build --config Release
   ```
2. **启动接收端**：
   ```
   build/Release/receiver.exe <listen_port> <output_file> <window> <packet_size> [--loss=0.05]
   ```
3. **启动发送端**：
   ```
   build/Release/sender.exe <ip> <port> <input_file> <window> <packet_size> [timeout_ms] [--loss=0.05]
   ```

通过修改 `window` 以及 `--loss` 参数，即可在同一机器上复制度量不同窗口 / 丢包率对吞吐的影响，程序会输出总耗时与平均吞吐率。实验报告可基于这些数据绘制性能曲线，并分析 RENO 与选择确认策略的效果。
