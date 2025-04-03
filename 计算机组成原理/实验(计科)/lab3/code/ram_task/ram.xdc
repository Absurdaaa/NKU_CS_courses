
create_clock -period 20.000 -name clk -waveform {0.000 10.000} [get_ports clk]
set_input_delay -clock clk [expr 4.0] [all_inputs]
set_output_delay -clock clk [expr 3.0] [all_outputs]