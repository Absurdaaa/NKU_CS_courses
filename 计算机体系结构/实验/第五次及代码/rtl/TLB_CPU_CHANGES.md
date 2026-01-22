# 本次修改总览：TLB + CP0 扩展 + TLB 指令

你可以直接把本仓库 `rtl` 目录加入 Vivado 工程，或把改动文件替换进你原工程后再综合/仿真。

> 重要说明：本次实现以“能集成、能跑通基本流程”为目标，**暂未实现 TLBL/TLBS/Mod 等 TLB 异常**。TLB 未命中时目前会退化为“不翻译，仍使用 vaddr 当作 paddr”。若实验要求异常，再继续补即可。

---

## ✅ 功能实现清单

### 1) 集成 TLB 到 CPU
- `myCPU/tlb.v` 已在 `myCPU/mycpu_core.v` 里实例化。
- 取指地址：`pre_IF_stage` 产生 vaddr → `mycpu_core` 顶层翻译后送外部 `inst_sram_addr`。
- 访存地址：`exe_stage` 产生 vaddr → `mycpu_core` 顶层翻译后送外部 `data_sram_addr`。
- 翻译规则（最小集合）：
  - `kseg0/kseg1`：直映（`paddr={3'b000,vaddr[28:0]}`）
  - 其它段：TLB 命中且页属性允许访问则用 PFN 拼接，否则退化为不翻译

页属性最小检查（已实现）：
- 取指侧：TLB 命中时要求 `V=1` 才使用 PFN
- 访存侧：TLB 命中时要求 `V=1`；写请求还要求 `D=1`；否则退化为“不翻译”（当前未实现 TLBL/TLBS/Mod）

### 2) 新增 TLB 指令
- `TLBP`：EXE 复用 TLB s1 端口对 `EntryHi(VPN2/ASID)` 查找；WB 提交时更新 `CP0.Index(P/index)`。
- `TLBWI`：WB 提交时按 `CP0.Index/EntryHi/EntryLo0/EntryLo1` 写入 TLB。
- `TLBR`：WB 提交时按 `CP0.Index` 从 TLB 读出并写回 `CP0.EntryHi/EntryLo0/EntryLo1`。

#### 冲突/重取处理
- **TLBP vs MTC0(EntryHi)**：无前递，直接阻塞。若 ID 阶段检测到后续 EX/MEM 有在途的 `MTC0 EntryHi`，则阻塞 `TLBP` 进入 EXE，等待写入完成后再查找。
- **TLBR/TLBWI 提交后 flush**：在 WB 精确提交 `TLBR/TLBWI` 时产生一次 `ws_tlb_flush`，并把取指 PC 重定向到 `ws_pc+4`，同时丢弃 flush 前的 outstanding inst/data 返回，确保后续使用更新后的 TLB/EntryHi 翻译结果。

### 3) 新增 CP0 寄存器
新增并支持 `mfc0/mtc0`：
- `Index`、`EntryHi`、`EntryLo0`、`EntryLo1`

字段使用：
- `Index[31]=P`（TLBP 未命中置 1；该位由 TLBP 更新，`mtc0 Index` 不写入 P 位），`Index[3:0]=index`
- `EntryHi.VPN2=EntryHi[31:13]`，`ASID=EntryHi[7:0]`
- `EntryLo0/1`：PFN/C/D/V/G 对应 `[25:6]/[5:3]/[2]/[1]/[0]`
- `TLBWI.G = EntryLo0.G & EntryLo1.G`

---

## 🧩 代码改动（按文件）

### 修改文件
- `myCPU/mycpu.h`
  - 扩展流水总线宽度：`DS_TO_ES/ES_TO_MS/MS_TO_WS`
  - 增加 CP0 寄存器地址宏：`CP0_INDEX_ADDR/CP0_ENTRYHI_ADDR/CP0_ENTRYLO0_ADDR/CP0_ENTRYLO1_ADDR`

- `myCPU/cp0.v`
  - 新增寄存器：`Index/EntryHi/EntryLo0/EntryLo1`
  - `Index` 写入规则：`mtc0 Index` 仅写 `Index[3:0]`（P 位保留）；`TLBP` 精确提交时更新 `{P,index}`
  - 新增提交接口：
    - `tlbp_we/tlbp_found/tlbp_index`（写 Index）
    - `tlbr_we + tlbr_*`（写 EntryHi/Lo0/Lo1）
  - `cp0_rdata` 增加上述寄存器的读出

- `myCPU/ID_stage.v`
  - 增加译码：`inst_tlbp/inst_tlbwi/inst_tlbr`
  - 扩展 `ds_to_es_bus` 打包 3 个指令位
  - `other_inst` 识别加入 TLB 指令，避免 RI

- `myCPU/EXE_stage.v`
  - 解包 3 个 TLB 指令位
  - 为 `TLBP` 生成查找 key（来自 `cp0_entryhi`）
  - 把 `{tlbp_found, tlbp_index}` + 3 个指令位打入 `es_to_ms_bus`
  - 增加端口：`cp0_entryhi`、`tlb_s1_*`
  - 增加导出：`es_mtc0_entryhi_o`（用于 `TLBP` 与 `MTC0 EntryHi` 冲突阻塞）

- `myCPU/MEM_stage.v`
  - 解包/透传新增字段到 `ms_to_ws_bus`
  - 增加导出：`ms_mtc0_entryhi_o`（用于 `TLBP` 与 `MTC0 EntryHi` 冲突阻塞）

- `myCPU/WB_stage.v`
  - 解包新增字段
  - CP0 实例化扩展端口，输出 `cp0_index/entryhi/entrylo0/entrylo1`
  - 产生 TLBWI 写端口信号（`tlb_we/tlb_w_*`）
  - TLBR 时把 `tlb_r_*` 写回 CP0
  - TLBP 时更新 CP0.Index
  - TLBR/TLBWI 精确提交时产生 `ws_tlb_flush/ws_tlb_flush_pc`

- `myCPU/mycpu_core.v`
  - 新增 `tlb` 实例
  - 在 core 顶层进行 inst/data 地址翻译
  - 连通 EXE 的 `tlb_s1_*` 与 WB 的 tlb 读写端口
  - 将 `ws_tlb_flush` 接入 preIF/IF/ID/EX/MEM 的清空与 inst/data outstanding discard


---

## 文件清单（快速定位）

- 说明：`rtl/TLB_INTEGRATION.md`、`rtl/TLB_CPU_CHANGES.md`
- 关键 RTL：
  - `rtl/myCPU/mycpu_core.v`
  - `rtl/myCPU/cp0.v`
  - `rtl/myCPU/ID_stage.v`
  - `rtl/myCPU/EXE_stage.v`
  - `rtl/myCPU/MEM_stage.v`
  - `rtl/myCPU/WB_stage.v`

---

## 🔎 关键改动代码位置 + 片段（可直接用于实验报告）

说明：本节给出**文件路径 + 搜索关键字**的定位方式，并附上关键片段（行号可能随格式化/注释微调而变化）。

### 1) `myCPU/mycpu.h`：新增 CP0 宏 + 总线宽度扩展

- 关键字：`CP0_INDEX_ADDR`、`DS_TO_ES_BUS_WD`

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

### 2) `myCPU/ID_stage.v`：TLB 指令译码 + hazard 阻塞

- 关键字：`//new inst in tlb`、`tlbp_entryhi_block`

```verilog
assign inst_tlbr  = op_d[6'h10] & rs_d[5'h10] & func_d[6'h01] & rd_d[5'h00] & rt_d[5'h00] & sa_d[5'h00];
assign inst_tlbwi = op_d[6'h10] & rs_d[5'h10] & func_d[6'h02] & rd_d[5'h00] & rt_d[5'h00] & sa_d[5'h00];
assign inst_tlbp  = op_d[6'h10] & rs_d[5'h10] & func_d[6'h08] & rd_d[5'h00] & rt_d[5'h00] & sa_d[5'h00];

wire tlbp_entryhi_block = ds_valid && inst_tlbp && (es_mtc0_entryhi || ms_mtc0_entryhi);
assign ds_ready_go = !(mfc0_block || tlbp_entryhi_block /* ... */);
```

### 3) `myCPU/EXE_stage.v`：TLBP 复用 s1 查找端口 + 透传结果

- 关键字：`// tlbp search key`、`es_to_ms_bus = {`

```verilog
assign tlb_s1_vpn2     = es_inst_tlbp ? cp0_entryhi[31:13] : es_data_vaddr[31:13];
assign tlb_s1_odd_page = es_inst_tlbp ? 1'b0              : es_data_vaddr[12];
assign tlb_s1_asid     = cp0_entryhi[7:0];

assign es_tlbp_found = es_valid && es_inst_tlbp && tlb_s1_found;
assign es_tlbp_index = tlb_s1_index;

assign es_mtc0_entryhi_o = es_valid && es_inst_mtc0 && (es_cp0_addr == `CP0_ENTRYHI_ADDR);
```

### 4) `myCPU/MEM_stage.v`：透传新增字段 + hazard 标志继续向前级提供

- 关键字：`ms_mtc0_entryhi_o`

```verilog
assign ms_mtc0_entryhi_o = ms_valid && ms_inst_mtc0 && (ms_cp0_addr == `CP0_ENTRYHI_ADDR);
```

### 5) `myCPU/WB_stage.v`：TLB 指令精确提交 + flush + TLBWI 写口

- 关键字：`// TLB ops commit`、`ws_tlb_flush`、`assign tlb_we`

```verilog
assign ws_tlbp_commit  = ws_valid && ws_inst_tlbp  && !ws_ex;
assign ws_tlbr_commit  = ws_valid && ws_inst_tlbr  && !ws_ex;
assign ws_tlbwi_commit = ws_valid && ws_inst_tlbwi && !ws_ex;

assign ws_tlb_flush    = ws_tlbr_commit || ws_tlbwi_commit;
assign ws_tlb_flush_pc = ws_pc + 32'h4;

assign tlb_we      = ws_tlbwi_commit;
assign tlb_w_index = ws_cp0_index[3:0];
assign tlb_w_vpn2  = ws_cp0_entryhi[31:13];
assign tlb_w_asid  = ws_cp0_entryhi[7:0];
assign tlb_w_g     = ws_cp0_entrylo0[0] & ws_cp0_entrylo1[0];
```

### 6) `myCPU/cp0.v`：Index/EntryHi/EntryLo0/EntryLo1 实现 + tlbp/tlbr 更新

- 关键字：`(TLB related)`、`tlbp_we`、`tlbr_we`

```verilog
// mtc0 Index：仅写 Index[3:0]，不写 P
if (mtc0_index) begin
  c0_index[3:0] <= cp0_wdata[3:0];
end

// tlbp：P=~found
if (tlbp_we) begin
  c0_index[31]  <= ~tlbp_found;
  c0_index[3:0] <= tlbp_index;
end

// tlbr：EntryLo0/1 的 G 同时置为 g（按 MIPS 规则）
if (tlbr_we) begin
  c0_entrylo0[25:0] <= {tlbr_pfn0, tlbr_c0, tlbr_d0, tlbr_v0, tlbr_g};
  c0_entrylo1[25:0] <= {tlbr_pfn1, tlbr_c1, tlbr_d1, tlbr_v1, tlbr_g};
end
```

### 7) `myCPU/mycpu_core.v`：顶层地址翻译 + outstanding discard + TLB 例化

- 关键字：`// vaddr->paddr translate`、`inst_sram_discard`、`tlb #(`

```verilog
wire inst_direct_map;
assign inst_direct_map = (inst_sram_vaddr[31:29] == 3'b100) || (inst_sram_vaddr[31:29] == 3'b101);
wire inst_tlb_ok;
assign inst_tlb_ok     = tlb_s0_found & tlb_s0_v;
assign inst_sram_addr = inst_direct_map ? {3'b000, inst_sram_vaddr[28:0]} :
             (inst_tlb_ok     ? {tlb_s0_pfn, inst_sram_vaddr[11:0]} : inst_sram_vaddr);

wire data_direct_map;
assign data_direct_map = (data_sram_vaddr[31:29] == 3'b100) || (data_sram_vaddr[31:29] == 3'b101);
wire data_tlb_ok = tlb_s1_found & tlb_s1_v & (~data_sram_wr | tlb_s1_d);
assign data_sram_addr = data_direct_map ? {3'b000, data_sram_vaddr[28:0]} :
             (data_tlb_ok     ? {tlb_s1_pfn, data_sram_vaddr[11:0]} : data_sram_vaddr);

// flush：丢弃 flush 前的返回
assign inst_sram_data_ok_discard = inst_sram_data_ok && ~|inst_sram_discard;
assign data_sram_data_ok_discard = data_sram_data_ok && ~|data_sram_discard;
```
