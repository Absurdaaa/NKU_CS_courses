`timescale 1ns / 1ps

// simple_burst_arb2
// - 2-master arbiter for cache.v-like burst memory interface
// - Each master has: rd_req/rd_addr/rd_rdy/ret_valid/ret_last/ret_data and wr_req/wr_addr/wr_data/wr_rdy
// - Downstream is a single memory interface of the same style.
//
// Policy:
// - At most one outstanding read burst in downstream at a time (memory enforces it)
// - At most one write accepted per cycle by downstream (wr_rdy can always be 1)
// - Round-robin between masters when both request and arb is idle

module simple_burst_arb2(
    input         clk,
    input         resetn,

    // master 0
    input         m0_rd_req,
    input  [31:0] m0_rd_addr,
    output        m0_rd_rdy,
    output        m0_ret_valid,
    output        m0_ret_last,
    output [31:0] m0_ret_data,

    input         m0_wr_req,
    input  [31:0] m0_wr_addr,
    input  [127:0] m0_wr_data,
    output        m0_wr_rdy,

    // master 1
    input         m1_rd_req,
    input  [31:0] m1_rd_addr,
    output        m1_rd_rdy,
    output        m1_ret_valid,
    output        m1_ret_last,
    output [31:0] m1_ret_data,

    input         m1_wr_req,
    input  [31:0] m1_wr_addr,
    input  [127:0] m1_wr_data,
    output        m1_wr_rdy,

    // downstream single port
    output        s_rd_req,
    output [31:0] s_rd_addr,
    input         s_rd_rdy,
    input         s_ret_valid,
    input         s_ret_last,
    input  [31:0] s_ret_data,

    output        s_wr_req,
    output [31:0] s_wr_addr,
    output [127:0] s_wr_data,
    input         s_wr_rdy
);

    // read arbitration
    reg        rd_busy;
    reg        rd_grant;   // 0->m0, 1->m1
    reg        rr_ptr;     // next priority when both request

    wire rd_idle = !rd_busy;
    wire choose_m0 = rd_idle && m0_rd_req && (!m1_rd_req || (rr_ptr==1'b0));
    wire choose_m1 = rd_idle && m1_rd_req && (!m0_rd_req || (rr_ptr==1'b1));

    assign s_rd_req  = choose_m0 || choose_m1;
    assign s_rd_addr = choose_m0 ? m0_rd_addr : m1_rd_addr;

    // only granted master sees ready
    assign m0_rd_rdy = choose_m0 ? s_rd_rdy : 1'b0;
    assign m1_rd_rdy = choose_m1 ? s_rd_rdy : 1'b0;

    // route return
    assign m0_ret_valid = s_ret_valid && (rd_grant==1'b0);
    assign m1_ret_valid = s_ret_valid && (rd_grant==1'b1);
    assign m0_ret_last  = s_ret_last;
    assign m1_ret_last  = s_ret_last;
    assign m0_ret_data  = s_ret_data;
    assign m1_ret_data  = s_ret_data;

    always @(posedge clk) begin
        if (!resetn) begin
            rd_busy  <= 1'b0;
            rd_grant <= 1'b0;
            rr_ptr   <= 1'b0;
        end else begin
            // accept a new downstream read when idle and memory ready
            if (s_rd_req && s_rd_rdy) begin
                rd_busy  <= 1'b1;
                rd_grant <= choose_m1; // if choose_m1 true then grant=1 else 0
                rr_ptr   <= ~choose_m1; // alternate next time
            end

            // clear when burst finishes
            if (rd_busy && s_ret_valid && s_ret_last) begin
                rd_busy <= 1'b0;
            end
        end
    end

    // write arbitration (single-beat accept; cache.v writeback is 1 request)
    // Give m1 priority when rr_ptr==1, else m0.
    wire choose_w0 = m0_wr_req && (!m1_wr_req || (rr_ptr==1'b0));
    wire choose_w1 = m1_wr_req && (!m0_wr_req || (rr_ptr==1'b1));

    assign s_wr_req  = choose_w0 || choose_w1;
    assign s_wr_addr = choose_w0 ? m0_wr_addr : m1_wr_addr;
    assign s_wr_data = choose_w0 ? m0_wr_data : m1_wr_data;

    assign m0_wr_rdy = choose_w0 ? s_wr_rdy : 1'b0;
    assign m1_wr_rdy = choose_w1 ? s_wr_rdy : 1'b0;

endmodule
