`timescale 1ns / 1ps

// dual_cache_hitrate_tb
// - Instantiate BOTH icache_top + dcache_top
// - Share ONE backing memory for BOTH caches via a 2-master burst arbiter
// - Drive synthetic workloads and report hit rates together
//
// Miss criterion (for this cache.v implementation):
// - Count a miss for a request if it caused a downstream burst read handshake (rd_req && rd_rdy)
//   during the lifetime of that request.

module dual_cache_hitrate_tb;

    reg clk;
    reg resetn;

    // -----------------
    // I$ CPU side
    // -----------------
    reg         inst_sram_req;
    reg         inst_sram_wr;
    reg  [ 1:0] inst_sram_size;
    reg  [31:0] inst_sram_addr;
    reg  [ 3:0] inst_sram_wstrb;
    reg  [31:0] inst_sram_wdata;
    reg         inst_cached;

    wire        inst_sram_addr_ok;
    wire        inst_sram_data_ok;
    wire [31:0] inst_sram_rdata;

    // I$ bypass (unused in this TB)
    wire        uc_inst_sram_req;
    wire        uc_inst_sram_wr;
    wire [ 1:0] uc_inst_sram_size;
    wire [31:0] uc_inst_sram_addr;
    wire [ 3:0] uc_inst_sram_wstrb;
    wire [31:0] uc_inst_sram_wdata;
    wire        uc_inst_sram_addr_ok;
    wire        uc_inst_sram_data_ok;
    wire [31:0] uc_inst_sram_rdata;

    // I$ cache mem side
    wire        i_rd_req;
    wire [ 2:0] i_rd_type;
    wire [31:0] i_rd_addr;
    wire        i_rd_rdy;
    wire        i_ret_valid;
    wire        i_ret_last;
    wire [31:0] i_ret_data;

    wire        i_wr_req;
    wire [ 2:0] i_wr_type;
    wire [31:0] i_wr_addr;
    wire [ 3:0] i_wr_wstrb;
    wire [127:0] i_wr_data;
    wire        i_wr_rdy;

    // -----------------
    // D$ CPU side
    // -----------------
    reg         data_sram_req;
    reg         data_sram_wr;
    reg  [ 1:0] data_sram_size;
    reg  [31:0] data_sram_addr;
    reg  [ 3:0] data_sram_wstrb;
    reg  [31:0] data_sram_wdata;
    reg         data_cached;

    wire        data_sram_addr_ok;
    wire        data_sram_data_ok;
    wire [31:0] data_sram_rdata;

    // D$ bypass (unused in this TB)
    wire        uc_data_sram_req;
    wire        uc_data_sram_wr;
    wire [ 1:0] uc_data_sram_size;
    wire [31:0] uc_data_sram_addr;
    wire [ 3:0] uc_data_sram_wstrb;
    wire [31:0] uc_data_sram_wdata;
    wire        uc_data_sram_addr_ok;
    wire        uc_data_sram_data_ok;
    wire [31:0] uc_data_sram_rdata;

    // D$ cache mem side
    wire        d_rd_req;
    wire [ 2:0] d_rd_type;
    wire [31:0] d_rd_addr;
    wire        d_rd_rdy;
    wire        d_ret_valid;
    wire        d_ret_last;
    wire [31:0] d_ret_data;

    wire        d_wr_req;
    wire [ 2:0] d_wr_type;
    wire [31:0] d_wr_addr;
    wire [ 3:0] d_wr_wstrb;
    wire [127:0] d_wr_data;
    wire        d_wr_rdy;

    // -----------------
    // shared memory port
    // -----------------
    wire        s_rd_req;
    wire [31:0] s_rd_addr;
    wire        s_rd_rdy;
    wire        s_ret_valid;
    wire        s_ret_last;
    wire [31:0] s_ret_data;

    wire        s_wr_req;
    wire [31:0] s_wr_addr;
    wire [127:0] s_wr_data;
    wire        s_wr_rdy;

    // shared backing memory (only burst interface used here)
    simple_unified_mem u_mem (
        .clk      (clk),
        .resetn   (resetn),

        .rd_req   (s_rd_req),
        .rd_addr  (s_rd_addr),
        .rd_rdy   (s_rd_rdy),
        .ret_valid(s_ret_valid),
        .ret_last (s_ret_last),
        .ret_data (s_ret_data),

        .wr_req   (s_wr_req),
        .wr_addr  (s_wr_addr),
        .wr_data  (s_wr_data),
        .wr_rdy   (s_wr_rdy),

        // uncached port unused
        .uc_req    (1'b0),
        .uc_wr     (1'b0),
        .uc_addr   (32'b0),
        .uc_wstrb  (4'b0),
        .uc_wdata  (32'b0),
        .uc_addr_ok(uc_inst_sram_addr_ok),
        .uc_data_ok(uc_inst_sram_data_ok),
        .uc_rdata  (uc_inst_sram_rdata)
    );

    // burst arbiter: master0=I$, master1=D$
    simple_burst_arb2 u_arb (
        .clk      (clk),
        .resetn   (resetn),

        .m0_rd_req (i_rd_req),
        .m0_rd_addr(i_rd_addr),
        .m0_rd_rdy (i_rd_rdy),
        .m0_ret_valid(i_ret_valid),
        .m0_ret_last (i_ret_last),
        .m0_ret_data (i_ret_data),

        .m0_wr_req (i_wr_req),
        .m0_wr_addr(i_wr_addr),
        .m0_wr_data(i_wr_data),
        .m0_wr_rdy (i_wr_rdy),

        .m1_rd_req (d_rd_req),
        .m1_rd_addr(d_rd_addr),
        .m1_rd_rdy (d_rd_rdy),
        .m1_ret_valid(d_ret_valid),
        .m1_ret_last (d_ret_last),
        .m1_ret_data (d_ret_data),

        .m1_wr_req (d_wr_req),
        .m1_wr_addr(d_wr_addr),
        .m1_wr_data(d_wr_data),
        .m1_wr_rdy (d_wr_rdy),

        .s_rd_req  (s_rd_req),
        .s_rd_addr (s_rd_addr),
        .s_rd_rdy  (s_rd_rdy),
        .s_ret_valid(s_ret_valid),
        .s_ret_last (s_ret_last),
        .s_ret_data (s_ret_data),

        .s_wr_req  (s_wr_req),
        .s_wr_addr (s_wr_addr),
        .s_wr_data (s_wr_data),
        .s_wr_rdy  (s_wr_rdy)
    );

    // I$ DUT
    icache_top u_ic (
        .clk      (clk),
        .resetn   (resetn),

        .inst_sram_req  (inst_sram_req),
        .inst_sram_wr   (inst_sram_wr),
        .inst_sram_size (inst_sram_size),
        .inst_sram_addr (inst_sram_addr),
        .inst_sram_wstrb(inst_sram_wstrb),
        .inst_sram_wdata(inst_sram_wdata),
        .inst_cached    (inst_cached),

        .inst_sram_addr_ok(inst_sram_addr_ok),
        .inst_sram_data_ok(inst_sram_data_ok),
        .inst_sram_rdata  (inst_sram_rdata),

        // bypass not used
        .uc_inst_sram_req  (uc_inst_sram_req),
        .uc_inst_sram_wr   (uc_inst_sram_wr),
        .uc_inst_sram_size (uc_inst_sram_size),
        .uc_inst_sram_addr (uc_inst_sram_addr),
        .uc_inst_sram_wstrb(uc_inst_sram_wstrb),
        .uc_inst_sram_wdata(uc_inst_sram_wdata),
        .uc_inst_sram_addr_ok(1'b0),
        .uc_inst_sram_data_ok(1'b0),
        .uc_inst_sram_rdata  (32'b0),

        .rd_req   (i_rd_req),
        .rd_type  (i_rd_type),
        .rd_addr  (i_rd_addr),
        .rd_rdy   (i_rd_rdy),
        .ret_valid(i_ret_valid),
        .ret_last (i_ret_last),
        .ret_data (i_ret_data),

        .wr_req   (i_wr_req),
        .wr_type  (i_wr_type),
        .wr_addr  (i_wr_addr),
        .wr_wstrb (i_wr_wstrb),
        .wr_data  (i_wr_data),
        .wr_rdy   (i_wr_rdy)
    );

    // D$ DUT
    dcache_top u_dc (
        .clk      (clk),
        .resetn   (resetn),

        .data_sram_req  (data_sram_req),
        .data_sram_wr   (data_sram_wr),
        .data_sram_size (data_sram_size),
        .data_sram_addr (data_sram_addr),
        .data_sram_wstrb(data_sram_wstrb),
        .data_sram_wdata(data_sram_wdata),
        .data_cached    (data_cached),

        .data_sram_addr_ok(data_sram_addr_ok),
        .data_sram_data_ok(data_sram_data_ok),
        .data_sram_rdata  (data_sram_rdata),

        // bypass not used
        .uc_data_sram_req  (uc_data_sram_req),
        .uc_data_sram_wr   (uc_data_sram_wr),
        .uc_data_sram_size (uc_data_sram_size),
        .uc_data_sram_addr (uc_data_sram_addr),
        .uc_data_sram_wstrb(uc_data_sram_wstrb),
        .uc_data_sram_wdata(uc_data_sram_wdata),
        .uc_data_sram_addr_ok(1'b0),
        .uc_data_sram_data_ok(1'b0),
        .uc_data_sram_rdata  (32'b0),

        .rd_req   (d_rd_req),
        .rd_type  (d_rd_type),
        .rd_addr  (d_rd_addr),
        .rd_rdy   (d_rd_rdy),
        .ret_valid(d_ret_valid),
        .ret_last (d_ret_last),
        .ret_data (d_ret_data),

        .wr_req   (d_wr_req),
        .wr_type  (d_wr_type),
        .wr_addr  (d_wr_addr),
        .wr_wstrb (d_wr_wstrb),
        .wr_data  (d_wr_data),
        .wr_rdy   (d_wr_rdy)
    );

    // clock
    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    // VCD
    initial begin
        if ($test$plusargs("dump")) begin
            $dumpfile("dual_cache_hitrate_tb.vcd");
            $dumpvars(0, dual_cache_hitrate_tb);
        end
    end

    task automatic wait_cycles(input integer n);
        integer k;
        begin
            for (k = 0; k < n; k = k + 1) @(posedge clk);
        end
    endtask

    // I$ cached read + miss detect
    task automatic ic_read_count;
        input  [31:0] addr;
        output [31:0] rdata;
        output        is_miss;
        integer timeout;
        reg miss_seen;
        begin
            miss_seen = 1'b0;

            inst_cached     = 1'b1;
            inst_sram_wr    = 1'b0;
            inst_sram_size  = 2'b10;
            inst_sram_addr  = addr;
            inst_sram_wstrb = 4'b0;
            inst_sram_wdata = 32'b0;
            inst_sram_req   = 1'b1;

            timeout = 0;
            while (!inst_sram_addr_ok) begin
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 20000) $fatal(1, "I$ TIMEOUT addr_ok addr=%08x", addr);
            end
            @(posedge clk);
            inst_sram_req = 1'b0;

            timeout = 0;
            while (!inst_sram_data_ok) begin
                if (i_rd_req && i_rd_rdy) miss_seen = 1'b1;
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 20000) $fatal(1, "I$ TIMEOUT data_ok addr=%08x", addr);
            end
            rdata  = inst_sram_rdata;
            is_miss= miss_seen;
            @(posedge clk);
        end
    endtask

    // D$ cached access + miss detect
    task automatic dc_access_count;
        input         wr;
        input  [31:0] addr;
        input  [ 3:0] wstrb;
        input  [31:0] wdata;
        output [31:0] rdata;
        output        is_miss;
        integer timeout;
        reg miss_seen;
        begin
            miss_seen = 1'b0;

            data_cached     = 1'b1;
            data_sram_wr    = wr;
            data_sram_size  = 2'b10;
            data_sram_addr  = addr;
            data_sram_wstrb = wstrb;
            data_sram_wdata = wdata;
            data_sram_req   = 1'b1;

            timeout = 0;
            while (!data_sram_addr_ok) begin
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 20000) $fatal(1, "D$ TIMEOUT addr_ok addr=%08x", addr);
            end
            @(posedge clk);
            data_sram_req = 1'b0;

            timeout = 0;
            while (!data_sram_data_ok) begin
                if (d_rd_req && d_rd_rdy) miss_seen = 1'b1;
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 20000) $fatal(1, "D$ TIMEOUT data_ok addr=%08x", addr);
            end
            rdata  = data_sram_rdata;
            is_miss= miss_seen;
            @(posedge clk);
        end
    endtask

    // counters
    integer itotal, imiss;
    integer dtotal, dmiss;
    integer d_r_total, d_r_miss;
    integer d_w_total, d_w_miss;
    integer d_wb_cnt;

    always @(posedge clk) begin
        if (!resetn) d_wb_cnt <= 0;
        else if (d_wr_req && d_wr_rdy) d_wb_cnt <= d_wb_cnt + 1;
    end

    // workload params
    integer N;
    integer I_RATIO;
    reg [31:0] lfsr;

    function [31:0] lfsr_next;
        input [31:0] cur;
        begin
            lfsr_next = {cur[30:0], cur[31] ^ cur[21] ^ cur[1] ^ 1'b1};
        end
    endfunction

    integer i;
    reg [31:0] r;
    reg is_miss;

    real i_hitrate;
    real d_hitrate;

    initial begin
        resetn = 1'b0;
        inst_sram_req = 1'b0;
        inst_sram_wr  = 1'b0;
        inst_sram_size= 2'b10;
        inst_sram_addr= 32'b0;
        inst_sram_wstrb=4'b0;
        inst_sram_wdata=32'b0;
        inst_cached   = 1'b1;

        data_sram_req = 1'b0;
        data_sram_wr  = 1'b0;
        data_sram_size= 2'b10;
        data_sram_addr= 32'b0;
        data_sram_wstrb=4'b0;
        data_sram_wdata=32'b0;
        data_cached   = 1'b1;

        lfsr = 32'h1357_9bdf;

        N = 5000;
        I_RATIO = 70; // percent of ops that are I$ reads
        if ($value$plusargs("N=%d", N)) ;
        if ($value$plusargs("IR=%d", I_RATIO)) ;

        itotal = 0; imiss = 0;
        dtotal = 0; dmiss = 0;
        d_r_total = 0; d_r_miss = 0;
        d_w_total = 0; d_w_miss = 0;
        d_wb_cnt  = 0;

        wait_cycles(10);
        resetn = 1'b1;
        wait_cycles(5);

        // interleaved workload
        for (i = 0; i < N; i = i + 1) begin
            lfsr = lfsr_next(lfsr);

            if (lfsr[7:0] < I_RATIO*256/100) begin
                // I$ read: mix hot+random
                ic_read_count(32'h0000_1000 + {lfsr[11:2], 2'b00}, r, is_miss);
                itotal = itotal + 1;
                if (is_miss) imiss = imiss + 1;
            end else begin
                // D$ access
                if (lfsr[0]) begin
                    // load
                    dc_access_count(1'b0, 32'h0000_2000 + {lfsr[13:2], 2'b00}, 4'b0000, 32'b0, r, is_miss);
                    dtotal = dtotal + 1;
                    d_r_total = d_r_total + 1;
                    if (is_miss) begin
                        dmiss = dmiss + 1;
                        d_r_miss = d_r_miss + 1;
                    end
                end else begin
                    // store
                    dc_access_count(1'b1, 32'h0000_2000 + {lfsr[13:2], 2'b00}, 4'b1111, (32'hA000_0000 ^ i), r, is_miss);
                    dtotal = dtotal + 1;
                    d_w_total = d_w_total + 1;
                    if (is_miss) begin
                        dmiss = dmiss + 1;
                        d_w_miss = d_w_miss + 1;
                    end
                end
            end
        end

        if (itotal == 0) i_hitrate = 0.0;
        else i_hitrate = (100.0 * (itotal - imiss)) / itotal;

        if (dtotal == 0) d_hitrate = 0.0;
        else d_hitrate = (100.0 * (dtotal - dmiss)) / dtotal;

        $display("\n==== Dual-cache hitrate report ====");
        $display("N=%0d IR=%0d%%", N, I_RATIO);
        $display("I$: total=%0d hit=%0d miss=%0d hitrate=%0.2f%%", itotal, itotal-imiss, imiss, i_hitrate);
        $display("D$: total=%0d hit=%0d miss=%0d hitrate=%0.2f%%", dtotal, dtotal-dmiss, dmiss, d_hitrate);
        $display("D$: read total=%0d miss=%0d | write total=%0d miss=%0d | writeback(line)=%0d",
                 d_r_total, d_r_miss, d_w_total, d_w_miss, d_wb_cnt);
        $display("==================================\n");

        $finish;
    end

endmodule
