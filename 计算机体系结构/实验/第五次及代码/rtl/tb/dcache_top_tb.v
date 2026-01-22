`timescale 1ns / 1ps

module dcache_top_tb;

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

    // wave dump
    initial begin
        if ($test$plusargs("dump")) begin
            $dumpfile("dcache_top_tb.vcd");
            $dumpvars(0, dcache_top_tb);
        end
    end

    task automatic wait_cycles(input integer n);
        integer k;
        begin
            for (k = 0; k < n; k = k + 1) @(posedge clk);
        end
    endtask

    task automatic data_access;
        input         cached;
        input         wr;
        input  [31:0] addr;
        input  [ 3:0] wstrb;
        input  [31:0] wdata;
        output [31:0] rdata;
        integer timeout;
        begin
            data_cached     = cached;
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
                if (timeout > 4000) begin
                    $display("TIMEOUT: addr_ok not asserted (cached=%0d wr=%0d addr=%08x)", cached, wr, addr);
                    $fatal(1);
                end
            end
            @(posedge clk);
            data_sram_req = 1'b0;

            timeout = 0;
            while (!data_sram_data_ok) begin
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 4000) begin
                    $display("TIMEOUT: data_ok not asserted (cached=%0d wr=%0d addr=%08x)", cached, wr, addr);
                    $fatal(1);
                end
            end
            rdata = data_sram_rdata;
            $display("[%0t] TB: data_%s cached=%0d addr=%08x wdata=%08x wstrb=%b -> rdata=%08x",
                     $time, wr?"WR":"RD", cached, addr, wdata, wstrb, rdata);
            @(posedge clk);
        end
    endtask

    reg [31:0] r;

    // addresses A/B/C share same index[11:4] (here use index=0x10)
    localparam [31:0] A = 32'h0000_0100; // tag=0x0, index=0x10
    localparam [31:0] B = 32'h0001_0100; // different tag, same index
    localparam [31:0] C = 32'h0002_0100; // different tag, same index

    initial begin
        resetn = 1'b0;
        data_sram_req   = 1'b0;
        data_sram_wr    = 1'b0;
        data_sram_size  = 2'b10;
        data_sram_addr  = 32'b0;
        data_sram_wstrb = 4'b0;
        data_sram_wdata = 32'b0;
        data_cached     = 1'b1;

        wait_cycles(10);
        resetn = 1'b1;
        wait_cycles(5);

        // 1) cached store miss (write-allocate) then cached load hit
        data_access(1'b1, 1'b1, A, 4'b1111, 32'hDEAD_BEEF, r);
        data_access(1'b1, 1'b0, A, 4'b0000, 32'b0, r);
        if (r !== 32'hDEAD_BEEF) begin
            $display("ERROR: load after store mismatch @A got=%08x", r);
            $fatal(1);
        end

        // 2) fill second way with another dirty line
        data_access(1'b1, 1'b1, B, 4'b1111, 32'h1111_1111, r);
        data_access(1'b1, 1'b0, B, 4'b0000, 32'b0, r);
        if (r !== 32'h1111_1111) begin
            $display("ERROR: load after store mismatch @B got=%08x", r);
            $fatal(1);
        end

        // 3) third miss should evict way1 deterministically (B) due to LFSR init/update;
        //    expect a writeback before/around refill. We don't hard-check ordering here,
        //    but later we verify B is written back by reloading B after eviction.
        data_access(1'b1, 1'b1, C, 4'b1111, 32'h2222_2222, r);

        // 4) reload B: should miss and fetch from memory which should contain 0x1111_1111 if writeback worked
        data_access(1'b1, 1'b0, B, 4'b0000, 32'b0, r);
        if (r !== 32'h1111_1111) begin
            $display("ERROR: writeback check failed, reload @B got=%08x (expect 11111111)", r);
            $fatal(1);
        end

        // 5) uncached path sanity
        data_access(1'b0, 1'b0, 32'h0000_0200, 4'b0000, 32'b0, r);
        data_access(1'b0, 1'b1, 32'h0000_0200, 4'b1111, 32'hA5A5_5A5A, r);
        data_access(1'b0, 1'b0, 32'h0000_0200, 4'b0000, 32'b0, r);
        if (r !== 32'hA5A5_5A5A) begin
            $display("ERROR: uncached store/load mismatch got=%08x", r);
            $fatal(1);
        end

        $display("dcache_top_tb PASS");
        $finish;
    end

endmodule
