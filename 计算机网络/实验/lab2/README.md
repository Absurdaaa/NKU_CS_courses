# 实验 2：可靠传输协议 (Reliable UDP)

基于 UDP 套接字实现的用户态可靠传输协议，满足课程实验对连接管理、差错检测、流水线选择确认、固定窗口流控以及 RENO 拥塞控制的全部要求。

- ✅ 单向文件传输，控制报文双向交互
- ✅ 选择确认 + RTT 自适应超时
- ✅ 固定窗口流控 + RENO 拥塞算法
- ✅ 可配置的模拟丢包，便于性能分析
- ✅ 输出总耗时与平均吞吐率

> 详细设计、报文格式与协议状态机说明请参见 `docs/design.md`。

## 构建方法

```powershell
cmake -S . -B build
cmake --build build --config Release
```

生成的可执行文件位于 `build/Release/sender.exe` 与 `build/Release/receiver.exe`。

## 运行方式

### 接收端

```powershell
build/Release/receiver.exe <listen_port> <output_file> <window_packets> <packet_size> [--loss=0.00] [--listen-ip=IP] [--peer-ip=IP]
```

- `window_packets`：接收窗口大小（报文数）。
- `packet_size`：最大负载字节数，需与发送端保持一致。
- `--loss`：可选参数，模拟本端发送 ACK 时的丢包概率（默认 0.0，不指定时不模拟丢包）。
- `--listen-ip`：可选，绑定到本机的指定 IP（默认绑定到所有网卡 INADDR_ANY）。
- `--peer-ip`：可选，仅解析并记录对端 IP；可用于后续严格校验（当前版本解析并保存，若需强制拒绝来自其他 IP 的包可开启）。

### 发送端

```powershell
build/Release/sender.exe <receiver_ip> <receiver_port> <input_file> <window_packets> <packet_size> [timeout_ms] [--loss=0.00] [--src-ip=IP]
```

- `timeout_ms`：额外的基础超时（毫秒），叠加到 RTT 自适应 RTO 上。
- `--loss`：模拟发送方报文丢失的概率（默认 0.0，不指定时不模拟丢包）。
- `--src-ip`：可选，将发送端 socket 绑定到指定本地源 IP（用于多网卡/实验控制）。

程序会在结束时输出：

- 传输的字节总数
- 总耗时（秒）
- 平均吞吐率（Mbps）

### ⚡ 快速测试示例（本机回环 / 多网卡）

以下命令可直接在 Windows PowerShell 中验证端到端传输流程：

```powershell
# 1. 构建项目
cmake -S . -B build
cmake --build build --config Release

# 2. 在【终端 A】启动接收端（监听所有地址）
build\Release\receiver.exe 9000 received.bin 32 15000

# 3. 在【终端 B】准备输入文件并启动发送端（发送到本地回环）
build\Release\sender.exe 127.0.0.1 9000 test\1.jpg 12 15000 200

# 另：如果你的机器有多个网卡并想绑定到特定网卡：
# 在接收端绑定到 192.168.1.42（指定网卡）
build\Release\receiver.exe 9000 received.bin 32 15000 --listen-ip=192.168.1.42

# 在发送端指定源地址为 192.168.1.10（本机某个网卡地址），目标为 192.168.1.42
build\Release\sender.exe 192.168.1.42 9000 test\1.jpg 32 15000 200 --src-ip=192.168.1.10

# 4. 观察双方输出的耗时与吞吐率，并确认 received.bin 与输入文件内容一致
```

> 如需模拟丢包，可在命令末尾附加 `--loss=0.05` 等参数观察重传与吞吐变化。

## 日志与静默运行

- 默认工程启用了详细日志宏 `RTP_VERBOSE_LOG`，便于调试握手、滑动窗口与重传行为。
- 若要在构建时关闭详细日志，请在 CMake 配置时传入：

```powershell
cmake -S . -B build -DENABLE_LOGGING=OFF
cmake --build build --config Release
```

这样会在编译阶段去除大量调试输出，适合跑批次实验与性能测试。

## 性能与实验建议

1. **窗口敏感性**：固定丢包率（例如 0% / 2% / 5%），分别设置窗口 4、8、16、32……记录吞吐率并绘图。
2. **丢包敏感性**：固定窗口（例如 16），调节 `--loss` 参数或者配合 NetEm，观察吞吐率与重传次数的变化。
3. **超时调优**：通过 `timeout_ms` 放大 / 缩小超时，验证 RTO 估计对性能的影响。
4. **日志开关**：默认启用 `RTP_VERBOSE_LOG`（可在 `CMakeLists.txt` 关闭），便于调试握手、滑动窗口等详细过程。

## 目录结构

```
├─ include/      # 协议头文件
├─ src/          # 发送端、接收端及公用组件
├─ docs/         # 设计、报告文档
└─ build/        # CMake 构建产物（执行 cmake 后自动生成）
```

## 后续可拓展方向

- 支持双向数据流与半可靠控制通道
- 根据 ACK 聚集策略减少反馈报文数量
- 引入 FEC / 冗余编码提升高丢包环境下的吞吐
- 提供 Python 脚本自动跑批测试窗口 / 丢包率组合
