`timescale 1ns/1ps
`default_nettype none
module tb;
    reg clk=0;
    always #500 clk=~clk;
    reg rst_n=0;
    reg ena=1;
    reg [7:0] ui_in=0, uio_in=0;
    wire [7:0] uo_out,uio_out,uio_oe;
    tt_um_chip8_feather user_project(
        .clk(clk),.rst_n(rst_n),.ena(ena),.ui_in(ui_in),.uo_out(uo_out),
        .uio_in(uio_in),.uio_out(uio_out),.uio_oe(uio_oe));
    reg [7:0] memory[0:8191];
    reg [20:0] trace[0:4095];
    reg [12:0] watch_addr=13'h1fff;
    reg watch_enable=0;
    reg [31:0] max_cycles=30000000;
    reg [15:0] key_initial=0,key_later=0;
    reg [31:0] key_switch_poll=0;
    reg timed_keys=0;
    reg [31:0] key_on_cycle=0,key_off_cycle=0;
    reg [31:0] cycle_count=0,write_count=0,poll_count=0,watch_count=0;
    reg [31:0] sound_start=0,sound_stop=0;
    reg error=0;
    reg [7:0] address_low;
    reg [4:0] address_high;
    reg operation;
    reg [15:0] key_snapshot;
    reg [1:0] delay_count=0;
    reg [10:0] held_bus;
    reg check_stable=0;
    wire request=uo_out[2];
    wire [1:0] phase=uo_out[1:0];
    wire wr=uo_out[3];
    wire [12:0] address={address_high,address_low};
    wire [7:0] byte_out=(phase==2 && !wr) ? 8'd0 : uio_out;
    wire [15:0] current_keys=timed_keys ?
        (((cycle_count>=key_on_cycle)&&(cycle_count<key_off_cycle)) ? key_initial : key_later) :
        ((poll_count+1<key_switch_poll) ? key_initial : key_later);
    wire finished=error || uo_out[5] || (watch_enable && watch_count>=3);
    always @(posedge clk) begin
        if (!rst_n) begin
            ui_in<=0;uio_in<=0;cycle_count<=0;write_count<=0;poll_count<=0;
            watch_count<=0;sound_start<=0;sound_stop<=0;error<=0;
            address_low<=0;address_high<=0;operation<=0;key_snapshot<=0;
            delay_count<=0;check_stable<=0;held_bus<=0;
        end else if (!finished) begin
            cycle_count<=cycle_count+1;
            if(cycle_count>=max_cycles) begin error<=1;$display("ERROR: cycle limit");end
            if(uo_out[4] && sound_start==0) sound_start<=cycle_count;
            if(!uo_out[4] && sound_start!=0 && sound_stop==0) sound_stop<=cycle_count;
            if(uio_oe !== ((phase==2 && !wr) ? 8'h00 : 8'hff)) begin
                error<=1;$display("ERROR: bus direction");
            end
            if(request && check_stable && {phase,wr,byte_out}!==held_bus) begin
                error<=1;$display("ERROR: request changed while stalled");
            end
            if(!request) begin
                ui_in<=0;delay_count<=0;check_stable<=0;
            end else if(!ui_in[0]) begin
                check_stable<=1;held_bus<={phase,wr,byte_out};
                delay_count<=delay_count+1;
                if(delay_count==2) begin
                    ui_in<=1;
                    case(phase)
                        0:begin address_low<=uio_out;operation<=wr;end
                        1:begin
                            address_high<=uio_out[4:0];
                            if(uio_out[7:5]!=0 || wr!=operation) begin error<=1;$display("ERROR: address header");end
                        end
                        2:begin
                            if(wr!=operation) begin error<=1;$display("ERROR: changed operation");end
                            if(wr) begin
                                if(address==13'h1120 || address==13'h1121 || address>=13'h1200) begin
                                    error<=1;$display("ERROR: write to read-only address %h",address);
                                end
                                memory[address]<=uio_out;
                                if(!(address>=13'h1130 && address<13'h1200)) begin
                                    if(write_count>=4096) begin error<=1;$display("ERROR: trace overflow");end
                                    else trace[write_count]<={address,uio_out};
                                    write_count<=write_count+1;
                                end
                            end else begin
                                if(watch_enable && address==watch_addr) watch_count<=watch_count+1;
                                if(address==13'h1120) begin
                                    poll_count<=poll_count+1;key_snapshot<=current_keys;uio_in<=current_keys[7:0];
                                end else if(address==13'h1121) uio_in<=key_snapshot[15:8];
                                else uio_in<=memory[address];
                            end
                        end
                        default:begin error<=1;$display("ERROR: invalid phase");end
                    endcase
                end
            end
        end
    end
    initial begin
        if($test$plusargs("WAVES")) begin
            $dumpfile("tb.fst");
            $dumpvars(1,tb);
            $dumpvars(0,tb.user_project);
        end
    end
endmodule
`default_nettype wire
