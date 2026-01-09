`timescale 1ns / 1ps

module icache_top_tb;

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

    // unified mem also serves uncached path
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

    // wave dump (works with e.g. iverilog+vvp; harmless otherwise)
    initial begin
        if ($test$plusargs("dump")) begin
            $dumpfile("icache_top_tb.vcd");
            $dumpvars(0, icache_top_tb);
        end
    end

    // helpers
    task automatic wait_cycles(input integer n);
        integer k;
        begin
            for (k = 0; k < n; k = k + 1) @(posedge clk);
        end
    endtask

    task automatic inst_read;
        input  [31:0] addr;
        input         cached;
        output [31:0] rdata;
        integer timeout;
        begin
            // drive request
            inst_cached     = cached;
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
                if (timeout > 2000) begin
                    $display("TIMEOUT: addr_ok not asserted (cached=%0d addr=%08x)", cached, addr);
                    $fatal(1);
                end
            end
            // accept at this posedge, drop req after
            @(posedge clk);
            inst_sram_req = 1'b0;

            timeout = 0;
            while (!inst_sram_data_ok) begin
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 2000) begin
                    $display("TIMEOUT: data_ok not asserted (cached=%0d addr=%08x)", cached, addr);
                    $fatal(1);
                end
            end
            rdata = inst_sram_rdata;
            $display("[%0t] TB: inst_read cached=%0d addr=%08x -> %08x", $time, cached, addr, rdata);
            @(posedge clk);
        end
    endtask

    // main test
    reg [31:0] r0, r1, r2;
    reg        saw_last;

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

        wait_cycles(10);
        resetn = 1'b1;
        wait_cycles(5);

        // 1) cached read miss then hit
        inst_read(32'h0000_1000, 1'b1, r0);
        inst_read(32'h0000_1000, 1'b1, r1);
        if (r0 !== r1) begin
            $display("ERROR: cached hit data mismatch r0=%08x r1=%08x", r0, r1);
            $fatal(1);
        end

        // 2) uncached read
        inst_read(32'h0000_2000, 1'b0, r2);

        // 3) stress: try to make bypass_ok coincide with cache_data_ok (exercise hold buffer)
        //    - start cached miss
        //    - when last beat observed, issue an uncached request one cycle later
        saw_last = 1'b0;

        fork
            begin : MONITOR_LAST
                forever begin
                    @(posedge clk);
                    if (ret_valid && ret_last) saw_last = 1'b1;
                end
            end

            begin : DO_COINCIDE
                // start a cached miss
                inst_cached     = 1'b1;
                inst_sram_wr    = 1'b0;
                inst_sram_size  = 2'b10;
                inst_sram_addr  = 32'h0000_3000;
                inst_sram_wstrb = 4'b0;
                inst_sram_wdata = 32'b0;
                inst_sram_req   = 1'b1;

                // wait accept
                while (!inst_sram_addr_ok) @(posedge clk);
                @(posedge clk);
                inst_sram_req = 1'b0;

                // wait until last beat seen
                while (!saw_last) @(posedge clk);
                // next cycle issue bypass request; its data_ok comes 1 cycle later,
                // which should coincide with cache data_ok (2 cycles after ret_last)
                @(posedge clk);

                inst_read(32'h0000_4000, 1'b0, r2);
            end
        join_any
        disable MONITOR_LAST;

        // allow cached miss to complete (should not deadlock)
        wait_cycles(50);

        $display("icache_top_tb PASS");
        $finish;
    end

endmodule
