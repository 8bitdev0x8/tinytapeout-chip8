`timescale 1ns/1ps
`default_nettype none
module live_tb;
    reg clk=0,rst_n=0;
    reg [7:0] ui_in=0,uio_in=0;
    wire [7:0] uo_out,uio_out,uio_oe;
    tt_um_chip8_feather dut(.clk(clk),.rst_n(rst_n),.ena(1'b1),
        .ui_in(ui_in),.uo_out(uo_out),.uio_in(uio_in),.uio_out(uio_out),.uio_oe(uio_oe));
    reg [7:0] memory[0:8191];
    reg [15:0] keys=0,key_snapshot=0;
    reg [7:0] address_low=0;
    reg [4:0] address_high=0;
    reg [1:0] delay_count=0;
    wire [12:0] address={address_high,address_low};
    wire request=uo_out[2],wr=uo_out[3];
    wire [1:0] phase=uo_out[1:0];
    wire [7:0] bus=(uio_oe==0) ? uio_in : uio_out;
    reg error=0;
    integer clocks=0,tx_count=0;
    reg [63:0] tx_time[0:63];
    reg [12:0] tx_addr[0:63];
    reg [7:0] tx_data[0:63];
    reg tx_write[0:63];
    wire [11:0] chip8_pc={memory['h1153][3:0],memory['h1152]};
    wire [15:0] chip8_opcode={memory['h1155],memory['h1156]};
    integer fetch_label='h248;
    wire boundary=(dut.core.pc==fetch_label[11:0] && dut.core.state==0);
    reg emit_trace=0;
    reg [63:0] wave_time[0:255];
    reg [367:0] wave_data[0:255];
    integer wave_count=0,k;
    string filename,command;
    integer count,trace_cycles,key_value,rc,i,j,step_limit,unused;
    reg was_boundary;
    reg [63:0] cycle_limit;
    always @(posedge clk) begin
        if(!rst_n) begin
            ui_in<=0;uio_in<=0;delay_count<=0;address_low<=0;address_high<=0;
            clocks<=0;tx_count<=0;error<=0;key_snapshot<=0;
        end else begin
            clocks<=clocks+1;
            if(!request) begin ui_in<=0;delay_count<=0;end
            else if(!ui_in[0]) begin
                delay_count<=delay_count+1;
                if(delay_count==2) begin
                    ui_in<=1;
                    case(phase)
                        0:address_low<=uio_out;
                        1:address_high<=uio_out[4:0];
                        2:begin
                            if(wr) begin
                                if(address=='h1120 || address=='h1121 || address>='h1200) error<=1;
                                else memory[address]<=uio_out;
                            end else begin
                                if(address=='h1120) begin key_snapshot<=keys;uio_in<=keys[7:0];end
                                else if(address=='h1121)uio_in<=key_snapshot[15:8];
                                else uio_in<=memory[address];
                            end
                        end
                        default:error<=1;
                    endcase
                end
            end
            // Record real native-memory completion edges, not UI-derived events.
            if(dut.valid && dut.ready) begin
                tx_time[tx_count%64]<=$time;
                tx_addr[tx_count%64]<=dut.addr;
                tx_data[tx_count%64]<=dut.wr ? dut.wdata : uio_in;
                tx_write[tx_count%64]<=dut.wr;
                tx_count<=tx_count+1;
            end
        end
    end
    task sample;
        begin
            wave_time[wave_count%256]=$time;
            wave_data[wave_count%256]={{15'd0,clk},
                {15'd0,rst_n},
                {15'd0,request},
                {15'd0,ui_in[0]},
                {14'd0,phase},
                {15'd0,wr},
                {8'd0,bus},
                {8'd0,uio_oe},
                {15'd0,dut.valid},
                {15'd0,dut.ready},
                {3'd0,dut.addr},
                {8'd0,dut.wdata},
                {8'd0,uio_in},
                {3'd0,{1'b1,dut.core.pc}},
                {3'd0,dut.core.pointer},
                {8'd0,dut.core.accumulator},
                {13'd0,dut.core.state},
                {8'd0,dut.core.delay_timer},
                {8'd0,dut.core.sound_timer},
                {4'd0,chip8_pc},
                chip8_opcode,
                dut.core.instruction,
                keys};
            wave_count=wave_count+1;
        end
    endtask
    task tick;
        begin
            #499;clk=1;#1;if(emit_trace)sample();
            #499;clk=0;#1;if(emit_trace)sample();
        end
    endtask
    task report;
        begin
            $display("M %0d %0t %h %h %h %h %h %h %h %h %h %h %h %h",
                clocks,$time,uo_out[5],uo_out[4],error,chip8_pc,chip8_opcode,
                {1'b1,dut.core.pc},dut.core.instruction,dut.core.accumulator,
                dut.core.pointer,dut.core.state,dut.core.delay_timer,dut.core.sound_timer);
            $write("F ");for(j=0;j<256;j=j+1)$write("%02h",memory['h1000+j]);$write("\n");
            $write("V ");for(j=0;j<16;j=j+1)$write("%02h",memory['h1140+j]);$write("\n");
            for(j=((tx_count>24)?tx_count-24:0);j<tx_count;j=j+1)
                $display("T %0t %h %h %h",tx_time[j%64],tx_write[j%64],tx_addr[j%64],tx_data[j%64]);
            for(j=((wave_count>256)?wave_count-256:0);j<wave_count;j=j+1)begin
                $write("W %0t",wave_time[j%256]);
                for(k=22;k>=0;k=k-1)$write(" %04h",wave_data[j%256][k*16+:16]);
                $write("\n");
            end
            $display("END");$fflush();
        end
    endtask
    initial begin
        $timeformat(-9,0,"",20);
        if(!$value$plusargs("IMAGE=%s",filename))begin $display("ERROR missing image");$finish;end
        unused=$value$plusargs("FETCH=%h",fetch_label);
        $readmemh(filename,memory);
        $dumpfile("capture.vcd");$dumpvars(0,dut);$dumpoff;
        emit_trace=1;repeat(3)tick();rst_n=1;emit_trace=0;
        report();
        while(!$feof(32'h80000000))begin
            rc=$fscanf(32'h80000000,"%s %d %h %d",command,count,key_value,trace_cycles);
            if(rc!=4)begin $display("ERROR invalid command");$fflush();$finish;end
            keys=key_value[15:0];wave_count=0;
            if(command=="QUIT")$finish;
            if(count<0 || count>1000000)count=0;
            if(trace_cycles<0)trace_cycles=0;
            if(trace_cycles>128)trace_cycles=128;
            if(command=="CAPTURE")$dumpon;
            was_boundary=boundary;
            begin:run_loop
                for(i=0;i<count;i=i+1)begin
                    emit_trace=(i>=count-trace_cycles || command=="INST");
                    tick();
                    if(uo_out[5] || error)disable run_loop;
                    if(command=="INST" && boundary && !was_boundary)disable run_loop;
                    was_boundary=boundary;
                end
            end
            emit_trace=0;
            if(command=="CAPTURE")begin $dumpoff;$dumpflush;end
            report();
        end
        $finish;
    end
endmodule
`default_nettype wire
