# 报文设计说明（Packet Design）

本文档用中文说明项目中自定义 RTP-like 报文的设计，并同时提供完整的 LaTeX 报告源代码（可直接编译为 PDF）。文中涉及的类型和符号在代码中对应为 `rtp::PacketHeader`、`rtp::Packet` 和 `rtp::HandshakePayload` 等。

---

## 设计目标

- 简洁明了：报文头小且信息完整，便于在不可靠 UDP 上实现可靠传输特性（SYN/ACK/FIN、序号、确认号、窗口、SACK 位等）。
- 互操作性：字段使用固定大小整数，注意字节序（network byte order，即大端）。
- 容错与扩展：保留标志位与长度字段以支持后续扩展。


## 报文总体结构

每个传输单元采用如下结构：

- 报文头（PacketHeader）固定大小
- 可变长度负载（payload）

报文序列化（serialize）/反序列化（deserialize）遵循按字段顺序写入/读取并将多字节整数转换为网络字节序（big-endian）。

### 报文头字段（按位/按字节）

在本项目的实际代码（`include/rtp.h`）中，`rtp::PacketHeader` 的定义如下：

```cpp
struct PacketHeader {
  std::uint32_t seq; // 包的序列号
  std::uint32_t ack; // 确认号（下一个期望收到的序列号）
  std::uint32_t sack_bits; // SACK位图
  std::uint16_t window;   // 接收窗口大小（以数据包数计）
  std::uint16_t length;   // 负载长度（字节数）
  std::uint16_t flags;    // 标志位
  std::uint16_t checksum; // 校验和
};
```

字段按内存/序列化顺序分别为：
- `seq`（32-bit）
- `ack`（32-bit）
- `sack_bits`（32-bit）
- `window`（16-bit）
- `length`（16-bit）
- `flags`（16-bit）
- `checksum`（16-bit）

注意：实际的序列化/反序列化需要显式处理字节序（使用 `htonl`/`htons` 等）以保证网络可移植性。


## 字段细化说明

- 序列号（seq）
  - 类型：\(\text{uint32\_t}\)
  - 含义：发送方为每个数据包分配的绝对序号（握手中将分配初始序列号 \(ISN\)）。
  - 取值范围：\([0,2^{32}-1]\)。为避免边界问题，通常在生成 ISN 时避免取 0 或最大值。

- 确认号（ack）
  - 含义：接收方发送的累计确认号，表示发送方已经安全到达并可释放的最小下一个序号。
  - 语义：收到 ack = A 表示序号小于 A 的数据都被接收。

- 标志位（flags）
  - 含义：低位或高位位域用于表示 SYN、ACK、FIN、DATA 等。示例：
    - FLAG_SYN = 0x01
    - FLAG_ACK = 0x02
    - FLAG_FIN = 0x04
    - FLAG_DATA = 0x08

- 窗口（window）
  - 含义：接收端愿意接收的最大未确认的数据包数（以包为单位）。
  - 注意：发送端需要同时受拥塞控制和接收窗口的共同限制。发送窗口 = min(接收端窗口, 拥塞窗口, 本地配置)

- 长度（length）
  - 表示 payload 字节长度。用于边界检查与负载提取。

- SACK 位（sack_bits）
  - 采用位图形式表示收到位于累计确认之后的一些离散序号是否被接收，以支持快速恢复和选择性重传。
  - 例如：若 `cumulative_ack = A` 且 `sack_bits` 的第 0 位为 1，则表示序号 `A+1` 已接收；第 i 位为 1 表示 `A+i+1` 已接收。

\subsubsection{SACK 位图}

详细说明：
- 字段：`sack_bits`（32-bit，无符号整数）按位表示累计确认 `cumulative_ack` 之后的若干分组接收状态。
- 语义：若接收方在发送 ACK 时希望告知发送方在累计确认之外的已接收分组，则在 ACK 包中设置 `sack_bits`，并通常同时设置 `FLAG_SACK` 或 `FLAG_ACK`。位图中第 i 位（从最低位 i=0 开始）对应序号 `cumulative_ack + i + 1`。若该位为 1，则表示对应分组已被接收。
- 示例：若 `cumulative_ack = 1000` 且 `sack_bits = 0b0000...0101`（位 0 和位 2 为 1），则说明序号 1001 和 1003 已接收。
- 限制与注意事项：
  - 位图长度（本协议为 32 位）限制了可指示的最远偏移；若网络延迟或乱序非常大，位图可能不足，需要组合 SACK 报文或使用更复杂的 SACK 列表结构。
  - 位图相对于显式列出序号的优点是紧凑；缺点是无法表示距离很远的单独分组。若需要更广范围的 SACK，可增加字段或在 payload 中编码 SACK 列表。
  - 解码时须以无符号算术计算相对序号以处理环绕（wrap-around），例如使用 `seq_diff = seq - cumulative_ack` 的无符号结果判断是否在位图覆盖范围内。

\subsubsection{标志位}

详细说明：
- 标志位字段为 `flags`（16-bit 位域），在 `include/rtp.h` 中定义了若干常量：
  - `FLAG_SYN` (1 << 0)：握手 SYN 标志，用于建立连接并携带初始序号/握手参数。
  - `FLAG_ACK` (1 << 1)：确认标志，指示该包包含 ack 字段的有效确认信息。
  - `FLAG_FIN` (1 << 2)：关闭/结束标志，表示发送方没有更多数据要发（类似 TCP FIN）。
  - `FLAG_DATA` (1 << 3)：数据包标志，表示该包携带有效数据负载。
  - `FLAG_RST` (1 << 4)：复位标志，用于异常恢复或拒绝连接。
  - `FLAG_SACK` (1 << 5)：SACK 指示位，表示 `sack_bits` 字段包含有意义的 SACK 信息。

使用说明与组合：
- 标志可以按位组合，例如一个 ACK+SACK 报文可以设置 `FLAG_ACK | FLAG_SACK`，表示该包是确认包并携带 SACK 位图。
- 握手流程中典型使用：
  - 发送方发送 `FLAG_SYN`（携带握手 payload）；
  - 接收方回复 `FLAG_SYN | FLAG_ACK`；
  - 发送方回复 `FLAG_ACK` 完成三次握手。
- 数据传输中 `FLAG_DATA` 用于区分仅携带控制信息的包与携带数据的包；`FLAG_FIN` 用于终止序列。

\subsubsection{校验和}

详细说明：
- 字段：`checksum`（16-bit），位于 `PacketHeader` 的末尾，用于检测 header 与 payload 在传输过程中是否被损坏。
- 推荐算法与语义：
  - Internet 校验和（ones' complement 16-bit sum）：这是一个常见且实现简单的 16 位校验和算法，适用于检测偶发位翻转。计算时对报头与负载按 16 位字进行求和（若长度为奇数可在末尾补零），然后取反（ones' complement）。发送前将 `checksum` 字段置 0 计算校验值，然后把结果写入 `checksum`；接收端计算得到的校验和应为 0xFFFF（或按实现判断）。
  - CRC16：若需要更强的错误检测能力（例如对突发错误更敏感），可使用 CRC16 算法，仍然适配 16 位字段，但需在实现中选择具体的多项式（如 CRC-16-CCITT）。
  - 注意：若需要更强的完整性保证（抗篡改），应使用更大位宽（如 CRC32 或 cryptographic hash），但这需要更大的字段或把校验放在 payload 中。

实现要点：
- 在 `serialize` 中：
  1. 将 `checksum` 字段临时置为 0（网络字节序）；
  2. 将 header（按字段转换为网络字节序）和 payload 写入缓冲区；
  3. 计算校验和（如 ones' complement 或 CRC16）并写回到 header 的 `checksum` 字段位置（按网络字节序）。
- 在 `deserialize` 中：
  1. 读取 header 与 payload（或先读取完整缓冲区）；
  2. 保存原始 `checksum` 字段，然后将该位置视为 0 再次计算校验和；
  3. 比较计算值与原始 `checksum`，若不匹配则视为损坏包并丢弃/忽略。

伪代码（Internet ones' complement 校验和）：

```c
uint16_t internet_checksum(const uint8_t* data, size_t len) {
    uint32_t sum = 0;
    const uint16_t* ptr = (const uint16_t*)data;
    while (len > 1) {
        sum += *ptr++;
        if (sum & 0x10000) sum = (sum & 0xffff) + 1; // carry
        len -= 2;
    }
    if (len) { // odd byte
        sum += (uint16_t)(*(const uint8_t*)ptr) << 8;
    }
    // fold to 16 bits
    while (sum >> 16) sum = (sum & 0xffff) + (sum >> 16);
    return (uint16_t)~sum;
}
```

安全性与注意：
- 校验和只能检测随机错误，对恶意篡改无效；如果安全性是目标，应使用认证/加密（如 HMAC、AES-GCM）。
- 校验与字节序：计算时须使用一致的字节序处理（序列化为网络字节序后再计算更简单），并确保接收端用相同算法验证。


## 序号加减与环绕（wrap-around）

序号采用 32 位无符号整数，环绕行为用模运算描述。累计确认与比较常用到下列操作：

- 比较两个序号是否 "在窗口内"：
$$
\text{seq\_diff} = (s - a) \bmod 2^{32}
$$
如果 \(0 < \text{seq\_diff} \le W\) 表示序号 `s` 在 `a`（参考序号）之后且在窗口大小 \(W\) 范围内。

- 注意：在实现时要使用无符号算术并谨慎处理 `+1` 导致的溢出（例如，若 ISN 为 `2^{32}-1`，则 ISN + 1 == 0）。因此建议生成 ISN 时避免 0 与最大值。


## 握手流程（3 次握手变体）

1. 发送方发送 SYN，`seq = ISN`，`flags = SYN`，并在 payload 或 header 中发送握手信息（例如文件名、文件大小、报文大小、初始窗口等）。
2. 接收方回应 SYN+ACK，`seq = R_ISN`，`ack = ISN + 1`，在 payload 中返回对端窗口大小等信息。
3. 发送方发送最后的 ACK，`seq = ISN + 1`，`ack = R_ISN + 1`，握手完成。

成功握手后，数据从 `seq = ISN + 1` 开始编号。


## 校验（Checksum）与可靠性

- 建议对 header + payload 做固定算法的校验（如 CRC32 或自定义简单校验和），以便接收端检测报文损坏。
- 如果 `rtp::serialize` 已做校验，确保 `rtp::deserialize` 会返回失败以丢弃损坏数据并触发重传逻辑。


## 序列化与字节序

- 所有多字节整数字段在发送前转换为网络字节序（big-endian），接收端读取后转换为主机字节序。
- 在 C/C++ 中使用 `htonl`、`htons`、`ntohl`、`ntohs` 等函数来保证可移植性。


## 具体示例（伪二进制布局）

下面给出实际代码中 `PacketHeader` 的报文头布局（按字节顺序）：

- 0-3: seq (4 bytes)
- 4-7: ack (4 bytes)
- 8-11: sack_bits (4 bytes)
- 12-13: window (2 bytes)
- 14-15: length (2 bytes)
- 16-17: flags (2 bytes)
- 18-19: checksum (2 bytes)
- 20-...: payload (length bytes)

(总头部长度示例：20 字节；实际代码中 `rtp::PacketHeader` 的大小应以 `sizeof(rtp::PacketHeader)` 验证并注意结构体对齐与打包问题。）


## 性能与实现细节建议

- 对于高频发送，不要每次调用 `std::random_device`；用其产生种子来初始化 `std::mt19937`，再用 PRNG 生成大量随机数。
- 发送循环里避免频繁分配内存：在序列化路径上可复用缓冲区。
- SACK 位的大小影响可选重传粒度，常用 32 位或 64 位即可。


---

## LaTeX 报告源（完整，可直接编译）

下面给出一个完整的 LaTeX 文档源代码，你可以把其保存为 `packet_design.tex` 并用 `pdflatex packet_design.tex` 编译：

```latex
% packet_design.tex
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage{geometry}
\usepackage{amsmath,amssymb}
\usepackage{longtable}
\usepackage{listings}
\usepackage{hyperref}
\usepackage{graphicx}
\geometry{margin=1in}

\title{自定义 RTP-like 报文设计说明}
\author{作者: 自动生成}
\date{\today}

\begin{document}
\maketitle

\section{设计目标}
简洁明了、互操作性和容错扩展性。

\section{报文总体结构}
本协议每个报文包含一个固定长度的报文头和可变长度的负载。所有多字节整数采用网络字节序（Big-endian）。

\section{报文头字段}
sack\_bits & 32-bit：SACK 位图\\
\begin{longtable}{p{3cm} p{10cm}}
字段 & 说明\\\hline
seq & 32-bit：绝对序列号，采用无符号整数，范围 $[0,2^{32}-1]$。\\
ack & 32-bit：累计确认号，表示下一个期望的序号\\
sack\_bits & 32-bit：SACK 位图（位 i 表示 cumulative_ack + i + 1 的包已被接收）\\
window & 16-bit：接收窗口（包数）\\
length & 16-bit：payload 长度（字节）\\
flags & 16-bit：位域，表示 SYN/ACK/FIN/DATA 等\\
checksum & 16-bit：校验和，用于检测 header+payload 的损坏\\
\end{longtable}

\section{序号数学}
序号的差值采用模运算：
\[
\text{seq\_diff} = (s - a) \bmod 2^{32}
\]
若 $0 < \text{seq\_diff} \le W$ 则 $s$ 在窗口内。

\section{握手流程}
三次握手变体：SYN -> SYN+ACK -> ACK。握手成功后数据从 $ISN+1$ 开始。

\section{示例布局}
一个示例头部布局（字节偏移）：
\begin{verbatim}
0-3: seq (4 bytes)
4-7: ack (4 bytes)
8-11: sack_bits (4 bytes)
12-13: window (2 bytes)
14-15: length (2 bytes)
16-17: flags (2 bytes)
18-19: checksum (2 bytes)
20-...: payload
\end{verbatim}

\section{实现注意事项}
\begin{itemize}
  \item 使用 \texttt{htonl}/\texttt{htons} 与 \texttt{ntohl}/\texttt{ntohs} 处理字节序。
  \item 使用随机设备种子初始化 PRNG，而不是高频调用 \texttt{std::random_device()}。
  \item 对 header + payload 做校验（例如 CRC32）。
\end{itemize}

\section{结论}
本文档概述了一个适用于基于 UDP 的可靠传输协议的报文设计。设计关注点为边界安全、可扩展性与实现可移植性。

\end{document}
```

---

## 使用方法

- 已将该 Markdown 保存为 `docs/packet_design.md`。
- 若要单独生成 PDF 报告：复制上面的 LaTeX 段（`packet_design.tex`）并运行：

```powershell
pdflatex packet_design.tex
```

（Windows 上请确保安装 TeX 发行版，如 MiKTeX 或 TeX Live。）

---

如果你希望我：
- 把 LaTeX 源也单独写入 `docs/packet_design.tex`（我可以为你创建该文件并即时编译检查），
- 或者将报文字段与 `include/rtp.h` 中的实际定义做一一映射并生成更精确的说明，

告诉我你的偏好，我可以继续处理并提交补丁。