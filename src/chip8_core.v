`default_nettype none

// Initial CHIP-8 core: 1nnn, 6xkk, 7xkk. Unsupported opcodes halt.
// Memory transfers complete on a rising edge with valid && ready.
module chip8_core (
    input wire clk,
    input wire rst_n,
    output wire mem_valid,
    output wire mem_write,
    output wire [12:0] mem_addr,
    output wire [7:0] mem_wdata,
    input wire mem_ready,
    input wire [7:0] mem_rdata,
    output reg halted,
    output wire [11:0] debug_pc,
    output wire [7:0] debug_v0
);
    localparam FETCH_HIGH = 2'd0, FETCH_LOW = 2'd1,
               EXECUTE = 2'd2, HALT = 2'd3;
    reg [1:0] state;
    reg [11:0] pc;
    reg [15:0] opcode;
    reg [7:0] v [0:15];
    integer i;

    assign mem_valid = rst_n &&
                       ((state == FETCH_HIGH) || (state == FETCH_LOW));
    assign mem_write = 1'b0;
    assign mem_addr = {1'b0, pc};
    assign mem_wdata = 8'd0;
    assign debug_pc = pc;
    assign debug_v0 = v[0];

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= FETCH_HIGH;
            pc <= 12'h200;
            opcode <= 16'd0;
            halted <= 1'b0;
            for (i = 0; i < 16; i = i + 1)
                v[i] <= 8'd0;
        end else begin
            case (state)
                FETCH_HIGH: if (mem_ready) begin
                    opcode[15:8] <= mem_rdata;
                    pc <= pc + 12'd1;
                    state <= FETCH_LOW;
                end
                FETCH_LOW: if (mem_ready) begin
                    opcode[7:0] <= mem_rdata;
                    pc <= pc + 12'd1;
                    state <= EXECUTE;
                end
                EXECUTE: begin
                    case (opcode[15:12])
                        4'h1: begin
                            pc <= opcode[11:0];
                            state <= FETCH_HIGH;
                        end
                        4'h6: begin
                            v[opcode[11:8]] <= opcode[7:0];
                            state <= FETCH_HIGH;
                        end
                        4'h7: begin
                            v[opcode[11:8]] <= v[opcode[11:8]] + opcode[7:0];
                            state <= FETCH_HIGH;
                        end
                        default: begin
                            halted <= 1'b1;
                            state <= HALT;
                        end
                    endcase
                end
                default: state <= HALT;
            endcase
        end
    end
endmodule

`default_nettype wire
