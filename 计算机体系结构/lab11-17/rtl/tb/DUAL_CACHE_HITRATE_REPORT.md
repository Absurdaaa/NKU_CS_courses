# dual_cache_hitrate_tb 设计说明与波形分析指南

本文档说明 `rtl/tb/dual_cache_hitrate_tb.v`（“dual TB”）的设计思路：**一个仿真同时驱动 I$ + D$**，共享同一份 backing memory，并分别统计命中率；同时给出在 Vivado 波形窗口里如何观察信号来分析行为。

---

## 1. 目标与范围

- **目标**：在不跑整机（`mycpu_top`）的前提下，快速验证：
  - I$/D$ 都能正常工作（miss→linefill→hit；D$ 的 write-allocate / write-back 能发生）
  - 并输出统计：I$ 命中率、D$ 命中率、D$ 读/写 miss 数、D$ writeback 次数
- **范围**：仅覆盖 `icache_top` / `dcache_top` / `cache.v` 的行为。uncached bypass 路径在该 TB 中**不使用**（固定走 cached）。

---

## 2. 组成模块与连接关系

dual TB 由 3 块组成：

1) `icache_top`（I$ wrapper）
- CPU 侧：`inst_sram_req/addr_ok/data_ok/rdata`
- 内存侧（burst）：`rd_req/rd_addr/rd_rdy/ret_valid/ret_last/ret_data`，以及 `wr_req/...`（一般 I$ 不会写回，但接口保留）

2) `dcache_top`（D$ wrapper）
- CPU 侧：`data_sram_req/addr_ok/data_ok/rdata`
- 内存侧（burst）：同上；D$ 会在 dirty eviction 时触发 `wr_req` 写回整行

3) 共享内存与仲裁：
- `simple_unified_mem.v`：简化 backing memory（这里仅用它的 **burst 口**）
- `simple_burst_arb2.v`：**2-master burst 仲裁器**，让 I$ 与 D$ 共用一份 burst memory 口

整体拓扑：

- I$ burst口 ┐
-          ├── `simple_burst_arb2` ── `simple_unified_mem`
- D$ burst口 ┘

---

## 3. 为什么需要 `simple_burst_arb2`

`cache.v` 的 miss/linefill 使用 burst：一次读 4 个 beat（16B line）。
如果 I$ 与 D$ 同时 miss，就会同时拉高 `rd_req`。

- 真实系统里：上游会有仲裁（例如你在 `mycpu_top.v` 里做的 I$ vs D$ burst 仲裁）。
- dual TB 里：为了模拟“集成后共享内存口”的现实情况，加入 `simple_burst_arb2`。

### 仲裁策略（实现点）

- **读 burst**：一次只允许一个 burst 在飞（通过 `rd_busy` 锁存 grant，直到 `ret_last`）。
- **选择策略**：当同时请求时 round-robin（`rr_ptr`）。
- **返回路由**：根据 `rd_grant` 把 `ret_*` 只送回被 grant 的那个 master。
- **写回**：`cache.v` 的写回接口是“1 次请求 = 写一整行 128-bit”，因此仲裁器按“单次写请求”仲裁即可。

---

## 4. 命中/缺失的统计口径（TB 如何判定 hit/miss）

本工程 `rtl/myCPU/cache.v` 是 **单 outstanding** 的 cache：

- `addr_ok=1` 仅在 `S_IDLE`（空闲）
- miss 时会在 `S_RD_REQ` 拉高 `rd_req` 并等待 `rd_rdy` 握手

因此 dual TB 采用如下等价判据：

- 对某次请求，如果在该请求等待 `*_data_ok` 的过程中，观测到对应 cache 侧发生 `rd_req && rd_rdy`（burst 读握手），则这次请求计为 **miss**。
- 否则计为 **hit**。

> 说明：这等价于 demand miss（发生了 refill）。对于当前 cache 实现足够准确、实现简单。

---

## 5. dual TB 的 workload 设计

TB 将 I$ 与 D$ 的访问 **交错进行**，模拟“取指 + 数据访问混合”的系统：

- 总操作数：`N`（默认 5000，可用 plusargs 覆盖）
- I$ 占比：`IR`（默认 70%，可用 plusargs 覆盖）
- 地址生成：使用 LFSR 产生伪随机序列；
  - I$：`0x0000_1000 + {lfsr[11:2],2'b00}`（对齐 word，形成一定局部性）
  - D$：`0x0000_2000 + {lfsr[13:2],2'b00}`
- D$ 读写混合：
  - `lfsr[0]==1` 做 load
  - `lfsr[0]==0` 做 store（写数据 `0xA000_0000 ^ i`）

最终打印：

- I$：`total/hit/miss/hitrate`
- D$：`total/hit/miss/hitrate` + `read miss/write miss` + `writeback(line)`

---

## 6. 如何跑（Vivado xsim）

仿真 sources 需要包含：

- `rtl/myCPU/cache.v`
- `rtl/myCPU/icache_top.v`
- `rtl/myCPU/dcache_top.v`
- `rtl/tb/simple_unified_mem.v`
- `rtl/tb/simple_burst_arb2.v`
- `rtl/tb/dual_cache_hitrate_tb.v`

把仿真顶层设为：`dual_cache_hitrate_tb`，Run Behavioral Simulation。

可选参数：

- `N=<int>`：总操作数
- `IR=<int>`：I$ 占比（百分数）

---

## 7. 波形分析：建议观察哪些信号

### 7.1 先看“是否发生 miss → linefill”

建议加波形：

- I$ 侧：
  - `inst_sram_req`, `inst_sram_addr_ok`, `inst_sram_data_ok`, `inst_sram_addr`
  - `i_rd_req`, `i_rd_rdy`, `i_ret_valid`, `i_ret_last`, `i_ret_data`
- D$ 侧：
  - `data_sram_req`, `data_sram_wr`, `data_sram_addr_ok`, `data_sram_data_ok`, `data_sram_addr`
  - `d_rd_req`, `d_rd_rdy`, `d_ret_valid`, `d_ret_last`, `d_ret_data`

你应该看到：

- **miss**：某次请求握手后，出现 `*_rd_req`，并看到 `*_ret_valid` 连续 4 拍，最后 `*_ret_last=1`，随后请求得到 `*_data_ok=1`。
- **hit**：请求握手后直接较快出现 `*_data_ok=1`，并且没有发生 `*_rd_req && *_rd_rdy`。

### 7.2 再看“仲裁器是否正确工作”

建议加波形（仲裁/共享口）：

- `s_rd_req`, `s_rd_addr`, `s_rd_rdy`, `s_ret_valid`, `s_ret_last`, `s_ret_data`
- `u_arb.rd_busy`, `u_arb.rd_grant`, `u_arb.rr_ptr`

你应该看到：

- `rd_busy=1` 期间，不会再出现第二个 burst 被接受；直到 `s_ret_last=1` 才释放。
- `rd_grant` 指示当前 burst 返回要送回 I$ 还是 D$。

### 7.3 D$ 的 write-back（dirty eviction）怎么在波形里体现

建议加波形：

- `d_wr_req`, `d_wr_addr`, `d_wr_data`, `d_wr_rdy`
- 共享口：`s_wr_req`, `s_wr_addr`, `s_wr_data`, `s_wr_rdy`

你应该看到：

- 当发生 dirty eviction 时，D$ 会拉高 `d_wr_req`，经过仲裁后 `s_wr_req` 拉高并写入 memory。
- TB 里统计的 `writeback(line)` 次数，就是按 `d_wr_req && d_wr_rdy` 计数。

---

## 8. 常见现象与快速定位

- `*_addr_ok` 很久不来：
  - 说明 cache 还在忙（单 outstanding），可能卡在等待返回；检查 `s_ret_valid/s_ret_last` 是否持续输出 4 拍。
- `*_data_ok` 超时：
  - 先看对应 `*_rd_req` 是否握手到了 `*_rd_rdy`
  - 再看返回是否有 4 拍且 `*_ret_last` 有出现
  - 再看仲裁器 `rd_grant` 是否把返回路由到正确 cache

---

## 9. VCD（可选）

`dual_cache_hitrate_tb.v` 支持 `+dump` 生成 `dual_cache_hitrate_tb.vcd`（适用于 Icarus/GTKWave）。
Vivado xsim 通常直接用 GUI 波形窗口即可。
