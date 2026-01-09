`timescale 1ns/1ps

// Basic functional test for icache_top + cache.v
//
// Checks:
// - inst_cached=0: request bypasses to uc_inst_* and does NOT trigger cache linefill
// - inst_cached=1: first access to a line triggers one 4-beat linefill, then subsequent hits
// - returned inst_sram_rdata matches backing memory contents
//
// How to run (Vivado/xsim):
// - Add simulation sources:
//   - rtl/myCPU/cache.v
//   - rtl/myCPU/icache_top.v
//   - rtl/tb/icache_basic_tb.v

module icache_basic_tb;

    reg clk;
    reg resetn;

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        resetn = 1'b0;
        repeat (20) @(posedge clk);
        resetn = 1'b1;
    end

    // CPU inst interface
    reg         inst_sram_req;
    reg         inst_sram_wr;
    reg [1:0]   inst_sram_size;
    reg [31:0]  inst_sram_addr;
    reg [3:0]   inst_sram_wstrb;
    reg [31:0]  inst_sram_wdata;
    reg         inst_cached;

    wire        inst_sram_addr_ok;
    wire        inst_sram_data_ok;
    wire [31:0] inst_sram_rdata;

    // bypass path (uncached)
    wire        uc_inst_sram_req;
    wire        uc_inst_sram_wr;
    wire [1:0]  uc_inst_sram_size;
    wire [31:0] uc_inst_sram_addr;
    wire [3:0]  uc_inst_sram_wstrb;
    wire [31:0] uc_inst_sram_wdata;
    reg         uc_inst_sram_addr_ok;
    reg         uc_inst_sram_data_ok;
    reg [31:0]  uc_inst_sram_rdata;

    // cache memory side
    wire        rd_req;
    wire [2:0]  rd_type;
    wire [31:0] rd_addr;
    reg         rd_rdy;
    reg         ret_valid;
    reg         ret_last;
    reg [31:0]  ret_data;

    wire        wr_req;
    wire [2:0]  wr_type;
    wire [31:0] wr_addr;
    wire [3:0]  wr_wstrb;
    wire [127:0] wr_data;
    reg         wr_rdy;

    icache_top dut(
        .clk                (clk),
        .resetn             (resetn),

        .inst_sram_req       (inst_sram_req),
        .inst_sram_wr        (inst_sram_wr),
        .inst_sram_size      (inst_sram_size),
        .inst_sram_addr      (inst_sram_addr),
        .inst_sram_wstrb     (inst_sram_wstrb),
        .inst_sram_wdata     (inst_sram_wdata),
        .inst_cached         (inst_cached),

        .inst_sram_addr_ok   (inst_sram_addr_ok),
        .inst_sram_data_ok   (inst_sram_data_ok),
        .inst_sram_rdata     (inst_sram_rdata),

        .uc_inst_sram_req    (uc_inst_sram_req),
        .uc_inst_sram_wr     (uc_inst_sram_wr),
        .uc_inst_sram_size   (uc_inst_sram_size),
        .uc_inst_sram_addr   (uc_inst_sram_addr),
        .uc_inst_sram_wstrb  (uc_inst_sram_wstrb),
        .uc_inst_sram_wdata  (uc_inst_sram_wdata),
        .uc_inst_sram_addr_ok(uc_inst_sram_addr_ok),
        .uc_inst_sram_data_ok(uc_inst_sram_data_ok),
        .uc_inst_sram_rdata  (uc_inst_sram_rdata),

        .rd_req              (rd_req),
        .rd_type             (rd_type),
        .rd_addr             (rd_addr),
        .rd_rdy              (rd_rdy),
        .ret_valid           (ret_valid),
        .ret_last            (ret_last),
        .ret_data            (ret_data),

        .wr_req              (wr_req),
        .wr_type             (wr_type),
        .wr_addr             (wr_addr),
        .wr_wstrb            (wr_wstrb),
        .wr_data             (wr_data),
        .wr_rdy              (wr_rdy)
    );

    // ----------------------
    // Backing memory model
    // ----------------------
    reg [31:0] mem [0:4095];
    integer i;

    initial begin
        for (i = 0; i < 4096; i = i + 1) begin
            mem[i] = 32'hC000_0000 ^ i;
        end
        // put some recognizable data at the tested area
        // NOTE: in the real integration, mycpu_core outputs *physical* inst_sram_addr;
        //       inst_cached is derived from virtual address segment (kseg0=Cached).
        //       So this TB uses physical addresses for cached accesses.
        mem[32'h0000_1000 >> 2] = 32'h1111_0000;
        mem[(32'h0000_1000 >> 2) + 1] = 32'h2222_0000;
        mem[(32'h0000_1010 >> 2) + 0] = 32'h3333_0000;
        mem[(32'h0000_1010 >> 2) + 1] = 32'h4444_0000;
    end

    // cache linefill responder: always ready, returns 4 beats
    reg        burst_active;
    reg [1:0]  burst_beat;
    reg [31:0] burst_base;

    // count linefill requests
    integer cache_linefill_cnt;

    always @(posedge clk) begin
        if (!resetn) begin
            rd_rdy <= 1'b1;
            wr_rdy <= 1'b1;

            ret_valid <= 1'b0;
            ret_last  <= 1'b0;
            ret_data  <= 32'h0;

            burst_active <= 1'b0;
            burst_beat   <= 2'b00;
            burst_base   <= 32'h0;

            cache_linefill_cnt <= 0;
        end else begin
            // default
            ret_valid <= 1'b0;
            ret_last  <= 1'b0;

            // ICache should never write back
            if (wr_req) begin
                $display("[TB][FAIL] ICache should not issue wr_req, but got wr_req=1 addr=%h", wr_addr);
                $finish;
            end

            if (rd_req && rd_rdy && !burst_active) begin
                burst_active <= 1'b1;
                burst_beat   <= 2'b00;
                burst_base   <= rd_addr;
                cache_linefill_cnt <= cache_linefill_cnt + 1;

                if (rd_addr[3:0] !== 4'b0000) begin
                    $display("[TB][FAIL] rd_addr not 16B-aligned: %h", rd_addr);
                    $finish;
                end
            end

            if (burst_active) begin
                ret_valid <= 1'b1;
                ret_data  <= mem[(burst_base >> 2) + burst_beat];
                if (burst_beat == 2'd3) begin
                    ret_last <= 1'b1;
                    burst_active <= 1'b0;
                end else begin
                    burst_beat <= burst_beat + 2'b01;
                end
            end
        end
    end

    // uncached bypass responder: 1-cycle response
    always @(posedge clk) begin
        if (!resetn) begin
            uc_inst_sram_addr_ok <= 1'b0;
            uc_inst_sram_data_ok <= 1'b0;
            uc_inst_sram_rdata   <= 32'h0;
        end else begin
            uc_inst_sram_addr_ok <= uc_inst_sram_req;
            uc_inst_sram_data_ok <= uc_inst_sram_req;
            // just return a recognizable pattern
            uc_inst_sram_rdata   <= 32'hFEED_0000 | uc_inst_sram_addr[15:0];
        end
    end

    // ----------------------
    // Helpers
    // ----------------------
    task do_fetch;
        input [31:0] addr;
        input cached;
        input [31:0] exp;
        begin
            @(posedge clk);
            inst_sram_req   <= 1'b1;
            inst_sram_wr    <= 1'b0;
            inst_sram_size  <= 2'b10;
            inst_sram_addr  <= addr;
            inst_sram_wstrb <= 4'h0;
            inst_sram_wdata <= 32'h0;
            inst_cached     <= cached;

            while (!inst_sram_addr_ok) @(posedge clk);
            @(posedge clk);
            inst_sram_req <= 1'b0;

            while (!inst_sram_data_ok) @(posedge clk);
            if (inst_sram_rdata !== exp) begin
                $display("[TB][FAIL] fetch addr=%h cached=%0d exp=%h got=%h", addr, cached, exp, inst_sram_rdata);
                $finish;
            end
        end
    endtask

    // ----------------------
    // Test sequence
    // ----------------------
    initial begin
        inst_sram_req   = 1'b0;
        inst_sram_wr    = 1'b0;
        inst_sram_size  = 2'b10;
        inst_sram_addr  = 32'h0;
        inst_sram_wstrb = 4'h0;
        inst_sram_wdata = 32'h0;
        inst_cached     = 1'b0;

        @(posedge resetn);
        repeat (5) @(posedge clk);

        // 1) uncached fetch (bypass)
        do_fetch(32'hBFC0_0000, 1'b0, 32'hFEED_0000 | 16'h0000);
        if (cache_linefill_cnt != 0) begin
            $display("[TB][FAIL] uncached fetch should not linefill, but cnt=%0d", cache_linefill_cnt);
            $finish;
        end

        // 2) cached miss then hit (same address) - use physical address
        do_fetch(32'h0000_1000, 1'b1, 32'h1111_0000);
        if (cache_linefill_cnt != 1) begin
            $display("[TB][FAIL] first cached fetch should linefill once, cnt=%0d", cache_linefill_cnt);
            $finish;
        end

        do_fetch(32'h0000_1000, 1'b1, 32'h1111_0000);
        if (cache_linefill_cnt != 1) begin
            $display("[TB][FAIL] cached hit should not linefill again, cnt=%0d", cache_linefill_cnt);
            $finish;
        end

        // 3) cached hit within the same line
        do_fetch(32'h0000_1004, 1'b1, 32'h2222_0000);
        if (cache_linefill_cnt != 1) begin
            $display("[TB][FAIL] same-line hit should not linefill again, cnt=%0d", cache_linefill_cnt);
            $finish;
        end

        // 4) cached access to next line triggers another linefill
        do_fetch(32'h0000_1010, 1'b1, 32'h3333_0000);
        if (cache_linefill_cnt != 2) begin
            $display("[TB][FAIL] next-line miss should linefill again, cnt=%0d", cache_linefill_cnt);
            $finish;
        end

        $display("[TB][PASS] icache_basic_tb");
        $finish;
    end

endmodule
