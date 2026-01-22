`timescale 1ns/1ps

// A small "TLB test suite" program running on mycpu_core, with a simple SRAM model.
// It covers more cases than cpu_tlb_hazard_tb:
//  - even/odd page selection (va[12]) -> pfn0/pfn1
//  - global bit (G=1) ignoring ASID for match (TLBP hit with ASID mismatch)
//  - TLBR read-back correctness (EntryHi/Lo0/Lo1)
//  - TLBR->TLBP immediate sequence (flush/hazard sensitivity)
//  - instruction-side TLB translation (fetch from kuseg via s0)

module cpu_tlb_suite_tb;

    // clock / reset
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

    // DUT <-> SRAM
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

    // Simple memories
    localparam IMEM_WORDS = 4096;     // enough for small program
    localparam DMEM_WORDS = 262144;   // 1MB bytes -> 256K words

    reg [31:0] imem [0:IMEM_WORDS-1];
    reg [31:0] dmem [0:DMEM_WORDS-1];

    // direct-map paddr = (vaddr & 32'h1FFF_FFFF)
    localparam [31:0] IMEM_BASE = 32'h1FC0_0000;

    // result base (kseg0 direct map 0x8000_1000 -> paddr 0x0000_1000)
    localparam [31:0] RES_BASE_PADDR = 32'h0000_1000;

    // Virtual addresses used for translation tests
    localparam [31:0] VA1_BASE = 32'h0040_0000; // vpn2=0x200
    localparam [31:0] VA2_BASE = 32'h0080_0000; // vpn2=0x400
    localparam [31:0] VA3_BASE = 32'h00C0_0000; // vpn2=0x600

    // Instruction-side TLB test: jump into kuseg code pages (even/odd)
    localparam [31:0] VA_CODE_EVEN = 32'h0041_0000;
    localparam [31:0] VA_CODE_ODD  = 32'h0041_1000;
    localparam [31:0] PA_CODE_EVEN = 32'h0005_0000; // PFN=0x50
    localparam [31:0] PA_CODE_ODD  = 32'h0005_1000; // PFN=0x51

    // Combinational addr_ok
    assign inst_sram_addr_ok = inst_sram_req;
    assign data_sram_addr_ok = data_sram_req;

    function [31:0] imem_read;
        input [31:0] paddr;
        reg [31:0] idx;
        begin
            // Boot code is placed at IMEM_BASE (kseg1 reset vector direct-map).
            // For instruction-side TLB tests, we also allow fetching from low physical memory
            // by reading dmem[] as unified memory when paddr < IMEM_BASE.
            if (paddr < IMEM_BASE) begin
                if ((paddr >> 2) >= DMEM_WORDS) imem_read = 32'h0000_0000;
                else imem_read = dmem[paddr >> 2];
            end else begin
                idx = (paddr - IMEM_BASE) >> 2;
                if (idx >= IMEM_WORDS) imem_read = 32'h0000_0000;
                else imem_read = imem[idx];
            end
        end
    endfunction

    // SRAM models: queue + fixed latency, response on negedge (stable for posedge sampling)
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
    integer inst_f;
    integer inst_r;
    integer data_f;
    integer data_r;

    reg [31:0] data_old;
    reg [31:0] data_nw;

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

    // inst enqueue + countdown
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
            for (qi = 0; qi < QDEPTH; qi = qi + 1) begin
                if (inst_q_valid[qi] && inst_q_cnt[qi] != 0)
                    inst_q_cnt[qi] <= inst_q_cnt[qi] - 1'b1;
            end
        end
    end

    // inst respond
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
                inst_q_addr[inst_r]  <= 32'h0;
                inst_q_cnt[inst_r]   <= 4'h0;
            end
        end
    end

    // data enqueue + countdown
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
            for (qi = 0; qi < QDEPTH; qi = qi + 1) begin
                if (data_q_valid[qi] && data_q_cnt[qi] != 0)
                    data_q_cnt[qi] <= data_q_cnt[qi] - 1'b1;
            end
        end
    end

    // data respond
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
                data_q_addr[data_r]  <= 32'h0;
                data_q_wdata[data_r] <= 32'h0;
                data_q_wstrb[data_r] <= 4'h0;
                data_q_wr[data_r]    <= 1'b0;
                data_q_cnt[data_r]   <= 4'h0;
            end
        end
    end

    // init memories + program
    integer i;
    initial begin
        for (i = 0; i < IMEM_WORDS; i = i + 1) imem[i] = 32'h0;
        for (i = 0; i < DMEM_WORDS; i = i + 1) dmem[i] = 32'h0;

        // Distinct physical pages
        dmem[32'h0001_0000 >> 2] = 32'h1111_1111; // PFN=0x10
        dmem[32'h0002_0000 >> 2] = 32'h2222_2222; // PFN=0x20
        dmem[32'h0003_0000 >> 2] = 32'h3333_3333; // PFN=0x30
        dmem[32'h0004_0000 >> 2] = 32'h4444_4444; // PFN=0x40

        // clear result area
        for (i = 0; i < 64; i = i + 1) dmem[(RES_BASE_PADDR >> 2) + i] = 32'h0;

        // Place small code snippets into low physical memory for inst-side TLB test
        // even page @ PA_CODE_EVEN:
        //   store 0xAAAA5555 to RES9; jump to odd page
        dmem[(PA_CODE_EVEN + 32'h0000) >> 2] = ins_lui(5'd8, 16'hAAAA);
        dmem[(PA_CODE_EVEN + 32'h0004) >> 2] = ins_ori(5'd8, 5'd8, 16'h5555);
        dmem[(PA_CODE_EVEN + 32'h0008) >> 2] = ins_sw(5'd8, 5'd10, 16'h0024);
        dmem[(PA_CODE_EVEN + 32'h000C) >> 2] = ins_j(VA_CODE_ODD[27:2]);
        dmem[(PA_CODE_EVEN + 32'h0010) >> 2] = 32'h0000_0000; // nop

        // odd page @ PA_CODE_ODD:
        //   store 0xBBBB6666 to RES10; write DONE magic; loop forever
        dmem[(PA_CODE_ODD + 32'h0000) >> 2] = ins_lui(5'd8, 16'hBBBB);
        dmem[(PA_CODE_ODD + 32'h0004) >> 2] = ins_ori(5'd8, 5'd8, 16'h6666);
        dmem[(PA_CODE_ODD + 32'h0008) >> 2] = ins_sw(5'd8, 5'd10, 16'h0028);
        dmem[(PA_CODE_ODD + 32'h000C) >> 2] = ins_lui(5'd8, 16'hDEAD);
        dmem[(PA_CODE_ODD + 32'h0010) >> 2] = ins_ori(5'd8, 5'd8, 16'hBEEF);
        dmem[(PA_CODE_ODD + 32'h0014) >> 2] = ins_sw(5'd8, 5'd10, 16'h003C);
        dmem[(PA_CODE_ODD + 32'h0018) >> 2] = ins_j(VA_CODE_ODD[27:2]);
        dmem[(PA_CODE_ODD + 32'h001C) >> 2] = 32'h0000_0000; // nop

        load_program();
    end

    // Self-check: wait DONE magic
    localparam [31:0] DONE_MAGIC = 32'hDEAD_BEEF;
    localparam [31:0] DONE_PADDR = RES_BASE_PADDR + 32'h003C;

    initial begin
        repeat (50000) @(posedge clk);
        $display("[TB][TIMEOUT] done=%08x", dmem[DONE_PADDR >> 2]);
        dump_results();
        $stop;
    end

    always @(posedge clk) begin
        if (resetn && dmem[DONE_PADDR >> 2] == DONE_MAGIC) begin
            check_all();
        end
    end

    task dump_results;
        begin
            $display("[TB] RES0  even VA1  = %08x", dmem[(RES_BASE_PADDR + 32'h00) >> 2]);
            $display("[TB] RES1  odd  VA1  = %08x", dmem[(RES_BASE_PADDR + 32'h04) >> 2]);
            $display("[TB] RES2  tlbp idx1 = %08x", dmem[(RES_BASE_PADDR + 32'h08) >> 2]);
            $display("[TB] RES3  even VA2  = %08x", dmem[(RES_BASE_PADDR + 32'h0C) >> 2]);
            $display("[TB] RES4  odd  VA2  = %08x", dmem[(RES_BASE_PADDR + 32'h10) >> 2]);
            $display("[TB] RES5  tlbr hi   = %08x", dmem[(RES_BASE_PADDR + 32'h14) >> 2]);
            $display("[TB] RES6  tlbr lo0  = %08x", dmem[(RES_BASE_PADDR + 32'h18) >> 2]);
            $display("[TB] RES7  tlbr lo1  = %08x", dmem[(RES_BASE_PADDR + 32'h1C) >> 2]);
            $display("[TB] RES8  tlbr->tlbp= %08x", dmem[(RES_BASE_PADDR + 32'h20) >> 2]);
            $display("[TB] RES9  ifetch even= %08x", dmem[(RES_BASE_PADDR + 32'h24) >> 2]);
            $display("[TB] RES10 ifetch odd = %08x", dmem[(RES_BASE_PADDR + 32'h28) >> 2]);
            $display("[TB] RES11 tlbp miss = %08x", dmem[(RES_BASE_PADDR + 32'h2C) >> 2]);
            $display("[TB] DONE            = %08x", dmem[(RES_BASE_PADDR + 32'h3C) >> 2]);
        end
    endtask

    task fail;
        input [255:0] msg;
        begin
            $display("[TB][FAIL] %0s", msg);
            dump_results();
            $stop;
        end
    endtask

    task check_all;
        reg [31:0] r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11;
        begin
            r0 = dmem[(RES_BASE_PADDR + 32'h00) >> 2];
            r1 = dmem[(RES_BASE_PADDR + 32'h04) >> 2];
            r2 = dmem[(RES_BASE_PADDR + 32'h08) >> 2];
            r3 = dmem[(RES_BASE_PADDR + 32'h0C) >> 2];
            r4 = dmem[(RES_BASE_PADDR + 32'h10) >> 2];
            r5 = dmem[(RES_BASE_PADDR + 32'h14) >> 2];
            r6 = dmem[(RES_BASE_PADDR + 32'h18) >> 2];
            r7 = dmem[(RES_BASE_PADDR + 32'h1C) >> 2];
            r8 = dmem[(RES_BASE_PADDR + 32'h20) >> 2];
            r9  = dmem[(RES_BASE_PADDR + 32'h24) >> 2];
            r10 = dmem[(RES_BASE_PADDR + 32'h28) >> 2];
            r11 = dmem[(RES_BASE_PADDR + 32'h2C) >> 2];

            if (r0 !== 32'h1111_1111) fail("even/odd select: VA1 even wrong");
            if (r1 !== 32'h2222_2222) fail("even/odd select: VA1 odd wrong");

            if (r2 !== 32'h0000_0001) fail("global+tlbp: expected hit at index=1 (P=0, idx=1)");
            if (r3 !== 32'h3333_3333) fail("global translate: VA2 even wrong");
            if (r4 !== 32'h4444_4444) fail("global translate: VA2 odd wrong");

            if (r5 !== 32'h0080_0001) fail("tlbr readback: EntryHi mismatch");
            if (r6 !== 32'h0000_0C07) fail("tlbr readback: EntryLo0 mismatch");
            if (r7 !== 32'h0000_1007) fail("tlbr readback: EntryLo1 mismatch");

            if (r8 !== 32'h0000_0002) fail("tlbr->tlbp: expected hit at index=2 (flush/hazard issue)");

            if (r11[31] !== 1'b1) fail("tlbp miss: expected Index.P=1");
            if (r9 !== 32'hAAAA_5555) fail("inst tlb: expected even page code executed");
            if (r10 !== 32'hBBBB_6666) fail("inst tlb: expected odd page code executed");

            $display("[TB][PASS] cpu_tlb_suite_tb");
            dump_results();
            $finish;
        end
    endtask

    // -----------------
    // Instruction encoding helpers
    // -----------------
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

    function [31:0] ins_addiu;
        input [4:0] rt;
        input [4:0] rs;
        input [15:0] imm;
        begin
            ins_addiu = (6'h09 << 26) | (rs << 21) | (rt << 16) | imm;
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

    function [31:0] ins_mfc0;
        input [4:0] rt;
        input [4:0] rd;
        input [2:0] sel;
        begin
            ins_mfc0 = (6'h10 << 26) | (5'h00 << 21) | (rt << 16) | (rd << 11) | sel;
        end
    endfunction

    function [31:0] ins_tlbwi;
        input dummy;
        begin
            ins_tlbwi = (6'h10 << 26) | (5'h10 << 21) | 6'h02;
        end
    endfunction

    function [31:0] ins_tlbp;
        input dummy;
        begin
            ins_tlbp = (6'h10 << 26) | (5'h10 << 21) | 6'h08;
        end
    endfunction

    function [31:0] ins_tlbr;
        input dummy;
        begin
            ins_tlbr = (6'h10 << 26) | (5'h10 << 21) | 6'h01;
        end
    endfunction

    function [31:0] ins_j;
        input [25:0] target;
        begin
            ins_j = (6'h02 << 26) | target;
        end
    endfunction

    function [31:0] ins_jr;
        input [4:0] rs;
        begin
            ins_jr = (6'h00 << 26) | (rs << 21) | (5'd0 << 16) | (5'd0 << 11) | (5'd0 << 6) | 6'h08;
        end
    endfunction

    // -----------------
    // Program loader
    // -----------------
    task load_program;
        integer pcw;
        begin
            pcw = 0;
            // regs: t0=8 t1=9 t2=10 t3=11

            // t2 = 0x8000_1000 (result base)
            imem[pcw] = ins_lui(5'd10, 16'h8000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd10, 5'd10, 16'h1000); pcw = pcw + 1;

            // -------- Test1: even/odd selection (index 0, VA1)
            // Index = 0
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd0, 3'd0); pcw = pcw + 1;
            // EntryHi = VA1 vpn2 + asid=1
            imem[pcw] = ins_lui(5'd9, 16'h0040); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0001); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1;
            // EntryLo0 = PFN 0x10, flags D/V=1, G=0 => 0x0406
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0406); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd2, 3'd0); pcw = pcw + 1;
            // EntryLo1 = PFN 0x20 => 0x0806
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0806); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd3, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_tlbwi(1'b0); pcw = pcw + 1;

            // t3 = VA1_BASE
            imem[pcw] = ins_lui(5'd11, 16'h0040); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd11, 5'd11, 16'h0000); pcw = pcw + 1;
            // lw t0,0(t3) -> 11111111
            imem[pcw] = ins_lw(5'd8, 5'd11, 16'h0000); pcw = pcw + 1;
            // addiu t3,t3,0x1000
            imem[pcw] = ins_addiu(5'd11, 5'd11, 16'h1000); pcw = pcw + 1;
            // lw t1,0(t3) -> 22222222 (odd page)
            imem[pcw] = ins_lw(5'd9, 5'd11, 16'h0000); pcw = pcw + 1;
            // store results
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_sw(5'd9, 5'd10, 16'h0004); pcw = pcw + 1;

            // -------- Test2: global bit + ASID mismatch (index 1, VA2)
            // Index = 1
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0001); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd0, 3'd0); pcw = pcw + 1;
            // EntryHi = VA2 vpn2 + asid=1
            imem[pcw] = ins_lui(5'd9, 16'h0080); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0001); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1;
            // EntryLo0 PFN=0x30 flags D/V/G=1 => 0x0C07
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0C07); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd2, 3'd0); pcw = pcw + 1;
            // EntryLo1 PFN=0x40 => 0x1007
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h1007); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd3, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_tlbwi(1'b0); pcw = pcw + 1;

            // Change EntryHi ASID to 2 (mismatch) and TLBP should still hit due to G=1
            imem[pcw] = ins_lui(5'd9, 16'h0080); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0002); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_tlbp(1'b0); pcw = pcw + 1;
            imem[pcw] = ins_mfc0(5'd8, 5'd0, 3'd0); pcw = pcw + 1; // t0 = Index
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h0008); pcw = pcw + 1; // RES2

            // Also test translation still works under ASID mismatch
            // t3 = VA2_BASE
            imem[pcw] = ins_lui(5'd11, 16'h0080); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd11, 5'd11, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_lw(5'd8, 5'd11, 16'h0000); pcw = pcw + 1; // 33333333
            imem[pcw] = ins_addiu(5'd11, 5'd11, 16'h1000); pcw = pcw + 1;
            imem[pcw] = ins_lw(5'd9, 5'd11, 16'h0000); pcw = pcw + 1; // 44444444
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h000C); pcw = pcw + 1; // RES3
            imem[pcw] = ins_sw(5'd9, 5'd10, 16'h0010); pcw = pcw + 1; // RES4

            // -------- Test3: TLBR readback (index 1)
            // Index = 1
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0001); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd0, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_tlbr(1'b0); pcw = pcw + 1;
            imem[pcw] = ins_mfc0(5'd8, 5'd10, 3'd0); pcw = pcw + 1; // t0 = EntryHi
            imem[pcw] = ins_mfc0(5'd9, 5'd2, 3'd0); pcw = pcw + 1;  // t1 = EntryLo0
            imem[pcw] = ins_mfc0(5'd11,5'd3, 3'd0); pcw = pcw + 1;  // t3 = EntryLo1
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h0014); pcw = pcw + 1; // RES5
            imem[pcw] = ins_sw(5'd9, 5'd10, 16'h0018); pcw = pcw + 1; // RES6
            imem[pcw] = ins_sw(5'd11,5'd10, 16'h001C); pcw = pcw + 1; // RES7

            // -------- Test4: TLBR -> immediate TLBP (index 2, VA3, G=0)
            // Write entry at index 2 (asid=3)
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0002); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd0, 3'd0); pcw = pcw + 1;
            // EntryHi = VA3 vpn2 + asid=3
            imem[pcw] = ins_lui(5'd9, 16'h00C0); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0003); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1;
            // Lo0 PFN=0x10 flags 0x6
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0406); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd2, 3'd0); pcw = pcw + 1;
            // Lo1 PFN=0x20 flags 0x6
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0806); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd3, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_tlbwi(1'b0); pcw = pcw + 1;

            // Set EntryHi to asid=2 (mismatch) BEFORE TLBR
            imem[pcw] = ins_lui(5'd9, 16'h00C0); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0002); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1;

            // Index=2; TLBR updates EntryHi to asid=3; immediate TLBP should hit (index=2)
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0002); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd0, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_tlbr(1'b0); pcw = pcw + 1;
            imem[pcw] = ins_tlbp(1'b0); pcw = pcw + 1;
            imem[pcw] = ins_mfc0(5'd8, 5'd0, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h0020); pcw = pcw + 1; // RES8

            // -------- Test5: TLBP miss should set Index.P=1
            // EntryHi = VA3_BASE (never inserted) + asid=1
            imem[pcw] = ins_lui(5'd9, 16'h00C0); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0001); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_tlbp(1'b0); pcw = pcw + 1;
            imem[pcw] = ins_mfc0(5'd8, 5'd0, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h002C); pcw = pcw + 1; // RES11

            // -------- Test6: instruction-side translation (jump into kuseg)
            // Install entry at index 3 for VA_CODE_EVEN/ODD, ASID=1, PFN0/1 = 0x50/0x51
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0003); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd0, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_lui(5'd9, 16'h0041); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0001); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1;
            // Lo0 PFN=0x50 flags D/V=1, G=0 => 0x1406
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h1406); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd2, 3'd0); pcw = pcw + 1;
            // Lo1 PFN=0x51 flags D/V=1 => 0x1446
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h1446); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd3, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_tlbwi(1'b0); pcw = pcw + 1;

            // jr to VA_CODE_EVEN; code there will write RES9/RES10/DONE and loop
            imem[pcw] = ins_lui(5'd8, 16'h0041); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd8, 5'd8, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_jr(5'd8); pcw = pcw + 1;
            imem[pcw] = 32'h0000_0000; pcw = pcw + 1; // nop

            // mirror to exception entry 0xBFC0_0380 (physical offset 0x380)
            for (i = 0; i < pcw; i = i + 1) begin
                imem[(32'h0000_0380 >> 2) + i] = imem[i];
            end

            $display("[TB] Program loaded: %0d words", pcw);
        end
    endtask

endmodule
