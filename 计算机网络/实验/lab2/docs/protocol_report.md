# 协议设计与实现详解（基于工程代码）

本文档以你工程中的代码为准（目录：`include/rtp.h`、`src/rtp.cpp`、`src/sender_main.cpp`、`src/receiver_main.cpp`），对自定义的 RTP-like 协议做全面详尽的说明，包含：报文格式、字段语义、序列化/校验、三次握手、数据传输流程、拥塞与重传机制、SACK 支持、关闭流程、以及关键伪代码/代码片段帮助理解实现细节。

文件：`docs/protocol_report.md`

---

## 目录

- 协议目标与设计原则
- 报文格式（PacketHeader / Packet）
- 序列化、字节序与校验（Checksum）
- 握手流程（Connection Establishment）
- 数据传输流程（Sender / Receiver 主循环）
- 窗口与拥塞控制（交互说明）
- 重传策略（超时与快速重传）
- SACK（选择确认）机制与实现
- 连接关闭（FIN）流程
- 关键伪代码（Sender / Receiver / Serialize / Deserialize）
- 常见问题与实现注意事项

---

## 协议目标与设计原则

该协议基于 UDP，实现可靠、有序的文件传输。设计要点：

- 保持报文头紧凑并包含必要控制信息（seq/ack/flags/window/sack_bits/checksum）。
- 使用三次握手建立会话，交换文件大小、分块大小与窗口大小等元信息。
- 每个数据包带有序号与长度，接收端维护重排序缓冲区以处理乱序。
- 提供累计确认（cumulative ACK）+ SACK 位图来支持选择性重传，提高恢复速度。
- 使用 16-bit 校验和保护 header+payload 完整性。
- 发送端受两种窗口约束：接收方通告窗口（header.window）与拥塞控制窗口（Reno 实现）。

---

## 报文格式（PacketHeader / Packet）

`include/rtp.h` 中定义：

```cpp
struct PacketHeader {
    std::uint32_t seq; // 包的序列号
    std::uint32_t ack; // 确认号（下一个期望收到的序列号）
    std::uint32_t sack_bits; // SACK位图（32 bit）
    std::uint16_t window;   // 接收窗口大小（以数据包数计）
    std::uint16_t length;   // 负载长度（字节数）
    std::uint16_t flags;    // 标志位
    std::uint16_t checksum; // 校验和
};

struct Packet {
    PacketHeader header;
    std::vector<std::uint8_t> payload;
};
```

- 字节序化顺序（网络上实际发送的字节偏移）：
  - 0-3: seq (4 bytes)
  - 4-7: ack (4 bytes)
  - 8-11: sack_bits (4 bytes)
  - 12-13: window (2 bytes)
  - 14-15: length (2 bytes)
  - 16-17: flags (2 bytes)
  - 18-19: checksum (2 bytes)
  - 20-...: payload (length bytes)

- flags 定义（`rtp.h`）：
  - FLAG_SYN, FLAG_ACK, FLAG_FIN, FLAG_DATA, FLAG_RST, FLAG_SACK

- sack_bits：32 位位图，第 i 位表示从 `cumulative_ack + 1` 起偏移 `i` 的包是否已接收。

---

## 序列化、字节序与校验（Checksum）

序列化实现位于 `src/rtp.cpp`：核心思想：

- 在发送前把 header 字段转为网络字节序（to_network），并先把 `checksum` 置 0。
- 将 header（网络序）和 payload 写入缓冲区。
- 计算 buffer 的 checksum（工程使用 `compute_checksum`，在 `checksum.h`/`checksum.cpp` 中实现），并写回 header 的 checksum 字段（网络序）。
- 反序列化时先检查长度、验证 checksum（verify_checksum），再把 header 转换为主机字节序。

代码摘录（简化）：

```cpp
PacketHeader to_network(PacketHeader header) { /* htonl/htons for fields */ }

std::vector<uint8_t> serialize(const Packet& packet) {
    PacketHeader net = to_network(packet.header);
    net.checksum = 0;
    std::vector<uint8_t> buf(HEADER_SIZE + packet.header.length);
    memcpy(buf.data(), &net, HEADER_SIZE);
    memcpy(buf.data() + HEADER_SIZE, packet.payload.data(), packet.header.length);
    uint16_t c = compute_checksum(buf.data(), buf.size());
    reinterpret_cast<PacketHeader*>(buf.data())->checksum = htons(c);
    return buf;
}

bool deserialize(const uint8_t* buf, size_t len, Packet& out) {
    if (len < HEADER_SIZE) return false;
    if (!verify_checksum(buf, len)) return false;
    PacketHeader h; memcpy(&h, buf, HEADER_SIZE);
    h = to_host(h);
    if (len < HEADER_SIZE + h.length) return false;
    out.header = h;
    out.payload.assign(buf + HEADER_SIZE, buf + HEADER_SIZE + h.length);
    return true;
}
```

注意事项：不要直接把 struct 原始内存写到网络（可能有 padding），要按字段序列化并转换字节序。

---

## 握手流程（Connection Establishment）

实现采用类似 TCP 的三次握手变体，用以交换文件元数据（文件名、文件大小、chunk_size、window 等）和初始序号（ISN）。

流程：

1. 发送方构造 SYN 包（FLAG_SYN），`header.seq = sender_isn`，`payload = encode_handshake(HandshakePayload)`，并设置 `header.length` 为握手 payload 长度。发送方反复发送 SYN 直到收到 SYN+ACK 或超时退出。
2. 接收方收到 SYN，解析 handshake payload（decode_handshake），生成自己的 ISN（receiver_isn），构造 SYN+ACK：`flags = FLAG_SYN | FLAG_ACK`，`ack = sender_isn + 1`，payload 置为其 handshake payload（比如支持的 chunk_size、window_size）。
3. 发送方收到 SYN+ACK 且确认号正确后，发送最后一个 ACK：`flags = FLAG_ACK`，`seq = sender_isn + 1`，`ack = receiver_isn + 1`，握手完成。

握手实现要点：
- 使用 10 秒握手超时阈值（sender 和 receiver 均有超时逻辑）。
- 握手 payload 以 `HandshakePayload` 编码，包含文件名（以 uint16_t length + bytes 形式追加），以便接收端恢复文件名。

代码要点（摘自 `sender_main.cpp` 与 `receiver_main.cpp`）：

```cpp
// Sender side
rtp::HandshakePayload payload{PROTOCOL_VERSION, packet_size, window_packets, file_size};
payload.filename = filename;
Packet syn; syn.header.seq = isn; syn.header.flags = FLAG_SYN;
syn.payload = encode_handshake(payload); syn.header.length = syn.payload.size();
// send and wait for SYN+ACK

// Receiver side
on receive SYN:
  decode_handshake(packet.payload, sender_payload);
  receiver_isn = random();
  Packet syn_ack; syn_ack.header.seq = receiver_isn; syn_ack.header.ack = sender_isn + 1;
  syn_ack.header.flags = FLAG_SYN | FLAG_ACK; syn_ack.payload = encode_handshake(response);
```

---

## 数据传输流程（Sender 主循环）

发送端主要循环（高层描述）：

- 将文件分块为 `chunks`（大小 = negotiated chunk_size），每个块对应一个数据包序号，从 `data_seq_start = sender_isn + 1` 开始。
- 维护 `inflight`（map<seq, PacketState>）记录当前未确认包以及上次发送时间、是否已重传等信息。
- 在循环中：
  - 计算允许发送窗口：`window = min(config.window_packets, peer_window, congestion_window)`（congestion.window 和 receiver_window 的取整）。
  - 在窗口内尽可能发送新数据包：构造 packet(header.seq = next_seq, flags = FLAG_DATA, payload = chunk)，调用 send_packet；记录发送时间到 inflight。
  - 接收 ACK（短超时，50ms），处理 ack：
    - 若 `cumulative_ack > last_ack`：把小于 cumulative_ack 的 inflight 标记为 acked，更新 RTT（如果非重传），删除确认的 inflight 条目，更新 last_ack，调用 congestion.on_new_ack() 与 on_recovery_ack()。
    - 若 `cumulative_ack == last_ack`：这是 duplicate ack，调用 congestion.on_duplicate_ack()。
    - 处理 `sack_bits`：如果 ack 包带 sack_bits，按位标记对应 inflight seq 为已确认并删除。
  - 如果 congestion.should_trigger_fast_retransmit() 且 inflight 包含 `cumulative_ack`，对该包进行快速重传（标记 retransmitted 并立刻 send_packet）。
  - 对每个未 ack 的 inflight 包，若 `now - last_sent >= rto` 则标记为超时重传，发送并调用 congestion.on_timeout()。
  - 当所有数据发送并且 fin 发送且被 ack，则退出。

关键数据结构（简化）：

```cpp
struct PacketState { Packet packet; time_point last_sent; bool acked; bool retransmitted; };
std::map<uint32_t, PacketState> inflight;
uint32_t next_seq = data_seq_start;
uint32_t last_ack = data_seq_start;

// send loop
while (!fin_acked) {
  while (next_seq < fin_seq && inflight.size() < window) {
    send data packet seq=next_seq; inflight[next_seq] = state; ++next_seq;
  }
  // receive ack, process SACK, duplicate acks, fast retransmit
  // check timers and RTO retransmit
}
```

注意：发送端使用 `RttEstimator` 来计算动态 RTO（并加上 base_timeout）。当没有 RTT 样本时使用 base_timeout。

---

## Receiver 主循环（接收侧）

接收端主要职责：

- 握手并获取 `sender_isn`、期望的 `file_size`、chunk_size 与 window。
- 使用 `expected_seq = sender_isn + 1` 表示下一个期望序号。
- 对接收到的 `FLAG_DATA`：
  - 如果 `seq < expected_seq`：重复包（忽略数据主体）；
  - 如果 `seq >= expected_seq + window_packets`：超出窗口，丢弃；
  - 否则把 payload 放到 `reorder_buffer[seq]`，若 `seq == expected_seq` 则 flush 连续数据写入磁盘并推进 expected_seq（`flush_contiguous()`）。
- 每次接收数据包后发送 ACK：
  - 构造 ACK 包：`ack.header.ack = expected_seq`（这是累计确认），设置 `FLAG_ACK | FLAG_SACK`，并计算 `sack_bits = build_sack_bits(expected_seq, reorder_buffer)`。
- 处理 FIN：接收 FIN 后更新 expected_seq = max(expected_seq, fin_seq+1)，回复 ACK，并发送自己的 FIN/ACK 以完成关闭。

关键函数（`receiver_main.cpp`）：

```cpp
uint32_t build_sack_bits(uint32_t base_seq, const map<uint32_t, vector<uint8_t>>& buffer) {
  uint32_t bits = 0;
  for (uint32_t i = 0; i < MAX_SACK_BITS; ++i) {
    if (buffer.find(base_seq + i + 1) != buffer.end()) bits |= (1u << i);
  }
  return bits;
}
```

ACK 示例（伪代码）：

```cpp
ack.header.seq = receiver_isn + 1;
ack.header.ack = expected_seq; // 累计确认
ack.header.flags = FLAG_ACK | FLAG_SACK;
ack.header.window = clamp_window(free_window);
ack.header.sack_bits = build_sack_bits(expected_seq, reorder_buffer);
ack.header.length = 0;
send_packet(sock, peer, ack);
```

---

## 窗口与拥塞控制

- 应用层窗口：`header.window`（16-bit）由接收方通告，单位为包数。
- 拥塞控制：代码中使用 `RenoCongestionControl congestion;`（实现文件 `congestion_control.h/.cpp`），提供 `window_packets()`（拥塞窗口大小）以及 `on_new_ack()`、`on_duplicate_ack()`、`on_timeout()`、`should_trigger_fast_retransmit()`、`clear_fast_retransmit_flag()` 等接口。
- 发送端计算实际允许窗口为：

```cpp
uint32_t allowed_window(const SenderConfig& cfg, double congestion_window, uint32_t peer_window) {
  uint32_t cc_window = max(1, (uint32_t)std::max(1.0, congestion_window));
  return max(1u, min({cfg.window_packets, peer_window, cc_window}));
}
```

---

## 重传策略（超时与快速重传）

1. 超时重传（RTO）
   - 发送端使用 `RttEstimator` 更新 RTT，并计算 `rto = rtt_estimator.current_rto() + base_timeout`。
   - 每个 inflight 包保存 `last_sent`。若 `now - last_sent >= rto`，则触发超时重传：设置 `retransmitted=true`、更新 `last_sent=now`、发送包，最后调用 `congestion.on_timeout()`。

2. 快速重传（Fast Retransmit）
   - 当接收到重复 ACK（`cumulative_ack == last_ack`）多次时，拥塞控制可能会设立快速重传触发条件（`should_trigger_fast_retransmit()`）。
   - 发送端在检测到该标志时会对 `inflight[cumulative_ack]` 执行快速重传（发送同序号包），并清除快速重传标志。该逻辑依赖于接收端发送 duplicate ACK 来指示丢包。

注：快速重传的触发逻辑写在 `RenoCongestionControl` 中；发送端只执行重传动作。

---

## SACK（选择确认）机制

- 接收端会在 ACK 报文中通过 `sack_bits`（配合 `FLAG_SACK`）告知发送端哪一些在累计确认之后的分组已经接收。
- 发送端在处理 ACK 时：
  - 若 `ack_packet.header.sack_bits` 非零，遍历每一位（最多 32 位），对 `seq = cumulative_ack + i + 1` 做 `mark_acked(seq)`；随后删除 inflight 中已 ack 的条目。
- 重要：SACK 位图的偏移从 `cumulative_ack + 1` 开始，这里和实现 `build_sack_bits` 的行为一致。

优点：在丢包环境下，SACK 能减少不必要的重传，提高恢复速度。

实现片段（发送端处理）摘录：

```cpp
if (ack_packet.header.sack_bits) {
  for (uint32_t i = 0; i < rtp::MAX_SACK_BITS; ++i) {
    if (ack_packet.header.sack_bits & (1u << i)) {
      uint32_t seq = cumulative_ack + i + 1;
      mark_acked(seq);
    }
  }
  // 删除 inflight 中已 ack 的条目
}
```

---

## 连接关闭（FIN）流程

- 当发送端发送完所有数据并且 inflight 为空时，发送一个 FIN（`flags = FLAG_FIN | FLAG_ACK`，`seq = fin_seq`），并等待对方对 FIN 的累计确认（`ack > fin_seq`）。
- 接收端在收到 FIN 后会发送 ACK（确认累计 ack），并随后发送自己的 FIN（带 ACK）。发送端等待接收方最终的 ACK 后关闭套接字。
- 关闭流程在代码中通过多次交换 FIN/ACK 并等待超时/确认来完成（类似简化的 TCP 四次挥手）。

---

## 关键伪代码（整合）

Sender（简化伪代码）：

```
init socket, handshake -> sender_isn, receiver_isn
chunks = load_chunks(file, chunk_size)
next_seq = sender_isn + 1
last_ack = next_seq
while not fin_acked:
  window = allowed_window(cfg, congestion.window_packets(), receiver_window)
  while next_seq < fin_seq and inflight.size() < window:
    build DATA packet for seq=next_seq; send; inflight[next_seq] = {packet, now, false, false}; ++next_seq
  if next_seq >= fin_seq and inflight.empty():
    send FIN packet; fin_sent = true
  if receive ACK within 50ms:
    if ack_packet.flags has ACK:
      process cumulative ack (mark acked, remove inflight entries, update last_ack, update congestion)
      process sack_bits: mark corresponding seq as acked
      if congestion.should_trigger_fast_retransmit() and inflight contains cumulative_ack:
         retransmit inflight[cumulative_ack]
      if fin_sent and cumulative_ack > fin_seq: fin_acked = true
  // timeout based retransmit
  for each inflight entry if now - last_sent >= rto:
    retransmit; timeout_triggered = true
  if timeout_triggered: congestion.on_timeout()
```

Receiver（简化伪代码）：

```
wait for SYN
decode handshake, respond SYN+ACK
wait for final ACK
expected_seq = sender_isn + 1
while not fin_received:
  receive packet
  if packet.flags & DATA:
    if seq < expected_seq: duplicate
    else if seq >= expected_seq + window: drop
    else: reorder_buffer[seq] = payload; if seq == expected_seq -> flush_contiguous()
    // send ACK+SACK
    build ack with ack = expected_seq, sack_bits = build_sack_bits(expected_seq, reorder_buffer)
    send ack
  if packet.flags & FIN:
    fin_received = true; expected_seq = max(expected_seq, packet.seq + 1)
    send ack; send fin; break
```

---

## 常见问题与实现注意事项

- 字节序：在 serialize/deserialize 中确保所有多字节整数字段都做 hton/ntoh，否则跨主机不可移植。
- 结构对齐（padding）：不要直接把 `PacketHeader` 的内存块写入网络（可能含 padding），本实现通过 memcpy & to_network 进行字段级转换。
- ISN 选择：不要选取 0 或 UINT32_MAX，建议用 random_device seed mt19937 生成并避免边界值。
- header.length 与 payload.size() 要一致，尤其是 handshake length 的设置处要确认使用的是 payload.size() 而非 sizeof(struct)（代码中有注释提醒此事）。
- SACK 位图范围有限（32），如需更大覆盖请使用 payload 中的 SACK 列表格式。
- 校验和算法：当前实现用 16-bit 校验和，能检测多数传输错误，但不能防篡改；若需要安全性，应使用 HMAC/加密。

---

## 将来可改进点（建议）

- 将 header.length 的来源统一为 `packet.payload.size()`；避免 `sizeof(HandshakePayload)` 与实际编码长度不一致的问题。
- 支持更灵活的 SACK 表示（例如以可变长度列表编码），以便处理极端乱序场景。
- 增加日志/调试开关以便在仿真/测试时观察序列/确认/重传行为。
- 增强握手安全性或协议版本协商逻辑（例如校验版本，拒绝不兼容参数）。

---

## 结语

本文档基于你仓库中现有实现（`include/rtp.h`, `src/rtp.cpp`, `src/sender_main.cpp`, `src/receiver_main.cpp`）把协议设计、关键实现流程与注意事项做了详尽说明，并给出伪代码帮助理解。若你希望我将其中某些伪代码直接替换为可编译的 C++ 函数（自动补丁），例如：(1) 把 handshake 长度设置改为 payload.size() 的安全修复；(2) 把 checksum 计算抽成公共 helper 并单元测试；(3) 将送达日志增加可配置的 RTP_VERBOSE_LOG 输出——我可以继续在仓库中实现并提交补丁。请告诉我你要我继续做哪一项或提出需要补充的地方。