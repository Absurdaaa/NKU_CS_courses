`timescale 1ns/1ps

// A focused regression TB to catch the remaining TLB-related corner case:
// 1) TLBR/TLBWI commit flush + refetch correctness (avoid using stale translation)
// 2) TLBP vs in-flight MTC0(EntryHi) hazard (stall, no forwarding)
//
// It instantiates mycpu_core directly and provides simple SRAM models
// (req/addr_ok/data_ok/rdata). Program is placed at kseg1 reset vector
// 0xBFC0_0000 (phys 0x1FC0_0000 via direct-map).

module cpu_tlb_hazard_tb;

    // -----------------
    // clock / reset
    // -----------------
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

    // -----------------
    // DUT <-> SRAM ports
    // -----------------
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

    // -----------------
    // Simple memories
    // -----------------
    localparam IMEM_WORDS = 4096;     // 16KB
    localparam DMEM_WORDS = 262144;   // 1MB (bytes) -> 256K words covers 0x0000_0000..0x000F_FFFF

    reg [31:0] imem [0:IMEM_WORDS-1];
    reg [31:0] dmem [0:DMEM_WORDS-1];

    // Combinational ready: treat each cycle with req as a new request.
    // Using wire avoids race with DUT sampling at posedge.
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

    // Program physical base for reset vector (kseg1):
    // DUT direct-map uses {3'b000, vaddr[28:0]}, so 0xBFC0_0000 -> 0x1FC0_0000.
    localparam [31:0] IMEM_BASE = 32'h1FC0_0000;

    // Result physical addresses (kseg0 direct map): 0x8000_1000/1004 -> 0x0000_1000/1004
    localparam [31:0] RES0_PADDR = 32'h0000_1000;
    localparam [31:0] RES1_PADDR = 32'h0000_1004;

    // Test virtual address in kuseg (must go through TLB): 0x0040_0000
    localparam [31:0] VA_BASE    = 32'h0040_0000;

    integer i;

    // simple progress counters (avoid flooding)
    integer inst_req_cnt;
    integer inst_rsp_cnt;
    integer data_req_cnt;
    integer data_rsp_cnt;
    reg [31:0] last_wb_pc;

    initial begin
        inst_req_cnt = 0;
        inst_rsp_cnt = 0;
        data_req_cnt = 0;
        data_rsp_cnt = 0;
        last_wb_pc   = 32'h0;

        // init memories
        for (i = 0; i < IMEM_WORDS; i = i + 1) imem[i] = 32'h0000_0000;
        for (i = 0; i < DMEM_WORDS; i = i + 1) dmem[i] = 32'h0000_0000;

        // Prepare physical pages with distinct data
        // PFN=0x10 -> paddr base 0x0001_0000
        // PFN=0x20 -> paddr base 0x0002_0000
        dmem[32'h0001_0000 >> 2] = 32'h1111_1111;
        dmem[32'h0002_0000 >> 2] = 32'h2222_2222;

        // Clear result locations
        dmem[RES0_PADDR >> 2] = 32'h0;
        dmem[RES1_PADDR >> 2] = 32'h0;

        // Load program to imem
        load_program();
    end

    // light-weight logging
    always @(posedge clk) begin
        if (resetn) begin
            if (inst_sram_req && inst_sram_addr_ok) begin
                inst_req_cnt = inst_req_cnt + 1;
                if (inst_req_cnt <= 20) begin
                    $display("[TB][IF_REQ ] t=%0t addr=%08x", $time, inst_sram_addr);
                end
            end
            if (inst_sram_data_ok) begin
                inst_rsp_cnt = inst_rsp_cnt + 1;
                if (inst_rsp_cnt <= 20) begin
                    $display("[TB][IF_RSP ] t=%0t rdata=%08x", $time, inst_sram_rdata);
                end
            end

            if (data_sram_req && data_sram_addr_ok) begin
                data_req_cnt = data_req_cnt + 1;
                if (data_req_cnt <= 20) begin
                    $display("[TB][DA_REQ ] t=%0t wr=%0d addr=%08x wstrb=%x wdata=%08x", $time, data_sram_wr, data_sram_addr, data_sram_wstrb, data_sram_wdata);
                end
            end
            if (data_sram_data_ok) begin
                data_rsp_cnt = data_rsp_cnt + 1;
                if (data_rsp_cnt <= 20) begin
                    $display("[TB][DA_RSP ] t=%0t rdata=%08x", $time, data_sram_rdata);
                end
            end

            if (debug_wb_pc != last_wb_pc) begin
                last_wb_pc <= debug_wb_pc;
                if (debug_wb_pc != 32'h0) begin
                    $display("[TB][WB_PC  ] t=%0t pc=%08x wen=%x wnum=%0d wdata=%08x", $time, debug_wb_pc, debug_wb_rf_wen, debug_wb_rf_wnum, debug_wb_rf_wdata);
                end
            end
        end
    end

    // -----------------
    // Minimal SRAM timing models
    // -----------------
    // addr_ok: always 1 on req
    // data_ok: returned after fixed latency; support multiple outstanding (small FIFO)

    localparam integer QDEPTH = 8;
    localparam [3:0] INST_LAT = 4'd3;   // cycles
    localparam [3:0] DATA_LAT = 4'd5;   // cycles

    // inst request queue
    reg [31:0] inst_q_addr [0:QDEPTH-1];
    reg [3:0]  inst_q_cnt  [0:QDEPTH-1];
    reg [QDEPTH-1:0] inst_q_valid;

    // data request queue
    reg [31:0] data_q_addr [0:QDEPTH-1];
    reg [31:0] data_q_wdata[0:QDEPTH-1];
    reg [3:0]  data_q_wstrb[0:QDEPTH-1];
    reg        data_q_wr   [0:QDEPTH-1];
    reg [3:0]  data_q_cnt  [0:QDEPTH-1];
    reg [QDEPTH-1:0] data_q_valid;

    integer qi;

    // helpers: find first free / first ready
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

    // inst channel
    integer inst_f;
    integer inst_r;
    integer data_f;
    integer data_r;

    reg [31:0] data_old;
    reg [31:0] data_nw;

    // NOTE: DUT samples *_data_ok and *_rdata at posedge.
    // So we generate them on negedge to ensure they are stable before posedge.

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
            // enqueue
            if (inst_sram_req && inst_sram_addr_ok) begin
                inst_f = find_free(inst_q_valid);
                if (inst_f >= 0) begin
                    inst_q_valid[inst_f] <= 1'b1;
                    inst_q_addr[inst_f]  <= inst_sram_addr;
                    inst_q_cnt[inst_f]   <= INST_LAT;
                end
            end

            // countdown
            for (qi = 0; qi < QDEPTH; qi = qi + 1) begin
                if (inst_q_valid[qi] && inst_q_cnt[qi] != 0)
                    inst_q_cnt[qi] <= inst_q_cnt[qi] - 1'b1;
            end

            // response is produced at negedge
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
                inst_q_valid[inst_r]   <= 1'b0;
                inst_q_addr[inst_r]    <= 32'h0;
                inst_q_cnt[inst_r]     <= 4'h0;
            end
        end
    end

    // data channel
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
            // enqueue
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

            // countdown
            for (qi = 0; qi < QDEPTH; qi = qi + 1) begin
                if (data_q_valid[qi] && data_q_cnt[qi] != 0)
                    data_q_cnt[qi] <= data_q_cnt[qi] - 1'b1;
            end

            // response is produced at negedge
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
                // apply write (byte enables)
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

    // -----------------
    // Self-check
    // -----------------
    reg seen_res0;
    reg seen_res1;

    initial begin
        seen_res0 = 1'b0;
        seen_res1 = 1'b0;

        // timeout
        repeat (20000) @(posedge clk);
        $display("[TB][TIMEOUT] res0=%08x res1=%08x", dmem[RES0_PADDR>>2], dmem[RES1_PADDR>>2]);
        $stop;
    end

    always @(posedge clk) begin
        if (resetn) begin
            // watch stores to result area
            if (dmem[RES0_PADDR >> 2] !== 32'h0) seen_res0 <= 1'b1;
            if (dmem[RES1_PADDR >> 2] !== 32'h0) seen_res1 <= 1'b1;

            if (seen_res0 && seen_res1) begin
                $display("[TB] RES0=%08x (expect 22222222)", dmem[RES0_PADDR>>2]);
                $display("[TB] RES1=%08x (expect 80000000)", dmem[RES1_PADDR>>2]);

                if (dmem[RES0_PADDR >> 2] !== 32'h2222_2222) begin
                    $display("[TB][FAIL] TLBR/TLBWI flush/refetch likely wrong (loaded stale PFN)");
                    $stop;
                end
                if (dmem[RES1_PADDR >> 2] !== 32'h8000_0000) begin
                    $display("[TB][FAIL] TLBP hazard/stall likely wrong (expected miss with ASID mismatch)");
                    $stop;
                end

                $display("[TB][PASS] cpu_tlb_hazard_tb");
                $finish;
            end
        end
    end

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
            // op=0x10 rs=0x04
            ins_mtc0 = (6'h10 << 26) | (5'h04 << 21) | (rt << 16) | (rd << 11) | sel;
        end
    endfunction

    function [31:0] ins_mfc0;
        input [4:0] rt;
        input [4:0] rd;
        input [2:0] sel;
        begin
            // op=0x10 rs=0x00
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

    function [31:0] ins_j;
        input [25:0] target;
        begin
            ins_j = (6'h02 << 26) | target;
        end
    endfunction

    task load_program;
        integer pcw;
        reg [31:0] word;
        begin
            pcw = 0;
            // registers: t0=8 t1=9 t2=10 t3=11

            // Index = 0
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd0, 3'd0); pcw = pcw + 1; // mtc0 t1, Index

            // EntryHi = 0x0040_0001 (vpn2=0x200, asid=1)
            imem[pcw] = ins_lui(5'd9, 16'h0040); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0001); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1; // mtc0 t1, EntryHi

            // EntryLo0/1 = PFN 0x10, flags: D=1,V=1,G=0 => 0x6; so 0x0000_0406
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0406); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd2, 3'd0); pcw = pcw + 1; // EntryLo0
            imem[pcw] = ins_mtc0(5'd9, 5'd3, 3'd0); pcw = pcw + 1; // EntryLo1

            // tlbwi (write mapping A)
            imem[pcw] = ins_tlbwi(1'b0); pcw = pcw + 1;
            imem[pcw] = 32'h0000_0000; pcw = pcw + 1; // nop

            // Update EntryLo0/1 -> PFN 0x20 => 0x0000_0806
            imem[pcw] = ins_lui(5'd9, 16'h0000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0806); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd2, 3'd0); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd3, 3'd0); pcw = pcw + 1;

            // tlbwi (update mapping B) + immediate lw from VA (flush should refetch this lw)
            imem[pcw] = ins_tlbwi(1'b0); pcw = pcw + 1;

            // t2 = VA_BASE
            imem[pcw] = ins_lui(5'd10, 16'h0040); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd10, 5'd10, 16'h0000); pcw = pcw + 1;

            // lw t0, 0(t2)  -> expect 0x2222_2222
            imem[pcw] = ins_lw(5'd8, 5'd10, 16'h0000); pcw = pcw + 1;

            // t2 = 0x8000_1000
            imem[pcw] = ins_lui(5'd10, 16'h8000); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd10, 5'd10, 16'h1000); pcw = pcw + 1;

            // sw t0, 0(t2) -> store loaded value to RES0
            imem[pcw] = ins_sw(5'd8, 5'd10, 16'h0000); pcw = pcw + 1;

            // ---- test TLBP hazard: mtc0 EntryHi (ASID=2) then immediately tlbp ----
            // Since G=0, ASID mismatch should make TLBP miss. Correct hazard handling
            // (stall) ensures TLBP uses the new EntryHi.
            imem[pcw] = ins_lui(5'd9, 16'h0040); pcw = pcw + 1;
            imem[pcw] = ins_ori(5'd9, 5'd9, 16'h0002); pcw = pcw + 1;
            imem[pcw] = ins_mtc0(5'd9, 5'd10, 3'd0); pcw = pcw + 1; // mtc0 EntryHi (asid=2)
            imem[pcw] = ins_tlbp(1'b0); pcw = pcw + 1;
            imem[pcw] = ins_mfc0(5'd11, 5'd0, 3'd0); pcw = pcw + 1; // mfc0 t3, Index
            imem[pcw] = ins_sw(5'd11, 5'd10, 16'h0004); pcw = pcw + 1; // sw t3, 4(t2) -> RES1

            // loop forever (jump to itself)
            // j target uses {PC+4[31:28], target, 2'b00}; choose current address.
            imem[pcw] = ins_j((32'hBFC0_0000 + (pcw<<2)) >> 2); pcw = pcw + 1;
            imem[pcw] = 32'h0000_0000; pcw = pcw + 1;

            // Also mirror the same program to exception entry (0xBFC0_0380),
            // in case the core vectors there early.
            for (i = 0; i < pcw; i = i + 1) begin
                imem[(32'h0000_0380 >> 2) + i] = imem[i];
            end

            $display("[TB] Program loaded: %0d words", pcw);
        end
    endtask

endmodule
