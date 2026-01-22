# TLB/CP0 集成说明（lab4-2）

本工程当前的 CPU 是经典 5 级流水（pre-IF/IF/ID/EXE/MEM/WB），CP0 在 `WB_stage.v` 内部实例化；`myCPU/tlb.v` 已在 `mycpu_core.v` 中接入（取指 s0 / 访存&TLBP s1 / TLBR 读口 / TLBWI 写口）。

本次实验要做的三件事：

1. **把 TLB 模块集成进 CPU**：取指与访存使用虚拟地址，经过“直映段/查 TLB”得到发往 AXI 的物理地址。
2. **新增指令**：`TLBP`、`TLBWI`、`TLBR`。
3. **新增 CP0 寄存器**：`Index`、`EntryHi`、`EntryLo0`、`EntryLo1`（并支持 `mfc0/mtc0` 读写）。

---

## 1. CP0 寄存器编码（与本工程一致）

`ID_stage.v` 中对 CP0 地址的编码是：

- `cp0_addr = {rd(15:11), sel(2:0)}`（共 8 bit）

因此常用寄存器地址如下（sel=0）：

- `Index`    ：`rd=0`  → `8'h00`
- `EntryLo0` ：`rd=2`  → `8'h10`
- `EntryLo1` ：`rd=3`  → `8'h18`
- `EntryHi`  ：`rd=10` → `8'h50`

字段（本实验只用到这些）：

- `Index`：`P` 位（未命中置 1）、`Index[3:0]`（16 项）
- `Index`：`P` 位（Probe 失败标志，仅由 `TLBP` 更新；`mtc0 Index` 不写该位）、`Index[3:0]`（16 项）
- `EntryHi`：`VPN2=EntryHi[31:13]`，`ASID=EntryHi[7:0]`
- `EntryLo0/1`：
  - `PFN = [25:6]`
  - `C   = [5:3]`
  - `D   = [2]`
  - `V   = [1]`
  - `G   = [0]`

`TLBWI` 写入 TLB 的 `G` 位按 MIPS 规则使用：

- `w_g = EntryLo0.G & EntryLo1.G`

`TLBR` 读出 `g` 时，会把 `EntryLo0.G` 与 `EntryLo1.G` 同时置为 `g`。

---

## 2. TLB 指令如何“装进流水”

指令编码（MIPS32 约定，本工程按 `ID_stage.v` 的 decode 风格实现）：

- `TLBR` ：`op=6'h10`，`rs=5'h10`，`func=6'h01`
- `TLBWI`：`op=6'h10`，`rs=5'h10`，`func=6'h02`
- `TLBP` ：`op=6'h10`，`rs=5'h10`，`func=6'h08`

实现策略（保证“精确异常/精确提交”的思路，尽量把状态更新放到 WB）：

- `TLBP`：在 **EXE** 阶段利用 TLB 的查找端口 1（s1）对 `EntryHi(VPN2/ASID)` 做比较；把 `{found,index}` 通过流水寄存器一路带到 **WB**，在 WB 时更新 CP0.Index。
- `TLBWI`：在 **WB** 提交时，根据 CP0 的 `Index/EntryHi/EntryLo0/EntryLo1` 产生 TLB 写端口信号，写入对应表项。
- `TLBR`：TLB 的读端口按 `Index.Index` 读出表项；在 **WB** 提交时，把读出的数据写回 CP0 的 `EntryHi/EntryLo0/EntryLo1`。

### 2.1 冲突处理（按指导书关键点）

#### (1) `TLBP` 与 `MTC0(EntryHi)` 冲突：阻塞（无需前递）

`TLBP` 在 EXE 阶段使用 `cp0_entryhi` 生成查找 key（VPN2/ASID）。
若前面流水中存在尚未提交的 `MTC0 EntryHi`，则 `TLBP` 必须等待写入完成再进入 EXE。

本工程实现：

- `EXE_stage.v` / `MEM_stage.v` 导出“正在写 EntryHi”的标志（`es_mtc0_entryhi_o/ms_mtc0_entryhi_o`）
- `ID_stage.v` 在 `TLBP` 译码后检测该标志，命中则拉低 `ds_ready_go` 产生阻塞

#### (2) `TLBR/TLBWI` 提交后的重取（flush 机制）

`TLBR/TLBWI` 在 WB 阶段提交会改变“后续取指/访存的翻译结果”。
为了避免使用 flush 前已经发出的旧翻译请求，本工程加入一次性 flush：

- `WB_stage.v` 在 `TLBR` 或 `TLBWI` **精确提交**时产生 `ws_tlb_flush=1`（1 周期）
- `ws_tlb_flush_pc = ws_pc + 4`，使取指从下一条指令重新开始
- `pre_IF_stage.v/IF_stage.v/ID_stage.v/EXE_stage.v/MEM_stage.v` 在 flush 时清空本级有效位/缓冲并阻止向后级发射
- `mycpu_core.v` 在 flush 时将 outstanding 的 inst/data 返回纳入 discard 机制，丢弃 flush 前发出的响应

---

## 3. 取指/访存地址转换怎么接

为了尽量少改流水级内部逻辑：

- `pre_IF_stage.v` 仍然输出“虚拟地址”（原本的 `inst_sram_addr`），在 `mycpu_core.v` 中对它做转换后再作为真正对外的 `inst_sram_addr`。
- `EXE_stage.v` 仍然输出“虚拟地址”（原本的 `data_sram_addr`），在 `mycpu_core.v` 中转换后再作为真正对外的 `data_sram_addr`。

转换规则（实验常用的最小集合）：

1. **直映段**：`kseg0/kseg1`（`vaddr[31:29]` 为 `3'b100/3'b101`）
   - `paddr = {3'b000, vaddr[28:0]}`
2. 其它段：用 TLB
  - 命中且页属性允许访问：`paddr = {pfn, vaddr[11:0]}`
    - 取指侧：要求 `V=1`
    - 访存侧：要求 `V=1`；若为写请求还要求 `D=1`
  - 未命中或页属性不允许访问（`V=0` 或写且 `D=0`）：当前实现先做“退化为不翻译”（不产生 TLBL/TLBS/Mod 异常），后续如果实验要求异常，再补异常编码与精确重定向。

---

## 4. 本次代码改动点（文件级）

- `myCPU/mycpu.h`：增加 CP0 新寄存器地址宏；扩展流水总线宽度（携带 tlb 指令与 tlbp 结果）。
- `myCPU/ID_stage.v`：新增 `TLBR/TLBWI/TLBP` decode；把指令位带入后级；避免被误判为 RI。
- `myCPU/EXE_stage.v`：为 `TLBP` 生成 TLB 查找 key；把 `{found,index}` 随流水带到 WB。
- `myCPU/MEM_stage.v`：透明传递新增的流水字段。
- `myCPU/WB_stage.v`：
  - 扩展 CP0：新增 `Index/EntryHi/EntryLo0/EntryLo1`；
  - 在 WB 产生 `tlbwi` 写端口信号；
  - 在 WB 对 `tlbr/tlbp` 更新 CP0。
- `myCPU/cp0.v`：实现新增寄存器与 `tlbr/tlbp` 更新接口。
- `myCPU/mycpu_core.v`：实例化 `tlb.v`，连接 s0/s1/读写端口；在 core 顶层完成 inst/data vaddr→paddr。

---

## 4.1 关键代码位置与片段（建议直接贴进报告）

说明：为避免行号随代码微调而漂移，下文以 **文件路径 + 可搜索关键字** 的方式定位；同时给出关键实现片段。

### (1) CP0 新增寄存器与 TLB 指令提交口

- 位置：`rtl/myCPU/cp0.v`
- 关键字：`// Index / EntryHi / EntryLo0 / EntryLo1 (TLB related)`、`tlbp_we`、`tlbr_we`

```verilog
// ------------------------------
// Index / EntryHi / EntryLo0 / EntryLo1 (TLB related)
// ------------------------------
reg [31:0] c0_index;
reg [31:0] c0_entryhi;
reg [31:0] c0_entrylo0;
reg [31:0] c0_entrylo1;

wire mtc0_index   = mtc0_we && (cp0_addr == `CP0_INDEX_ADDR);
wire mtc0_entryhi = mtc0_we && (cp0_addr == `CP0_ENTRYHI_ADDR);

// mtc0 Index：仅写 Index[3:0]，保护 P 位（Index[31]）
if (mtc0_index) begin
  c0_index[3:0] <= cp0_wdata[3:0];
  c0_index[30:4]<= 27'b0;
end

// tlbp：精确提交时更新 {P,index}
if (tlbp_we) begin
  c0_index[31]   <= ~tlbp_found;
  c0_index[30:4] <= 27'b0;
  c0_index[3:0]  <= tlbp_index;
end

// tlbr：精确提交时写回 EntryHi/EntryLo0/EntryLo1
if (tlbr_we) begin
  c0_entryhi[31:13] <= tlbr_vpn2;
  c0_entryhi[7:0]   <= tlbr_asid;
  c0_entrylo0[25:0] <= {tlbr_pfn0, tlbr_c0, tlbr_d0, tlbr_v0, tlbr_g};
  c0_entrylo1[25:0] <= {tlbr_pfn1, tlbr_c1, tlbr_d1, tlbr_v1, tlbr_g};
end
```

### (2) 新增 CP0 地址宏 + 流水总线扩展

- 位置：`rtl/myCPU/mycpu.h`
- 关键字：`DS_TO_ES_BUS_WD`、`CP0_INDEX_ADDR`

```verilog
// ds_to_es: 增加 TLBR/TLBWI/TLBP 3 个指令位
`define DS_TO_ES_BUS_WD     214
// es_to_ms / ms_to_ws: 透传 3 个 TLB 指令位 + tlbp {found,index}
`define ES_TO_MS_BUS_WD     171
`define MS_TO_WS_BUS_WD     132

// CP0 addr = {rd[15:11], sel[2:0]}
`define CP0_INDEX_ADDR       8'h00
`define CP0_ENTRYLO0_ADDR    8'h10
`define CP0_ENTRYLO1_ADDR    8'h18
`define CP0_ENTRYHI_ADDR     8'h50
```

### (3) ID 译码：TLBR/TLBWI/TLBP + 避免误判 RI + hazard 阻塞

- 位置：`rtl/myCPU/ID_stage.v`
- 关键字：`//new inst in tlb`、`tlbp_entryhi_block`、`ds_to_es_bus = {`

```verilog
//new inst in tlb
assign inst_tlbr  = op_d[6'h10] & rs_d[5'h10] & func_d[6'h01] & rd_d[5'h00] & rt_d[5'h00] & sa_d[5'h00];
assign inst_tlbwi = op_d[6'h10] & rs_d[5'h10] & func_d[6'h02] & rd_d[5'h00] & rt_d[5'h00] & sa_d[5'h00];
assign inst_tlbp  = op_d[6'h10] & rs_d[5'h10] & func_d[6'h08] & rd_d[5'h00] & rt_d[5'h00] & sa_d[5'h00];

// 与在途 MTC0 EntryHi 冲突：TLBP 不前递，直接阻塞
wire tlbp_entryhi_block;
assign tlbp_entryhi_block = ds_valid && inst_tlbp && (es_mtc0_entryhi || ms_mtc0_entryhi);
assign ds_ready_go = !(mfc0_block || tlbp_entryhi_block /* ... */);

// ds_to_es_bus：打包 3 个 TLB 指令位，供后级提交
assign ds_to_es_bus = {
  /* ... */
  inst_tlbp,  //157
  inst_tlbwi, //156
  inst_tlbr,  //155
  /* ... */
};
```

### (4) EXE：TLBP 查找 key + 透传 {found,index}，并导出 EntryHi 写冲突标志

- 位置：`rtl/myCPU/EXE_stage.v`
- 关键字：`// tlbp search key`、`es_mtc0_entryhi_o`、`es_to_ms_bus = {`

```verilog
// tlbp search key (reuse tlb port1)
assign tlb_s1_vpn2     = es_inst_tlbp ? cp0_entryhi[31:13] : es_data_vaddr[31:13];
assign tlb_s1_odd_page = es_inst_tlbp ? 1'b0              : es_data_vaddr[12];
assign tlb_s1_asid     = cp0_entryhi[7:0];

assign es_tlbp_found = es_valid && es_inst_tlbp && tlb_s1_found;
assign es_tlbp_index = tlb_s1_index;

assign es_to_ms_bus = {
  es_tlbp_found,
  es_tlbp_index,
  es_inst_tlbp,
  es_inst_tlbwi,
  es_inst_tlbr,
  /* ... */
};

// hazard flag: in-flight MTC0 writing EntryHi
assign es_mtc0_entryhi_o = es_valid && es_inst_mtc0 && (es_cp0_addr == `CP0_ENTRYHI_ADDR);
```

### (5) MEM：透明传递新增字段 + 继续导出 EntryHi 写冲突标志

- 位置：`rtl/myCPU/MEM_stage.v`
- 关键字：`ms_mtc0_entryhi_o`、`ms_to_ws_bus = {`

```verilog
assign ms_to_ws_bus = {
  ms_tlbp_found,
  ms_tlbp_index,
  ms_inst_tlbp,
  ms_inst_tlbwi,
  ms_inst_tlbr,
  /* ... */
};

assign ms_mtc0_entryhi_o = ms_valid && ms_inst_mtc0 && (ms_cp0_addr == `CP0_ENTRYHI_ADDR);
```

### (6) WB：TLBP/TLBR/TLBWI 精确提交 + flush + 产生 TLBWI 写口

- 位置：`rtl/myCPU/WB_stage.v`
- 关键字：`// TLB ops commit`、`ws_tlb_flush`、`assign tlb_we`

```verilog
// TLB ops commit
assign ws_tlbp_commit  = ws_valid && ws_inst_tlbp  && !ws_ex;
assign ws_tlbr_commit  = ws_valid && ws_inst_tlbr  && !ws_ex;
assign ws_tlbwi_commit = ws_valid && ws_inst_tlbwi && !ws_ex;

// TLBR/TLBWI 提交后 flush + 重取 ws_pc+4
assign ws_tlb_flush    = ws_tlbr_commit || ws_tlbwi_commit;
assign ws_tlb_flush_pc = ws_pc + 32'h4;

// TLBWI：把 CP0(Index/EntryHi/EntryLo0/1) 打到 tlb 写口
assign tlb_we      = ws_tlbwi_commit;
assign tlb_w_index = ws_cp0_index[3:0];
assign tlb_w_vpn2  = ws_cp0_entryhi[31:13];
assign tlb_w_asid  = ws_cp0_entryhi[7:0];
assign tlb_w_g     = ws_cp0_entrylo0[0] & ws_cp0_entrylo1[0];
assign tlb_w_pfn0  = ws_cp0_entrylo0[25:6];
assign tlb_w_v0    = ws_cp0_entrylo0[1];
assign tlb_w_d0    = ws_cp0_entrylo0[2];
assign tlb_w_pfn1  = ws_cp0_entrylo1[25:6];
assign tlb_w_v1    = ws_cp0_entrylo1[1];
assign tlb_w_d1    = ws_cp0_entrylo1[2];
```

### (7) 顶层翻译：inst/data vaddr→paddr + flush 前 outstanding 返回丢弃

- 位置：`rtl/myCPU/mycpu_core.v`
- 关键字：`// vaddr->paddr translate`、`inst_sram_discard`、`data_sram_discard`、`tlb #(`

```verilog
// vaddr->paddr translate (minimal: kseg0/kseg1 direct map, else TLB if found)
wire inst_direct_map;
assign inst_direct_map = (inst_sram_vaddr[31:29] == 3'b100) || (inst_sram_vaddr[31:29] == 3'b101);
wire inst_tlb_ok;
assign inst_tlb_ok     = tlb_s0_found & tlb_s0_v;
assign inst_sram_addr = inst_direct_map ? {3'b000, inst_sram_vaddr[28:0]} :
             (inst_tlb_ok     ? {tlb_s0_pfn, inst_sram_vaddr[11:0]} : inst_sram_vaddr);

wire data_direct_map;
assign data_direct_map = (data_sram_vaddr[31:29] == 3'b100) || (data_sram_vaddr[31:29] == 3'b101);
wire data_tlb_ok;
assign data_tlb_ok     = tlb_s1_found & tlb_s1_v & (~data_sram_wr | tlb_s1_d);
assign data_sram_addr = data_direct_map ? {3'b000, data_sram_vaddr[28:0]} :
             (data_tlb_ok     ? {tlb_s1_pfn, data_sram_vaddr[11:0]} : data_sram_vaddr);

// flush/eret/exception：丢弃 flush 前已发出的 inst/data 返回
always @(posedge clk) begin
  if (reset) begin
    inst_sram_discard <= 2'b00;
  end else if (ws_ex || ws_eret || ws_tlb_flush) begin
    inst_sram_discard <= {pfs_inst_waiting, fs_inst_waiting};
  end
end
assign inst_sram_data_ok_discard = inst_sram_data_ok && ~|inst_sram_discard;
```

---

## 5. 实现 TODO（对应本仓库）

### 5.1 已完成（本仓库当前代码已具备）

- [x] 扩展 `mycpu.h`：CP0 新寄存器宏 + 各级 BUS 宽度
- [x] `ID_stage.v`：加入 `TLBR/TLBWI/TLBP` decode，写入 ds_to_es_bus
- [x] `EXE_stage.v`：生成 `TLBP` 查找 key，复用 tlb s1 查找并向后传递 found/index
- [x] `MEM_stage.v`：透传新增字段
- [x] `WB_stage.v`：
  - [x] `TLBP` 提交更新 CP0.Index
  - [x] `TLBR` 提交写回 CP0.EntryHi/EntryLo*
  - [x] `TLBWI` 提交写 TLB
  - [x] `TLBR/TLBWI` 提交后 flush+重取（`ws_tlb_flush/ws_tlb_flush_pc`）
- [x] `cp0.v`：补齐 `Index/EntryHi/EntryLo0/EntryLo1` 与 `tlbp/tlbr` 更新通道
- [x] `mycpu_core.v`：实例化 tlb；完成 inst/data 地址转换；连通 tlb 读写口
- [x] 冲突处理：`TLBP` 与前序 `MTC0(EntryHi)` 阻塞（无前递）

### 5.2 后续可选（若实验测试要求）

- [ ] 实现 TLBL/TLBS/Mod（TLB miss/invalid/dirty）异常编码与精确重定向
- [ ] 增加 Wired/Random 等更完整的 TLB 管理寄存器

> 注：如果后续实验要求实现 TLBL/TLBS/Mod 异常，需要在 `mycpu.h` 中新增异常编码，并在 IF/EXE/MEM 侧把“TLB 未命中/无效/不可写”变成精确异常。

---

## 6. 定位用仿真 TB（面向剩余 1 个测试点）

为定位 flush/重取与 `TLBP` 阻塞边界问题，仓库在 `rtl/tb/` 下提供了一个“CPU 级”聚焦用例：

- `rtl/tb/cpu_tlb_hazard_tb.v`
  - 覆盖：`TLBWI` 提交后紧跟 `lw`（验证 WB flush + outstanding discard + 重取生效）
  - 覆盖：`MTC0 EntryHi` 紧跟 `TLBP`（ASID 不同且 `G=0`，期望 miss，验证 ID 阻塞生效）

此外还提供一个更系统的 suite：

- `rtl/tb/cpu_tlb_suite_tb.v`
  - 覆盖：偶/奇页选择（`vaddr[12]`）
  - 覆盖：`G=1` 忽略 ASID（ASID 不同仍应命中）
  - 覆盖：`TLBR` 读回 `EntryHi/EntryLo0/EntryLo1` 一致性
  - 覆盖：`TLBR -> TLBP` 紧邻序列（对 flush/时序敏感）
  - 覆盖：`TLBP` miss 时 `Index.P=1`
  - 覆盖：**取指侧 s0 TLB 翻译**（跳转到 kuseg 代码页执行，验证取指也能正确走 TLB 命中并选偶/奇页 PFN）

该 TB 直接例化 `mycpu_core`，并用简化 SRAM 模型提供 `addr_ok/data_ok` 行为；适合在 Vivado/xsim 下观察波形与对照预期。

> 说明：TB 中 reset 向量按本工程直映规则使用 `0xBFC0_0000 -> 0x1FC0_0000`（`paddr={3'b000,vaddr[28:0]}`）。
