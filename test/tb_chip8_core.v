`timescale 1ns/1ps
`default_nettype none
module tb_chip8_core;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0;
    wire valid,wr,halted,sound;
    wire [12:0] addr;
    wire [7:0] wdata,a;
    wire [11:0] pc;
    reg ready=0;
    reg [7:0] rdata=0;
    reg [7:0] ram[0:8191];
    integer cycles=0,i;
    reg stalled=0;
    reg [21:0] held;
    chip8_core dut(.clk(clk),.rst_n(rst_n),.mem_valid(valid),.mem_write(wr),
        .mem_addr(addr),.mem_wdata(wdata),.mem_ready(ready),.mem_rdata(rdata),
        .halted(halted),.sound_active(sound),.debug_pc(pc),.debug_v0(a));
    always @(negedge clk) begin
        cycles=cycles+1;ready=valid && cycles%5==0;rdata=ram[addr];
    end
    always @(posedge clk) begin
        if(rst_n) begin
            if(stalled && (!valid || {wr,addr,wdata}!==held)) $fatal(1,"Unstable request");
            stalled=valid&&!ready;held={wr,addr,wdata};
            if(valid&&ready&&wr)ram[addr]=wdata;
        end else stalled=0;
    end
    initial begin
        for(i=0;i<8192;i=i+1)ram[i]=0;
        // Native: A=255; A+=2; P=0x900; [P]=A; halt.
        ram['h1200]=0;ram['h1201]='hff;
        ram['h1202]=1;ram['h1203]=2;
        ram['h1204]='hd9;ram['h1205]=0;
        ram['h1206]='h20;ram['h1207]=0;
        ram['h1208]='h0f;ram['h1209]=0;
        repeat(3)@(negedge clk);rst_n=1;
        repeat(150)@(negedge clk);
        if(!halted || valid || ram['h900]!==1 || a!==1) $fatal(1,"Native engine failed");
        rst_n=0;repeat(2)@(negedge clk);
        if(halted || a!==0 || pc!==12'h200 || valid) $fatal(1,"Reset failed");
        $display("PASS: native arithmetic, memory, stalls, halt and reset");$finish;
    end
    initial begin #20000;$fatal(1,"Timeout");end
endmodule
`default_nettype wire
