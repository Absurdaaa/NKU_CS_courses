`timescale 1ns/1ps

// Self-contained testbench for transfer_bridge burst extension.
//
// What it checks:
// 1) Cache linefill uses AXI burst: ARLEN=3, ARSIZE=2, ARCACHE=4'b1111, RID=CACHE_ID.
// 2) Cache return stream is 4 beats and forwarded via cache_ret_*.
// 3) Cache writeback (optional) uses AWLEN=3 and WLAST asserted on 4th beat.
// 4) Data port single read/write (ARLEN/AWLEN=0) still works.
//
// This TB instantiates:
// - transfer_bridge
// - a tiny AXI memory model (supports INCR burst len 0 and 3)
//
// How to compile (Vivado/xsim example):
// - Add simulation sources:
//   - rtl/myCPU/tools.v
//   - rtl/myCPU/transfer_bridge.v
//   - rtl/tb/transfer_bridge_burst_tb.v

module transfer_bridge_burst_tb;

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
        repeat (20) @(posedge aclk);
        aresetn = 1'b1;
    end

    // -----------------
    // AXI wires
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

    // -----------------
    // SRAM inst/data ports
    // -----------------
    reg         inst_sram_req;
    reg         inst_sram_wr;
    reg [1:0]   inst_sram_size;
    reg [31:0]  inst_sram_addr;
    reg [3:0]   inst_sram_wstrb;
    reg [31:0]  inst_sram_wdata;
    wire        inst_sram_addr_ok;
    wire        inst_sram_data_ok;
    wire [31:0] inst_sram_rdata;

    reg         data_sram_req;
    reg         data_sram_wr;
    reg [1:0]   data_sram_size;
    reg [31:0]  data_sram_addr;
    reg [31:0]  data_sram_wdata;
    reg [3:0]   data_sram_wstrb;
    wire        data_sram_addr_ok;
    wire        data_sram_data_ok;
    wire [31:0] data_sram_rdata;

    // -----------------
    // Cache burst side
    // -----------------
    reg         cache_rd_req;
    reg [2:0]   cache_rd_type;
    reg [31:0]  cache_rd_addr;
    wire        cache_rd_rdy;
    wire        cache_ret_valid;
    wire        cache_ret_last;
    wire [31:0] cache_ret_data;

    reg         cache_wr_req;
    reg [2:0]   cache_wr_type;
    reg [31:0]  cache_wr_addr;
    reg [3:0]   cache_wr_wstrb;
    reg [127:0] cache_wr_data;
    wire        cache_wr_rdy;

    // DUT
    transfer_bridge dut (
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

        .inst_sram_req      (inst_sram_req),
        .inst_sram_wr       (inst_sram_wr),
        .inst_sram_size     (inst_sram_size),
        .inst_sram_addr     (inst_sram_addr),
        .inst_sram_wstrb    (inst_sram_wstrb),
        .inst_sram_wdata    (inst_sram_wdata),
        .inst_sram_addr_ok  (inst_sram_addr_ok),
        .inst_sram_data_ok  (inst_sram_data_ok),
        .inst_sram_rdata    (inst_sram_rdata),

        .cache_rd_req       (cache_rd_req),
        .cache_rd_type      (cache_rd_type),
        .cache_rd_addr      (cache_rd_addr),
        .cache_rd_rdy       (cache_rd_rdy),
        .cache_ret_valid    (cache_ret_valid),
        .cache_ret_last     (cache_ret_last),
        .cache_ret_data     (cache_ret_data),

        .cache_wr_req       (cache_wr_req),
        .cache_wr_type      (cache_wr_type),
        .cache_wr_addr      (cache_wr_addr),
        .cache_wr_wstrb     (cache_wr_wstrb),
        .cache_wr_data      (cache_wr_data),
        .cache_wr_rdy       (cache_wr_rdy),

        .data_sram_req      (data_sram_req),
        .data_sram_wr       (data_sram_wr),
        .data_sram_size     (data_sram_size),
        .data_sram_addr     (data_sram_addr),
        .data_sram_wdata    (data_sram_wdata),
        .data_sram_wstrb    (data_sram_wstrb),
        .data_sram_addr_ok  (data_sram_addr_ok),
        .data_sram_data_ok  (data_sram_data_ok),
        .data_sram_rdata    (data_sram_rdata)
    );

    // -----------------
    // Tiny AXI memory model
    // -----------------
    // word-addressed memory: mem[word_addr] -> 32-bit
    reg [31:0] mem [0:4095];
    integer k;

    initial begin
        for (k = 0; k < 4096; k = k + 1) begin
            mem[k] = 32'hA000_0000 ^ k;
        end
    end

    // read channel state
    reg        rd_active;
    reg [3:0]  rd_id;
    reg [31:0] rd_addr;
    reg [7:0]  rd_len;
    reg [2:0]  rd_size;
    reg [7:0]  rd_beat;

    // write channel state
    reg        wr_active;
    reg [3:0]  wr_id;
    reg [31:0] wr_addr;
    reg [7:0]  wr_len;
    reg [2:0]  wr_size;
    reg [7:0]  wr_beat;

    wire [31:0] rd_word_addr0 = (rd_addr >> 2);
    wire [31:0] wr_word_addr0 = (wr_addr >> 2);

    // always-ready by default
    always @(posedge aclk) begin
        if (!aresetn) begin
            arready <= 1'b0;
            awready <= 1'b0;
            wready  <= 1'b0;

            rvalid <= 1'b0;
            rlast  <= 1'b0;
            rid    <= 4'h0;
            rdata  <= 32'h0;
            rresp  <= 2'b00;

            bvalid <= 1'b0;
            bid    <= 4'h0;
            bresp  <= 2'b00;

            rd_active <= 1'b0;
            rd_id     <= 4'h0;
            rd_addr   <= 32'h0;
            rd_len    <= 8'h0;
            rd_size   <= 3'h0;
            rd_beat   <= 8'h0;

            wr_active <= 1'b0;
            wr_id     <= 4'h0;
            wr_addr   <= 32'h0;
            wr_len    <= 8'h0;
            wr_size   <= 3'h0;
            wr_beat   <= 8'h0;
        end else begin
            // default: ready
            arready <= 1'b1;
            awready <= 1'b1;
            wready  <= 1'b1;

            // default: drive R/B only when active
            if (rvalid && rready) begin
                rvalid <= 1'b0;
                rlast  <= 1'b0;
            end
            if (bvalid && bready) begin
                bvalid <= 1'b0;
                bid    <= 4'h0;
                bresp  <= 2'b00;
            end

            // capture AR
            if (!rd_active && arvalid && arready) begin
                rd_active <= 1'b1;
                rd_id   <= arid;
                rd_addr <= araddr;
                rd_len  <= arlen;
                rd_size <= arsize;
                rd_beat <= 0;
            end

            // issue R beats
            if (rd_active) begin
                if (!rvalid || (rvalid && rready)) begin
                    // one beat per cycle
                    rvalid <= 1'b1;
                    rid    <= rd_id;
                    rresp  <= 2'b00;

                    // only support 32-bit beats (arsize==2)
                    rdata <= mem[rd_word_addr0 + rd_beat];

                    if (rd_beat == rd_len) begin
                        rlast <= 1'b1;
                        rd_active <= 1'b0;
                    end else begin
                        rlast <= 1'b0;
                        rd_beat <= rd_beat + 1;
                    end
                end
            end

            // capture AW
            if (!wr_active && awvalid && awready) begin
                wr_active <= 1'b1;
                wr_id   <= awid;
                wr_addr <= awaddr;
                wr_len  <= awlen;
                wr_size <= awsize;
                wr_beat <= 0;
            end

            // accept W beats
            if (wr_active && wvalid && wready) begin
                // only support 32-bit beats
                if (wstrb[0]) mem[wr_word_addr0 + wr_beat][7:0]   <= wdata[7:0];
                if (wstrb[1]) mem[wr_word_addr0 + wr_beat][15:8]  <= wdata[15:8];
                if (wstrb[2]) mem[wr_word_addr0 + wr_beat][23:16] <= wdata[23:16];
                if (wstrb[3]) mem[wr_word_addr0 + wr_beat][31:24] <= wdata[31:24];

                if (wr_beat == wr_len) begin
                    // expect wlast
                    if (!wlast) begin
                        $display("[TB][FAIL] WLAST not asserted on last beat");
                        $finish;
                    end
                    wr_active <= 1'b0;
                    // emit B next cycle
                    if (!bvalid) begin
                        bvalid <= 1'b1;
                        bid    <= wr_id;
                        bresp  <= 2'b00;
                    end
                end else begin
                    if (wlast) begin
                        $display("[TB][FAIL] WLAST asserted early beat=%0d len=%0d", wr_beat, wr_len);
                        $finish;
                    end
                    wr_beat <= wr_beat + 1;
                end
            end
        end
    end

    // -----------------
    // TB helpers
    // -----------------
    localparam [3:0] INST_ID  = 4'h0;
    localparam [3:0] DATA_ID  = 4'h1;
    localparam [3:0] CACHE_ID = 4'h2;

    task axi_expect_cache_ar;
        begin
            // wait for AR handshake with cache id
            while (!(arvalid && arready && arid == CACHE_ID)) @(posedge aclk);
            if (arlen !== 8'd3) begin
                $display("[TB][FAIL] cache ARLEN exp=3 got=%0d", arlen);
                $finish;
            end
            if (arsize !== 3'b010) begin
                $display("[TB][FAIL] cache ARSIZE exp=2 got=%b", arsize);
                $finish;
            end
            if (arcache !== 4'b1111) begin
                $display("[TB][FAIL] cache ARCACHE exp=1111 got=%b", arcache);
                $finish;
            end
        end
    endtask

    task do_data_read;
        input [31:0] addr;
        reg [31:0] exp;
        begin
            exp = mem[addr >> 2];
            @(posedge aclk);
            data_sram_req   <= 1'b1;
            data_sram_wr    <= 1'b0;
            data_sram_size  <= 2'b10;
            data_sram_addr  <= addr;
            data_sram_wdata <= 32'h0;
            data_sram_wstrb <= 4'h0;
            while (!data_sram_addr_ok) @(posedge aclk);
            @(posedge aclk);
            data_sram_req <= 1'b0;
            while (!data_sram_data_ok) @(posedge aclk);
            if (data_sram_rdata !== exp) begin
                $display("[TB][FAIL] data read addr=%h exp=%h got=%h", addr, exp, data_sram_rdata);
                $finish;
            end
        end
    endtask

    task do_inst_read;
        input [31:0] addr;
        reg [31:0] exp;
        begin
            exp = mem[addr >> 2];
            @(posedge aclk);
            inst_sram_req   <= 1'b1;
            inst_sram_wr    <= 1'b0;
            inst_sram_size  <= 2'b10;
            inst_sram_addr  <= addr;
            inst_sram_wstrb <= 4'h0;
            inst_sram_wdata <= 32'h0;
            while (!inst_sram_addr_ok) @(posedge aclk);
            @(posedge aclk);
            inst_sram_req <= 1'b0;
            while (!inst_sram_data_ok) @(posedge aclk);
            if (inst_sram_rdata !== exp) begin
                $display("[TB][FAIL] inst read addr=%h exp=%h got=%h", addr, exp, inst_sram_rdata);
                $finish;
            end
        end
    endtask

    task do_data_write;
        input [31:0] addr;
        input [31:0] dat;
        begin
            @(posedge aclk);
            data_sram_req   <= 1'b1;
            data_sram_wr    <= 1'b1;
            data_sram_size  <= 2'b10;
            data_sram_addr  <= addr;
            data_sram_wdata <= dat;
            data_sram_wstrb <= 4'hF;
            while (!data_sram_addr_ok) @(posedge aclk);
            @(posedge aclk);
            data_sram_req <= 1'b0;
            while (!data_sram_data_ok) @(posedge aclk);
            if (mem[addr >> 2] !== dat) begin
                $display("[TB][FAIL] data write not committed addr=%h exp=%h got=%h", addr, dat, mem[addr >> 2]);
                $finish;
            end
        end
    endtask

    task do_cache_linefill;
        input [31:0] line_addr;
        reg [31:0] exp0, exp1, exp2, exp3;
        reg [1:0]  beat;
        begin
            exp0 = mem[(line_addr >> 2) + 0];
            exp1 = mem[(line_addr >> 2) + 1];
            exp2 = mem[(line_addr >> 2) + 2];
            exp3 = mem[(line_addr >> 2) + 3];

            @(posedge aclk);
            cache_rd_req  <= 1'b1;
            cache_rd_type <= 3'b010;
            cache_rd_addr <= line_addr;
            while (!cache_rd_rdy) @(posedge aclk);
            @(posedge aclk);
            cache_rd_req <= 1'b0;

            axi_expect_cache_ar();

            beat = 0;
            while (beat != 2'd3) begin
                while (!cache_ret_valid) @(posedge aclk);
                case (beat)
                    2'd0: if (cache_ret_data !== exp0) begin $display("[TB][FAIL] cache beat0 exp=%h got=%h", exp0, cache_ret_data); $finish; end
                    2'd1: if (cache_ret_data !== exp1) begin $display("[TB][FAIL] cache beat1 exp=%h got=%h", exp1, cache_ret_data); $finish; end
                    2'd2: if (cache_ret_data !== exp2) begin $display("[TB][FAIL] cache beat2 exp=%h got=%h", exp2, cache_ret_data); $finish; end
                    default: ;
                endcase
                if (cache_ret_last) begin
                    $display("[TB][FAIL] cache ret_last asserted early beat=%0d", beat);
                    $finish;
                end
                beat = beat + 1;
                @(posedge aclk);
            end
            // beat 3
            while (!cache_ret_valid) @(posedge aclk);
            if (cache_ret_data !== exp3) begin
                $display("[TB][FAIL] cache beat3 exp=%h got=%h", exp3, cache_ret_data);
                $finish;
            end
            if (!cache_ret_last) begin
                $display("[TB][FAIL] cache ret_last not asserted on beat3");
                $finish;
            end
            @(posedge aclk);
        end
    endtask

    task do_cache_writeback;
        input [31:0] line_addr;
        input [127:0] line_dat;
        reg [31:0] d0,d1,d2,d3;
        begin
            d0 = line_dat[31:0];
            d1 = line_dat[63:32];
            d2 = line_dat[95:64];
            d3 = line_dat[127:96];

            @(posedge aclk);
            cache_wr_req   <= 1'b1;
            cache_wr_type  <= 3'b010;
            cache_wr_addr  <= line_addr;
            cache_wr_wstrb <= 4'hF;
            cache_wr_data  <= line_dat;
            while (!cache_wr_rdy) @(posedge aclk);
            @(posedge aclk);
            cache_wr_req <= 1'b0;

            // expect AW handshake for cache
            while (!(awvalid && awready && awid == CACHE_ID)) @(posedge aclk);
            if (awlen !== 8'd3) begin
                $display("[TB][FAIL] cache AWLEN exp=3 got=%0d", awlen);
                $finish;
            end
            if (awsize !== 3'b010) begin
                $display("[TB][FAIL] cache AWSIZE exp=2 got=%b", awsize);
                $finish;
            end

            // wait few cycles for writes to commit
            repeat (10) @(posedge aclk);

            if (mem[(line_addr >> 2) + 0] !== d0 ||
                mem[(line_addr >> 2) + 1] !== d1 ||
                mem[(line_addr >> 2) + 2] !== d2 ||
                mem[(line_addr >> 2) + 3] !== d3) begin
                $display("[TB][FAIL] cache writeback not committed");
                $finish;
            end
        end
    endtask

    // -----------------
    // stimulus
    // -----------------
    initial begin
        inst_sram_req   = 1'b0;
        inst_sram_wr    = 1'b0;
        inst_sram_size  = 2'b10;
        inst_sram_addr  = 32'h0;
        inst_sram_wstrb = 4'h0;
        inst_sram_wdata = 32'h0;

        data_sram_req   = 1'b0;
        data_sram_wr    = 1'b0;
        data_sram_size  = 2'b10;
        data_sram_addr  = 32'h0;
        data_sram_wdata = 32'h0;
        data_sram_wstrb = 4'h0;

        cache_rd_req  = 1'b0;
        cache_rd_type = 3'b010;
        cache_rd_addr = 32'h0;

        cache_wr_req   = 1'b0;
        cache_wr_type  = 3'b010;
        cache_wr_addr  = 32'h0;
        cache_wr_wstrb = 4'hF;
        cache_wr_data  = 128'h0;

        @(posedge aresetn);
        repeat (5) @(posedge aclk);

        // basic data read/write sanity
        do_inst_read(32'h0000_0080);
        do_data_read(32'h0000_0040);
        do_data_write(32'h0000_0040, 32'hDEAD_BEEF);
        do_data_read(32'h0000_0040);

        // cache linefill check
        do_cache_linefill(32'h0000_0100);

        // cache writeback check
        do_cache_writeback(32'h0000_0200, {32'h4444_3333, 32'h2222_1111, 32'hbbbb_aaaa, 32'hdddd_cccc});
        do_cache_linefill(32'h0000_0200);

        $display("[TB][PASS] transfer_bridge_burst_tb");
        $finish;
    end

endmodule
