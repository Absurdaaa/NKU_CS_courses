
# I$ / D$（cache.v）集成说明（含 kseg0 固定 Cached）

本文档记录将给定两路组相连 `cache.v` 集成到 CPU（I$ + D$）的所有关键改动点，并尽量给出“改前/改后”的关键代码片段，方便复查。

> 关键需求：**kseg0 固定为 Cached 属性**。

---

## 1. 总体结构

集成后的数据通路（SRAM-like 接口）为：

- `mycpu_core` 仍产生两路 SRAM-like 访问：`inst_sram_*` / `data_sram_*`（地址已是 paddr 或直映射地址）。
- `mycpu_core` 额外输出：`inst_cached` / `data_cached`（段属性），用于顶层决定 **走 cache** 还是 **uncached bypass**。
- `icache_top` / `dcache_top`：
  - cached：请求进入 `cache.v`，并通过 cache burst 端口完成 linefill/writeback。
  - uncached：请求直接透传到 `transfer_bridge` 原来的 inst/data 单拍通路。
- `mycpu_top` 顶层增加 **I$ / D$ 的 cache burst 仲裁**，把两路 cache 的 burst 合并到 `transfer_bridge` 的单一 cache burst 端口。
- `transfer_bridge` 新增 cache burst（4 beat）通路，使用 **AXI ID 分流**（INST/DATA/CACHE）。

---

## 2. 段属性（kseg0 固定 Cached）——`rtl/myCPU/mycpu_core.v`

### 2.1 改动目的

- `mycpu_top` 需要一个“是否走 cache”的判定信号。
- 需求强制：**kseg0（0x8000_0000 ~ 0x9fff_ffff）始终 Cached**。
- kseg1（0xa000_0000 ~ 0xbfff_ffff）始终 Uncached。
- 其余段：TLB 命中且有效时，按 TLB 的 C 位判断（这里使用 `C != 3'b010` 视为 cached）。

### 2.2 关键原码/改后码

**改前**：`mycpu_core` 只有 inst/data SRAM-like 接口，没有段属性输出。

**改后**：新增端口，并实现属性逻辑：

```verilog
// memory segment attribute (for cache/bypass mux in top)
output        inst_cached,
output        data_cached,

// segment attribute (kseg0 fixed cached)
wire inst_kseg0;
wire inst_kseg1;
assign inst_kseg0 = (inst_sram_vaddr[31:29] == 3'b100);
assign inst_kseg1 = (inst_sram_vaddr[31:29] == 3'b101);
assign inst_cached = inst_kseg0 ? 1'b1 :
					 inst_kseg1 ? 1'b0 :
					 (inst_tlb_ok && (tlb_s0_c != 3'b010));

wire data_kseg0;
wire data_kseg1;
assign data_kseg0 = (data_sram_vaddr[31:29] == 3'b100);
assign data_kseg1 = (data_sram_vaddr[31:29] == 3'b101);
assign data_cached = data_kseg0 ? 1'b1 :
					 data_kseg1 ? 1'b0 :
					 (data_tlb_ok && (tlb_s1_c != 3'b010));
```

> 注：本工程中 inst/data 的 vaddr→paddr 翻译仍保持原先“kseg0/kseg1 直映射 + 其他段 TLB（命中才用 pfn）”的最小实现；段属性判断独立输出用于 cache/bypass 选择。

---

## 3. I$/D$ wrapper ——`rtl/myCPU/icache_top.v`、`rtl/myCPU/dcache_top.v`

### 3.1 改动目的

`cache.v` 的 CPU 侧接口是 SRAM-like（`valid/addr_ok/data_ok/rdata`），但还需要：

1) 根据 `*_cached` 动态选择 **cached** 或 **uncached bypass**；
2) 避免一个常见坑：**bypass 返回不能被门控**。

原因：uncached bypass 这一路最终由 `transfer_bridge` 内部 FIFO 驱动，如果你把 `*_data_ok` 按“当前 cached/bypass 状态”去门控，有可能发生：

- bridge/FIFO 已经 pop 了返回（`*_data_ok` 拉高 1 拍）
- 但 wrapper 由于 “当前选择 cached” 把 `data_ok` 门掉
- core 永久等不到这笔返回 → 死锁/卡死

因此这里的原则是：

- **uncached 返回（bypass 的 data_ok）永远优先直通，不做选择门控**。

此外，为处理极端情况（同一周期 bypass 返回和 cache 返回同时到达），增加了 **1-deep hold buffer**。

### 3.2 icache_top 关键实现

```verilog
wire cached_req = inst_sram_req && inst_cached;
wire bypass_req = inst_sram_req && !inst_cached;

assign uc_inst_sram_req   = bypass_req;
...
assign inst_sram_addr_ok = inst_cached ? cache_addr_ok : uc_inst_sram_addr_ok;

// bypass return is NEVER gated
wire bypass_ok = uc_inst_sram_data_ok;
wire use_bypass = bypass_ok;
wire use_hold   = !use_bypass && hold_valid;
wire use_cache  = !use_bypass && !hold_valid && cache_data_ok;

assign inst_sram_data_ok = use_bypass || use_hold || use_cache;
assign inst_sram_rdata   = use_bypass ? uc_inst_sram_rdata :
						   use_hold   ? hold_rdata :
										cache_rdata;

wire set_hold     = cache_data_ok && bypass_ok;
wire consume_hold = hold_valid && !bypass_ok;
```

### 3.3 dcache_top 关键实现

与 I$ 相同思想，但 D$ 会把 store 请求也送入 `cache.v`（write-back + write-allocate），关键片段：

```verilog
wire cached_req = data_sram_req && data_cached;
wire bypass_req = data_sram_req && !data_cached;

cache u_dcache (
	.valid      (cached_req),
	.op         (data_sram_wr),
	.wstrb      (data_sram_wstrb),
	.wdata      (data_sram_wdata),
	...
);

// bypass return is NEVER gated + 1-deep buffer
wire bypass_ok = uc_data_sram_data_ok;
...
```

---

## 4. 顶层插入 I$/D$ 并仲裁 cache burst ——`rtl/myCPU/mycpu_top.v`

### 4.1 改动目的

- 在 `mycpu_core` 与 `transfer_bridge` 中间插入 I$/D$。
- uncached 请求仍走原来的 `transfer_bridge` inst/data 单拍接口。
- cached 的 linefill/writeback 通过新增的 cache burst 口进入 `transfer_bridge`。
- 由于 `transfer_bridge` 只提供一组 cache burst 端口，顶层需要在 I$ 与 D$ 之间仲裁。

### 4.2 关键原码/改后码

**改前（未集成 cache）**：`transfer_bridge` 直接连接 core 的 inst/data SRAM 接口（节选）：

```verilog
transfer_bridge u_transfer_bridge(
	...
	.inst_sram_req      (inst_sram_req      ),
	.inst_sram_wr       (inst_sram_wr       ),
	.inst_sram_size     (inst_sram_size     ),
	.inst_sram_addr     (inst_sram_addr     ),
	.inst_sram_wstrb    (inst_sram_wstrb    ),
	.inst_sram_wdata    (inst_sram_wdata    ),
	.inst_sram_addr_ok  (inst_sram_addr_ok  ),
	.inst_sram_data_ok  (inst_sram_data_ok  ),
	.inst_sram_rdata    (inst_sram_rdata    ),

	.data_sram_req      (data_sram_req      ),
	.data_sram_wr       (data_sram_wr       ),
	.data_sram_size     (data_sram_size     ),
	.data_sram_addr     (data_sram_addr     ),
	.data_sram_wstrb    (data_sram_wstrb    ),
	.data_sram_wdata    (data_sram_wdata    ),
	.data_sram_addr_ok  (data_sram_addr_ok  ),
	.data_sram_data_ok  (data_sram_data_ok  ),
	.data_sram_rdata    (data_sram_rdata    )
);
```

**改后**：

1) core 增加 `inst_cached/data_cached` 接出；
2) 实例化 `icache_top`、`dcache_top`；
3) uncached 端口接回 bridge 原 inst/data 口；
4) 新增 cache burst 仲裁后接 bridge 的 cache burst 口。

仲裁关键代码（D$ 优先，且避免 read burst 进行中切 owner）：

```verilog
reg  [1:0]  cache_owner; // 0:none 1:icache 2:dcache
reg         cache_rd_inflight;

wire ic_need = ic_rd_req || ic_wr_req;
wire dc_need = dc_rd_req || dc_wr_req;

always @(posedge aclk) begin
	if (!aresetn) begin
		cache_owner       <= 2'd0;
		cache_rd_inflight <= 1'b0;
	end else begin
		if (!cache_rd_inflight) begin
			if ((cache_owner == 2'd1) && ic_rd_req && cache_rd_rdy) begin
				cache_rd_inflight <= 1'b1;
			end else if ((cache_owner == 2'd2) && dc_rd_req && cache_rd_rdy) begin
				cache_rd_inflight <= 1'b1;
			end
		end else if (cache_ret_valid && cache_ret_last) begin
			cache_rd_inflight <= 1'b0;
		end

		if (!cache_rd_inflight) begin
			case (cache_owner)
				2'd0: begin
					if (dc_need) cache_owner <= 2'd2;
					else if (ic_need) cache_owner <= 2'd1;
				end
				...
			endcase
		end
	end
end
```

uncached 回接 + cache burst 接入（节选）：

```verilog
.inst_sram_req      (uc_inst_sram_req   ),
...
.data_sram_req      (uc_data_sram_req   ),
...
.cache_rd_req       (cache_rd_req       ),
.cache_ret_valid    (cache_ret_valid    ),
...
.cache_wr_req       (cache_wr_req       ),
...
```

同时补齐 `transfer_bridge` 端口所需的 AXI 返回信号连线（`rresp/rlast/bid/bresp`）。

---

## 5. AXI 桥扩展为支持 cache burst ——`rtl/myCPU/transfer_bridge.v`

### 5.1 改动目的

- 保持原 inst/data 单拍 SRAM-like 语义。
- 新增 cache burst 语义：
  - read：一次 linefill 读 4 beat（`arlen=3`），输出 `cache_ret_valid/cache_ret_last/cache_ret_data`。
  - write：一次 writeback 写 4 beat（`awlen=3`）。
- 使用 `CACHE_ID=4'h2` 进行 AXI ID 分流，避免与 inst/data FIFO 混用。

### 5.2 关键原码/改后码

**(1) 新增 cache burst 端口与 ID**

```verilog
parameter INST_ID = 4'h0;
parameter DATA_ID = 4'h1;
parameter CACHE_ID= 4'h2;

// cache burst side (for I$/D$ linefill & writeback)
input               cache_rd_req,
...
output              cache_ret_valid,
output              cache_ret_last,
output  [31:0]      cache_ret_data,
...
output              cache_wr_rdy,
```

**(2) AR 通道支持 burst（len/cache 字段）**

改前：固定单拍读（`arlen=0`），且 `arcache=0`。

改后：对 cache 选择 `len=3` 且 `arcache=4'b1111`：

```verilog
assign read_req_id    = read_req_sel_cache ? CACHE_ID : (read_req_sel_data ? DATA_ID : INST_ID);
assign read_req_addr  = read_req_sel_cache ? cache_rd_addr : ...;
assign read_req_size  = read_req_sel_cache ? 3'b010 : ...;
assign read_req_len   = read_req_sel_cache ? 8'd3   : 8'd0;
assign read_req_cache = read_req_sel_cache ? 4'b1111: 4'b0000;
```

**(3) cache 返回不被 inst/data FIFO 反压阻塞（关键修复点）**

改前：

```verilog
assign rready = !read_inst_resp_full && !read_data_resp_full;
```

改后：当 AXI R 返回属于 `CACHE_ID` 时，`rready` 强制 1（否则可能被 inst/data FIFO 满间接阻塞 cache burst，导致 cache 无法收齐 linefill → 死锁）：

```verilog
assign rready = (rvalid && rid == CACHE_ID) ? 1'b1 : (!read_inst_resp_full && !read_data_resp_full);

assign cache_ret_valid = axi_r_cache_ok;
assign cache_ret_last  = rlast;
assign cache_ret_data  = axi_r_data;
```

**(3.5) 读返回乱序问题（PC 差 4）的根因与修复**

现象（func_all94/trace 对比常见表现之一）：

- reference PC 比 mycpu PC **大 4**（例如 ref=0x9fc1e898、mycpu=0x9fc1e894），看起来像“少走了一条/顺序被打乱”。

根因：

- 引入 `CACHE_ID`（burst）之后，如果 `transfer_bridge` 允许在**上一笔读响应还没收完**时继续发起新的 `AR`，那么 AXI 从设备可能在**不同 ID 之间乱序返回**（AXI 允许不同 ID 并发/乱序）。
- 但原 CPU 的 inst/data SRAM-like 语义隐含了“**读请求/读返回按发起顺序**”的假设；一旦乱序，`read_inst_resp_buff/read_data_resp_buff` 的数据会和流水线期待的那一拍对不上，最终在 debug trace 中表现为 PC 对不上（常见就是差 4）。

修复：

- 在 `transfer_bridge` 内增加 `rd_outstanding/rd_out_id`，**强制整个桥只允许 1 笔 outstanding 读事务**：
  - `AR` 握手成功后置 `rd_outstanding=1`
  - 对 inst/data（单拍）在对应 `R` 握手成功时清零
  - 对 cache（burst）在对应 `R` 握手且 `rlast=1` 时清零
- 同时 `read_*_req_ok/cache_rd_rdy` 统一受 `can_issue_read = !axi_ar_busy && !rd_outstanding` 约束。

关键代码片段（改后）：

```verilog
/* AXI read outstanding (one at a time) */
reg         rd_outstanding;
reg  [ 3:0] rd_out_id;

// issue AR only when no outstanding read
... else if (!axi_ar_busy && !rd_outstanding && read_req_valid) begin
	axi_ar_busy <= 1'b1;
	axi_ar_id   <= read_req_id;
	...
end

// track outstanding read: block new AR until previous read response is fully received
always @(posedge aclk) begin
	if (!aresetn) begin
		rd_outstanding <= 1'b0;
		rd_out_id      <= 4'h0;
	end else begin
		if (arvalid && arready) begin
			rd_outstanding <= 1'b1;
			rd_out_id      <= arid;
		end

		if (rd_outstanding) begin
			if ((rd_out_id == CACHE_ID) && axi_r_cache_ok && rlast) begin
				rd_outstanding <= 1'b0;
			end else if ((rd_out_id == INST_ID) && axi_r_inst_ok) begin
				rd_outstanding <= 1'b0;
			end else if ((rd_out_id == DATA_ID) && axi_r_data_ok) begin
				rd_outstanding <= 1'b0;
			end
		end
	end
end

wire can_issue_read = !axi_ar_busy && !rd_outstanding;
assign read_inst_req_ok = read_req_sel_inst && can_issue_read;
assign read_data_req_ok = read_req_sel_data && can_issue_read;
assign cache_rd_rdy     = read_req_sel_cache && can_issue_read;
```

**(4) 写通道支持 cache writeback burst**

新增写状态机：cache 写优先；cache 写 `awlen=3`，`awcache=4'b1111`；W 通道按 beat 发送 128-bit 行的 4 个 word。

```verilog
assign awlen   = wr_len;
assign awcache = wr_is_cache ? 4'b1111 : 4'b0000;
assign wlast   = (wr_beat == wr_len);

wire [31:0] wr_wdata_cache =
	(wr_beat[1:0] == 2'd0) ? wr_wdata_line[31:0] :
	(wr_beat[1:0] == 2'd1) ? wr_wdata_line[63:32] :
	(wr_beat[1:0] == 2'd2) ? wr_wdata_line[95:64] :
							 wr_wdata_line[127:96];
```

**(5) cache 写响应不被 data 写响应 FIFO 反压阻塞**

```verilog
assign bready = (bvalid && bid == CACHE_ID) ? 1'b1 : !write_data_resp_full;
```

**(6) Uncached（inst/data 单拍通路）写后顺序性保证（MMIO 安全）**

背景：

- 本工程中 **uncached** 访问不进入 `cache.v`，而是由 `icache_top/dcache_top` 直接走 bypass 回接到 `transfer_bridge` 的原 inst/data 单拍通路。
- 对于 I/O 外设（MMIO），uncached 的 load/store 必须保持严格顺序：如果存在一个未完成的 uncached 写（尚未收到 `B`），必须阻塞后续所有 uncached 读/写，避免外设语义被乱序破坏。

实现：

- 利用 `transfer_bridge` 内部写状态机的 `wr_active/wr_is_cache` 判定当前是否有“uncached data 写”在飞：
	- `uncached_write_inflight = wr_active && !wr_is_cache`
- 当 `uncached_write_inflight=1` 时：
	- 禁止选择 inst/data 的读请求（避免在 `AR` 通道发出读）
	- 相应地 `inst_sram_addr_ok/data_sram_addr_ok` 也不会对读请求放行
- cache burst（`CACHE_ID`）不受该约束影响。

关键代码片段（改后）：

```verilog
wire uncached_write_inflight = wr_active && !wr_is_cache;

assign read_req_sel_cache   = cache_rd_req;
assign read_req_sel_data    = !read_req_sel_cache && !uncached_write_inflight && data_read_valid;
assign read_req_sel_inst    = !read_req_sel_cache && !uncached_write_inflight && !data_read_valid && inst_read_valid;

wire can_issue_read      = !axi_ar_busy && !rd_outstanding;
wire can_issue_read_uc   = can_issue_read && !uncached_write_inflight;

assign read_data_req_ok = read_req_sel_data && can_issue_read_uc;
assign read_inst_req_ok = read_req_sel_inst && can_issue_read_uc;
```

---

## 6. 新增 `cache.v` ——`rtl/myCPU/cache.v`

- 2-way set associative
- 256 sets（`index[7:0]`）
- line size 16B（4x32-bit beat）
- write-back + write-allocate
- 单 outstanding（`addr_ok` 仅在 idle 时为 1）

关键接口说明（节选）：

```verilog
// CPU side
input  valid;
output addr_ok;
output reg data_ok;
output reg [31:0] rdata;

// memory side
output reg        rd_req;
output reg [31:0] rd_addr;
input             rd_rdy;
input             ret_valid;
input             ret_last;
input      [31:0] ret_data;

output reg        wr_req;
output reg [31:0] wr_addr;
output reg [127:0] wr_data;
input             wr_rdy;
```

---

## 7. 其他改动（工程/外设）

### 7.1 `rtl/CONFREG/confreg.v`

`open_trace` 复位默认值修改（便于默认打开 trace）：

```diff
-        open_trace <= 1'b0;
+        open_trace <= 1'b1;
```

### 7.2 `run_vivado/mycpu_prj1/mycpu.xpr`

工程文件集更新：将 `cache.v`、`icache_top.v`、`dcache_top.v` 加入 sources；同时仿真文件集部分条目顺序/禁用属性有调整（Vivado 工程层面的变动）。

---

## 8. 已知关键点回顾（避免踩坑）

1) **uncached bypass 返回不能门控**（否则可能吞掉 bridge/FIFO 已弹出的 data_ok）。
2) **cache burst 返回不能被 inst/data FIFO 反压卡住**（`transfer_bridge` 中对 `CACHE_ID` 的 `rready/bready` 强制接收）。

---

## 9. 文件清单

- 新增
  - `rtl/myCPU/cache.v`
  - `rtl/myCPU/icache_top.v`
  - `rtl/myCPU/dcache_top.v`
- 修改
  - `rtl/myCPU/mycpu_core.v`
  - `rtl/myCPU/mycpu_top.v`
  - `rtl/myCPU/transfer_bridge.v`
  - `rtl/CONFREG/confreg.v`
  - `run_vivado/mycpu_prj1/mycpu.xpr`

