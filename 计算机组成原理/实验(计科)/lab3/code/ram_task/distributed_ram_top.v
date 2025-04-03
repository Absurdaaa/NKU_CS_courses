module ram_top (
    input         clk      ,
    input  [15:0] ram_addr ,
    input  [31:0] ram_wdata,
    input         ram_wen  ,
    output [31:0] ram_rdata		   
);
					   
distributed_ram distributed_ram(
    .clk (clk       ),
    .we  (ram_wen   ),
    .a   (ram_addr  ),
    .d   (ram_wdata ),
    .spo (ram_rdata ) 
);

endmodule
