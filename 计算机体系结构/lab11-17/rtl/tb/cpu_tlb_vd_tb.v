`timescale 1ns/1ps

// Regression TB to check V/D bit handling in address translation.
// Since this project currently does NOT implement TLBL/TLBS/Mod exceptions,
// the expected "safe" behavior is:
//   - if TLB tag matches but V=0: do NOT translate (treat as miss / fallback)
//   - if store and D=0: do NOT translate (treat as miss / fallback)
// This TB makes those behaviors observable by choosing low kuseg vaddrs
// that are still within the simple dmem range when not translated.

module cpu_tlb_vd_tb;

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

    wire        inst_sram_req;
    wire        inst_sram_wr;
    wire [ 1:0] inst_sram_size;
    wire [31:0] inst_sram_addr;
    wire [ 3:0] inst_sram_wstrb;
    wire [31:0] inst_sram_wdata;
    wire        inst_sram_addr_ok;
    reg         inst_sram_data_ok;
    reg  [31:0] inst_sram_rdata;

    wire        data_sram_req;
    wire        data_sram_wr;
    wire [ 1:0] data_sram_size;
    wire [31:0] data_sram_addr;
    wire [ 3:0] data_sram_wstrb;
    wire [31:0] data_sram_wdata;
    wire        data_sram_addr_ok;
    reg         data_sram_data_ok;
    reg  [31:0] data_sram_rdata;

    wire [31:0] debug_wb_pc;
    wire [ 3:0] debug_wb_rf_wen;
    wire [ 4:0] debug_wb_rf_wnum;
    wire [31:0] debug_wb_rf_wdata;

    mycpu_core dut (
        .clk                (clk),
        .resetn             (resetn),

        .inst_sram_req       (inst_sram_req),
        .inst_sram_wr        (inst_sram_wr),
        .inst_sram_size      (inst_sram_size),
        .inst_sram_addr      (inst_sram_addr),
        .inst_sram_wstrb     (inst_sram_wstrb),
        .inst_sram_wdata     (inst_sram_wdata),
        .inst_sram_addr_ok   (inst_sram_addr_ok),
        .inst_sram_data_ok   (inst_sram_data_ok),
        .inst_sram_rdata     (inst_sram_rdata),

        .data_sram_req       (data_sram_req),
        .data_sram_wr        (data_sram_wr),
        .data_sram_size      (data_sram_size),
        .data_sram_addr      (data_sram_addr),
        .data_sram_wstrb     (data_sram_wstrb),
        .data_sram_wdata     (data_sram_wdata),
        .data_sram_addr_ok   (data_sram_addr_ok),
        .data_sram_data_ok   (data_sram_data_ok),
        .data_sram_rdata     (data_sram_rdata),

        .debug_wb_pc         (debug_wb_pc),
        .debug_wb_rf_wen     (debug_wb_rf_wen),
        .debug_wb_rf_wnum    (debug_wb_rf_wnum),
        .debug_wb_rf_wdata   (debug_wb_rf_wdata)
    );

    // memories
    localparam IMEM_WORDS = 4096;
    localparam DMEM_WORDS = 262144;

    reg [31:0] imem [0:IMEM_WORDS-1];
    reg [31:0] dmem [0:DMEM_WORDS-1];

    localparam [31:0] IMEM_BASE      = 32'h1FC0_0000;
    localparam [31:0] RES_BASE_PADDR = 32'h0000_1000;

    // low kuseg vaddrs that remain in-range when "not translated"
    localparam [31:0] VA_V0 = 32'h0000_2000; // for V=0 test
    localparam [31:0] VA_D0 = 32'h0000_3000; // for D=0 test

    // translated physical pages (in range)
    localparam [31:0] PA_V0 = 32'h0006_0000; // PFN=0x60
    localparam [31:0] PA_D0 = 32'h0007_0000; // PFN=0x70

    // addr_ok always
    assign inst_sram_addr_ok = inst_sram_req;
    assign data_sram_addr_ok = data_sram_req;

    function [31:0] imem_read;
        input [31:0] paddr;
        reg [31:0] idx;
        begin
            if (paddr < IMEM_BASE) begin
                imem_read = 32'h0000_0000;
            end else begin
                idx = (paddr - IMEM_BASE) >> 2;
                if (idx >= IMEM_WORDS) imem_read = 32'h0000_0000;
                else imem_read = imem[idx];
            end
        end
    endfunction

    // fixed-latency FIFO SRAM models (same style as other TBs)
    localparam integer QDEPTH = 8;
    localparam [3:0] INST_LAT = 4'd3;
    localparam [3:0] DATA_LAT = 4'd5;

    reg [31:0] inst_q_addr [0:QDEPTH-1];
    reg [3:0]  inst_q_cnt  [0:QDEPTH-1];
    reg [QDEPTH-1:0] inst_q_valid;

    reg [31:0] data_q_addr [0:QDEPTH-1];
    reg [31:0] data_q_wdata[0:QDEPTH-1];
    reg [3:0]  data_q_wstrb[0:QDEPTH-1];
    reg        data_q_wr   [0:QDEPTH-1];
    reg [3:0]  data_q_cnt  [0:QDEPTH-1];
    reg [QDEPTH-1:0] data_q_valid;

    integer qi;
    integer inst_f, inst_r;
    integer data_f, data_r;
    reg [31:0] data_old, data_nw;

    function integer find_free;
        input [QDEPTH-1:0] v;
        integer k;
        begin
            find_free = -1;
            for (k = 0; k < QDEPTH; k = k + 1)
                if (!v[k]) begin find_free = k; k = QDEPTH; end
        end
    endfunction

    function integer find_ready;
        input [QDEPTH-1:0] v;
        input [3:0] cnt0;
        input [3:0] cnt1;
        input [3:0] cnt2;
        input [3:0] cnt3;
        input [3:0] cnt4;
        input [3:0] cnt5;
        input [3:0] cnt6;
        input [3:0] cnt7;
        integer k;
        begin
            find_ready = -1;
            for (k = 0; k < QDEPTH; k = k + 1) begin
                if (v[k]) begin
                    case (k)
                        0: if (cnt0 == 0) begin find_ready = 0; k = QDEPTH; end
                        1: if (cnt1 == 0) begin find_ready = 1; k = QDEPTH; end
                        2: if (cnt2 == 0) begin find_ready = 2; k = QDEPTH; end
                        3: if (cnt3 == 0) begin find_ready = 3; k = QDEPTH; end
                        4: if (cnt4 == 0) begin find_ready = 4; k = QDEPTH; end
                        5: if (cnt5 == 0) begin find_ready = 5; k = QDEPTH; end
                        6: if (cnt6 == 0) begin find_ready = 6; k = QDEPTH; end
                        7: if (cnt7 == 0) begin find_ready = 7; k = QDEPTH; end
                    endcase
                end
            end
        end
    endfunction

    always @(posedge clk) begin
        if (!resetn) begin
            inst_sram_data_ok <= 1'b0;
            inst_sram_rdata   <= 32'h0;
            inst_q_valid      <= {QDEPTH{1'b0}};
            for (qi = 0; qi < QDEPTH; qi = qi + 1) begin
                inst_q_addr[qi] <= 32'h0;
                inst_q_cnt[qi]  <= 4'h0;
            end
        end else begin
            if (inst_sram_req && inst_sram_addr_ok) begin
                inst_f = find_free(inst_q_valid);
                if (inst_f >= 0) begin
                    inst_q_valid[inst_f] <= 1'b1;
                    inst_q_addr[inst_f]  <= inst_sram_addr;
                    inst_q_cnt[inst_f]   <= INST_LAT;
                end
            end
            for (qi = 0; qi < QDEPTH; qi = qi + 1)
                if (inst_q_valid[qi] && inst_q_cnt[qi] != 0)
                    inst_q_cnt[qi] <= inst_q_cnt[qi] - 1'b1;
        end
    end

    always @(negedge clk) begin
        if (!resetn) begin
            inst_sram_data_ok <= 1'b0;
            inst_sram_rdata   <= 32'h0;
        end else begin
            inst_sram_data_ok <= 1'b0;
            inst_r = find_ready(inst_q_valid,
                           inst_q_cnt[0],inst_q_cnt[1],inst_q_cnt[2],inst_q_cnt[3],
                           inst_q_cnt[4],inst_q_cnt[5],inst_q_cnt[6],inst_q_cnt[7]);
            if (inst_r >= 0) begin
                inst_sram_data_ok <= 1'b1;
                inst_sram_rdata   <= imem_read(inst_q_addr[inst_r]);
                inst_q_valid[inst_r] <= 1'b0;
                inst_q_cnt[inst_r]   <= 4'h0;
            end
        end
    end

    always @(posedge clk) begin
        if (!resetn) begin
            data_sram_data_ok <= 1'b0;
            data_sram_rdata   <= 32'h0;
            data_q_valid      <= {QDEPTH{1'b0}};
            for (qi = 0; qi < QDEPTH; qi = qi + 1) begin
                data_q_addr[qi]  <= 32'h0;
                data_q_wdata[qi] <= 32'h0;
                data_q_wstrb[qi] <= 4'h0;
                data_q_wr[qi]    <= 1'b0;
                data_q_cnt[qi]   <= 4'h0;
            end
        end else begin
            if (data_sram_req && data_sram_addr_ok) begin
                data_f = find_free(data_q_valid);
                if (data_f >= 0) begin
                    data_q_valid[data_f] <= 1'b1;
                    data_q_addr[data_f]  <= data_sram_addr;
                    data_q_wdata[data_f] <= data_sram_wdata;
                    data_q_wstrb[data_f] <= data_sram_wstrb;
                    data_q_wr[data_f]    <= data_sram_wr;
                    data_q_cnt[data_f]   <= DATA_LAT;
                end
            end
            for (qi = 0; qi < QDEPTH; qi = qi + 1)
                if (data_q_valid[qi] && data_q_cnt[qi] != 0)
                    data_q_cnt[qi] <= data_q_cnt[qi] - 1'b1;
        end
    end

    always @(negedge clk) begin
        if (!resetn) begin
            data_sram_data_ok <= 1'b0;
            data_sram_rdata   <= 32'h0;
        end else begin
            data_sram_data_ok <= 1'b0;
            data_r = find_ready(data_q_valid,
                           data_q_cnt[0],data_q_cnt[1],data_q_cnt[2],data_q_cnt[3],
                           data_q_cnt[4],data_q_cnt[5],data_q_cnt[6],data_q_cnt[7]);
            if (data_r >= 0) begin
                if (data_q_wr[data_r]) begin
                    data_old = dmem[data_q_addr[data_r] >> 2];
                    data_nw  = data_old;
                    if (data_q_wstrb[data_r][0]) data_nw[ 7: 0] = data_q_wdata[data_r][ 7: 0];
                    if (data_q_wstrb[data_r][1]) data_nw[15: 8] = data_q_wdata[data_r][15: 8];
                    if (data_q_wstrb[data_r][2]) data_nw[23:16] = data_q_wdata[data_r][23:16];
                    if (data_q_wstrb[data_r][3]) data_nw[31:24] = data_q_wdata[data_r][31:24];
                    dmem[data_q_addr[data_r] >> 2] = data_nw;
                    data_sram_rdata <= 32'h0;
                end else begin
                    data_sram_rdata <= dmem[data_q_addr[data_r] >> 2];
                end
                data_sram_data_ok <= 1'b1;
                data_q_valid[data_r] <= 1'b0;
                data_q_cnt[data_r]   <= 4'h0;
            end
        end
    end

    // instruction encoders
    function [31:0] ins_lui;
        input [4:0] rt;
        input [15:0] imm;
        begin
            ins_lui = (6'h0F << 26) | (5'd0 << 21) | (rt << 16) | imm;
        end
    endfunction

    function [31:0] ins_ori;
        input [4:0] rt;
        input [4:0] rs;
        input [15:0] imm;
        begin
            ins_ori = (6'h0D << 26) | (rs << 21) | (rt << 16) | imm;
        end
    endfunction

    function [31:0] ins_lw;
        input [4:0] rt;
        input [4:0] rs;
        input [15:0] imm;
        begin
            ins_lw = (6'h23 << 26) | (rs << 21) | (rt << 16) | imm;
        end
    endfunction

    function [31:0] ins_sw;
        input [4:0] rt;
        input [4:0] rs;
        input [15:0] imm;
        begin
            ins_sw = (6'h2B << 26) | (rs << 21) | (rt << 16) | imm;
        end
    endfunction

    function [31:0] ins_mtc0;
        input [4:0] rt;
        input [4:0] rd;
        input [2:0] sel;
        begin
            ins_mtc0 = (6'h10 << 26) | (5'h04 << 21) | (rt << 16) | (rd << 11) | sel;
        end
    endfunction

    function [31:0] ins_tlbwi;
        input dummy;
        begin
            ins_tlbwi = (6'h10 << 26) | (5'h10 << 21) | 6'h02;
        end
    endfunction

    function [31:0] ins_j;
        input [25:0] target;
        begin
            ins_j = (6'h02 << 26) | target;
        end
    endfunction

    // program
    integer i;
    initial begin
        for (i = 0; i < IMEM_WORDS; i = i + 1) imem[i] = 32'h0;
        for (i = 0; i < DMEM_WORDS; i = i + 1) dmem[i] = 32'h0;

        // prepare data patterns
        dmem[VA_V0 >> 2] = 32'hAAAA_AAAA; // if not translated, load gets AAAA
        dmem[PA_V0 >> 2] = 32'hBBBB_BBBB; // if wrongly translated, load gets BBBB
        dmem[VA_D0 >> 2] = 32'h0000_0000;
        dmem[PA_D0 >> 2] = 32'h0000_0000;

        // clear result area
        for (i = 0; i < 64; i = i + 1)
            dmem[(RES_BASE_PADDR >> 2) + i] = 32'h0;

        load_program();
    end

    task load_program;
        integer pcw;
        begin
            pcw = 0;
            // t2 = 0x8000_1000 (result base)
            imem[pcw] = ins_lui(5'd10, 16'h8000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd10, 5'd10, 16'h1000); pcw = pcw + 1;

            // -------- Setup TLB entry idx0 for VA_V0 with V=0 (invalid)
            // Index=0
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd0, 3'd0); pcw = pcw + 1;
            // EntryHi = VA_V0 vpn2 + asid=1
            imem[pcw] = ins_lui(5'd9, VA_V0[31:16]); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0001); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1;
            // EntryLo0: PFN=0x60, D=1, V=0, G=0 => 0x1804
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h1804); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd2, 3'd0); pcw = pcw + 1;
            // EntryLo1 (unused)
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd3, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_tlbwi(1'b0); pcw = pcw + 1;

            // lw t0, 0(VA_V0) ; store to RES0
            imem[pcw] = ins_lui(5'd11, VA_V0[31:16]); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd11, 5'd11, VA_V0[15:0]); pcw = pcw + 1;
            imem[pcw] = ins_lw(5'd8, 5'd11, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h0000); pcw = pcw + 1;

            // -------- Setup TLB entry idx1 for VA_D0 with D=0 (not dirty)
            // Index=1
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0001); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd0, 3'd0); pcw = pcw + 1;
            // EntryHi = VA_D0 vpn2 + asid=1
            imem[pcw] = ins_lui(5'd9, VA_D0[31:16]); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0001); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1;
            // EntryLo0: PFN=0x70, D=0, V=1, G=0 => 0x1C02
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h1C02); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd2, 3'd0); pcw = pcw + 1;
            // EntryLo1 (unused)
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd3, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_tlbwi(1'b0); pcw = pcw + 1;

            // sw 0xCCCC_CCCC, 0(VA_D0)
            imem[pcw] = ins_lui(5'd8, 16'hCCCC); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd8, 5'd8, 16'hCCCC); pcw = pcw + 1;
            imem[pcw] = ins_lui(5'd11, VA_D0[31:16]); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd11, 5'd11, VA_D0[15:0]); pcw = pcw + 1;
            imem[pcw] = ins_sw(5'd8, 5'd11, 16'h0000); pcw = pcw + 1;

            // write observed locations to RES1/RES2
            // RES1 = dmem[VA_D0]
            imem[pcw] = ins_lw(5'd8, 5'd11, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h0004); pcw = pcw + 1;
            // RES2 = dmem[PA_D0]
            imem[pcw] = ins_lui(5'd11, PA_D0[31:16]); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd11, 5'd11, PA_D0[15:0]); pcw = pcw + 1;
            imem[pcw] = ins_lw(5'd8, 5'd11, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h0008); pcw = pcw + 1;

            // done magic
            imem[pcw] = ins_lui(5'd8, 16'hDEAD); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd8, 5'd8, 16'hBEEF); pcw = pcw + 1;
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h003C); pcw = pcw + 1;

            // loop forever
            imem[pcw] = ins_j((32'hBFC0_0000 + (pcw<<2)) >> 2); pcw = pcw + 1;
            imem[pcw] = 32'h0000_0000; pcw = pcw + 1;

            // mirror to exception entry
            for (i = 0; i < pcw; i = i + 1)
                imem[(32'h0000_0380 >> 2) + i] = imem[i];

            $display("[TB] Program loaded: %0d words", pcw);
        end
    endtask

    // self-check
    localparam [31:0] DONE_MAGIC = 32'hDEAD_BEEF;
    localparam [31:0] DONE_PADDR = RES_BASE_PADDR + 32'h003C;

    initial begin
        repeat (50000) @(posedge clk);
        $display("[TB][TIMEOUT] res0=%08x res1=%08x res2=%08x", dmem[(RES_BASE_PADDR+0)>>2], dmem[(RES_BASE_PADDR+4)>>2], dmem[(RES_BASE_PADDR+8)>>2]);
        $stop;
    end

    always @(posedge clk) begin
        if (resetn && dmem[DONE_PADDR >> 2] == DONE_MAGIC) begin
            check_all();
        end
    end

    task fail;
        input [255:0] msg;
        begin
            $display("[TB][FAIL] %0s", msg);
            $display("[TB] RES0(load V=0) = %08x (expect AAAA_AAAA)", dmem[(RES_BASE_PADDR+0)>>2]);
            $display("[TB] RES1(d0@VA)    = %08x (expect CCCC_CCCC)", dmem[(RES_BASE_PADDR+4)>>2]);
            $display("[TB] RES2(d0@PA)    = %08x (expect 0000_0000)", dmem[(RES_BASE_PADDR+8)>>2]);
            $stop;
        end
    endtask

    task check_all;
        reg [31:0] r0,r1,r2;
        begin
            r0 = dmem[(RES_BASE_PADDR + 32'h00) >> 2];
            r1 = dmem[(RES_BASE_PADDR + 32'h04) >> 2];
            r2 = dmem[(RES_BASE_PADDR + 32'h08) >> 2];

            // V=0 should not translate => load from VA_V0 yields AAAA
            if (r0 !== 32'hAAAA_AAAA) fail("V=0 handling: load was translated (or unexpected)");

            // D=0 store should not translate => VA_D0 updated, PA_D0 unchanged
            if (r1 !== 32'hCCCC_CCCC) fail("D=0 handling: store did not go to VA fallback");
            if (r2 !== 32'h0000_0000) fail("D=0 handling: store incorrectly wrote translated PA");

            $display("[TB][PASS] cpu_tlb_vd_tb");
            $display("[TB] RES0(load V=0) = %08x", r0);
            $display("[TB] RES1(d0@VA)    = %08x", r1);
            $display("[TB] RES2(d0@PA)    = %08x", r2);
            $finish;
        end
    endtask

endmodule
