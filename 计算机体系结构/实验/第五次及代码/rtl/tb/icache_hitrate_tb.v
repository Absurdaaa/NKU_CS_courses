`timescale 1ns / 1ps

// icache_hitrate_tb
// 统计 I$ cached 访问命中率：
// - 以“本次请求是否触发 rd_req 握手”为 miss 判据（cache.v 单 outstanding，等价于 demand miss）

module icache_hitrate_tb;

    reg clk;
    reg resetn;

    // CPU inst side
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

    // bypass (uncached)
    wire        uc_inst_sram_req;
    wire        uc_inst_sram_wr;
    wire [ 1:0] uc_inst_sram_size;
    wire [31:0] uc_inst_sram_addr;
    wire [ 3:0] uc_inst_sram_wstrb;
    wire [31:0] uc_inst_sram_wdata;
    wire        uc_inst_sram_addr_ok;
    wire        uc_inst_sram_data_ok;
    wire [31:0] uc_inst_sram_rdata;

    // cache memory side
    wire        rd_req;
    wire [ 2:0] rd_type;
    wire [31:0] rd_addr;
    wire        rd_rdy;
    wire        ret_valid;
    wire        ret_last;
    wire [31:0] ret_data;

    wire        wr_req;
    wire [ 2:0] wr_type;
    wire [31:0] wr_addr;
    wire [ 3:0] wr_wstrb;
    wire [127:0] wr_data;
    wire        wr_rdy;

    simple_unified_mem u_mem (
        .clk      (clk),
        .resetn   (resetn),

        .rd_req   (rd_req),
        .rd_addr  (rd_addr),
        .rd_rdy   (rd_rdy),
        .ret_valid(ret_valid),
        .ret_last (ret_last),
        .ret_data (ret_data),

        .wr_req   (wr_req),
        .wr_addr  (wr_addr),
        .wr_data  (wr_data),
        .wr_rdy   (wr_rdy),

        .uc_req   (uc_inst_sram_req),
        .uc_wr    (uc_inst_sram_wr),
        .uc_addr  (uc_inst_sram_addr),
        .uc_wstrb (uc_inst_sram_wstrb),
        .uc_wdata (uc_inst_sram_wdata),
        .uc_addr_ok(uc_inst_sram_addr_ok),
        .uc_data_ok(uc_inst_sram_data_ok),
        .uc_rdata  (uc_inst_sram_rdata)
    );

    icache_top dut (
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

        .uc_inst_sram_req  (uc_inst_sram_req),
        .uc_inst_sram_wr   (uc_inst_sram_wr),
        .uc_inst_sram_size (uc_inst_sram_size),
        .uc_inst_sram_addr (uc_inst_sram_addr),
        .uc_inst_sram_wstrb(uc_inst_sram_wstrb),
        .uc_inst_sram_wdata(uc_inst_sram_wdata),
        .uc_inst_sram_addr_ok(uc_inst_sram_addr_ok),
        .uc_inst_sram_data_ok(uc_inst_sram_data_ok),
        .uc_inst_sram_rdata  (uc_inst_sram_rdata),

        .rd_req   (rd_req),
        .rd_type  (rd_type),
        .rd_addr  (rd_addr),
        .rd_rdy   (rd_rdy),
        .ret_valid(ret_valid),
        .ret_last (ret_last),
        .ret_data (ret_data),

        .wr_req   (wr_req),
        .wr_type  (wr_type),
        .wr_addr  (wr_addr),
        .wr_wstrb (wr_wstrb),
        .wr_data  (wr_data),
        .wr_rdy   (wr_rdy)
    );

    // clock
    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    // wave dump (Icarus)
    initial begin
        if ($test$plusargs("dump")) begin
            $dumpfile("icache_hitrate_tb.vcd");
            $dumpvars(0, icache_hitrate_tb);
        end
    end

    task automatic wait_cycles(input integer n);
        integer k;
        begin
            for (k = 0; k < n; k = k + 1) @(posedge clk);
        end
    endtask

    // one cached read + miss detect
    task automatic cached_read_count;
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
            inst_sram_wstrb = 4'b0000;
            inst_sram_wdata = 32'b0;
            inst_sram_req   = 1'b1;

            timeout = 0;
            while (!inst_sram_addr_ok) begin
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 5000) $fatal(1, "TIMEOUT addr_ok addr=%08x", addr);
            end
            @(posedge clk);
            inst_sram_req = 1'b0;

            timeout = 0;
            while (!inst_sram_data_ok) begin
                // miss if demand refill AR happened for this request
                if (rd_req && rd_rdy) miss_seen = 1'b1;
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 5000) $fatal(1, "TIMEOUT data_ok addr=%08x", addr);
            end
            rdata  = inst_sram_rdata;
            is_miss= miss_seen;
            @(posedge clk);
        end
    endtask

    // simple LFSR for address generation
    reg [31:0] lfsr;
    function [31:0] lfsr_next;
        input [31:0] cur;
        begin
            lfsr_next = {cur[30:0], cur[31] ^ cur[21] ^ cur[1] ^ 1'b1};
        end
    endfunction

    integer i;
    integer total;
    integer miss;
    integer hit;
    reg [31:0] r;
    reg        is_miss;
    real       hitrate;

    integer NSEQ;
    integer NRAND;
    reg [31:0] base_small;
    reg [31:0] base_big;

    initial begin
        // defaults
        resetn = 1'b0;
        inst_sram_req   = 1'b0;
        inst_sram_wr    = 1'b0;
        inst_sram_size  = 2'b10;
        inst_sram_addr  = 32'b0;
        inst_sram_wstrb = 4'b0;
        inst_sram_wdata = 32'b0;
        inst_cached     = 1'b1;

        lfsr = 32'h1234_5678;

        NSEQ  = 512;
        NRAND = 2048;
        if ($value$plusargs("NSEQ=%d", NSEQ)) ;
        if ($value$plusargs("NRAND=%d", NRAND)) ;

        // address regions
        base_small = 32'h0000_1000; // small hot region (fits easily)
        base_big   = 32'h0010_0000; // larger cold region

        wait_cycles(10);
        resetn = 1'b1;
        wait_cycles(5);

        total = 0;
        miss  = 0;

        // Phase A: sequential in a small region (high hit after warmup)
        for (i = 0; i < NSEQ; i = i + 1) begin
            cached_read_count(base_small + (i << 2), r, is_miss);
            total = total + 1;
            if (is_miss) miss = miss + 1;
        end

        // Phase B: pseudo-random over a big region (lower hit)
        for (i = 0; i < NRAND; i = i + 1) begin
            lfsr = lfsr_next(lfsr);
            // word aligned, spread over 64KB
            cached_read_count(base_big + {lfsr[15:2], 2'b00}, r, is_miss);
            total = total + 1;
            if (is_miss) miss = miss + 1;
        end

        hit = total - miss;
        if (total == 0) hitrate = 0.0;
        else hitrate = (100.0 * hit) / total;

        $display("\n==== I$ hitrate report ====");
        $display("NSEQ=%0d NRAND=%0d", NSEQ, NRAND);
        $display("total=%0d hit=%0d miss=%0d hitrate=%0.2f%%", total, hit, miss, hitrate);
        $display("===========================\n");

        $finish;
    end

endmodule
