`timescale 1ns / 1ps

module tb_top();

reg         clk;

reg  [ 4:0] raddr1;
wire [31:0] rdata1;
reg  [ 4:0] raddr2;
wire [31:0] rdata2;
reg         we;
reg  [ 4:0] waddr;
reg  [31:0] wdata;

reg  [ 3:0] task_phase;

regfile u_regfile(
    .clk      (clk       ),
    .raddr1   (raddr1    ),
    .rdata1   (rdata1    ),
    .raddr2   (raddr2    ),
    .rdata2   (rdata2    ),
    .we       (we        ),
    .waddr    (waddr     ),
    .wdata    (wdata     ) 
);

//clk
initial 
begin
    clk = 1'b1;
end
always #5 clk = ~clk;
					
initial 
begin
    raddr1 =  5'd0;
    raddr2 =  5'd0;
	waddr  =  5'd0;
	wdata  = 32'd0;
	we     =  1'd0;
	task_phase =  4'd0;
	#2000;
	
	$display("=============================");
	$display("Test Begin");
	#1;
	// Part 0 Begin
	#10;
	task_phase = 4'd0;
	we         = 1'b0;
	waddr      = 5'd1;
	wdata      = 32'hffffffff;
    raddr1     = 5'd1;
    #10;
	we         = 1'b1;
	waddr      = 5'd1;
	wdata      = 32'h1111ffff;
    #10;
	we         = 1'b0;
    raddr1     = 5'd2;
    raddr2     = 5'd1;
	#10;
    raddr1     = 5'd1;
    
    #200;
    // Part 1 Begin
    #10;
	task_phase = 4'd1;
	we         = 1'b1;
	wdata      = 32'h0000ffff;
	waddr      =  5'h10;
    raddr1     =  5'h10;
    raddr2     =  5'h0f;
	#10;
	wdata      = 32'h1111ffff;
	waddr      =  5'h11;
    raddr1     =  5'h11;
    raddr2     =  5'h10;
	#10;
	wdata      = 32'h2222ffff;
	waddr      =  5'h12;
    raddr1     =  5'h12;
    raddr2     =  5'h11;
	#10;
	wdata      = 32'h3333ffff;
	waddr      =  5'h13;
    raddr1     =  5'h13;
    raddr2     =  5'h12;
	#10;
	wdata      = 32'h4444ffff;
	waddr      =  5'h14;
    raddr1     =  5'h14;
    raddr2     =  5'h13;
	#10;
    raddr1     =  5'h15;
    raddr2     =  5'h14;
	#10;

    #200;
	// Part 2 Begin
	#10;
	task_phase = 4'd2;
	we         = 1'b1;
    raddr1     =  5'h10;
    raddr2     =  5'h0f;
	#10;
    raddr1     =  5'h11;
    raddr2     =  5'h10;
	#10;
    raddr1     =  5'h12;
    raddr2     =  5'h11;
	#10;
    raddr1     =  5'h13;
    raddr2     =  5'h12;
	#10;
    raddr1     =  5'h14;
    raddr2     =  5'h13;
	#10;
	
	#50;
	$display("TEST END");
	$finish;
end

endmodule
