`timescale 1ns/1ps
`default_nettype none

module tb_chip8_core;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    wire valid, wr, halted;
    wire [12:0] addr;
    wire [7:0] wdata, v0;
    wire [11:0] pc;
    reg ready = 0;
    reg [7:0] rdata = 0;
    reg [7:0] ram [0:8191];
    integer cycles = 0;
    integer transfers = 0;
    integer index;
    reg stalled = 0;
    reg [12:0] held_addr;
    reg saw_loop = 0;

    chip8_core dut (
        .clk(clk), .rst_n(rst_n), .mem_valid(valid),
        .mem_write(wr), .mem_addr(addr), .mem_wdata(wdata),
        .mem_ready(ready), .mem_rdata(rdata), .halted(halted),
        .debug_pc(pc), .debug_v0(v0)
    );

    // Respond on selected cycles, producing several consecutive wait states.
    always @(negedge clk) begin
        cycles = cycles + 1;
        ready = valid && ((cycles % 5) == 0);
        rdata = ram[addr];
    end

    always @(posedge clk) begin
        if (rst_n) begin
            if (stalled && (!valid || addr !== held_addr))
                $fatal(1, "Request changed while waiting");
            stalled = valid && !ready;
            held_addr = addr;
            if (valid && ready) begin
                if (wr) $fatal(1, "Unexpected write");
                transfers = transfers + 1;
            end
            if (valid && addr == 13'h206) saw_loop = 1;
        end else stalled = 0;
    end

    initial begin
        for (index = 0; index < 8192; index = index + 1)
            ram[index] = 0;
        // V0=255; V0+=2 (wrap to 1); V0+=2; jump to self.
        ram['h200] = 'h60; ram['h201] = 'hff;
        ram['h202] = 'h70; ram['h203] = 'h02;
        ram['h204] = 'h70; ram['h205] = 'h02;
        ram['h206] = 'h12; ram['h207] = 'h06;
        repeat (3) @(negedge clk);
        rst_n = 1;
        repeat (150) @(negedge clk);
        if (halted || v0 !== 8'd3 || !saw_loop || transfers < 12)
            $fatal(1, "Program failed: V0=%h PC=%h", v0, pc);
        // Replace loop with an unsupported instruction, which must halt.
        ram['h206] = 0; ram['h207] = 0;
        repeat (40) @(negedge clk);
        if (!halted || valid) $fatal(1, "Unsupported opcode did not halt");
        // Reset must recover from halt and clear registers.
        rst_n = 0;
        repeat (2) @(negedge clk);
        if (halted || v0 !== 0 || pc !== 12'h200 || valid)
            $fatal(1, "Reset failed");
        $display("PASS: execution, overflow, jumps, stalls, halt, reset");
        $finish;
    end

    initial begin
        #20000;
        $fatal(1, "Timeout");
    end
endmodule

`default_nettype wire
