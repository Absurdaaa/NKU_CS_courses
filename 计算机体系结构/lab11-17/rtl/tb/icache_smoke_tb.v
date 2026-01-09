`timescale 1ns/1ps

// Smoke test for icache_top + cache.v.
// Notes:
// - This TB is self-contained and does NOT require AXI IPs.
// - It only checks basic handshake behaviors and a couple of cache hits/misses.

module icache_smoke_tb;

    reg clk;
    reg resetn;

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        resetn = 1'b0;
        repeat (10) @(posedge clk);
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

    // Simple cache backing memory model: always ready; returns 4 beats with deterministic pattern
    reg [1:0] burst_cnt;
    reg       burst_active;
    reg [31:0] base_addr;

    always @(posedge clk) begin
        if (!resetn) begin
            rd_rdy <= 1'b1;
            wr_rdy <= 1'b1;
            ret_valid <= 1'b0;
            ret_last  <= 1'b0;
            ret_data  <= 32'h0;
            burst_cnt <= 2'b00;
            burst_active <= 1'b0;
            base_addr <= 32'h0;
        end else begin
            ret_valid <= 1'b0;
            ret_last  <= 1'b0;

            if (rd_req && rd_rdy && !burst_active) begin
                burst_active <= 1'b1;
                burst_cnt <= 2'b00;
                base_addr <= rd_addr;
            end

            if (burst_active) begin
                ret_valid <= 1'b1;
                ret_data  <= {base_addr[15:4], burst_cnt, 14'h123}; // simple unique per beat
                if (burst_cnt == 2'd3) begin
                    ret_last <= 1'b1;
                    burst_active <= 1'b0;
                end else begin
                    burst_cnt <= burst_cnt + 2'b01;
                end
            end
        end
    end

    // Uncached backing: 1-cycle response
    always @(posedge clk) begin
        if (!resetn) begin
            uc_inst_sram_addr_ok <= 1'b0;
            uc_inst_sram_data_ok <= 1'b0;
            uc_inst_sram_rdata   <= 32'h0;
        end else begin
            uc_inst_sram_addr_ok <= uc_inst_sram_req;
            uc_inst_sram_data_ok <= uc_inst_sram_req;
            uc_inst_sram_rdata   <= 32'hfeed_0000 | uc_inst_sram_addr[15:0];
        end
    end

    task do_fetch;
        input [31:0] addr;
        input cached;
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
        end
    endtask

    initial begin
        inst_sram_req   = 1'b0;
        inst_sram_wr    = 1'b0;
        inst_sram_size  = 2'b10;
        inst_sram_addr  = 32'h0;
        inst_sram_wstrb = 4'h0;
        inst_sram_wdata = 32'h0;
        inst_cached     = 1'b0;

        @(posedge resetn);
        repeat (2) @(posedge clk);

        // uncached fetch
        do_fetch(32'hbfc0_0000, 1'b0);
        if (inst_sram_rdata[31:16] != 16'hfeed) begin
            $display("[TB][FAIL] uncached fetch bad rdata=%h", inst_sram_rdata);
            $finish;
        end

        // cached miss then hit
        do_fetch(32'h8000_1000, 1'b1);
        do_fetch(32'h8000_1000, 1'b1);

        $display("[TB][PASS] icache_smoke_tb");
        $finish;
    end

endmodule
