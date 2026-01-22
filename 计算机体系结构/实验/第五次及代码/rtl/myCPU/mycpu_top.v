`include "mycpu.h"
module mycpu_top(
    input   [ 5:0]      int,
    input               aclk,
    input               aresetn,
    //axi interface
    //read request
    output  [ 3:0]      arid,
    output  [31:0]      araddr,
    output  [ 7:0]      arlen,
    output  [ 2:0]      arsize,
    output  [ 1:0]      arburst,
    output  [ 1:0]      arlock,
    output  [ 3:0]      arcache,
    output  [ 2:0]      arprot,
    output              arvalid,
    input               arready,

    //read response
    input   [ 3:0]      rid,
    input   [31:0]      rdata,
    input   [ 1:0]      rresp,
    input               rlast,
    input               rvalid,
    output              rready,

    //write request
    output  [ 3:0]      awid,
    output  [31:0]      awaddr,
    output  [ 7:0]      awlen,
    output  [ 2:0]      awsize,
    output  [ 1:0]      awburst,
    output  [ 1:0]      awlock,
    output  [ 3:0]      awcache,
    output  [ 2:0]      awprot,
    output              awvalid,
    input               awready,

    //write data
    output  [ 3:0]      wid,
    output  [31:0]      wdata,
    output  [ 3:0]      wstrb,
    output              wlast,
    output              wvalid,
    input               wready,

    //write response
    input   [ 3:0]      bid,
    input   [ 1:0]      bresp,
    input               bvalid,
    output              bready,
    
    // trace debug interface
    output [31:0] debug_wb_pc,
    output [ 3:0] debug_wb_rf_wen,
    output [ 4:0] debug_wb_rf_wnum,
    output [31:0] debug_wb_rf_wdata
);

// inst sram interface
    wire        inst_sram_req;
    wire        inst_sram_wr;
    wire [ 1:0] inst_sram_size;
    wire [31:0] inst_sram_addr;
    wire [ 3:0] inst_sram_wstrb;
    wire [31:0] inst_sram_wdata;
    wire        inst_sram_addr_ok;
    wire        inst_sram_data_ok;
    wire [31:0] inst_sram_rdata;
    // data sram interface
    wire        data_sram_req;
    wire        data_sram_wr;
    wire [ 1:0] data_sram_size;
    wire [31:0] data_sram_addr;
    wire [ 3:0] data_sram_wstrb;
    wire [31:0] data_sram_wdata;
    wire        data_sram_addr_ok;
    wire        data_sram_data_ok;
    wire [31:0] data_sram_rdata;

    // segment attribute from core
    wire        inst_cached;
    wire        data_cached;

    // uncached bypass ports to transfer_bridge
    wire        uc_inst_sram_req;
    wire        uc_inst_sram_wr;
    wire [ 1:0] uc_inst_sram_size;
    wire [31:0] uc_inst_sram_addr;
    wire [ 3:0] uc_inst_sram_wstrb;
    wire [31:0] uc_inst_sram_wdata;
    wire        uc_inst_sram_addr_ok;
    wire        uc_inst_sram_data_ok;
    wire [31:0] uc_inst_sram_rdata;

    wire        uc_data_sram_req;
    wire        uc_data_sram_wr;
    wire [ 1:0] uc_data_sram_size;
    wire [31:0] uc_data_sram_addr;
    wire [ 3:0] uc_data_sram_wstrb;
    wire [31:0] uc_data_sram_wdata;
    wire        uc_data_sram_addr_ok;
    wire        uc_data_sram_data_ok;
    wire [31:0] uc_data_sram_rdata;

    // icache memory side
    wire        ic_rd_req;
    wire [ 2:0] ic_rd_type;
    wire [31:0] ic_rd_addr;
    wire        ic_rd_rdy;
    wire        ic_ret_valid;
    wire        ic_ret_last;
    wire [31:0] ic_ret_data;
    wire        ic_wr_req;
    wire [ 2:0] ic_wr_type;
    wire [31:0] ic_wr_addr;
    wire [ 3:0] ic_wr_wstrb;
    wire [127:0] ic_wr_data;
    wire        ic_wr_rdy;

    // dcache memory side
    wire        dc_rd_req;
    wire [ 2:0] dc_rd_type;
    wire [31:0] dc_rd_addr;
    wire        dc_rd_rdy;
    wire        dc_ret_valid;
    wire        dc_ret_last;
    wire [31:0] dc_ret_data;
    wire        dc_wr_req;
    wire [ 2:0] dc_wr_type;
    wire [31:0] dc_wr_addr;
    wire [ 3:0] dc_wr_wstrb;
    wire [127:0] dc_wr_data;
    wire        dc_wr_rdy;

    // shared cache burst to transfer_bridge
    wire        cache_rd_req;
    wire [ 2:0] cache_rd_type;
    wire [31:0] cache_rd_addr;
    wire        cache_rd_rdy;
    wire        cache_ret_valid;
    wire        cache_ret_last;
    wire [31:0] cache_ret_data;

    wire        cache_wr_req;
    wire [ 2:0] cache_wr_type;
    wire [31:0] cache_wr_addr;
    wire [ 3:0] cache_wr_wstrb;
    wire [127:0] cache_wr_data;
    wire        cache_wr_rdy;

mycpu_core u_mycpu_core(
    .clk                (aclk               ),
    .resetn             (aresetn            ),
    
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
    .data_sram_rdata    (data_sram_rdata    ),

    .inst_cached        (inst_cached        ),
    .data_cached        (data_cached        ),

    .debug_wb_pc        (debug_wb_pc        ),
    .debug_wb_rf_wen    (debug_wb_rf_wen    ),
    .debug_wb_rf_wnum   (debug_wb_rf_wnum   ),
    .debug_wb_rf_wdata  (debug_wb_rf_wdata  )
);

icache_top u_icache_top (
    .clk                (aclk               ),
    .resetn             (aresetn            ),

    .inst_sram_req       (inst_sram_req      ),
    .inst_sram_wr        (inst_sram_wr       ),
    .inst_sram_size      (inst_sram_size     ),
    .inst_sram_addr      (inst_sram_addr     ),
    .inst_sram_wstrb     (inst_sram_wstrb    ),
    .inst_sram_wdata     (inst_sram_wdata    ),
    .inst_cached         (inst_cached        ),

    .inst_sram_addr_ok   (inst_sram_addr_ok  ),
    .inst_sram_data_ok   (inst_sram_data_ok  ),
    .inst_sram_rdata     (inst_sram_rdata    ),

    .uc_inst_sram_req    (uc_inst_sram_req   ),
    .uc_inst_sram_wr     (uc_inst_sram_wr    ),
    .uc_inst_sram_size   (uc_inst_sram_size  ),
    .uc_inst_sram_addr   (uc_inst_sram_addr  ),
    .uc_inst_sram_wstrb  (uc_inst_sram_wstrb ),
    .uc_inst_sram_wdata  (uc_inst_sram_wdata ),
    .uc_inst_sram_addr_ok(uc_inst_sram_addr_ok),
    .uc_inst_sram_data_ok(uc_inst_sram_data_ok),
    .uc_inst_sram_rdata  (uc_inst_sram_rdata ),

    .rd_req              (ic_rd_req          ),
    .rd_type             (ic_rd_type         ),
    .rd_addr             (ic_rd_addr         ),
    .rd_rdy              (ic_rd_rdy          ),
    .ret_valid           (ic_ret_valid       ),
    .ret_last            (ic_ret_last        ),
    .ret_data            (ic_ret_data        ),

    .wr_req              (ic_wr_req          ),
    .wr_type             (ic_wr_type         ),
    .wr_addr             (ic_wr_addr         ),
    .wr_wstrb            (ic_wr_wstrb        ),
    .wr_data             (ic_wr_data         ),
    .wr_rdy              (ic_wr_rdy          )
);

dcache_top u_dcache_top (
    .clk                (aclk               ),
    .resetn             (aresetn            ),

    .data_sram_req       (data_sram_req      ),
    .data_sram_wr        (data_sram_wr       ),
    .data_sram_size      (data_sram_size     ),
    .data_sram_addr      (data_sram_addr     ),
    .data_sram_wstrb     (data_sram_wstrb    ),
    .data_sram_wdata     (data_sram_wdata    ),
    .data_cached         (data_cached        ),

    .data_sram_addr_ok   (data_sram_addr_ok  ),
    .data_sram_data_ok   (data_sram_data_ok  ),
    .data_sram_rdata     (data_sram_rdata    ),

    .uc_data_sram_req    (uc_data_sram_req   ),
    .uc_data_sram_wr     (uc_data_sram_wr    ),
    .uc_data_sram_size   (uc_data_sram_size  ),
    .uc_data_sram_addr   (uc_data_sram_addr  ),
    .uc_data_sram_wstrb  (uc_data_sram_wstrb ),
    .uc_data_sram_wdata  (uc_data_sram_wdata ),
    .uc_data_sram_addr_ok(uc_data_sram_addr_ok),
    .uc_data_sram_data_ok(uc_data_sram_data_ok),
    .uc_data_sram_rdata  (uc_data_sram_rdata ),

    .rd_req              (dc_rd_req          ),
    .rd_type             (dc_rd_type         ),
    .rd_addr             (dc_rd_addr         ),
    .rd_rdy              (dc_rd_rdy          ),
    .ret_valid           (dc_ret_valid       ),
    .ret_last            (dc_ret_last        ),
    .ret_data            (dc_ret_data        ),

    .wr_req              (dc_wr_req          ),
    .wr_type             (dc_wr_type         ),
    .wr_addr             (dc_wr_addr         ),
    .wr_wstrb            (dc_wr_wstrb        ),
    .wr_data             (dc_wr_data         ),
    .wr_rdy              (dc_wr_rdy          )
);

// -----------------------------------------
// Shared cache burst arbitration (I$ vs D$)
// -----------------------------------------
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
                2'd1: begin
                    if (!ic_need && dc_need) cache_owner <= 2'd2;
                    else if (!ic_need && !dc_need) cache_owner <= 2'd0;
                end
                2'd2: begin
                    if (!dc_need && ic_need) cache_owner <= 2'd1;
                    else if (!dc_need && !ic_need) cache_owner <= 2'd0;
                end
                default: cache_owner <= 2'd0;
            endcase
        end
    end
end

assign cache_rd_req  = (cache_owner == 2'd1) ? ic_rd_req  : (cache_owner == 2'd2) ? dc_rd_req  : 1'b0;
assign cache_rd_type = (cache_owner == 2'd1) ? ic_rd_type : dc_rd_type;
assign cache_rd_addr = (cache_owner == 2'd1) ? ic_rd_addr : dc_rd_addr;

assign cache_wr_req   = (cache_owner == 2'd1) ? ic_wr_req   : (cache_owner == 2'd2) ? dc_wr_req   : 1'b0;
assign cache_wr_type  = (cache_owner == 2'd1) ? ic_wr_type  : dc_wr_type;
assign cache_wr_addr  = (cache_owner == 2'd1) ? ic_wr_addr  : dc_wr_addr;
assign cache_wr_wstrb = (cache_owner == 2'd1) ? ic_wr_wstrb : dc_wr_wstrb;
assign cache_wr_data  = (cache_owner == 2'd1) ? ic_wr_data  : dc_wr_data;

assign ic_rd_rdy = (cache_owner == 2'd1) ? cache_rd_rdy : 1'b0;
assign ic_wr_rdy = (cache_owner == 2'd1) ? cache_wr_rdy : 1'b0;
assign dc_rd_rdy = (cache_owner == 2'd2) ? cache_rd_rdy : 1'b0;
assign dc_wr_rdy = (cache_owner == 2'd2) ? cache_wr_rdy : 1'b0;

assign ic_ret_valid = (cache_owner == 2'd1) ? cache_ret_valid : 1'b0;
assign ic_ret_last  = (cache_owner == 2'd1) ? cache_ret_last  : 1'b0;
assign ic_ret_data  = cache_ret_data;

assign dc_ret_valid = (cache_owner == 2'd2) ? cache_ret_valid : 1'b0;
assign dc_ret_last  = (cache_owner == 2'd2) ? cache_ret_last  : 1'b0;
assign dc_ret_data  = cache_ret_data;

transfer_bridge u_transfer_bridge(
    .aclk               (aclk               ),
    .aresetn            (aresetn            ),

    .arid               (arid               ),
    .araddr             (araddr             ),
    .arlen              (arlen              ),
    .arsize             (arsize             ),
    .arburst            (arburst            ),
    .arlock             (arlock             ),
    .arcache            (arcache            ),
    .arprot             (arprot             ),
    .arvalid            (arvalid            ),
    .arready            (arready            ),

    .rid                (rid                ),
    .rdata              (rdata              ),
    .rresp              (rresp              ),
    .rlast              (rlast              ),
    .rvalid             (rvalid             ),
    .rready             (rready             ),

    .awid               (awid               ),
    .awaddr             (awaddr             ),
    .awlen              (awlen              ),
    .awsize             (awsize             ),
    .awburst            (awburst            ),
    .awlock             (awlock             ),
    .awcache            (awcache            ),
    .awprot             (awprot             ),
    .awvalid            (awvalid            ),
    .awready            (awready            ),

    .wid                (wid                ),
    .wdata              (wdata              ),
    .wstrb              (wstrb              ),
    .wlast              (wlast              ),
    .wvalid             (wvalid             ),
    .wready             (wready             ),

    .bid                (bid                ),
    .bresp              (bresp              ),
    .bvalid             (bvalid             ),
    .bready             (bready             ),

    .inst_sram_req      (uc_inst_sram_req   ),
    .inst_sram_wr       (uc_inst_sram_wr    ),
    .inst_sram_size     (uc_inst_sram_size  ),
    .inst_sram_addr     (uc_inst_sram_addr  ),
    .inst_sram_wstrb    (uc_inst_sram_wstrb ),
    .inst_sram_wdata    (uc_inst_sram_wdata ),
    .inst_sram_addr_ok  (uc_inst_sram_addr_ok),
    .inst_sram_data_ok  (uc_inst_sram_data_ok),
    .inst_sram_rdata    (uc_inst_sram_rdata ),

    .cache_rd_req       (cache_rd_req       ),
    .cache_rd_type      (cache_rd_type      ),
    .cache_rd_addr      (cache_rd_addr      ),
    .cache_rd_rdy       (cache_rd_rdy       ),
    .cache_ret_valid    (cache_ret_valid    ),
    .cache_ret_last     (cache_ret_last     ),
    .cache_ret_data     (cache_ret_data     ),

    .cache_wr_req       (cache_wr_req       ),
    .cache_wr_type      (cache_wr_type      ),
    .cache_wr_addr      (cache_wr_addr      ),
    .cache_wr_wstrb     (cache_wr_wstrb     ),
    .cache_wr_data      (cache_wr_data      ),
    .cache_wr_rdy       (cache_wr_rdy       ),

    .data_sram_req      (uc_data_sram_req   ),
    .data_sram_wr       (uc_data_sram_wr    ),
    .data_sram_size     (uc_data_sram_size  ),
    .data_sram_addr     (uc_data_sram_addr  ),
    .data_sram_wdata    (uc_data_sram_wdata ),
    .data_sram_wstrb    (uc_data_sram_wstrb ),
    .data_sram_addr_ok  (uc_data_sram_addr_ok),
    .data_sram_data_ok  (uc_data_sram_data_ok),
    .data_sram_rdata    (uc_data_sram_rdata )
);

endmodule
