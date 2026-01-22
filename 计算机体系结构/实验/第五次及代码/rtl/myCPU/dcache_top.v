`timescale 1ns / 1ps

// dcache_top
// - Wraps cache.v as a D$ (read/write, write-back + write-allocate)
// - Provides a bypass (uncached) path with the same SRAM-like handshake
// - Ensures uncached return is NEVER gated (avoid losing FIFO-pop returns)
// - Adds a 1-deep buffer to survive the rare case: bypass data_ok and cache data_ok in same cycle

module dcache_top(
    input         clk,
    input         resetn,

    // CPU data interface
    input         data_sram_req,
    input         data_sram_wr,
    input  [ 1:0] data_sram_size,
    input  [31:0] data_sram_addr,
    input  [ 3:0] data_sram_wstrb,
    input  [31:0] data_sram_wdata,
    input         data_cached,

    output        data_sram_addr_ok,
    output        data_sram_data_ok,
    output [31:0] data_sram_rdata,

    // bypass path (uncached)
    output        uc_data_sram_req,
    output        uc_data_sram_wr,
    output [ 1:0] uc_data_sram_size,
    output [31:0] uc_data_sram_addr,
    output [ 3:0] uc_data_sram_wstrb,
    output [31:0] uc_data_sram_wdata,
    input         uc_data_sram_addr_ok,
    input         uc_data_sram_data_ok,
    input  [31:0] uc_data_sram_rdata,

    // cache memory side
    output        rd_req,
    output [ 2:0] rd_type,
    output [31:0] rd_addr,
    input         rd_rdy,
    input         ret_valid,
    input         ret_last,
    input  [31:0] ret_data,

    output        wr_req,
    output [ 2:0] wr_type,
    output [31:0] wr_addr,
    output [ 3:0] wr_wstrb,
    output [127:0] wr_data,
    input         wr_rdy
);

    // ----------------------
    // Request split
    // ----------------------
    wire cached_req = data_sram_req && data_cached;
    wire bypass_req = data_sram_req && !data_cached;

    // bypass forward
    assign uc_data_sram_req   = bypass_req;
    assign uc_data_sram_wr    = data_sram_wr;
    assign uc_data_sram_size  = data_sram_size;
    assign uc_data_sram_addr  = data_sram_addr;
    assign uc_data_sram_wstrb = data_sram_wstrb;
    assign uc_data_sram_wdata = data_sram_wdata;

    // addr_ok: select by current segment attribute
    wire cache_addr_ok;
    assign data_sram_addr_ok = data_cached ? cache_addr_ok : uc_data_sram_addr_ok;

    // ----------------------
    // D$ (cache.v)
    // ----------------------
    wire cache_data_ok;
    wire [31:0] cache_rdata;

    cache u_dcache (
        .clk_g      (clk),
        .resetn     (resetn),

        .valid      (cached_req),
        .op         (data_sram_wr),
        .index      (data_sram_addr[11:4]),
        .tag        (data_sram_addr[31:12]),
        .offset     (data_sram_addr[3:0]),
        .wstrb      (data_sram_wstrb),
        .wdata      (data_sram_wdata),

        .addr_ok    (cache_addr_ok),
        .data_ok    (cache_data_ok),
        .rdata      (cache_rdata),

        .rd_req     (rd_req),
        .rd_type    (rd_type),
        .rd_addr    (rd_addr),
        .rd_rdy     (rd_rdy),
        .ret_valid  (ret_valid),
        .ret_last   (ret_last),
        .ret_data   (ret_data),

        .wr_req     (wr_req),
        .wr_type    (wr_type),
        .wr_addr    (wr_addr),
        .wr_wstrb   (wr_wstrb),
        .wr_data    (wr_data),
        .wr_rdy     (wr_rdy)
    );

    // ----------------------
    // Response mux + 1-deep buffer
    // ----------------------
    reg        hold_valid;
    reg [31:0] hold_rdata;

    wire bypass_ok = uc_data_sram_data_ok;

    wire use_bypass = bypass_ok;
    wire use_hold   = !use_bypass && hold_valid;
    wire use_cache  = !use_bypass && !hold_valid && cache_data_ok;

    assign data_sram_data_ok = use_bypass || use_hold || use_cache;
    assign data_sram_rdata   = use_bypass ? uc_data_sram_rdata :
                               use_hold   ? hold_rdata :
                                            cache_rdata;

    wire set_hold     = cache_data_ok && bypass_ok;
    wire consume_hold = hold_valid && !bypass_ok;

    always @(posedge clk) begin
        if (!resetn) begin
            hold_valid <= 1'b0;
            hold_rdata <= 32'b0;
        end else begin
            if (set_hold) begin
                hold_valid <= 1'b1;
                hold_rdata <= cache_rdata;
            end else if (consume_hold) begin
                hold_valid <= 1'b0;
            end
        end
    end

endmodule
