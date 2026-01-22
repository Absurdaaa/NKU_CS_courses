module tlb
#(
  parameter TLBNUM = 16  // TLB表项数量，默认16项，可配置
)
(
  input clk,
  // 查找端口0（专供取指阶段使用）
  input[18:0]               s0_vpn2,
  input                     s0_odd_page,
  input[7:0]                s0_asid,
  output                    s0_found,
  output [$clog2(TLBNUM)-1:0] s0_index,
  output [19:0]             s0_pfn,
  output [2:0]              s0_c,
  output                    s0_d,
  output                    s0_v,

  // 查找端口1（专供访存阶段使用，支持TLBP指令复用）
  input[18:0]               s1_vpn2,
  input                     s1_odd_page,
  input[7:0]                s1_asid,
  output                    s1_found,
  output [$clog2(TLBNUM)-1:0] s1_index,
  output [19:0]             s1_pfn,
  output [2:0]              s1_c,
  output                    s1_d,
  output                    s1_v,

  // 独立写端口（支持TLBWI指令）
  input                     we,
  input [$clog2(TLBNUM)-1:0] w_index,
  input[18:0]               w_vpn2,
  input[7:0]                w_asid,
  input                     w_g,
  input[19:0]               w_pfn0,
  input[2:0]                w_c0,
  input                     w_d0,
  input                     w_v0,
  input[19:0]               w_pfn1,
  input[2:0]                w_c1,
  input                     w_d1,
  input                     w_v1,

  // 独立读端口（支持TLBR指令）
  input [$clog2(TLBNUM)-1:0] r_index,
  output[18:0]              r_vpn2,
  output[7:0]               r_asid,
  output                    r_g,
  output[19:0]              r_pfn0,
  output[2:0]               r_c0,
  output                    r_d0,
  output                    r_v0,
  output[19:0]              r_pfn1,
  output[2:0]               r_c1,
  output                    r_d1,
  output                    r_v1
);

  // TLB存储阵列：对应实验指导书的二维组织结构
  // 第一部分（参与读写+查找比较）：vpn2、asid、g
  reg[18:0]  tlb_vpn2[TLBNUM-1:0];
  reg[7:0]   tlb_asid[TLBNUM-1:0];
  reg        tlb_g[TLBNUM-1:0];
  // 第二部分（仅参与读写，不参与查找比较）：pfn0/c0/d0/v0、pfn1/c1/d1/v1
  reg[19:0]  tlb_pfn0[TLBNUM-1:0];
  reg[2:0]   tlb_c0[TLBNUM-1:0];
  reg        tlb_d0[TLBNUM-1:0];
  reg        tlb_v0[TLBNUM-1:0];
  reg[19:0]  tlb_pfn1[TLBNUM-1:0];
  reg[2:0]   tlb_c1[TLBNUM-1:0];
  reg        tlb_d1[TLBNUM-1:0];
  reg        tlb_v1[TLBNUM-1:0];

  // 整数变量，用于遍历TLB表项
  integer i;

  // ------------------------------
  // 1. 独立写端口逻辑（时序逻辑，时钟同步，支持TLBWI指令）
  // 功能：在we使能时，将写端口数据写入w_index指定的TLB表项
  // ------------------------------
  always @(posedge clk) begin
    if (we) begin  // 写使能有效时执行写入操作
      tlb_vpn2[w_index]  <= w_vpn2;
      tlb_asid[w_index]  <= w_asid;
      tlb_g[w_index]     <= w_g;
      tlb_pfn0[w_index]  <= w_pfn0;
      tlb_c0[w_index]    <= w_c0;
      tlb_d0[w_index]    <= w_d0;
      tlb_v0[w_index]    <= w_v0;
      tlb_pfn1[w_index]  <= w_pfn1;
      tlb_c1[w_index]    <= w_c1;
      tlb_d1[w_index]    <= w_d1;
      tlb_v1[w_index]    <= w_v1;
    end
  end

  // ------------------------------
  // 2. 独立读端口逻辑（组合逻辑，无时钟延迟，支持TLBR指令）
  // 功能：根据r_index索引，直接读取对应TLB表项的所有信息
  // ------------------------------
  assign r_vpn2  = tlb_vpn2[r_index];
  assign r_asid  = tlb_asid[r_index];
  assign r_g     = tlb_g[r_index];
  assign r_pfn0  = tlb_pfn0[r_index];
  assign r_c0    = tlb_c0[r_index];
  assign r_d0    = tlb_d0[r_index];
  assign r_v0    = tlb_v0[r_index];
  assign r_pfn1  = tlb_pfn1[r_index];
  assign r_c1    = tlb_c1[r_index];
  assign r_d1    = tlb_d1[r_index];
  assign r_v1    = tlb_v1[r_index];

  // ------------------------------
  // 3. 查找端口0逻辑（组合逻辑，并行查找，专供取指阶段）
  // 功能：匹配s0_vpn2 + s0_asid（或g=1），输出命中状态及属性信息
  // ------------------------------
  // 定义寄存器存储查找结果（组合逻辑内部使用）
  reg                    s0_found_r;
  reg [$clog2(TLBNUM)-1:0] s0_index_r;
  reg [19:0]             s0_pfn_r;
  reg [2:0]              s0_c_r;
  reg                    s0_d_r;
  reg                    s0_v_r;

  always @(*) begin
    // 初始状态：未命中，索引置0，属性置默认值
    s0_found_r  = 1'b0;
    s0_index_r  = {($clog2(TLBNUM)){1'b0}};
    s0_pfn_r    = 20'd0;
    s0_c_r      = 3'd0;
    s0_d_r      = 1'b0;
    s0_v_r      = 1'b0;

    // 遍历所有TLB表项，进行并行查找匹配
    for (i = 0; i < TLBNUM; i = i + 1) begin
      // 匹配条件：表项VPN2一致 + （全局位有效 或 ASID一致）
      if (tlb_vpn2[i] == s0_vpn2 && (tlb_g[i] || (tlb_asid[i] == s0_asid))) begin
        s0_found_r  = 1'b1;        // 置位命中标志
        s0_index_r  = i[$clog2(TLBNUM)-1:0];  // 记录命中索引

        // 根据奇数页标志选择对应属性（0选pfn0/c0/d0/v0，1选pfn1/c1/d1/v1）
        if (s0_odd_page == 1'b0) begin
          s0_pfn_r  = tlb_pfn0[i];
          s0_c_r    = tlb_c0[i];
          s0_d_r    = tlb_d0[i];
          s0_v_r    = tlb_v0[i];
        end else begin
          s0_pfn_r  = tlb_pfn1[i];
          s0_c_r    = tlb_c1[i];
          s0_d_r    = tlb_d1[i];
          s0_v_r    = tlb_v1[i];
        end
      end
    end
  end

  // 将寄存器结果赋值给输出端口
  assign s0_found = s0_found_r;
  assign s0_index = s0_index_r;
  assign s0_pfn   = s0_pfn_r;
  assign s0_c     = s0_c_r;
  assign s0_d     = s0_d_r;
  assign s0_v     = s0_v_r;

  // ------------------------------
  // 4. 查找端口1逻辑（组合逻辑，并行查找，专供访存阶段+TLBP指令复用）
  // 功能：与端口0逻辑一致，独立并行工作，支持TLBP指令的s1_index输出
  // ------------------------------
  // 定义寄存器存储查找结果（组合逻辑内部使用）
  reg                    s1_found_r;
  reg [$clog2(TLBNUM)-1:0] s1_index_r;
  reg [19:0]             s1_pfn_r;
  reg [2:0]              s1_c_r;
  reg                    s1_d_r;
  reg                    s1_v_r;

  always @(*) begin
    // 初始状态：未命中，索引置0，属性置默认值
    s1_found_r  = 1'b0;
    s1_index_r  = {($clog2(TLBNUM)){1'b0}};
    s1_pfn_r    = 20'd0;
    s1_c_r      = 3'd0;
    s1_d_r      = 1'b0;
    s1_v_r      = 1'b0;

    // 遍历所有TLB表项，进行并行查找匹配
    for (i = 0; i < TLBNUM; i = i + 1) begin
      // 匹配条件：表项VPN2一致 + （全局位有效 或 ASID一致）
      if (tlb_vpn2[i] == s1_vpn2 && (tlb_g[i] || (tlb_asid[i] == s1_asid))) begin
        s1_found_r  = 1'b1;        // 置位命中标志
        s1_index_r  = i[$clog2(TLBNUM)-1:0];  // 记录命中索引（供TLBP指令使用）

        // 根据奇数页标志选择对应属性（0选pfn0/c0/d0/v0，1选pfn1/c1/d1/v1）
        if (s1_odd_page == 1'b0) begin
          s1_pfn_r  = tlb_pfn0[i];
          s1_c_r    = tlb_c0[i];
          s1_d_r    = tlb_d0[i];
          s1_v_r    = tlb_v0[i];
        end else begin
          s1_pfn_r  = tlb_pfn1[i];
          s1_c_r    = tlb_c1[i];
          s1_d_r    = tlb_d1[i];
          s1_v_r    = tlb_v1[i];
        end
      end
    end
  end

  // 将寄存器结果赋值给输出端口
  assign s1_found = s1_found_r;
  assign s1_index = s1_index_r;
  assign s1_pfn   = s1_pfn_r;
  assign s1_c     = s1_c_r;
  assign s1_d     = s1_d_r;
  assign s1_v     = s1_v_r;

endmodule