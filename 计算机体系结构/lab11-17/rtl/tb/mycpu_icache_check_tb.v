`timescale 1ns/1ps

// mycpu-level ICache check TB
//
// Goal:
// - Drive mycpu_top with a tiny AXI memory model
// - Boot from kseg1 reset vector (BFC0_0000 -> paddr 1FC0_0000)
// - Jump to kseg0 code (8000_1000 -> paddr 0000_1000)
// - Verify that at least one cache linefill burst happens on AXI:
//     ARID=CACHE_ID(=2), ARLEN=3 (4 beats), ARSIZE=2, ARCACHE=4'b1111
// - Also verify the CPU makes forward progress by performing a store
//
// How to run (Vivado/xsim GUI):
// 1) Add design sources (at least):
//    - rtl/myCPU/*.v
//    - rtl/axi_wrap/axi_wrap.v (if your sim top includes it; this TB does not)
// 2) Add this TB: rtl/tb/mycpu_icache_check_tb.v
// 3) Set top = mycpu_icache_check_tb, run.
//
// PASS condition:
// - Prints [TB][PASS] mycpu_icache_check_tb

module mycpu_icache_check_tb;

    // -----------------
    // clock/reset
    // -----------------
    reg aclk;
    reg aresetn;

    initial begin
        aclk = 1'b0;
        forever #5 aclk = ~aclk;
    end

    initial begin
        aresetn = 1'b0;
        repeat (50) @(posedge aclk);
        aresetn = 1'b1;
    end

    wire [5:0] int = 6'b0;

    // -----------------
    // AXI master from mycpu_top
    // -----------------
    wire [3:0]  arid;
    wire [31:0] araddr;
    wire [7:0]  arlen;
    wire [2:0]  arsize;
    wire [1:0]  arburst;
    wire [1:0]  arlock;
    wire [3:0]  arcache;
    wire [2:0]  arprot;
    wire        arvalid;
    reg         arready;

    reg  [3:0]  rid;
    reg  [31:0] rdata;
    reg  [1:0]  rresp;
    reg         rlast;
    reg         rvalid;
    wire        rready;

    wire [3:0]  awid;
    wire [31:0] awaddr;
    wire [7:0]  awlen;
    wire [2:0]  awsize;
    wire [1:0]  awburst;
    wire [1:0]  awlock;
    wire [3:0]  awcache;
    wire [2:0]  awprot;
    wire        awvalid;
    reg         awready;

    wire [3:0]  wid;
    wire [31:0] wdata;
    wire [3:0]  wstrb;
    wire        wlast;
    wire        wvalid;
    reg         wready;

    reg  [3:0]  bid;
    reg  [1:0]  bresp;
    reg         bvalid;
    wire        bready;

    // debug
    wire [31:0] debug_wb_pc;
    wire [3:0]  debug_wb_rf_wen;
    wire [4:0]  debug_wb_rf_wnum;
    wire [31:0] debug_wb_rf_wdata;

    mycpu_top dut(
        .int                (int),
        .aclk               (aclk),
        .aresetn            (aresetn),

        .arid               (arid),
        .araddr             (araddr),
        .arlen              (arlen),
        .arsize             (arsize),
        .arburst            (arburst),
        .arlock             (arlock),
        .arcache            (arcache),
        .arprot             (arprot),
        .arvalid            (arvalid),
        .arready            (arready),

        .rid                (rid),
        .rdata              (rdata),
        .rresp              (rresp),
        .rlast              (rlast),
        .rvalid             (rvalid),
        .rready             (rready),

        .awid               (awid),
        .awaddr             (awaddr),
        .awlen              (awlen),
        .awsize             (awsize),
        .awburst            (awburst),
        .awlock             (awlock),
        .awcache            (awcache),
        .awprot             (awprot),
        .awvalid            (awvalid),
        .awready            (awready),

        .wid                (wid),
        .wdata              (wdata),
        .wstrb              (wstrb),
        .wlast              (wlast),
        .wvalid             (wvalid),
        .wready             (wready),

        .bid                (bid),
        .bresp              (bresp),
        .bvalid             (bvalid),
        .bready             (bready),

        .debug_wb_pc        (debug_wb_pc),
        .debug_wb_rf_wen    (debug_wb_rf_wen),
        .debug_wb_rf_wnum   (debug_wb_rf_wnum),
        .debug_wb_rf_wdata  (debug_wb_rf_wdata)
    );

    // -----------------
    // Tiny AXI memory model
    // -----------------
    // Memory map used here:
    // - Boot ROM @ 1FC0_0000 (physical) : holds a tiny program that jumps to kseg0
    // - RAM @ 0000_0000 (physical)      : holds kseg0 target code
    //
    // Assumptions:
    // - INCR burst
    // - beats are 32-bit (size==2)
    // - single outstanding read and single outstanding write are enough for this lab bridge

    localparam [3:0] CACHE_ID = 4'h2;

    // bootrom: 4KB (1024 words)
    reg [31:0] bootrom [0:1023];
    // ram: 64KB (16384 words)
    reg [31:0] ram [0:16383];

    integer i;
    initial begin
        for (i = 0; i < 1024; i = i + 1) bootrom[i] = 32'h0;
        for (i = 0; i < 16384; i = i + 1) ram[i] = 32'h0;

        // Boot code @ paddr 1FC0_0000 (vaddr BFC0_0000)
        //   lui  t0,0x8000
        //   ori  t0,t0,0x1000
        //   jr   t0
        //   nop
        bootrom[0] = 32'h3c08_8000;
        bootrom[1] = 32'h3508_1000;
        bootrom[2] = 32'h0100_0008;
        bootrom[3] = 32'h0000_0000;

        // kseg0 target code @ paddr 0000_1000 (vaddr 8000_1000)
        //   lui  t2,0xA000
        //   ori  t2,t2,0x0000
        //   addi t1,zero,0x1234
        //   sw   t1,0(t2)          ; store to kseg1 0xA000_0000 -> paddr 0
        // loop:
        //   j    loop
        //   nop
        ram[(32'h0000_1000 >> 2) + 0] = 32'h3c0a_a000;
        ram[(32'h0000_1000 >> 2) + 1] = 32'h354a_0000;
        ram[(32'h0000_1000 >> 2) + 2] = 32'h2009_1234;
        ram[(32'h0000_1000 >> 2) + 3] = 32'had49_0000;
        ram[(32'h0000_1000 >> 2) + 4] = 32'h0800_0404; // j 0x8000_1010
        ram[(32'h0000_1000 >> 2) + 5] = 32'h0000_0000;
    end

    function [31:0] mem_read_word;
        input [31:0] addr;
        reg [31:0] word_index;
        begin
            // 1FC0_0000..1FC0_0FFF
            if (addr[31:12] == 20'h1FC00) begin
                word_index = (addr[11:2]);
                mem_read_word = bootrom[word_index[9:0]];
            end else begin
                word_index = (addr[15:2]);
                mem_read_word = ram[word_index[13:0]];
            end
        end
    endfunction

    task mem_write_word;
        input [31:0] addr;
        input [31:0] data;
        input [3:0]  strb;
        reg [31:0] word_index;
        reg [31:0] old;
        reg [31:0] nw;
        begin
            // write only to RAM region for this TB
            word_index = addr[15:2];
            old = ram[word_index[13:0]];
            nw  = old;
            if (strb[0]) nw[7:0]   = data[7:0];
            if (strb[1]) nw[15:8]  = data[15:8];
            if (strb[2]) nw[23:16] = data[23:16];
            if (strb[3]) nw[31:24] = data[31:24];
            ram[word_index[13:0]] = nw;
        end
    endtask

    // read state
    reg        rd_active;
    reg [3:0]  rd_id;
    reg [31:0] rd_addr;
    reg [7:0]  rd_len;
    reg [7:0]  rd_beat;

    // write state
    reg        wr_active;
    reg [3:0]  wr_id;
    reg [31:0] wr_addr;
    reg [7:0]  wr_len;
    reg [7:0]  wr_beat;

    // monitors
    reg seen_cache_burst;
    reg seen_store;

    always @(posedge aclk) begin
        if (!aresetn) begin
            arready <= 1'b0;
            awready <= 1'b0;
            wready  <= 1'b0;

            rid   <= 4'h0;
            rdata <= 32'h0;
            rresp <= 2'b00;
            rlast <= 1'b0;
            rvalid<= 1'b0;

            bid   <= 4'h0;
            bresp <= 2'b00;
            bvalid<= 1'b0;

            rd_active <= 1'b0;
            rd_id     <= 4'h0;
            rd_addr   <= 32'h0;
            rd_len    <= 8'h0;
            rd_beat   <= 8'h0;

            wr_active <= 1'b0;
            wr_id     <= 4'h0;
            wr_addr   <= 32'h0;
            wr_len    <= 8'h0;
            wr_beat   <= 8'h0;

            seen_cache_burst <= 1'b0;
            seen_store       <= 1'b0;
        end else begin
            // always ready (this TB doesn't stress backpressure)
            arready <= 1'b1;
            awready <= 1'b1;
            wready  <= 1'b1;

            // default: clear handshaked responses
            if (rvalid && rready) begin
                rvalid <= 1'b0;
                rlast  <= 1'b0;
            end
            if (bvalid && bready) begin
                bvalid <= 1'b0;
                bid    <= 4'h0;
                bresp  <= 2'b00;
            end

            // AR capture
            if (!rd_active && arvalid && arready) begin
                rd_active <= 1'b1;
                rd_id   <= arid;
                rd_addr <= araddr;
                rd_len  <= arlen;
                rd_beat <= 0;

                if (arid == CACHE_ID) begin
                    if (arlen == 8'd3 && arsize == 3'b010 && arcache == 4'b1111) begin
                        seen_cache_burst <= 1'b1;
                    end else begin
                        $display("[TB][FAIL] cache AR mismatch: len=%0d size=%b cache=%b", arlen, arsize, arcache);
                        $finish;
                    end
                end
            end

            // drive R
            if (rd_active) begin
                if (!rvalid || (rvalid && rready)) begin
                    rvalid <= 1'b1;
                    rid    <= rd_id;
                    rresp  <= 2'b00;
                    rdata  <= mem_read_word(rd_addr + {rd_beat, 2'b00});

                    if (rd_beat == rd_len) begin
                        rlast <= 1'b1;
                        rd_active <= 1'b0;
                    end else begin
                        rlast <= 1'b0;
                        rd_beat <= rd_beat + 1;
                    end
                end
            end

            // AW capture
            if (!wr_active && awvalid && awready) begin
                wr_active <= 1'b1;
                wr_id   <= awid;
                wr_addr <= awaddr;
                wr_len  <= awlen;
                wr_beat <= 0;

                // detect the store our tiny program performs (to paddr 0)
                if (awaddr[31:0] == 32'h0000_0000) begin
                    seen_store <= 1'b1;
                end
            end

            // W accept
            if (wr_active && wvalid && wready) begin
                mem_write_word(wr_addr + {wr_beat, 2'b00}, wdata, wstrb);

                if (wr_beat == wr_len) begin
                    if (!wlast) begin
                        $display("[TB][FAIL] WLAST not asserted on last beat");
                        $finish;
                    end
                    wr_active <= 1'b0;

                    if (!bvalid) begin
                        bvalid <= 1'b1;
                        bid    <= wr_id;
                        bresp  <= 2'b00;
                    end
                end else begin
                    if (wlast) begin
                        $display("[TB][FAIL] WLAST asserted early");
                        $finish;
                    end
                    wr_beat <= wr_beat + 1;
                end
            end
        end
    end

    // -----------------
    // finish condition
    // -----------------
    integer cyc;
    always @(posedge aclk) begin
        if (!aresetn) begin
            cyc <= 0;
        end else begin
            cyc <= cyc + 1;

            // optional visibility
            if ((cyc % 2000) == 0) begin
                $display("[TB] cyc=%0d pc=%h seen_cache_burst=%0d seen_store=%0d", cyc, debug_wb_pc, seen_cache_burst, seen_store);
            end

            if (seen_cache_burst && seen_store) begin
                $display("[TB][PASS] mycpu_icache_check_tb");
                $finish;
            end

            if (cyc > 200000) begin
                $display("[TB][FAIL] timeout pc=%h seen_cache_burst=%0d seen_store=%0d", debug_wb_pc, seen_cache_burst, seen_store);
                $finish;
            end
        end
    end

endmodule
