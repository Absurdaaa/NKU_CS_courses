
module show_sw (
    input             clk,          
    input             resetn,     

    input      [3 :0] switch,    //input

    output     [7 :0] num_csn,   //new value 
    //这个是数码管  
    output     [6 :0] num_a_g,      

    output     [3 :0] led        //previous value
);
//1. get switch data
//2. show switch data in digital number:
//   only show 0~9
//   if >=10, digital number keep old data.
//3. show previous switch data in led.
//   can show any switch data.

reg [3:0] show_data;
reg [3:0] show_data_r;
reg [3:0] prev_data;

//new value
always @(posedge clk)
begin
//1111111111111111
    show_data   <= ~switch;
end

always @(posedge clk)
begin
    show_data_r <= show_data;
end
//previous value
always @(posedge clk)
begin
    if(!resetn)
    begin
        prev_data <= 4'd0;
    end
    else if(show_data_r != show_data)
    begin
        prev_data = show_data_r;
    end
end

//show led: previous value
assign led = ~prev_data;

//show number: new value
show_num u_show_num(
        .clk        (clk      ),
        .resetn     (resetn   ),
        
        .show_data  (show_data),
        //444444444444444444444444444
        .num_csn    (num_scn  ),
        .num_a_g    (num_a_g  )
);

endmodule

//---------------------------{digital number}begin-----------------------//
module show_num (
    input             clk,          
    input             resetn,     

    input      [3 :0] show_data,
    output     [7 :0] num_csn,      
    output reg [6 :0] num_a_g      
);
//digital number display
assign num_csn = 8'b0111_1111;//选择第几个数码管

wire [6:0] nxt_a_g;

always @(posedge clk)
begin
    if ( !resetn )
    begin
        num_a_g <= 7'b0000000;
    end
    else
    begin
        num_a_g <= nxt_a_g;
    end
end

//keep unchange if show_dtaa>=10
wire [6:0] keep_a_g;
assign     keep_a_g  = show_data>=10?keep_a_g :num_a_g;

assign nxt_a_g = show_data==4'd0 ? 7'b1111110 :   //0
                 show_data==4'd1 ? 7'b0110000 :   //1
                 show_data==4'd2 ? 7'b1101101 :   //2
                 show_data==4'd3 ? 7'b1111001 :   //3
                 show_data==4'd4 ? 7'b0110011 :   //4
                 show_data==4'd5 ? 7'b1011011 :   //5
                 //222222222222222222222222222
                 show_data==4'd6 ? 7'b1011111 :   //6
                 show_data==4'd7 ? 7'b1110000 :   //7
                 show_data==4'd8 ? 7'b1111111 :   //8
                 show_data==4'd9 ? 7'b1111011 :   //9
                                   keep_a_g   ;
endmodule
//----------------------------{digital number}end------------------------//
