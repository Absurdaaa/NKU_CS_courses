# I$/D$ cache 单元测试与波形观察指南

本目录新增 3 个文件用于 **不跑整机** 的快速自测：

- `simple_unified_mem.v`：简化“内存”模型（同时提供 burst 口 + uncached SRAM-like 口，背后共享一份 memory）
- `icache_top_tb.v`：`icache_top` 单元测试
- `dcache_top_tb.v`：`dcache_top` 单元测试

另外新增 2 个文件用于 **统计命中率**（同样不跑整机）：

- `icache_hitrate_tb.v`：I$ cached 读访问命中率统计（以“是否触发 `rd_req` 握手”为 miss 判据）
- `dcache_hitrate_tb.v`：D$ cached 读/写命中率统计 + writeback 次数统计

如果你已经把 I$ + D$ 都集成了，希望 **一个仿真同时统计两者**，新增：

- `dual_cache_hitrate_tb.v`：同时实例化 `icache_top` + `dcache_top`，共享同一份 backing memory，分别统计 I$/D$ 命中率
- `simple_burst_arb2.v`：给 `dual_cache_hitrate_tb.v` 用的 2-master burst 仲裁器（I$ 与 D$ 共享 burst memory 口）

> 目标：用很少的激励覆盖最关键行为：**miss linefill → hit**、**uncached bypass**、以及 D$ 的 **write-allocate / write-back（dirty eviction）**。

---

## 1. 怎么跑（Vivado xsim）

1) 把下面文件加入仿真 sources（Simulation Sources）：

- `rtl/myCPU/cache.v`
- `rtl/myCPU/icache_top.v` 或 `rtl/myCPU/dcache_top.v`
- `rtl/tb/simple_unified_mem.v`
- `rtl/tb/icache_top_tb.v` 或 `rtl/tb/dcache_top_tb.v`

2) 在 **Simulation Sources** 里把顶层设为：

- 跑 I$：`icache_top_tb`
- 跑 D$：`dcache_top_tb`

如果要统计命中率，把顶层设为：

- 跑 I$ 命中率：`icache_hitrate_tb`
- 跑 D$ 命中率：`dcache_hitrate_tb`

如果要 **一个 TB 同时统计 I$ + D$**：

- 跑双 cache 命中率：`dual_cache_hitrate_tb`

3) Run Simulation → Run Behavioral Simulation

4) 看 Transcript：

- TB 会打印每次访问的地址/数据
- `simple_unified_mem` 会打印 burst 接收与 4-beat 返回，以及写回写入的 4 个 word
- 结束打印 `... PASS` 则本用例通过

命中率 TB 会在末尾打印形如：

- `total/hit/miss/hitrate`（I$）
- `read/write` 分拆统计 + `writeback(line) count`（D$）

---

## 2. 波形图应该怎么看（关键现象）

### 2.1 I$（`icache_top_tb`）

建议加到波形的信号（从 tb 层一路点进去也行）：

- CPU 侧：
  - `inst_sram_req`, `inst_cached`, `inst_sram_addr`, `inst_sram_addr_ok`
  - `inst_sram_data_ok`, `inst_sram_rdata`
- uncached 侧：
  - `uc_inst_sram_req`, `uc_inst_sram_addr_ok`, `uc_inst_sram_data_ok`, `uc_inst_sram_rdata`
- cache 内存侧（linefill）：
  - `rd_req`, `rd_addr`, `rd_rdy`
  - `ret_valid`, `ret_last`, `ret_data`

你应该能看到：

1) **第一次 cached 读（miss）**：
   - `inst_cached=1` 时，`inst_sram_req` 只要握手成功（`inst_sram_addr_ok=1` 的那个上升沿）
   - 随后出现 `rd_req`，并且 `ret_valid` 连续 4 拍，最后一拍 `ret_last=1`
   - 再过一小段，`inst_sram_data_ok=1`，`inst_sram_rdata` 给出目标 word

2) **第二次同地址 cached 读（hit）**：
   - 不再出现 `rd_req/ret_valid`（或至少明显减少外部访问）
   - `inst_sram_data_ok` 更快到来

3) **uncached 读（bypass）**：
   - `inst_cached=0` 时，`uc_inst_sram_req` 会有活动
   - 同时 **不应该** 有 `rd_req`（因为 bypass 不走 cache linefill）

4) **hold buffer 场景**：
   - TB 会刻意安排一次“bypass 返回”和“cache 返回”靠近/同周期，验证 wrapper 不会因为门控丢返回
   - 现象上：`inst_sram_data_ok` 不会卡死，仿真能走到 PASS

### 2.2 D$（`dcache_top_tb`）

建议加到波形的信号：

- CPU 侧：
  - `data_sram_req`, `data_cached`, `data_sram_wr`, `data_sram_addr_ok`
  - `data_sram_data_ok`, `data_sram_addr`, `data_sram_wstrb`, `data_sram_wdata`, `data_sram_rdata`
- cache 内存侧：
  - 读：`rd_req`, `rd_addr`, `ret_valid`, `ret_last`, `ret_data`
  - 写回：`wr_req`, `wr_addr`, `wr_data`, `wr_rdy`

你应该能看到：

1) **store miss（write-allocate）**：
   - 先出现 `rd_req` + 4-beat `ret_valid`（把整行 refill 进来）
   - 然后 `data_sram_data_ok=1`（store 完成）

2) **load hit**：
   - 对刚写过的地址读回，`data_sram_rdata` 应等于刚写的数据

3) **dirty eviction（write-back）**：
   - TB 连续写 A、B、C 三个不同 tag 但同 index 的地址
   - 第三次写（C）会触发替换：你应该能看到 `wr_req=1`（把被替换的 dirty line 写回）
   - 随后再读回 B，读出的值仍应是 `0x11111111`（证明写回生效）

---

## 3. 常见问题定位

- `addr_ok` 一直不来：通常是 cache 侧还没回到 `S_IDLE`（上一笔没完成）或你的激励在同一周期脉冲太短。TB 里是“拉高 req 直到 addr_ok”为了避免这个问题。
- `data_ok` 超时：重点看
  - `rd_req/rd_rdy` 是否握手
  - `ret_valid/ret_last` 是否真的回了 4 拍
  - 是否有 `rready/bready` 相关死锁（整机里在 `transfer_bridge.v` 已做 `CACHE_ID` 强制 ready）

---

## 4. 可选：VCD/GTKWave（如果你用 Icarus Verilog）

TB 支持 `+dump` 参数打开 VCD：

- `icache_top_tb.vcd`
- `dcache_top_tb.vcd`

如果你用的是 Vivado xsim，通常直接看默认的波形窗口即可，不需要 VCD。

---

## 5. 命中率统计 TB 的可调参数

你可以用仿真参数（plusargs）控制访问次数（Vivado xsim 可在 Simulation Settings 里加 xsim.elab/xsim.sim 的参数；Icarus 则是运行 vvp 时带参数）。

- `icache_hitrate_tb.v`
   - `NSEQ=<int>`：顺序热区访问次数（默认 512）
   - `NRAND=<int>`：随机冷区访问次数（默认 2048）

- `dcache_hitrate_tb.v`
   - `N=<int>`：总访问次数（默认 4096，内部会混合读写/冷热区）

> 统计口径说明：本工程 `cache.v` 单 outstanding，因此“某次请求是否触发了对内存的 `rd_req && rd_rdy` 握手”可以作为 demand miss 的等价判据。
