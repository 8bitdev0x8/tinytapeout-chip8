`default_nettype none

// Provisional, read-only bring-up interface; not the final Feather bus.
module tt_um_chip8_feather (
    input wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input wire ena,
    input wire clk,
    input wire rst_n
);
    wire valid;
    wire [12:0] addr;
    wire halted;
    wire [7:0] v0;
    wire unused_write;
    wire [7:0] unused_wdata;
    wire [11:0] unused_pc;

    chip8_core core (
        .clk(clk), .rst_n(rst_n),
        .mem_valid(valid), .mem_write(unused_write),
        .mem_addr(addr), .mem_wdata(unused_wdata),
        .mem_ready(ena && uio_in[7]), .mem_rdata(ui_in),
        .halted(halted), .debug_pc(unused_pc), .debug_v0(v0)
    );

    assign uo_out = valid ? addr[7:0] : v0;
    assign uio_out = {1'b0, halted, (valid && ena), addr[12:8]};
    assign uio_oe = 8'h7f;
    wire _unused = &{1'b0, uio_in[6:0], unused_write,
                     unused_wdata, unused_pc};
endmodule

`default_nettype wire
