module transfer_bridge(
    input               aclk,
    input               aresetn,

    //read request
    output  [ 3:0]      arid,
    output  [31:0]      araddr,
    output  [ 7:0]      arlen,
    output  [ 2:0]      arsize,
    output  [ 1:0]      arburst,
    output  [ 1:0]      arlock,
    output  [ 3:0]      arcache,
    output  [ 2:0]      arprot,
    output              arvalid,
    input               arready,

    //read response
    input   [ 3:0]      rid,
    input   [31:0]      rdata,
    input   [ 1:0]      rresp,
    input               rlast,
    input               rvalid,
    output              rready,

    //write request
    output  [ 3:0]      awid,
    output  [31:0]      awaddr,
    output  [ 7:0]      awlen,
    output  [ 2:0]      awsize,
    output  [ 1:0]      awburst,
    output  [ 1:0]      awlock,
    output  [ 3:0]      awcache,
    output  [ 2:0]      awprot,
    output              awvalid,
    input               awready,

    //write data
    output  [ 3:0]      wid,
    output  [31:0]      wdata,
    output  [ 3:0]      wstrb,
    output              wlast,
    output              wvalid,
    input               wready,

    //write response
    input   [ 3:0]      bid,
    input   [ 1:0]      bresp,
    input               bvalid,
    output              bready,

    //scram inst
    input               inst_sram_req,
    input               inst_sram_wr,
    input   [ 1:0]      inst_sram_size,
    input   [31:0]      inst_sram_addr,
    input   [ 3:0]      inst_sram_wstrb,
    input   [31:0]      inst_sram_wdata,
    output              inst_sram_addr_ok,
    output              inst_sram_data_ok,
    output  [31:0]      inst_sram_rdata,

    // cache burst side (for I$/D$ linefill & writeback)
    input               cache_rd_req,
    input   [ 2:0]      cache_rd_type,
    input   [31:0]      cache_rd_addr,
    output              cache_rd_rdy,
    output              cache_ret_valid,
    output              cache_ret_last,
    output  [31:0]      cache_ret_data,

    input               cache_wr_req,
    input   [ 2:0]      cache_wr_type,
    input   [31:0]      cache_wr_addr,
    input   [ 3:0]      cache_wr_wstrb,
    input   [127:0]     cache_wr_data,
    output              cache_wr_rdy,

    //scram data
    input               data_sram_req,
    input               data_sram_wr,
    input   [ 1:0]      data_sram_size,
    input   [31:0]      data_sram_addr,
    input   [31:0]      data_sram_wdata,
    input   [ 3:0]      data_sram_wstrb,
    output              data_sram_addr_ok,
    output              data_sram_data_ok,
    output  [31:0]      data_sram_rdata
);
// some constant
// ID
parameter INST_ID = 4'h0;
parameter DATA_ID = 4'h1;
parameter CACHE_ID= 4'h2;

// constant fields
assign arburst  = 2'b01;
assign arlock   = 2'b00;
assign arprot   = 3'b000;

assign awburst  = 2'b01;
assign awlock   = 2'b00;
assign awprot   = 3'b000;

/************ define ************/
/* AXI read request */
reg         axi_ar_busy;
reg  [ 3:0] axi_ar_id;
reg  [31:0] axi_ar_addr;
reg  [ 2:0] axi_ar_size;
reg  [ 7:0] axi_ar_len;
reg  [ 3:0] axi_ar_cache;

/* AXI read outstanding (one at a time) */
reg         rd_outstanding;
reg  [ 3:0] rd_out_id;

/* AXI read response */
wire        axi_r_data_ok;
wire        axi_r_inst_ok;
wire        axi_r_cache_ok;
wire [31:0] axi_r_data;

/* AXI write (single + burst) */
reg         wr_active;
reg         wr_is_cache;
reg         wr_aw_pending;
reg         wr_w_pending;
reg         wr_b_pending;
reg  [ 3:0] wr_id;
reg  [31:0] wr_addr;
reg  [ 2:0] wr_size;
reg  [ 7:0] wr_len;
reg  [ 7:0] wr_beat;
reg  [31:0] wr_wdata_single;
reg  [ 3:0] wr_wstrb_reg;
reg  [127:0] wr_wdata_line;

/* AXI write response */
wire        axi_b_ok_data;
wire        axi_b_ok_cache;

/* middle read request */
wire        read_req_sel_cache;
wire        read_req_sel_data;
wire        read_req_sel_inst;

wire        read_req_valid;
wire [ 3:0] read_req_id;
wire [31:0] read_req_addr;
wire [ 2:0] read_req_size;
wire [ 7:0] read_req_len;
wire [ 3:0] read_req_cache;

wire        read_data_req_ok;
wire        read_inst_req_ok;

/* middle read inst response */
wire        read_inst_resp_wen;
wire        read_inst_resp_ren;
wire        read_inst_resp_empty;
wire        read_inst_resp_full;
wire [31:0] read_inst_resp_input;
wire [31:0] read_inst_resp_output;
fifo_buffer #(
    .DATA_WIDTH     (32),
    .BUFF_DEPTH     (6),
    .ADDR_WIDTH     (3)
) read_inst_resp_buff (
    .clk            (aclk),
    .resetn         (aresetn),
    .wen            (read_inst_resp_wen),
    .ren            (read_inst_resp_ren),
    .empty          (read_inst_resp_empty),
    .full           (read_inst_resp_full),
    .input_data     (read_inst_resp_input),
    .output_data    (read_inst_resp_output)
);

/* middle read data response */
wire        read_data_resp_wen;
wire        read_data_resp_ren;
wire        read_data_resp_empty;
wire        read_data_resp_full;
wire [31:0] read_data_resp_input;
wire [31:0] read_data_resp_output;
fifo_buffer #(
    .DATA_WIDTH     (32),
    .BUFF_DEPTH     (6),
    .ADDR_WIDTH     (3)
) read_data_resp_buff (
    .clk            (aclk),
    .resetn         (aresetn),
    .wen            (read_data_resp_wen),
    .ren            (read_data_resp_ren),
    .empty          (read_data_resp_empty),
    .full           (read_data_resp_full),
    .input_data     (read_data_resp_input),
    .output_data    (read_data_resp_output)
);

/* middle write request */
wire        write_sel_cache;
wire        write_sel_data;
wire        write_data_req_ok;

/* middle write response */
wire        write_data_resp_wen;
wire        write_data_resp_ren;
wire        write_data_resp_empty;
wire        write_data_resp_full;
fifo_count #(
    .BUFF_DEPTH     (6),
    .ADDR_WIDTH     (3)
) write_data_resp_count (
    .clk            (aclk),
    .resetn         (aresetn),
    .wen            (write_data_resp_wen),
    .ren            (write_data_resp_ren),
    .empty          (write_data_resp_empty),
    .full           (write_data_resp_full)
);

/* SRAM inst request */
wire        inst_read_valid;
wire        inst_related;  // TODO

/* SRAM inst response */
wire        inst_read_ready;

/* SRAM data request */
wire        data_read_valid;
wire        data_write_valid;
wire        data_related;   

// request record
wire        data_req_record_wen;
wire        data_req_record_ren;
wire        data_req_record_empty;
wire        data_req_record_full;
wire        data_req_record_related_1;
wire [32:0] data_req_record_input;      // {wr, addr}
wire [32:0] data_req_record_output;     // {wr, addr}
fifo_buffer_valid #(
    .DATA_WIDTH     (33),
    .BUFF_DEPTH     (6),
    .ADDR_WIDTH     (3),
    .RLAT_WIDTH     (32)
) data_req_record (
    .clk            (aclk),
    .resetn         (aresetn),
    .wen            (data_req_record_wen),
    .ren            (data_req_record_ren),
    .empty          (data_req_record_empty),
    .full           (data_req_record_full),
    .related_1      (data_req_record_related_1),
    .input_data     (data_req_record_input),
    .output_data    (data_req_record_output),
    .related_data_1 (data_sram_addr)
);

/* SRAM data response */
wire        data_read_ready;
wire        data_write_ready;


/************ assign ************/
/* AXI read request */
always @ (posedge aclk) begin
    if (!aresetn) begin
        axi_ar_busy <= 1'b0;
        axi_ar_id   <= 4'h0;
        axi_ar_addr <= 32'h0;
        axi_ar_size <= 3'h0;
        axi_ar_len  <= 8'h0;
        axi_ar_cache<= 4'h0;
    end else if (!axi_ar_busy && !rd_outstanding && read_req_valid) begin
        axi_ar_busy <= 1'b1;
        axi_ar_id   <= read_req_id;
        axi_ar_addr <= read_req_addr;
        axi_ar_size <= read_req_size;
        axi_ar_len  <= read_req_len;
        axi_ar_cache<= read_req_cache;
    end else if (axi_ar_busy && arvalid && arready) begin
        axi_ar_busy <= 1'b0;
        axi_ar_id   <= 4'h0;
        axi_ar_addr <= 32'h0;
        axi_ar_size <= 3'h0;
        axi_ar_len  <= 8'h0;
        axi_ar_cache<= 4'h0;
    end
end
assign arvalid  = axi_ar_busy;
assign arid     = axi_ar_id;
assign araddr   = axi_ar_addr;
assign arsize   = axi_ar_size;
assign arlen    = axi_ar_len;
assign arcache  = axi_ar_cache;

/* AXI read response */
assign axi_r_data_ok = rvalid && rready && rid == DATA_ID;
assign axi_r_inst_ok = rvalid && rready && rid == INST_ID;
assign axi_r_cache_ok= rvalid && rready && rid == CACHE_ID;
assign axi_r_data    = rdata;

assign rready = (rvalid && rid == CACHE_ID) ? 1'b1 : (!read_inst_resp_full && !read_data_resp_full);

assign cache_ret_valid = axi_r_cache_ok;
assign cache_ret_last  = rlast;
assign cache_ret_data  = axi_r_data;

// track outstanding read: block new AR until previous read response is fully received
always @(posedge aclk) begin
    if (!aresetn) begin
        rd_outstanding <= 1'b0;
        rd_out_id      <= 4'h0;
    end else begin
        // AR accepted by slave -> a read transaction becomes outstanding
        if (arvalid && arready) begin
            rd_outstanding <= 1'b1;
            rd_out_id      <= arid;
        end

        // clear when the corresponding response is accepted
        if (rd_outstanding) begin
            if ((rd_out_id == CACHE_ID) && axi_r_cache_ok && rlast) begin
                rd_outstanding <= 1'b0;
            end else if ((rd_out_id == INST_ID) && axi_r_inst_ok) begin
                rd_outstanding <= 1'b0;
            end else if ((rd_out_id == DATA_ID) && axi_r_data_ok) begin
                rd_outstanding <= 1'b0;
            end
        end
    end
end

/* AXI write: accept new request (cache has priority) */
wire can_accept_write = !wr_active;
assign write_sel_cache = cache_wr_req;
assign write_sel_data  = !write_sel_cache && data_write_valid;

assign cache_wr_rdy     = can_accept_write && write_sel_cache;
assign write_data_req_ok= can_accept_write && write_sel_data;

always @ (posedge aclk) begin
    if (!aresetn) begin
        wr_active       <= 1'b0;
        wr_is_cache     <= 1'b0;
        wr_aw_pending   <= 1'b0;
        wr_w_pending    <= 1'b0;
        wr_b_pending    <= 1'b0;
        wr_id           <= 4'h0;
        wr_addr         <= 32'h0;
        wr_size         <= 3'h0;
        wr_len          <= 8'h0;
        wr_beat         <= 8'h0;
        wr_wdata_single <= 32'h0;
        wr_wstrb_reg    <= 4'h0;
        wr_wdata_line   <= 128'h0;
    end else begin
        // latch a new write request
        if (!wr_active && (write_sel_cache || write_sel_data)) begin
            wr_active     <= 1'b1;
            wr_is_cache   <= write_sel_cache;
            wr_aw_pending <= 1'b1;
            wr_w_pending  <= 1'b0;
            wr_b_pending  <= 1'b0;
            wr_id         <= write_sel_cache ? CACHE_ID : DATA_ID;
            wr_addr       <= write_sel_cache ? cache_wr_addr : data_sram_addr;
            wr_size       <= write_sel_cache ? 3'b010 : {1'b0, data_sram_size};
            wr_len        <= write_sel_cache ? 8'd3   : 8'd0;
            wr_beat       <= 8'd0;
            wr_wstrb_reg  <= write_sel_cache ? cache_wr_wstrb : data_sram_wstrb;
            wr_wdata_single <= data_sram_wdata;
            wr_wdata_line   <= cache_wr_data;
        end

        // AW handshake -> start W
        if (wr_aw_pending && awvalid && awready) begin
            wr_aw_pending <= 1'b0;
            wr_w_pending  <= 1'b1;
        end

        // W handshake beats
        if (wr_w_pending && wvalid && wready) begin
            if (wr_beat == wr_len) begin
                wr_w_pending <= 1'b0;
                wr_b_pending <= 1'b1;
            end
            wr_beat <= wr_beat + 8'd1;
        end

        // B handshake completes
        if (wr_b_pending && bvalid && bready && bid == wr_id) begin
            wr_b_pending <= 1'b0;
            wr_active    <= 1'b0;
        end
    end
end

assign awvalid = wr_aw_pending;
assign awid    = wr_id;
assign awaddr  = wr_addr;
assign awsize  = wr_size;
assign awlen   = wr_len;
assign awcache = wr_is_cache ? 4'b1111 : 4'b0000;

assign wvalid  = wr_w_pending;
assign wid     = wr_id;
assign wstrb   = wr_wstrb_reg;
assign wlast   = (wr_beat == wr_len);

wire [31:0] wr_wdata_cache =
    (wr_beat[1:0] == 2'd0) ? wr_wdata_line[31:0] :
    (wr_beat[1:0] == 2'd1) ? wr_wdata_line[63:32] :
    (wr_beat[1:0] == 2'd2) ? wr_wdata_line[95:64] :
                             wr_wdata_line[127:96];

assign wdata = wr_is_cache ? wr_wdata_cache : wr_wdata_single;

/* AXI write response */
assign axi_b_ok_data  = bvalid && bready && bid == DATA_ID;
assign axi_b_ok_cache = bvalid && bready && bid == CACHE_ID;

assign bready = (bvalid && bid == CACHE_ID) ? 1'b1 : !write_data_resp_full;

/* middle read request */
// Uncached ordering rule (MMIO safety):
// If an uncached data write has been accepted but B response hasn't returned,
// block all subsequent uncached reads/writes (inst/data single-beat paths).
// Cached burst (CACHE_ID) is not blocked.
wire uncached_write_inflight = wr_active && !wr_is_cache;

assign read_req_sel_cache   = cache_rd_req;
assign read_req_sel_data    = !read_req_sel_cache && !uncached_write_inflight && data_read_valid;
assign read_req_sel_inst    = !read_req_sel_cache && !uncached_write_inflight && !data_read_valid && inst_read_valid;

// to axi
assign read_req_valid       = read_req_sel_cache || read_req_sel_data || read_req_sel_inst;
assign read_req_id          = read_req_sel_cache ? CACHE_ID : (read_req_sel_data ? DATA_ID : INST_ID);
assign read_req_addr        = read_req_sel_cache ? cache_rd_addr : (read_req_sel_data ? data_sram_addr : inst_sram_addr);
assign read_req_size        = read_req_sel_cache ? 3'b010 : (read_req_sel_data ? {1'b0, data_sram_size} : {1'b0, inst_sram_size});
assign read_req_len         = read_req_sel_cache ? 8'd3   : 8'd0;
assign read_req_cache       = read_req_sel_cache ? 4'b1111: 4'b0000;

// to sram
wire can_issue_read      = !axi_ar_busy && !rd_outstanding;
wire can_issue_read_uc   = can_issue_read && !uncached_write_inflight;

assign read_data_req_ok = read_req_sel_data && can_issue_read_uc;
assign read_inst_req_ok = read_req_sel_inst && can_issue_read_uc;
assign cache_rd_rdy     = read_req_sel_cache && can_issue_read;

/* middle read inst response */
assign read_inst_resp_ren = inst_read_ready;
assign read_inst_resp_wen = axi_r_inst_ok;
assign read_inst_resp_input = axi_r_data;

/* middle read data response */
assign read_data_resp_ren = data_read_ready;
assign read_data_resp_wen = axi_r_data_ok;
assign read_data_resp_input = axi_r_data;

/* middle write request */
/* middle write response */
assign write_data_resp_ren = data_write_ready;
assign write_data_resp_wen = axi_b_ok_data;

/* SRAM inst request */
assign inst_read_valid = inst_sram_req && !inst_sram_wr && !inst_related;
assign inst_sram_addr_ok = read_inst_req_ok;
assign inst_related = 0;

/* SRAM inst response */
assign inst_read_ready = 1;
assign inst_sram_data_ok = !read_inst_resp_empty;
assign inst_sram_rdata = read_inst_resp_output;

/* SRAM data request */
assign data_related      = data_req_record_related_1;
assign data_read_valid   = data_sram_req && !data_sram_wr && !data_related;
assign data_write_valid  = data_sram_req && data_sram_wr && !data_related;
assign data_sram_addr_ok = read_data_req_ok || write_data_req_ok;

// request record
assign data_req_record_ren = data_sram_data_ok;
assign data_req_record_wen = data_sram_req && data_sram_addr_ok;
assign data_req_record_input = {data_sram_wr, data_sram_addr};

/* SRAM data response */
assign data_sram_rdata  = read_data_resp_output;
assign data_read_ready  = !data_req_record_empty && !data_req_record_output[32];
assign data_write_ready = !data_req_record_empty && data_req_record_output[32];

assign data_sram_data_ok = 
    (data_read_ready && !read_data_resp_empty) || 
    (data_write_ready && !write_data_resp_empty);

endmodule