`define CP0_BADV_ADDR   8'b01000000
`define CP0_COUNT_ADDR  8'b01001000
`define CP0_COMP_ADDR   8'b01011000
`define CP0_STATUS_ADDR 8'b01100000
`define CP0_CAUSE_ADDR  8'b01101000
`define CP0_EPC_ADDR    8'b01110000
`define CP0_CONFIG_ADDR 8'b10000000
`define CP0_INDEX_ADDR   8'b00000000
`define CP0_ENTRYLO0_ADDR 8'b00010000
`define CP0_ENTRYLO1_ADDR 8'b00011000
`define CP0_ENTRYHI_ADDR  8'b01010000

module cp0(
    input         clk,
    input         rst, 
    input         wb_ex,
    input         wb_bd,
    input         ws_eret,
    input  [4:0]  wb_excode,
    input  [31:0] wb_pc,
    input  [31:0] wb_badvaddr,
    input  [5:0]  ext_int_in,   

    input  [ 7:0] cp0_addr,
    output [31:0] cp0_rdata,
   
    input         mtc0_we,       
    input  [31:0] cp0_wdata,   

    // tlb op commit (from WB)
    input         tlbp_we,
    input         tlbp_found,
    input  [3:0]  tlbp_index,

    input         tlbr_we,
    input  [18:0] tlbr_vpn2,
    input  [7:0]  tlbr_asid,
    input         tlbr_g,
    input  [19:0] tlbr_pfn0,
    input  [2:0]  tlbr_c0,
    input         tlbr_d0,
    input         tlbr_v0,
    input  [19:0] tlbr_pfn1,
    input  [2:0]  tlbr_c1,
    input         tlbr_d1,
    input         tlbr_v1,

    output [31:0] cp0_status,
    output [31:0] cp0_cause,
    output [31:0] cp0_epc,
    output [31:0] cp0_badvaddr,
    output [31:0] cp0_count,
    output [31:0] cp0_compare,

    output [31:0] cp0_index,
    output [31:0] cp0_entryhi,
    output [31:0] cp0_entrylo0,
    output [31:0] cp0_entrylo1
    );


//CP0_STATUS
wire cp0_status_bev;
assign cp0_status_bev = 1'b1;

reg [7:0] cp0_status_im;
always @(posedge clk) begin
    if (mtc0_we && cp0_addr == `CP0_STATUS_ADDR)
        cp0_status_im <= cp0_wdata[15:8];
end

reg cp0_status_exl;
always @(posedge clk) begin
    if(rst)
        cp0_status_exl <= 1'b0;
    else if(wb_ex)
        cp0_status_exl <= 1'b1;
    else if(ws_eret)
        cp0_status_exl <= 1'b0;
    else if(mtc0_we && cp0_addr == `CP0_STATUS_ADDR)
        cp0_status_exl <= cp0_wdata[1];
end

reg cp0_status_ie;
always @(posedge clk) begin
    if(rst)
        cp0_status_ie <= 1'b0;
    else if(mtc0_we && cp0_addr == `CP0_STATUS_ADDR)
        cp0_status_ie <= cp0_wdata[0];
end

assign cp0_status = 
{
    9'b0,               //31:23
    cp0_status_bev,     //22:22
    6'b0,               //21:16
    cp0_status_im,      //15:8
    6'b0,     //7:2
    cp0_status_exl,     //1:1
    cp0_status_ie       //0:0
};

//CP0_CAUSE
reg cp0_cause_bd;
always @(posedge clk) begin
    if(rst)
        cp0_cause_bd <= 1'b0;
    else if(wb_ex && !cp0_status_exl)
        cp0_cause_bd <= wb_bd;
end

reg cp0_cause_ti;
wire count_eq_compare;
assign count_eq_compare = (cp0_count == cp0_compare);

always @(posedge clk) begin
    if(rst)
        cp0_cause_ti <= 1'b0;
    else if(mtc0_we && cp0_addr == `CP0_COMP_ADDR)
        cp0_cause_ti <= 1'b0;
    else if(count_eq_compare)
        cp0_cause_ti <= 1'b1;
end

reg [7:0]cp0_cause_ip;
always @(posedge clk) begin
    if(rst)
        cp0_cause_ip[7:2] <= 6'b0;
    else begin
        cp0_cause_ip[7] <= ext_int_in[5] | cp0_cause_ti;
        cp0_cause_ip[6 : 2] <= ext_int_in[4:0];
    end
end

always @(posedge clk) begin
    if(rst)
        cp0_cause_ip[1:0] <= 2'b0;
    else if(mtc0_we && cp0_addr == `CP0_CAUSE_ADDR)
        cp0_cause_ip[1:0] <= cp0_wdata[9:8];
end

reg [4:0] cp0_cause_excode;
always @(posedge clk) begin
    if(rst)
        cp0_cause_excode <= 5'b0;
    else if(wb_ex)
        cp0_cause_excode <= wb_excode;
end

assign cp0_cause = 
{
    cp0_cause_bd,       //31:31
    cp0_cause_ti,       //30:30
    14'b0,              //29:16
    cp0_cause_ip,       //15:8
    1'b0,               //7:7
    cp0_cause_excode,   //6:2
    2'b0       //1:0
};

//EPC
reg [31:0] c0_epc;
always @(posedge clk) begin
    if(wb_ex && !cp0_status_exl)
        c0_epc <= wb_bd ? wb_pc - 32'h4 : wb_pc;
    else if(mtc0_we && cp0_addr == `CP0_EPC_ADDR)
        c0_epc <= cp0_wdata;
end

assign cp0_epc = c0_epc;

//BADVADDR
reg [31:0] c0_badvaddr;
always @(posedge clk) begin
    if(wb_ex && ((wb_excode == 5'h04) || (wb_excode == 5'h05)))
        c0_badvaddr <= wb_badvaddr;
end

assign cp0_badvaddr = c0_badvaddr;

//COUNT
reg tick;
always @(posedge clk) begin
    if(rst)
        tick <= 1'b0;
    else
        tick <= ~tick;
end

reg [31:0] c0_count;
always @(posedge clk) begin
    if(rst)
        c0_count <= 32'b0;
    else if(mtc0_we && cp0_addr == `CP0_COUNT_ADDR)
        c0_count <= cp0_wdata;
    else if(tick)
        c0_count <= c0_count + 1'b1;
end

assign cp0_count = c0_count;

//COMPARE
reg [31:0]c0_compare;
always @(posedge clk) begin
    if(mtc0_we && cp0_addr == `CP0_COMP_ADDR)
        c0_compare <= cp0_wdata;
end

assign cp0_compare = c0_compare;

// ------------------------------
// Index / EntryHi / EntryLo0 / EntryLo1 (TLB related)
// ------------------------------
reg [31:0] c0_index;
reg [31:0] c0_entryhi;
reg [31:0] c0_entrylo0;
reg [31:0] c0_entrylo1;

wire mtc0_index   = mtc0_we && (cp0_addr == `CP0_INDEX_ADDR);
wire mtc0_entryhi = mtc0_we && (cp0_addr == `CP0_ENTRYHI_ADDR);
wire mtc0_entrylo0= mtc0_we && (cp0_addr == `CP0_ENTRYLO0_ADDR);
wire mtc0_entrylo1= mtc0_we && (cp0_addr == `CP0_ENTRYLO1_ADDR);

always @(posedge clk) begin
    if (rst) begin
        c0_index    <= 32'b0;
        c0_entryhi  <= 32'b0;
        c0_entrylo0 <= 32'b0;
        c0_entrylo1 <= 32'b0;
    end else begin
        // mtc0 writes (mask to the fields we actually implement)
        if (mtc0_index) begin
            // c0_index[31] <= cp0_wdata[31]; // 删除或注释掉这一行，保护 P 位
            c0_index[3:0] <= cp0_wdata[3:0];
            c0_index[30:4]<= 27'b0;
        end
        if (mtc0_entryhi) begin
            c0_entryhi[31:13] <= cp0_wdata[31:13];
            c0_entryhi[12:8]  <= 5'b0;
            c0_entryhi[7:0]   <= cp0_wdata[7:0];
        end
        if (mtc0_entrylo0) begin
            c0_entrylo0[31:26] <= 6'b0;
            c0_entrylo0[25:0]  <= {cp0_wdata[25:6], cp0_wdata[5:3], cp0_wdata[2], cp0_wdata[1], cp0_wdata[0]};
        end
        if (mtc0_entrylo1) begin
            c0_entrylo1[31:26] <= 6'b0;
            c0_entrylo1[25:0]  <= {cp0_wdata[25:6], cp0_wdata[5:3], cp0_wdata[2], cp0_wdata[1], cp0_wdata[0]};
        end

        // tlbp updates Index (precise commit)
        if (tlbp_we) begin
            c0_index[31]   <= ~tlbp_found;
            c0_index[30:4] <= 27'b0;
            c0_index[3:0]  <= tlbp_index;
        end

        // tlbr updates EntryHi/Lo0/Lo1 (precise commit)
        if (tlbr_we) begin
            c0_entryhi[31:13] <= tlbr_vpn2;
            c0_entryhi[12:8]  <= 5'b0;
            c0_entryhi[7:0]   <= tlbr_asid;

            c0_entrylo0[31:26] <= 6'b0;
            c0_entrylo0[25:0]  <= {tlbr_pfn0, tlbr_c0, tlbr_d0, tlbr_v0, tlbr_g};

            c0_entrylo1[31:26] <= 6'b0;
            c0_entrylo1[25:0]  <= {tlbr_pfn1, tlbr_c1, tlbr_d1, tlbr_v1, tlbr_g};
        end
    end
end

assign cp0_index    = c0_index;
assign cp0_entryhi  = c0_entryhi;
assign cp0_entrylo0 = c0_entrylo0;
assign cp0_entrylo1 = c0_entrylo1;

assign cp0_rdata = 
    (cp0_addr == `CP0_INDEX_ADDR) ? cp0_index :
    (cp0_addr == `CP0_ENTRYHI_ADDR) ? cp0_entryhi :
    (cp0_addr == `CP0_ENTRYLO0_ADDR) ? cp0_entrylo0 :
    (cp0_addr == `CP0_ENTRYLO1_ADDR) ? cp0_entrylo1 :
    (cp0_addr == `CP0_STATUS_ADDR)? cp0_status :
    (cp0_addr == `CP0_CAUSE_ADDR)? cp0_cause :
    (cp0_addr == `CP0_EPC_ADDR)? cp0_epc :
    (cp0_addr == `CP0_BADV_ADDR)? cp0_badvaddr :
    (cp0_addr == `CP0_COUNT_ADDR)? cp0_count :
    (cp0_addr == `CP0_COMP_ADDR)? cp0_compare :
    32'b0;

endmodule