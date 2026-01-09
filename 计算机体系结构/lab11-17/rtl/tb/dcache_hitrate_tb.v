`timescale 1ns / 1ps

// dcache_hitrate_tb
// 统计 D$ cached 访问命中率：
// - 以“本次请求是否触发 rd_req 握手”为 miss 判据（包含 load miss / store miss(write-allocate)）
// - 额外统计 write-back 次数（wr_req 握手次数），便于观察 dirty eviction

module dcache_hitrate_tb;

    reg clk;
    reg resetn;

    // CPU data side
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

    // bypass (uncached)
    wire        uc_data_sram_req;
    wire        uc_data_sram_wr;
    wire [ 1:0] uc_data_sram_size;
    wire [31:0] uc_data_sram_addr;
    wire [ 3:0] uc_data_sram_wstrb;
    wire [31:0] uc_data_sram_wdata;
    wire        uc_data_sram_addr_ok;
    wire        uc_data_sram_data_ok;
    wire [31:0] uc_data_sram_rdata;

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

        .uc_req    (uc_data_sram_req),
        .uc_wr     (uc_data_sram_wr),
        .uc_addr   (uc_data_sram_addr),
        .uc_wstrb  (uc_data_sram_wstrb),
        .uc_wdata  (uc_data_sram_wdata),
        .uc_addr_ok(uc_data_sram_addr_ok),
        .uc_data_ok(uc_data_sram_data_ok),
        .uc_rdata  (uc_data_sram_rdata)
    );

    dcache_top dut (
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

        .uc_data_sram_req  (uc_data_sram_req),
        .uc_data_sram_wr   (uc_data_sram_wr),
        .uc_data_sram_size (uc_data_sram_size),
        .uc_data_sram_addr (uc_data_sram_addr),
        .uc_data_sram_wstrb(uc_data_sram_wstrb),
        .uc_data_sram_wdata(uc_data_sram_wdata),
        .uc_data_sram_addr_ok(uc_data_sram_addr_ok),
        .uc_data_sram_data_ok(uc_data_sram_data_ok),
        .uc_data_sram_rdata  (uc_data_sram_rdata),

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
            $dumpfile("dcache_hitrate_tb.vcd");
            $dumpvars(0, dcache_hitrate_tb);
        end
    end

    task automatic wait_cycles(input integer n);
        integer k;
        begin
            for (k = 0; k < n; k = k + 1) @(posedge clk);
        end
    endtask

    // one cached access + miss detect
    task automatic cached_access_count;
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
                if (timeout > 8000) $fatal(1, "TIMEOUT addr_ok addr=%08x", addr);
            end
            @(posedge clk);
            data_sram_req = 1'b0;

            timeout = 0;
            while (!data_sram_data_ok) begin
                if (rd_req && rd_rdy) miss_seen = 1'b1;
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 8000) $fatal(1, "TIMEOUT data_ok addr=%08x", addr);
            end
            rdata  = data_sram_rdata;
            is_miss= miss_seen;
            @(posedge clk);
        end
    endtask

    // LFSR
    reg [31:0] lfsr;
    function [31:0] lfsr_next;
        input [31:0] cur;
        begin
            lfsr_next = {cur[30:0], cur[31] ^ cur[21] ^ cur[1] ^ 1'b1};
        end
    endfunction

    // counters
    integer total;
    integer miss;
    integer hit;
    integer r_total, r_miss, r_hit;
    integer w_total, w_miss, w_hit;
    integer wb_cnt;

    // params
    integer N;
    reg [31:0] base_hot;
    reg [31:0] base_cold;

    // monitor writeback count (wr_req handshake)
    always @(posedge clk) begin
        if (!resetn) begin
            wb_cnt <= 0;
        end else begin
            if (wr_req && wr_rdy) wb_cnt <= wb_cnt + 1;
        end
    end

    integer i;
    reg [31:0] r;
    reg        is_miss;
    real       hitrate;

    initial begin
        // defaults
        resetn = 1'b0;
        data_sram_req   = 1'b0;
        data_sram_wr    = 1'b0;
        data_sram_size  = 2'b10;
        data_sram_addr  = 32'b0;
        data_sram_wstrb = 4'b0;
        data_sram_wdata = 32'b0;
        data_cached     = 1'b1;

        lfsr = 32'hCAFE_BABE;

        N = 4096;
        if ($value$plusargs("N=%d", N)) ;

        base_hot  = 32'h0000_1000; // hot region
        base_cold = 32'h0020_0000; // cold region

        wait_cycles(10);
        resetn = 1'b1;
        wait_cycles(5);

        total = 0; miss = 0;
        r_total = 0; r_miss = 0;
        w_total = 0; w_miss = 0;
        wb_cnt  = 0;

        // workload:
        // - 75% access hot region with spatial locality
        // - 25% access cold region pseudo-random
        // - mix reads/writes: every 4th op is a store
        for (i = 0; i < N; i = i + 1) begin
            lfsr = lfsr_next(lfsr);

            // choose region
            if (lfsr[7:0] < 8'd192) begin
                // hot: 4KB window
                data_sram_addr = base_hot + {lfsr[11:2], 2'b00};
            end else begin
                // cold: 64KB window
                data_sram_addr = base_cold + {lfsr[15:2], 2'b00};
            end

            if ((i & 3) == 0) begin
                // store
                cached_access_count(1'b1, data_sram_addr, 4'b1111, (32'h9000_0000 ^ i), r, is_miss);
                total = total + 1;
                w_total = w_total + 1;
                if (is_miss) begin
                    miss = miss + 1;
                    w_miss = w_miss + 1;
                end
            end else begin
                // load
                cached_access_count(1'b0, data_sram_addr, 4'b0000, 32'b0, r, is_miss);
                total = total + 1;
                r_total = r_total + 1;
                if (is_miss) begin
                    miss = miss + 1;
                    r_miss = r_miss + 1;
                end
            end
        end

        hit = total - miss;
        r_hit = r_total - r_miss;
        w_hit = w_total - w_miss;

        if (total == 0) hitrate = 0.0;
        else hitrate = (100.0 * hit) / total;

        $display("\n==== D$ hitrate report ====");
        $display("N=%0d", N);
        $display("total=%0d hit=%0d miss=%0d hitrate=%0.2f%%", total, hit, miss, hitrate);
        $display("read : total=%0d hit=%0d miss=%0d", r_total, r_hit, r_miss);
        $display("write: total=%0d hit=%0d miss=%0d", w_total, w_hit, w_miss);
        $display("writeback(line) count=%0d", wb_cnt);
        $display("===========================\n");

        $finish;
    end

endmodule
