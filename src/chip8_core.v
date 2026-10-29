`default_nettype none

// Classic CHIP-8 with external byte memory. See docs/architecture.md.
module chip8_core #(
    parameter integer CLOCK_HZ = 1000000
) (
    input wire clk,
    input wire rst_n,
    output reg mem_valid,
    output reg mem_write,
    output reg [12:0] mem_addr,
    output reg [7:0] mem_wdata,
    input wire mem_ready,
    input wire [7:0] mem_rdata,
    output reg halted,
    output wire sound_active,
    output wire [11:0] debug_pc,
    output wire [7:0] debug_v0
);
    localparam FH=5'd0, FL=5'd1, EXEC=5'd2, STOP=5'd3,
        CLEAR=5'd4, PUSH_H=5'd5, PUSH_L=5'd6,
        POP_H=5'd7, POP_L=5'd8, STORE=5'd9, LOAD=5'd10,
        BCD_H=5'd11, BCD_T=5'd12, BCD_WRITE=5'd13,
        SPRITE=5'd14, PIXEL=5'd15, PIX_READ=5'd16, PIX_WRITE=5'd17,
        KEY_LO=5'd18, KEY_HI=5'd19, KEY_APPLY=5'd20;
    reg [4:0] state;
    reg [11:0] pc, index_reg;
    reg [15:0] opcode;
    reg [7:0] v [0:15];
    reg [4:0] sp;
    reg [7:0] delay_timer, sound_timer;
    localparam integer TIMER_BITS = $clog2(CLOCK_HZ + 60);
    reg [TIMER_BITS-1:0] timer_phase;
    reg [15:0] random_state;
    reg [7:0] offset;
    reg [3:0] transfer;
    reg [11:0] return_pc;
    reg [7:0] bcd_value;
    reg [3:0] hundreds, tens;
    reg [5:0] draw_x;
    reg [4:0] draw_y;
    reg [3:0] row;
    reg [2:0] column;
    reg [7:0] sprite_byte, pixel_result;
    reg [15:0] keys;
    reg waiting_release;
    reg [3:0] held_key;
    wire [3:0] x = opcode[11:8];
    wire [3:0] y = opcode[7:4];
    wire [7:0] vx = v[x];
    wire [7:0] vy = v[y];
    wire [8:0] sum = {1'b0, vx} + {1'b0, vy};
    wire [6:0] pixel_x = {1'b0, draw_x} + {4'd0, column};
    wire [5:0] pixel_y = {1'b0, draw_y} + {2'd0, row};
    wire [7:0] pixel_mask = 8'h80 >> pixel_x[2:0];
    wire [11:0] data_addr = index_reg + {8'd0, transfer};
    wire [11:0] sprite_addr = index_reg + {8'd0, row};
    wire [12:0] frame_addr = 13'h1000 + {5'd0, pixel_y[4:0], pixel_x[5:3]};
    wire [4:0] stack_slot = {sp[3:0], 1'b0};
    integer i;
    assign debug_pc = pc;
    assign debug_v0 = v[0];
    assign sound_active = (sound_timer != 0) && !halted && rst_n;

    // All outputs depend only on registered state and remain stable on stalls.
    always @* begin
        mem_valid = 1'b1;
        mem_write = 1'b0;
        mem_addr = 13'd0;
        mem_wdata = 8'd0;
        case (state)
            FH, FL: mem_addr = {1'b0, pc};
            CLEAR: begin
                mem_addr = 13'h1000 + {5'd0, offset};
                mem_write = 1'b1;
            end
            PUSH_H, PUSH_L: begin
                mem_addr = 13'h1100 + {8'd0, stack_slot} +
                           ((state == PUSH_L) ? 13'd1 : 13'd0);
                mem_write = 1'b1;
                mem_wdata = (state == PUSH_H) ? {4'd0, pc[11:8]} : pc[7:0];
            end
            POP_H, POP_L: mem_addr = 13'h1100 + {8'd0, stack_slot} +
                                      ((state == POP_L) ? 13'd1 : 13'd0);
            STORE, LOAD: begin
                mem_addr = {1'b0, data_addr};
                mem_write = (state == STORE);
                mem_wdata = v[transfer];
            end
            BCD_WRITE: begin
                mem_addr = {1'b0, data_addr};
                mem_write = 1'b1;
                case (transfer)
                    4'd0: mem_wdata = {4'd0, hundreds};
                    4'd1: mem_wdata = {4'd0, tens};
                    default: mem_wdata = bcd_value;
                endcase
            end
            SPRITE: mem_addr = {1'b0, sprite_addr};
            PIX_READ, PIX_WRITE: begin
                mem_addr = frame_addr;
                mem_write = (state == PIX_WRITE);
                mem_wdata = pixel_result;
            end
            KEY_LO: mem_addr = 13'h1120;
            KEY_HI: mem_addr = 13'h1121;
            default: mem_valid = 1'b0;
        endcase
        if (!rst_n) mem_valid = 1'b0;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= FH;
            pc <= 12'h200;
            index_reg <= 0;
            opcode <= 0;
            sp <= 0;
            delay_timer <= 0;
            sound_timer <= 0;
            timer_phase <= 0;
            random_state <= 16'hace1;
            halted <= 0;
            offset <= 0;
            transfer <= 0;
            return_pc <= 0;
            bcd_value <= 0;
            hundreds <= 0;
            tens <= 0;
            draw_x <= 0;
            draw_y <= 0;
            row <= 0;
            column <= 0;
            sprite_byte <= 0;
            pixel_result <= 0;
            keys <= 0;
            waiting_release <= 0;
            held_key <= 0;
            for (i=0; i<16; i=i+1) v[i] <= 0;
        end else begin
            // Fractional divider: exactly 60 ticks per CLOCK_HZ clocks.
            // Timer writes below take priority over a simultaneous tick.
            if (timer_phase >= TIMER_BITS'(CLOCK_HZ - 60)) begin
                timer_phase <= timer_phase - TIMER_BITS'(CLOCK_HZ - 60);
                if (delay_timer != 0) delay_timer <= delay_timer - 8'd1;
                if (sound_timer != 0) sound_timer <= sound_timer - 8'd1;
            end else timer_phase <= timer_phase + TIMER_BITS'(60);
            case (state)
                FH: if (mem_ready) begin
                    opcode[15:8] <= mem_rdata;
                    pc <= pc + 12'd1;
                    state <= FL;
                end
                FL: if (mem_ready) begin
                    opcode[7:0] <= mem_rdata;
                    pc <= pc + 12'd1;
                    state <= EXEC;
                end
                EXEC: begin
                    state <= FH;
                    case (opcode[15:12])
                        4'h0: begin
                            if (opcode == 16'h00e0) begin
                                offset <= 0;
                                state <= CLEAR;
                            end else if (opcode == 16'h00ee) begin
                                if (sp == 0) begin halted <= 1; state <= STOP; end
                                else begin sp <= sp - 5'd1; state <= POP_H; end
                            end
                            // Other 0nnn legacy RCA machine-code calls are
                            // ignored, as on modern CHIP-8 interpreters.
                        end
                        4'h1: pc <= opcode[11:0];
                        4'h2: begin
                            if (sp == 16) begin halted <= 1; state <= STOP; end
                            else state <= PUSH_H;
                        end
                        4'h3: if (vx == opcode[7:0]) pc <= pc + 12'd2;
                        4'h4: if (vx != opcode[7:0]) pc <= pc + 12'd2;
                        4'h5: begin
                            if (opcode[3:0] != 0) begin halted <= 1; state <= STOP; end
                            else if (vx == vy) pc <= pc + 12'd2;
                        end
                        4'h6: v[x] <= opcode[7:0];
                        4'h7: v[x] <= vx + opcode[7:0];
                        4'h8: case (opcode[3:0])
                            4'h0: v[x] <= vy;
                            4'h1: v[x] <= vx | vy;
                            4'h2: v[x] <= vx & vy;
                            4'h3: v[x] <= vx ^ vy;
                            4'h4: begin v[x] <= sum[7:0]; v[15] <= {7'd0, sum[8]}; end
                            4'h5: begin v[x] <= vx - vy; v[15] <= {7'd0, (vx >= vy)}; end
                            4'h6: begin v[x] <= vx >> 1; v[15] <= {7'd0, vx[0]}; end
                            4'h7: begin v[x] <= vy - vx; v[15] <= {7'd0, (vy >= vx)}; end
                            4'he: begin v[x] <= vx << 1; v[15] <= {7'd0, vx[7]}; end
                            default: begin halted <= 1; state <= STOP; end
                        endcase
                        4'h9: begin
                            if (opcode[3:0] != 0) begin halted <= 1; state <= STOP; end
                            else if (vx != vy) pc <= pc + 12'd2;
                        end
                        4'ha: index_reg <= opcode[11:0];
                        4'hb: pc <= opcode[11:0] + {4'd0, v[0]};
                        4'hc: begin
                            v[x] <= random_state[7:0] & opcode[7:0];
                            random_state <= {random_state[14:0],
                                random_state[15] ^ random_state[13] ^
                                random_state[12] ^ random_state[10]};
                        end
                        4'hd: begin
                            draw_x <= vx[5:0]; draw_y <= vy[4:0];
                            v[15] <= 0;
                            row <= 0; column <= 0;
                            if (opcode[3:0] != 0) state <= SPRITE;
                        end
                        4'he: begin
                            if (opcode[7:0] == 8'h9e || opcode[7:0] == 8'ha1)
                                state <= KEY_LO;
                            else begin halted <= 1; state <= STOP; end
                        end
                        4'hf: case (opcode[7:0])
                            8'h07: v[x] <= delay_timer;
                            8'h0a: begin waiting_release <= 0; state <= KEY_LO; end
                            8'h15: delay_timer <= vx;
                            8'h18: sound_timer <= vx;
                            8'h1e: index_reg <= index_reg + {4'd0, vx};
                            8'h29: index_reg <= 12'h050 + {8'd0, vx[3:0]} +
                                                          {6'd0, vx[3:0], 2'b00};
                            8'h33: begin
                                bcd_value <= vx; hundreds <= 0; tens <= 0;
                                transfer <= 0; state <= BCD_H;
                            end
                            8'h55: begin transfer <= 0; state <= STORE; end
                            8'h65: begin transfer <= 0; state <= LOAD; end
                            default: begin halted <= 1; state <= STOP; end
                        endcase
                        default: begin halted <= 1; state <= STOP; end
                    endcase
                end
                CLEAR: if (mem_ready) begin
                    offset <= offset + 8'd1;
                    if (offset == 8'hff) state <= FH;
                end
                PUSH_H: if (mem_ready) state <= PUSH_L;
                PUSH_L: if (mem_ready) begin
                    sp <= sp + 5'd1; pc <= opcode[11:0]; state <= FH;
                end
                POP_H: if (mem_ready) begin
                    return_pc[11:8] <= mem_rdata[3:0]; state <= POP_L;
                end
                POP_L: if (mem_ready) begin pc <= {return_pc[11:8], mem_rdata}; state <= FH; end
                STORE, LOAD: if (mem_ready) begin
                    if (state == LOAD) v[transfer] <= mem_rdata;
                    if (transfer == x) state <= FH;
                    else transfer <= transfer + 4'd1;
                end
                BCD_H: begin
                    if (bcd_value >= 100) begin
                        bcd_value <= bcd_value - 8'd100; hundreds <= hundreds + 4'd1;
                    end else state <= BCD_T;
                end
                BCD_T: begin
                    if (bcd_value >= 10) begin
                        bcd_value <= bcd_value - 8'd10; tens <= tens + 4'd1;
                    end else state <= BCD_WRITE;
                end
                BCD_WRITE: if (mem_ready) begin
                    if (transfer == 2) state <= FH;
                    else transfer <= transfer + 4'd1;
                end
                SPRITE: if (mem_ready) begin
                    sprite_byte <= mem_rdata; column <= 0; state <= PIXEL;
                end
                PIXEL: begin
                    if (!pixel_x[6] && !pixel_y[5] && sprite_byte[7-column]) state <= PIX_READ;
                    else if (column == 7) begin
                        if ((row + 4'd1) == opcode[3:0]) state <= FH;
                        else begin row <= row + 4'd1; state <= SPRITE; end
                    end else column <= column + 3'd1;
                end
                PIX_READ: if (mem_ready) begin
                    pixel_result <= mem_rdata ^ pixel_mask;
                    if ((mem_rdata & pixel_mask) != 0) v[15] <= 1;
                    state <= PIX_WRITE;
                end
                PIX_WRITE: if (mem_ready) begin
                    if (column == 7) begin
                        if ((row + 4'd1) == opcode[3:0]) state <= FH;
                        else begin row <= row + 4'd1; state <= SPRITE; end
                    end else begin column <= column + 3'd1; state <= PIXEL; end
                end
                KEY_LO: if (mem_ready) begin keys[7:0] <= mem_rdata; state <= KEY_HI; end
                KEY_HI: if (mem_ready) begin keys[15:8] <= mem_rdata; state <= KEY_APPLY; end
                KEY_APPLY: begin
                    if (opcode[15:12] == 4'he) begin
                        if ((opcode[7:0] == 8'h9e && vx < 16 && keys[vx[3:0]]) ||
                            (opcode[7:0] == 8'ha1 && (vx >= 16 || !keys[vx[3:0]])))
                            pc <= pc + 12'd2;
                        state <= FH;
                    end else if (!waiting_release) begin
                        if (keys != 0) begin
                            for (i=15; i>=0; i=i-1) if (keys[i]) held_key <= 4'(i);
                            waiting_release <= 1;
                        end
                        state <= KEY_LO;
                    end else if (!keys[held_key]) begin
                        v[x] <= {4'd0, held_key}; state <= FH;
                    end else state <= KEY_LO;
                end
                default: begin halted <= 1; state <= STOP; end
            endcase
        end
    end
endmodule
`default_nettype wire
