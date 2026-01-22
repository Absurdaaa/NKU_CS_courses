`timescale 1ns / 1ps

// simple_unified_mem
// - A tiny synthesizable-ish memory model for simulation
// - Provides:
//   (1) cache burst interface: 4-beat read (ret_valid/ret_last/ret_data), whole-line write (wr_data[127:0])
//   (2) uncached SRAM-like interface: req/addr_ok/data_ok/rdata with byte-enable writes
// - Backing storage is shared between the two interfaces.
//
// Notes:
// - This is NOT an AXI model; it matches cache.v memory-side handshake.
// - Read latency: burst returns start 1 cycle after rd_req handshake, 1 beat per cycle.
// - Uncached latency: data_ok pulses 1 cycle after req handshake.

module simple_unified_mem #(
    parameter integer MEM_WORDS = 65536,           // 64K words = 256KB
    parameter [31:0]  INIT_BASE = 32'h1fc0_0000    // init pattern base
)(
    input         clk,
    input         resetn,

    // -----------------
    // cache burst side
    // -----------------
    input         rd_req,
    input  [31:0] rd_addr,
    output        rd_rdy,
    output reg        ret_valid,
    output reg        ret_last,
    output reg [31:0] ret_data,

    input         wr_req,
    input  [31:0] wr_addr,
    input  [127:0] wr_data,
    output        wr_rdy,

    // -----------------
    // uncached SRAM-like side
    // -----------------
    input         uc_req,
    input         uc_wr,
    input  [31:0] uc_addr,
    input  [ 3:0] uc_wstrb,
    input  [31:0] uc_wdata,
    output        uc_addr_ok,
    output reg        uc_data_ok,
    output reg [31:0] uc_rdata
);

    // backing memory
    reg [31:0] mem [0:MEM_WORDS-1];
    integer i;

    // init for easier checking
    initial begin
        for (i = 0; i < MEM_WORDS; i = i + 1) begin
            mem[i] = INIT_BASE + (i << 2);
        end
    end

    // -----------------
    // burst read
    // -----------------
    reg        rd_busy;
    reg [31:0] rd_base;
    reg [1:0]  rd_beat;

    assign rd_rdy = !rd_busy;

    wire [31:0] rd_base_aligned = {rd_addr[31:4], 4'b0000};

    // -----------------
    // line writeback
    // -----------------
    assign wr_rdy = 1'b1;
    wire [31:0] wr_base_aligned = {wr_addr[31:4], 4'b0000};

    // -----------------
    // uncached
    // -----------------
    reg        uc_pending;
    reg        uc_pending_wr;
    reg [31:0] uc_pending_addr;
    reg [ 3:0] uc_pending_wstrb;
    reg [31:0] uc_pending_wdata;

    assign uc_addr_ok = !uc_pending;

    // helpers
    function [31:0] mem_read_word;
        input [31:0] addr;
        integer idx;
        begin
            idx = (addr >> 2) % MEM_WORDS;
            mem_read_word = mem[idx];
        end
    endfunction

    task mem_write_word;
        input [31:0] addr;
        input [ 3:0] wstrb;
        input [31:0] wdata;
        integer idx;
        reg [31:0] old;
        reg [31:0] nw;
        begin
            idx = (addr >> 2) % MEM_WORDS;
            old = mem[idx];
            nw  = old;
            if (wstrb[0]) nw[7:0]   = wdata[7:0];
            if (wstrb[1]) nw[15:8]  = wdata[15:8];
            if (wstrb[2]) nw[23:16] = wdata[23:16];
            if (wstrb[3]) nw[31:24] = wdata[31:24];
            mem[idx] = nw;
        end
    endtask

    // main sequential
    always @(posedge clk) begin
        if (!resetn) begin
            rd_busy    <= 1'b0;
            rd_base    <= 32'b0;
            rd_beat    <= 2'b00;
            ret_valid  <= 1'b0;
            ret_last   <= 1'b0;
            ret_data   <= 32'b0;

            uc_pending <= 1'b0;
            uc_pending_wr   <= 1'b0;
            uc_pending_addr <= 32'b0;
            uc_pending_wstrb<= 4'b0;
            uc_pending_wdata<= 32'b0;
            uc_data_ok <= 1'b0;
            uc_rdata   <= 32'b0;
        end else begin
            // defaults
            ret_valid <= 1'b0;
            ret_last  <= 1'b0;
            uc_data_ok<= 1'b0;

            // accept burst read
            if (rd_req && rd_rdy) begin
                rd_busy <= 1'b1;
                rd_base <= rd_base_aligned;
                rd_beat <= 2'b00;
                $display("[%0t] MEM: accept burst RD @%08x", $time, rd_base_aligned);
            end

            // drive burst return (1 beat/cycle) when busy
            if (rd_busy) begin
                ret_valid <= 1'b1;
                ret_data  <= mem_read_word(rd_base + (rd_beat << 2));
                ret_last  <= (rd_beat == 2'd3);

                $display("[%0t] MEM: burst RET beat=%0d last=%0d data=%08x", $time, rd_beat, (rd_beat==2'd3), mem_read_word(rd_base + (rd_beat << 2)));

                if (rd_beat == 2'd3) begin
                    rd_busy <= 1'b0;
                    rd_beat <= 2'b00;
                end else begin
                    rd_beat <= rd_beat + 2'b01;
                end
            end

            // accept line writeback
            if (wr_req && wr_rdy) begin
                // store 4 words (little-endian word lanes)
                mem_write_word(wr_base_aligned + 32'd0,  4'b1111, wr_data[31:0]);
                mem_write_word(wr_base_aligned + 32'd4,  4'b1111, wr_data[63:32]);
                mem_write_word(wr_base_aligned + 32'd8,  4'b1111, wr_data[95:64]);
                mem_write_word(wr_base_aligned + 32'd12, 4'b1111, wr_data[127:96]);
                $display("[%0t] MEM: accept line WR @%08x w0=%08x w1=%08x w2=%08x w3=%08x", $time, wr_base_aligned,
                         wr_data[31:0], wr_data[63:32], wr_data[95:64], wr_data[127:96]);
            end

            // accept uncached request
            if (uc_req && uc_addr_ok) begin
                uc_pending       <= 1'b1;
                uc_pending_wr    <= uc_wr;
                uc_pending_addr  <= uc_addr;
                uc_pending_wstrb <= uc_wstrb;
                uc_pending_wdata <= uc_wdata;
                $display("[%0t] MEM: accept UC %s @%08x wstrb=%b wdata=%08x", $time,
                         uc_wr ? "WR" : "RD", uc_addr, uc_wstrb, uc_wdata);
            end

            // respond uncached 1 cycle later
            if (uc_pending) begin
                uc_pending <= 1'b0;
                uc_data_ok <= 1'b1;
                if (uc_pending_wr) begin
                    mem_write_word(uc_pending_addr, uc_pending_wstrb, uc_pending_wdata);
                    uc_rdata <= 32'b0;
                    $display("[%0t] MEM: UC WR done @%08x", $time, uc_pending_addr);
                end else begin
                    uc_rdata <= mem_read_word(uc_pending_addr);
                    $display("[%0t] MEM: UC RD done @%08x rdata=%08x", $time, uc_pending_addr, mem_read_word(uc_pending_addr));
                end
            end
        end
    end

endmodule
