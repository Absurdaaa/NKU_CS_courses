`include "mycpu.h"

module wb_stage(
    input                           clk           ,
    input                           reset         ,
    //allowin
    output                          ws_allowin    ,
    //from ms
    input                           ms_to_ws_valid,
    input  [`MS_TO_WS_BUS_WD -1:0]  ms_to_ws_bus  ,
    //to rf: for write back
    output [`WS_TO_RF_BUS_WD -1:0]  ws_to_rf_bus  ,
    //trace debug interface
    output [31:0] debug_wb_pc     ,
    output [ 3:0] debug_wb_rf_wen ,
    output [ 4:0] debug_wb_rf_wnum,
    output [31:0] debug_wb_rf_wdata,

    //block
    output                          ws_inst_mfc0_o,
    output [4:0]                    ws_rf_dest    ,
    //exception
    output                          ws_eret  ,
    output                          ws_ex_o       ,
    output [31:0]                   cp0_epc       ,
    output [31:0]                   cp0_status    ,
    output [31:0]                   cp0_cause,

    // expose tlb-related cp0 regs to core
    output [31:0]                   cp0_index,
    output [31:0]                   cp0_entryhi,
    output [31:0]                   cp0_entrylo0,
    output [31:0]                   cp0_entrylo1,

    // flush/refetch after TLBR/TLBWI commit
    output                          ws_tlb_flush,
    output [31:0]                   ws_tlb_flush_pc,

    // tlb rdata from core (TLBR)
    input  [18:0]                   tlb_r_vpn2,
    input  [7:0]                    tlb_r_asid,
    input                           tlb_r_g,
    input  [19:0]                   tlb_r_pfn0,
    input  [2:0]                    tlb_r_c0,
    input                           tlb_r_d0,
    input                           tlb_r_v0,
    input  [19:0]                   tlb_r_pfn1,
    input  [2:0]                    tlb_r_c1,
    input                           tlb_r_d1,
    input                           tlb_r_v1,

    // tlb write port to core (TLBWI)
    output                          tlb_we,
    output [3:0]                    tlb_w_index,
    output [18:0]                   tlb_w_vpn2,
    output [7:0]                    tlb_w_asid,
    output                          tlb_w_g,
    output [19:0]                   tlb_w_pfn0,
    output [2:0]                    tlb_w_c0,
    output                          tlb_w_d0,
    output                          tlb_w_v0,
    output [19:0]                   tlb_w_pfn1,
    output [2:0]                    tlb_w_c1,
    output                          tlb_w_d1,
    output                          tlb_w_v1
);

reg         ws_valid;
wire        ws_ready_go;

reg [`MS_TO_WS_BUS_WD -1:0] ms_to_ws_bus_r;
wire [ 3:0] ws_gr_strb;
wire [ 4:0] ws_dest;
wire [31:0] ws_final_result;
wire [31:0] ws_pc;

wire        ws_bd;
wire        ws_inst_eret;
wire        ws_inst_syscall;  
wire        ws_inst_mtc0;
wire [7:0]  cp0_addr;
wire [4:0]      ws_excode;
wire [31:0]     ws_badvaddr;

wire        ws_inst_tlbp;
wire        ws_inst_tlbwi;
wire        ws_inst_tlbr;
wire        ws_tlbp_found;
wire [3:0]  ws_tlbp_index;

assign {
    ws_tlbp_found   ,  //131:131
    ws_tlbp_index   ,  //130:127
    ws_inst_tlbp    ,  //126:126
    ws_inst_tlbwi   ,  //125:125
    ws_inst_tlbr    ,  //124:124
    ws_excode       ,  //123:119
    ws_badvaddr     ,  //118:87
    cp0_addr     ,  //86:79
    ws_ex           ,  //78:78
    ws_bd           ,  //77:77
    ws_inst_eret    ,  //76:76
    ws_inst_syscall ,  //75:75
    ws_inst_mfc0    ,  //74:74
    ws_inst_mtc0    ,  //73:73
    ws_gr_strb,         //72:69
    ws_dest,            //68:64
    ws_final_result,    //63:32
    ws_pc               //31:0
} = ms_to_ws_bus_r;



wire [ 3:0] rf_we;
wire [ 4:0] rf_waddr;
wire [31:0] rf_wdata;
assign ws_to_rf_bus = {
    rf_we,      //40:37
    rf_waddr,   //36:32
    rf_wdata    //31:0
};

assign ws_ready_go = 1'b1;
assign ws_allowin  = !ws_valid || ws_ready_go;
always @(posedge clk) begin
    if (reset) begin
        ws_valid <= 1'b0;
    end
    else if (ws_allowin) begin
        ws_valid <= ms_to_ws_valid;
    end

    if (ms_to_ws_valid && ws_allowin) begin
        ms_to_ws_bus_r <= ms_to_ws_bus;
    end
end


//lab8


wire [5:0]      ext_int_in;
wire [31:0]     cp0_rdata;
wire            cp0_we;
wire [31:0]     cp0_wdata;


wire [31:0]     ws_cp0_epc;
wire [31:0]     ws_cp0_status;
wire [31:0]     ws_cp0_cause;
wire [31:0]     ws_cp0_index;
wire [31:0]     ws_cp0_entryhi;
wire [31:0]     ws_cp0_entrylo0;
wire [31:0]     ws_cp0_entrylo1;

//valid
assign ws_inst_mfc0_o = ws_valid && ws_inst_mfc0;
assign ws_rf_dest = ws_valid ? ws_dest : 5'b0;

assign ws_ex_o = ws_valid && ws_ex;
// assign cp0_epc = ws_valid && ws_cp0_epc;
assign cp0_epc    = ws_cp0_epc;
assign cp0_cause  = ws_cp0_cause;
assign cp0_status = ws_cp0_status;

assign cp0_index    = ws_cp0_index;
assign cp0_entryhi  = ws_cp0_entryhi;
assign cp0_entrylo0 = ws_cp0_entrylo0;
assign cp0_entrylo1 = ws_cp0_entrylo1;


//init
assign ext_int_in = 6'b0;
assign ws_eret = ws_inst_eret && ws_valid;

// TODO
assign rf_we    = {4{ ws_valid & ~ws_ex }} & ws_gr_strb;
assign rf_waddr = ws_dest;
assign rf_wdata = ws_inst_mfc0 ? cp0_rdata :
                  ws_final_result;

// debug info generate
assign debug_wb_pc       = ws_pc;
assign debug_wb_rf_wen   = rf_we;
assign debug_wb_rf_wnum  = ws_dest;
assign debug_wb_rf_wdata = rf_wdata;

assign cp0_we = ws_inst_mtc0 && ws_valid && !ws_ex;
assign cp0_wdata = ws_final_result;

// TLB ops commit
wire ws_tlbp_commit;
wire ws_tlbr_commit;
wire ws_tlbwi_commit;
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
assign tlb_w_pfn0  = ws_cp0_entrylo0[25:6];
assign tlb_w_c0    = ws_cp0_entrylo0[5:3];
assign tlb_w_d0    = ws_cp0_entrylo0[2];
assign tlb_w_v0    = ws_cp0_entrylo0[1];
assign tlb_w_pfn1  = ws_cp0_entrylo1[25:6];
assign tlb_w_c1    = ws_cp0_entrylo1[5:3];
assign tlb_w_d1    = ws_cp0_entrylo1[2];
assign tlb_w_v1    = ws_cp0_entrylo1[1];

cp0 u_cp0(
    .clk                (clk),
    .rst                (reset),
    
    .wb_ex              (ws_ex),
    .wb_bd              (ws_bd),
    .wb_excode          (ws_excode),
    .wb_pc              (ws_pc),
    .wb_badvaddr        (ws_badvaddr),
    .ws_eret            (ws_eret),
    .ext_int_in         (ext_int_in),

    .cp0_addr           (cp0_addr),
    .cp0_rdata          (cp0_rdata),
    .mtc0_we            (cp0_we),
    .cp0_wdata          (cp0_wdata),

    .tlbp_we             (ws_tlbp_commit),
    .tlbp_found          (ws_tlbp_found),
    .tlbp_index          (ws_tlbp_index),

    .tlbr_we             (ws_tlbr_commit),
    .tlbr_vpn2           (tlb_r_vpn2),
    .tlbr_asid           (tlb_r_asid),
    .tlbr_g              (tlb_r_g),
    .tlbr_pfn0           (tlb_r_pfn0),
    .tlbr_c0             (tlb_r_c0),
    .tlbr_d0             (tlb_r_d0),
    .tlbr_v0             (tlb_r_v0),
    .tlbr_pfn1           (tlb_r_pfn1),
    .tlbr_c1             (tlb_r_c1),
    .tlbr_d1             (tlb_r_d1),
    .tlbr_v1             (tlb_r_v1),
  
    .cp0_epc            (ws_cp0_epc),  
    .cp0_status         (ws_cp0_status),
    .cp0_cause          (ws_cp0_cause),
    .cp0_index          (ws_cp0_index),
    .cp0_entryhi        (ws_cp0_entryhi),
    .cp0_entrylo0       (ws_cp0_entrylo0),
    .cp0_entrylo1       (ws_cp0_entrylo1)
);

endmodule
