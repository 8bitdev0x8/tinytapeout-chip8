`default_nettype none

// Three-byte, four-phase-handshake companion bus. See docs/architecture.md.
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
    wire valid, wr, halted, sound;
    wire [12:0] addr;
    wire [7:0] wdata;
    wire [7:0] unused_v0;
    wire [11:0] unused_pc;
    reg [1:0] phase;
    reg wait_low;
    (* async_reg = "true" *) reg ack_meta, ack;
    wire request = valid && !wait_low && ena && rst_n;
    wire ready = request && (phase == 2) && ack;

    always @(posedge clk) begin
        if (!rst_n) begin
            ack_meta <= 0; ack <= 0; phase <= 0; wait_low <= 0;
        end else begin
            ack_meta <= uio_in[6];
            ack <= ack_meta;
            if (ena) begin
                if (wait_low) begin
                    if (!ack) begin
                        wait_low <= 0;
                        phase <= (phase == 2) ? 2'd0 : phase + 2'd1;
                    end
                end else if (request && ack) wait_low <= 1;
            end
        end
    end

    chip8_core core (
        .clk(clk), .rst_n(rst_n),
        .mem_valid(valid), .mem_write(wr), .mem_addr(addr), .mem_wdata(wdata),
        .mem_ready(ready), .mem_rdata(ui_in), .halted(halted),
        .sound_active(sound), .debug_pc(unused_pc), .debug_v0(unused_v0)
    );
    assign uo_out = (phase == 0) ? addr[7:0] :
                    (phase == 1) ? {3'd0, addr[12:8]} : wdata;
    assign uio_out = {2'b00, halted, sound, wr, request, phase};
    assign uio_oe = 8'h3f;
    wire _unused = &{1'b0, uio_in[7], uio_in[5:0], unused_pc, unused_v0};
endmodule
`default_nettype wire
