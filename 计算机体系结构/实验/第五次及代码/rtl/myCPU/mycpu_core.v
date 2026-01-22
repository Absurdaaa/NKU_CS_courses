`include "mycpu.h"
module mycpu_core(
    input         clk,
    input         resetn,
    // inst sram interface
    output        inst_sram_req,
    output        inst_sram_wr,
    output [ 1:0] inst_sram_size,
    output [31:0] inst_sram_addr,
    output [ 3:0] inst_sram_wstrb,
    output [31:0] inst_sram_wdata,
    input         inst_sram_addr_ok,
    input         inst_sram_data_ok,
    input  [31:0] inst_sram_rdata,
    // data sram interface
    output        data_sram_req,
    output        data_sram_wr,
    output [ 1:0] data_sram_size,
    output [31:0] data_sram_addr,
    output [ 3:0] data_sram_wstrb,
    output [31:0] data_sram_wdata,
    input         data_sram_addr_ok,
    input         data_sram_data_ok,
    input  [31:0] data_sram_rdata,

    // memory segment attribute (for cache/bypass mux in top)
    output        inst_cached,
    output        data_cached,
    // trace debug interface
    output [31:0] debug_wb_pc,
    output [ 3:0] debug_wb_rf_wen,
    output [ 4:0] debug_wb_rf_wnum,
    output [31:0] debug_wb_rf_wdata
);
reg         reset;
always @(posedge clk) reset <= ~resetn;

wire         fs_allowin;
wire         ds_allowin;
wire         es_allowin;
wire         ms_allowin;
wire         ws_allowin;
wire         pfs_to_fs_valid;
wire         fs_to_ds_valid;
wire         ds_to_es_valid;
wire         es_to_ms_valid;
wire         ms_to_ws_valid;
wire [`PFS_TO_FS_BUS_WD -1:0] pfs_to_fs_bus;
wire [`FS_TO_DS_BUS_WD  -1:0] fs_to_ds_bus;
wire [`DS_TO_ES_BUS_WD  -1:0] ds_to_es_bus;
wire [`ES_TO_MS_BUS_WD  -1:0] es_to_ms_bus;
wire [`MS_TO_WS_BUS_WD  -1:0] ms_to_ws_bus;
wire [`WS_TO_RF_BUS_WD  -1:0] ws_to_rf_bus;
wire [`BR_BUS_WD        -1:0] br_bus;
wire [`ES_FWD_BLK_BUS_WD -1:0] es_fwd_blk_bus;
wire [`MS_FWD_BLK_BUS_WD -1:0] ms_fwd_blk_bus;

wire        fs_inst_buff_full;
wire        fs_valid;
wire        ms_data_buff_full;

wire [31:0] cp0_epc;
wire        ws_ex;
wire        ws_eret;
wire        ws_tlb_flush;
wire [31:0] ws_tlb_flush_pc;
wire [4:0]  ws_rf_dest;
wire        ws_inst_mfc0;

wire        ms_ex;
wire        ms_eret;
wire        ms_inst_mfc0;
wire        es_inst_mfc0;
wire        es_mtc0_entryhi;
wire        ms_mtc0_entryhi;

wire [31:0] cp0_status;
wire [31:0] cp0_cause;
wire [31:0] cp0_index;
wire [31:0] cp0_entryhi;
wire [31:0] cp0_entrylo0;
wire [31:0] cp0_entrylo1;

// inst/data vaddr from stages (before translation)
wire [31:0] inst_sram_vaddr;
wire [31:0] data_sram_vaddr;

// tlb ports
wire        tlb_s0_found;
wire [3:0]  tlb_s0_index;
wire [19:0] tlb_s0_pfn;
wire [2:0]  tlb_s0_c;
wire        tlb_s0_d;
wire        tlb_s0_v;

wire [18:0] tlb_s1_vpn2;
wire        tlb_s1_odd_page;
wire [7:0]  tlb_s1_asid;
wire        tlb_s1_found;
wire [3:0]  tlb_s1_index;
wire [19:0] tlb_s1_pfn;
wire [2:0]  tlb_s1_c;
wire        tlb_s1_d;
wire        tlb_s1_v;

wire        tlb_we;
wire [3:0]  tlb_w_index;
wire [18:0] tlb_w_vpn2;
wire [7:0]  tlb_w_asid;
wire        tlb_w_g;
wire [19:0] tlb_w_pfn0;
wire [2:0]  tlb_w_c0;
wire        tlb_w_d0;
wire        tlb_w_v0;
wire [19:0] tlb_w_pfn1;
wire [2:0]  tlb_w_c1;
wire        tlb_w_d1;
wire        tlb_w_v1;

wire [18:0] tlb_r_vpn2;
wire [7:0]  tlb_r_asid;
wire        tlb_r_g;
wire [19:0] tlb_r_pfn0;
wire [2:0]  tlb_r_c0;
wire        tlb_r_d0;
wire        tlb_r_v0;
wire [19:0] tlb_r_pfn1;
wire [2:0]  tlb_r_c1;
wire        tlb_r_d1;
wire        tlb_r_v1;


// inst_sram
assign inst_sram_wr     = 1'b0;
assign inst_sram_size   = 2'h2;
assign inst_sram_wstrb  = 4'h0;
assign inst_sram_wdata  = 32'h0;

// vaddr->paddr translate (minimal: kseg0/kseg1 direct map, else TLB if found)
wire inst_direct_map;
assign inst_direct_map = (inst_sram_vaddr[31:29] == 3'b100) || (inst_sram_vaddr[31:29] == 3'b101);
wire inst_tlb_ok;
assign inst_tlb_ok   = tlb_s0_found & tlb_s0_v;
assign inst_sram_addr = inst_direct_map ? {3'b000, inst_sram_vaddr[28:0]} :
                       (inst_tlb_ok     ? {tlb_s0_pfn, inst_sram_vaddr[11:0]} : inst_sram_vaddr);

// segment attribute (kseg0 fixed cached)
wire inst_kseg0;
wire inst_kseg1;
assign inst_kseg0 = (inst_sram_vaddr[31:29] == 3'b100);
assign inst_kseg1 = (inst_sram_vaddr[31:29] == 3'b101);
assign inst_cached = inst_kseg0 ? 1'b1 :
                     inst_kseg1 ? 1'b0 :
                     (inst_tlb_ok && (tlb_s0_c != 3'b010));

wire        pfs_inst_waiting;
wire        fs_inst_waiting;
reg  [1:0]  inst_sram_discard;
wire        inst_sram_data_ok_discard;

always @ (posedge clk) begin
    if (reset) begin
        inst_sram_discard <= 2'b00;
    end else if (ws_ex || ws_eret || ws_tlb_flush) begin
        inst_sram_discard <= {pfs_inst_waiting, fs_inst_waiting};
    end else if (inst_sram_data_ok) begin
        if (inst_sram_discard == 2'b11) begin
            inst_sram_discard <= 2'b01;
        end else if (inst_sram_discard == 2'b01) begin
            inst_sram_discard <= 2'b00;
        end else if (inst_sram_discard == 2'b10) begin
            inst_sram_discard <= 2'b00;
        end
    end
end
assign inst_sram_data_ok_discard = inst_sram_data_ok && ~|inst_sram_discard;

// data_sram
wire        es_data_waiting;
wire        ms_data_waiting;
reg  [1:0]  data_sram_discard;
wire        data_sram_data_ok_discard;

always @ (posedge clk) begin
    if (reset) begin
        data_sram_discard <= 2'b00;
    end else if (ws_ex || ws_eret || ws_tlb_flush) begin
        data_sram_discard <= {es_data_waiting, ms_data_waiting};
    end else if (data_sram_data_ok) begin
        if (data_sram_discard == 2'b11) begin
            data_sram_discard <= 2'b01;
        end else if (data_sram_discard == 2'b01) begin
            data_sram_discard <= 2'b00;
        end else if (data_sram_discard == 2'b10) begin
            data_sram_discard <= 2'b00;
        end
    end
end
assign data_sram_data_ok_discard = data_sram_data_ok && ~|data_sram_discard;

// pre-IF stage
pre_if_stage pre_if_stage(
    .clk                    (clk),
    .reset                  (reset),
    // allowin
    .fs_allowin             (fs_allowin),
    // to fs
    .pfs_to_fs_valid        (pfs_to_fs_valid),
    .pfs_to_fs_bus          (pfs_to_fs_bus),
    // from fs
    .fs_inst_unable         (fs_inst_unable),
    // br_bus
    .br_bus                 (br_bus),
    .fs_valid               (fs_valid),
    // inst_ram interface
    .inst_sram_req          (inst_sram_req),
    .inst_sram_addr         (inst_sram_vaddr),
    .inst_sram_addr_ok      (inst_sram_addr_ok),
    .inst_sram_rdata        (inst_sram_rdata),
    .inst_sram_data_ok      (inst_sram_data_ok_discard),
    .pfs_inst_waiting       (pfs_inst_waiting),
    .ws_eret                (ws_eret),
    .ws_ex                  (ws_ex),
    .ws_tlb_flush            (ws_tlb_flush),
    .ws_tlb_flush_pc         (ws_tlb_flush_pc),
    .cp0_epc                (cp0_epc)
);

// IF stage
if_stage if_stage(
    .clk                    (clk),
    .reset                  (reset),
    //allowin
    .ds_allowin             (ds_allowin),
    .fs_allowin             (fs_allowin),
    // from pfs
    .pfs_to_fs_valid        (pfs_to_fs_valid),
    .pfs_to_fs_bus          (pfs_to_fs_bus),
    // to ds
    .fs_to_ds_valid         (fs_to_ds_valid),
    .fs_to_ds_bus           (fs_to_ds_bus),
    // to pfs
    .fs_inst_unable         (fs_inst_unable),
    .fs_valid_o             (fs_valid),
    // inst_ram interface
    .inst_sram_rdata        (inst_sram_rdata),
    .inst_sram_data_ok      (inst_sram_data_ok_discard),
    .fs_inst_waiting        (fs_inst_waiting),
    //exception
    .ws_ex                  (ws_ex),
    .ws_eret                (ws_eret),
    .ws_tlb_flush            (ws_tlb_flush),
    .cp0_epc                (cp0_epc)
);
// ID stage
id_stage id_stage(
    .clk            (clk            ),
    .reset          (reset          ),
    //allowin
    .es_allowin     (es_allowin     ),
    .ds_allowin     (ds_allowin     ),
    //from fs
    .fs_to_ds_valid (fs_to_ds_valid ),
    .fs_to_ds_bus   (fs_to_ds_bus   ),
    //to es
    .ds_to_es_valid (ds_to_es_valid ),
    .ds_to_es_bus   (ds_to_es_bus   ),
    //to fs
    .br_bus         (br_bus         ),
    //to rf: for write back
    .ws_to_rf_bus   (ws_to_rf_bus   ),
    // forward & block
    .es_fwd_blk_bus (es_fwd_blk_bus ),
    .ms_fwd_blk_bus (ms_fwd_blk_bus ),
    //exception & block
    .ws_ex          (ws_ex),
    .ws_eret     (ws_eret),
    .ws_tlb_flush    (ws_tlb_flush),
    .es_inst_mfc0   (es_inst_mfc0),
    .ms_inst_mfc0   (ms_inst_mfc0),
    .ws_inst_mfc0   (ws_inst_mfc0),
    .ws_rf_dest     (ws_rf_dest),
    .es_mtc0_entryhi (es_mtc0_entryhi),
    .ms_mtc0_entryhi (ms_mtc0_entryhi),
    .cp0_cause      (cp0_cause),
    .cp0_status     (cp0_status)
);
// EXE stage
exe_stage exe_stage(
    .clk                    (clk            ),
    .reset                  (reset          ),
    //allowin
    .ms_allowin             (ms_allowin     ),
    .es_allowin             (es_allowin     ),
    //from ds
    .ds_to_es_valid         (ds_to_es_valid ),
    .ds_to_es_bus           (ds_to_es_bus   ),
    //to ms
    .es_to_ms_valid         (es_to_ms_valid ),
    .es_to_ms_bus           (es_to_ms_bus   ),
    //from ms
    .ms_inst_unable         (ms_inst_unable ),
    // data sram interface
    .data_sram_req          (data_sram_req  ),
    .data_sram_wr           (data_sram_wr   ),
    .data_sram_size         (data_sram_size ),
    .data_sram_wdata        (data_sram_wdata),
    .data_sram_wstrb        (data_sram_wstrb),
    .data_sram_addr         (data_sram_vaddr ),
    .data_sram_addr_ok      (data_sram_addr_ok),
    .data_sram_rdata        (data_sram_rdata),
    .data_sram_data_ok      (data_sram_data_ok_discard),
    .es_data_waiting        (es_data_waiting),
    // forward & block
    .es_fwd_blk_bus         (es_fwd_blk_bus ),
    //exception & block
    .ws_ex                  (ws_ex),
    .ws_eret                (ws_eret),
    .ws_tlb_flush            (ws_tlb_flush),
    .ms_ex                  (ms_ex),
    .ms_eret                (ms_eret),
    .es_inst_mfc0_o         (es_inst_mfc0),
    .es_mtc0_entryhi_o      (es_mtc0_entryhi),

    .cp0_entryhi            (cp0_entryhi),
    .tlb_s1_found           (tlb_s1_found),
    .tlb_s1_index           (tlb_s1_index),
    .tlb_s1_vpn2            (tlb_s1_vpn2),
    .tlb_s1_odd_page        (tlb_s1_odd_page),
    .tlb_s1_asid            (tlb_s1_asid)
);
// MEM stage
mem_stage mem_stage(
    .clk                    (clk            ),
    .reset                  (reset          ),
    //allowin
    .ws_allowin             (ws_allowin     ),
    .ms_allowin             (ms_allowin     ),
    //from es
    .es_to_ms_valid         (es_to_ms_valid ),
    .es_to_ms_bus           (es_to_ms_bus   ),
    //to ws
    .ms_to_ws_valid         (ms_to_ws_valid ),
    .ms_to_ws_bus           (ms_to_ws_bus   ),
    //to es
    .ms_inst_unable         (ms_inst_unable ),
    //from data-sram
    .data_sram_rdata        (data_sram_rdata),
    .data_sram_data_ok      (data_sram_data_ok_discard),
    .ms_data_waiting        (ms_data_waiting),
    // forward & block
    .ms_fwd_blk_bus         (ms_fwd_blk_bus),
    //exception & block
    .ws_ex                  (ws_ex),
    .ws_eret                (ws_eret),
    .ws_tlb_flush            (ws_tlb_flush),
    .ms_ex_o                (ms_ex),
    .ms_eret                (ms_eret),
    .ms_inst_mfc0_o         (ms_inst_mfc0),
    .ms_mtc0_entryhi_o      (ms_mtc0_entryhi)
);
// WB stage
wb_stage wb_stage(
    .clk            (clk            ),
    .reset          (reset          ),
    //allowin
    .ws_allowin     (ws_allowin     ),
    //from ms
    .ms_to_ws_valid (ms_to_ws_valid ),
    .ms_to_ws_bus   (ms_to_ws_bus   ),
    //to rf: for write back
    .ws_to_rf_bus   (ws_to_rf_bus   ),
    //trace debug interface
    .debug_wb_pc      (debug_wb_pc      ),
    .debug_wb_rf_wen  (debug_wb_rf_wen  ),
    .debug_wb_rf_wnum (debug_wb_rf_wnum ),
    .debug_wb_rf_wdata(debug_wb_rf_wdata),
    //exception & block
    .ws_ex_o        (ws_ex),
    .ws_eret        (ws_eret),
    .ws_tlb_flush   (ws_tlb_flush),
    .ws_tlb_flush_pc(ws_tlb_flush_pc),
    .cp0_epc        (cp0_epc),
    .ws_inst_mfc0_o (ws_inst_mfc0),
    .ws_rf_dest     (ws_rf_dest),
    .cp0_cause      (cp0_cause),
        .cp0_status     (cp0_status),
        .cp0_index      (cp0_index),
        .cp0_entryhi    (cp0_entryhi),
        .cp0_entrylo0   (cp0_entrylo0),
        .cp0_entrylo1   (cp0_entrylo1),

        .tlb_r_vpn2     (tlb_r_vpn2),
        .tlb_r_asid     (tlb_r_asid),
        .tlb_r_g        (tlb_r_g),
        .tlb_r_pfn0     (tlb_r_pfn0),
        .tlb_r_c0       (tlb_r_c0),
        .tlb_r_d0       (tlb_r_d0),
        .tlb_r_v0       (tlb_r_v0),
        .tlb_r_pfn1     (tlb_r_pfn1),
        .tlb_r_c1       (tlb_r_c1),
        .tlb_r_d1       (tlb_r_d1),
        .tlb_r_v1       (tlb_r_v1),

        .tlb_we         (tlb_we),
        .tlb_w_index    (tlb_w_index),
        .tlb_w_vpn2     (tlb_w_vpn2),
        .tlb_w_asid     (tlb_w_asid),
        .tlb_w_g        (tlb_w_g),
        .tlb_w_pfn0     (tlb_w_pfn0),
        .tlb_w_c0       (tlb_w_c0),
        .tlb_w_d0       (tlb_w_d0),
        .tlb_w_v0       (tlb_w_v0),
        .tlb_w_pfn1     (tlb_w_pfn1),
        .tlb_w_c1       (tlb_w_c1),
        .tlb_w_d1       (tlb_w_d1),
        .tlb_w_v1       (tlb_w_v1)
);

// data vaddr->paddr translate (same rule as inst)
wire data_direct_map;
assign data_direct_map = (data_sram_vaddr[31:29] == 3'b100) || (data_sram_vaddr[31:29] == 3'b101);
wire data_tlb_ok;
assign data_tlb_ok = tlb_s1_found & tlb_s1_v & (~data_sram_wr | tlb_s1_d);
assign data_sram_addr  = data_direct_map ? {3'b000, data_sram_vaddr[28:0]} :
                                                (data_tlb_ok    ? {tlb_s1_pfn, data_sram_vaddr[11:0]} : data_sram_vaddr);

wire data_kseg0;
wire data_kseg1;
assign data_kseg0 = (data_sram_vaddr[31:29] == 3'b100);
assign data_kseg1 = (data_sram_vaddr[31:29] == 3'b101);
assign data_cached = data_kseg0 ? 1'b1 :
                     data_kseg1 ? 1'b0 :
                     (data_tlb_ok && (tlb_s1_c != 3'b010));

// TLB instance
tlb #(
    .TLBNUM(16)
) u_tlb (
    .clk        (clk),

    // s0: inst
    .s0_vpn2    (inst_sram_vaddr[31:13]),
    .s0_odd_page(inst_sram_vaddr[12]),
    .s0_asid    (cp0_entryhi[7:0]),
    .s0_found   (tlb_s0_found),
    .s0_index   (tlb_s0_index),
    .s0_pfn     (tlb_s0_pfn),
    .s0_c       (tlb_s0_c),
    .s0_d       (tlb_s0_d),
    .s0_v       (tlb_s0_v),

    // s1: data / tlbp
    .s1_vpn2    (tlb_s1_vpn2),
    .s1_odd_page(tlb_s1_odd_page),
    .s1_asid    (tlb_s1_asid),
    .s1_found   (tlb_s1_found),
    .s1_index   (tlb_s1_index),
    .s1_pfn     (tlb_s1_pfn),
    .s1_c       (tlb_s1_c),
    .s1_d       (tlb_s1_d),
    .s1_v       (tlb_s1_v),

    // write (TLBWI)
    .we         (tlb_we),
    .w_index    (tlb_w_index),
    .w_vpn2     (tlb_w_vpn2),
    .w_asid     (tlb_w_asid),
    .w_g        (tlb_w_g),
    .w_pfn0     (tlb_w_pfn0),
    .w_c0       (tlb_w_c0),
    .w_d0       (tlb_w_d0),
    .w_v0       (tlb_w_v0),
    .w_pfn1     (tlb_w_pfn1),
    .w_c1       (tlb_w_c1),
    .w_d1       (tlb_w_d1),
    .w_v1       (tlb_w_v1),

    // read (TLBR)
    .r_index    (cp0_index[3:0]),
    .r_vpn2     (tlb_r_vpn2),
    .r_asid     (tlb_r_asid),
    .r_g        (tlb_r_g),
    .r_pfn0     (tlb_r_pfn0),
    .r_c0       (tlb_r_c0),
    .r_d0       (tlb_r_d0),
    .r_v0       (tlb_r_v0),
    .r_pfn1     (tlb_r_pfn1),
    .r_c1       (tlb_r_c1),
    .r_d1       (tlb_r_d1),
    .r_v1       (tlb_r_v1)
);

endmodule
