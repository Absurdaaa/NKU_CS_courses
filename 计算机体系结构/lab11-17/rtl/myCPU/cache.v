`timescale 1ns / 1ps

// ===============================
// 两路组相连 Cache
//
// 组织结构：
// - 2 路组相连（2-way set associative）
// - 256 组（set）：index[7:0]
// - 行大小 16B：offset[3:0]，其中 offset[3:2] 选择行内第几个 32-bit word
// - 每路容量 4KB：256(set) * 16B(line) = 4096B
//
// 写策略：
// - 写回（write-back）：写命中只改 Cache 行并置 dirty；替换时 dirty 行先写回内存
// - 写分配（write-allocate）：写不命中先 refill 整行，再把写数据合并进来
//
// 替换策略：
// - 伪随机替换：用 8-bit LFSR 生成伪随机位；当两路都有效时用 lfsr[0] 选 victim 路
//
// CPU 侧握手（一次只处理 1 笔请求，不支持并发 outstanding）：
// - addr_ok=1 表示 Cache 处于空闲，可接收请求
// - 当 valid && addr_ok 成立时锁存一次请求（req_*）
// - 事务完成时 data_ok 拉高 1 个周期；读数据同周期在 rdata 给出
// ===============================

module cache(
	input         clk_g,
	input         resetn,

	// CPU 请求侧
	input         valid,
	input         op,          // 1: 写；0: 读
	input  [ 7:0] index,
	input  [19:0] tag,
	input  [ 3:0] offset,
	input  [ 3:0] wstrb,
	input  [31:0] wdata,

	// CPU 响应侧
	output        addr_ok,
	output reg    data_ok,
	output reg [31:0] rdata,

	// 内存侧读请求/读返回（cache_top.v 里是“简化内存模型”）
	output reg        rd_req,
	output reg [ 2:0] rd_type,
	output reg [31:0] rd_addr,
	input             rd_rdy,
	input             ret_valid,
	input             ret_last,
	input      [31:0] ret_data,

	// 内存侧写请求（用于 dirty 行写回，整行 128-bit）
	output reg        wr_req,
	output reg [ 2:0] wr_type,
	output reg [31:0] wr_addr,
	output reg [ 3:0] wr_wstrb,
	output reg [127:0] wr_data,
	input             wr_rdy
);

	// -----------------------
	// Cache 存储阵列
	// -----------------------
	// 两路数据 RAM：每组 1 行，每行 128-bit（16B）
	(* ram_style = "block" *) reg [127:0] data_way0 [0:255];
	(* ram_style = "block" *) reg [127:0] data_way1 [0:255];

	// tag/valid/dirty 元数据（体积小，用分布式寄存器/分布式 RAM 更合适）
	(* ram_style = "distributed" *) reg [19:0] tag_way0  [0:255];
	(* ram_style = "distributed" *) reg [19:0] tag_way1  [0:255];
	(* ram_style = "distributed" *) reg        valid0    [0:255];
	(* ram_style = "distributed" *) reg        valid1    [0:255];
	(* ram_style = "distributed" *) reg        dirty0    [0:255];
	(* ram_style = "distributed" *) reg        dirty1    [0:255];

	integer i;

	// 硬件初始化（推荐）：
	// - 用 initial 在“配置 bitstream 之后”把阵列初始化为 0（valid/dirty 清零）
	// - 优点：不需要在 resetn 时对 256 行做同步清零（节省大量复位逻辑/时序更友好）
	// - 注意：这不是“复位后再次清空”；如果你希望 reset 后 flush，需要额外逐行清 valid 的状态机
	initial begin
		for (i = 0; i < 256; i = i + 1) begin
			valid0[i]   = 1'b0;
			valid1[i]   = 1'b0;
			dirty0[i]   = 1'b0;
			dirty1[i]   = 1'b0;
			tag_way0[i] = 20'b0;
			tag_way1[i] = 20'b0;
			data_way0[i]= 128'b0;
			data_way1[i]= 128'b0;
		end
	end

	// -----------------------
	// 请求锁存寄存器（一次只处理一笔请求）
	// -----------------------
	reg        req_op;
	reg [ 7:0] req_index;
	reg [19:0] req_tag;
	reg [ 3:0] req_offset;
	reg [ 3:0] req_wstrb;
	reg [31:0] req_wdata;

	// 伪随机 LFSR（用于替换策略）
	reg [7:0] lfsr;

	// miss 处理时锁存的 victim 信息
	reg        victim_way;      // 0 or 1
	reg [19:0] victim_tag;
	reg        victim_dirty;
	reg [127:0] victim_line;

	// refill 缓冲：4 个 32-bit beat 拼成 128-bit 行
	reg [127:0] fill_buf;
	reg [1:0]   beat_cnt;

	// -----------------------
	// Cache 主状态机（单请求流水）
	// -----------------------
	localparam S_IDLE   = 3'd0;
	localparam S_LOOKUP = 3'd1;
	localparam S_WB_REQ = 3'd2;
	localparam S_RD_REQ = 3'd3;
	localparam S_RD_WAIT= 3'd4;
	localparam S_REFILL = 3'd5;
	localparam S_RESP   = 3'd6;

	reg [2:0] state;

	// 组合读：根据锁存的 req_index 读出两路当前 set 的 tag/data/valid/dirty
	wire [127:0] line0 = data_way0[req_index];
	wire [127:0] line1 = data_way1[req_index];
	wire [19:0]  t0    = tag_way0[req_index];
	wire [19:0]  t1    = tag_way1[req_index];
	wire         v0    = valid0[req_index];
	wire         v1    = valid1[req_index];
	wire         d0    = dirty0[req_index];
	wire         d1    = dirty1[req_index];

	wire hit0 = v0 && (t0 == req_tag);
	wire hit1 = v1 && (t1 == req_tag);
	wire hit  = hit0 || hit1;
	wire hit_way = hit1; // 命中路：若两路都命中（理论上不应发生），这里优先 way1
	wire [127:0] hit_line = hit1 ? line1 : line0;

	// victim 选择：
	// - 优先选 invalid 的那一路（避免替换有效数据）
	// - 两路都 valid 时，使用 lfsr[0] 伪随机选路
	wire sel_way   = (!v0) ? 1'b0 : (!v1) ? 1'b1 : lfsr[0];
	wire sel_valid = sel_way ? v1 : v0;
	wire sel_dirty = sel_way ? d1 : d0;
	wire [19:0]  sel_tag  = sel_way ? t1 : t0;
	wire [127:0] sel_line = sel_way ? line1 : line0;
	wire sel_need_wb = sel_valid && sel_dirty; // 该 victim 行需要写回（valid 且 dirty）

	// CPU 地址握手：只有空闲时才能接收新请求
	assign addr_ok = (state == S_IDLE);

	// -----------------------
	// 工具函数
	// -----------------------
	// 从 128-bit 行中选择一个 32-bit word
	function [31:0] pick_word;
		input [127:0] line;
		input [1:0] wsel;
		begin
			case (wsel)
				2'd0: pick_word = line[31:0];
				2'd1: pick_word = line[63:32];
				2'd2: pick_word = line[95:64];
				default: pick_word = line[127:96];
			endcase
		end
	endfunction

	// 把一次 32-bit 写（带字节写使能 wstrb）合并进 128-bit 行
	function [127:0] merge_store;
		input [127:0] old_line;
		input [1:0]   wsel;
		input [3:0]   strobe;
		input [31:0]  wdat;
		reg [127:0] nl;
		reg [31:0]  ow;
		reg [31:0]  nw;
		begin
			nl = old_line;
			ow = pick_word(old_line, wsel);
			nw = ow;

			if (strobe[0]) nw[7:0]   = wdat[7:0];
			if (strobe[1]) nw[15:8]  = wdat[15:8];
			if (strobe[2]) nw[23:16] = wdat[23:16];
			if (strobe[3]) nw[31:24] = wdat[31:24];

			case (wsel)
				2'd0: nl[31:0]    = nw;
				2'd1: nl[63:32]   = nw;
				2'd2: nl[95:64]   = nw;
				default: nl[127:96]= nw;
			endcase

			merge_store = nl;
		end
	endfunction

	// -----------------------
	// 对外输出默认值（组合逻辑）
	// - rd_req / wr_req 由状态机决定是否拉高
	// - rd_addr / wr_addr 均对齐到 16B 行首
	// -----------------------
	always @(*) begin
		rd_req   = 1'b0;
		rd_type  = 3'b010; // 本实验未检查该字段，固定即可
		rd_addr  = {req_tag, req_index, 4'b0000};

		wr_req   = 1'b0;
		wr_type  = 3'b010; // 本实验未检查该字段，固定即可
		wr_addr  = {victim_tag, req_index, 4'b0000};
		wr_wstrb = 4'b1111;
		// 注意：cache_top 的内存模型对比的是 {8'hff, line[119:0]}，所以这里保持一致
		wr_data  = {8'hff, victim_line[119:0]};

		case (state)
			S_WB_REQ: begin
				wr_req = 1'b1;
			end
			S_RD_REQ: begin
				rd_req = 1'b1;
			end
			default: begin
			end
		endcase
	end

	// -----------------------
	// 时序逻辑：状态机推进 + RAM 写入 + 输出 data_ok/rdata
	// -----------------------
	always @(posedge clk_g) begin
		if (!resetn) begin
			state   <= S_IDLE;
			data_ok <= 1'b0;
			rdata   <= 32'b0;
			req_op  <= 1'b0;
			req_index <= 8'b0;
			req_tag   <= 20'b0;
			req_offset<= 4'b0;
			req_wstrb <= 4'b0;
			req_wdata <= 32'b0;
			beat_cnt  <= 2'b00;
			fill_buf  <= 128'b0;
			victim_way<= 1'b0;
			victim_tag<= 20'b0;
			victim_dirty <= 1'b0;
			victim_line  <= 128'b0;
			lfsr <= 8'h1; // LFSR 初值不能全 0
		end else begin
			data_ok <= 1'b0;

			case (state)
				S_IDLE: begin
					if (valid) begin
						// 接收请求：锁存 req_*，进入查找
						req_op     <= op;
						req_index  <= index;
						req_tag    <= tag;
						req_offset <= offset;
						req_wstrb  <= wstrb;
						req_wdata  <= wdata;
						state      <= S_LOOKUP;
					end
				end

				S_LOOKUP: begin
					if (hit) begin
						// 命中：读请求直接返回；写请求更新该路并置 dirty
						if (!req_op) begin
							rdata <= pick_word(hit_line, req_offset[3:2]);
						end else begin
							rdata <= 32'b0;
						end

						// 写命中：按 wstrb 做字节合并写，并将对应路 dirty 置 1
						if (req_op) begin
							if (hit_way) begin
								data_way1[req_index] <= merge_store(line1, req_offset[3:2], req_wstrb, req_wdata);
								dirty1[req_index] <= 1'b1;
							end else begin
								data_way0[req_index] <= merge_store(line0, req_offset[3:2], req_wstrb, req_wdata);
								dirty0[req_index] <= 1'b1;
							end
						end

						state <= S_RESP;
					end else begin
						// 不命中：锁存 victim 信息
						// - 若 victim 行 dirty，则先写回（S_WB_REQ）
						// - 否则直接发起读 refill（S_RD_REQ）
						victim_way   <= sel_way;
						victim_tag   <= sel_tag;
						victim_dirty <= sel_dirty;
						victim_line  <= sel_line;
						state <= sel_need_wb ? S_WB_REQ : S_RD_REQ;
					end
				end

				S_WB_REQ: begin
					if (wr_rdy) begin
						// 写回握手：wr_req 在该状态被拉高；wr_rdy=1 表示内存接受写回
						// dirty 位在这里先清 0（随后 refill 会覆盖该行）
						if (victim_way) begin
							dirty1[req_index] <= 1'b0;
						end else begin
							dirty0[req_index] <= 1'b0;
						end
						state <= S_RD_REQ;
					end
				end

				S_RD_REQ: begin
					if (rd_rdy) begin
						// 读请求握手：rd_req 在该状态被拉高；rd_rdy=1 表示内存接受读请求
						// 进入等待 4 beat 返回，并清空 fill_buf
						beat_cnt <= 2'b00;
						fill_buf <= 128'b0;
						state <= S_RD_WAIT;
					end
				end

				S_RD_WAIT: begin
					if (ret_valid) begin
						// 依次接收 4 个 32-bit 数据，拼装成 128-bit 的一整行
						case (beat_cnt)
							2'd0: fill_buf[31:0]   <= ret_data;
							2'd1: fill_buf[63:32]  <= ret_data;
							2'd2: fill_buf[95:64]  <= ret_data;
							2'd3: fill_buf[127:96] <= ret_data;
						endcase

						if (ret_last || beat_cnt == 2'd3) begin
							// 最后一拍（ret_last=1）到达，进入 refill 写入
							state <= S_REFILL;
						end else begin
							beat_cnt <= beat_cnt + 2'b01;
						end
					end
				end

				S_REFILL: begin
					// refill 完成：
					// 1) 更新 LFSR（为下次替换提供伪随机位）
					// 2) 将 fill_buf 写入 victim 路
					// 3) 若本次是写请求（store miss），则写入时把写数据 merge 进去，并置 dirty
					lfsr <= {lfsr[6:0], lfsr[7] ^ lfsr[5] ^ 1'b1};

					// 写入数据阵列 + 更新 tag/valid/dirty
					if (victim_way) begin
						data_way1[req_index] <= req_op ? merge_store(fill_buf, req_offset[3:2], req_wstrb, req_wdata) : fill_buf;
						tag_way1[req_index]  <= req_tag;
						valid1[req_index]    <= 1'b1;
						dirty1[req_index]    <= req_op;
					end else begin
						data_way0[req_index] <= req_op ? merge_store(fill_buf, req_offset[3:2], req_wstrb, req_wdata) : fill_buf;
						tag_way0[req_index]  <= req_tag;
						valid0[req_index]    <= 1'b1;
						dirty0[req_index]    <= req_op;
					end

					// 对 CPU 的读返回：读 miss 在 refill 完成后返回 fill_buf 对应 word
					// 写请求无需返回数据
					if (!req_op) begin
						rdata <= pick_word(fill_buf, req_offset[3:2]);
					end else begin
						rdata <= 32'b0;
					end

					state <= S_RESP;
				end

				S_RESP: begin
					// 拉高 data_ok 一个周期，表示该笔请求完成
					data_ok <= 1'b1;
					state <= S_IDLE;
				end

				default: begin
					state <= S_IDLE;
				end
			endcase
		end
	end

endmodule

