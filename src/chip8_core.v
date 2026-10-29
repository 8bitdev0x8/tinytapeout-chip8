`default_nettype none
// Small accumulator engine. The external ROM executes the CHIP-8 interpreter.
module chip8_core #(parameter integer CLOCK_HZ=1000000) (
    input wire clk, input wire rst_n,
    output reg mem_valid, output reg mem_write,
    output reg [12:0] mem_addr, output wire [7:0] mem_wdata,
    input wire mem_ready, input wire [7:0] mem_rdata,
    output wire halted, output wire sound_active,
    output wire [11:0] debug_pc, output wire [7:0] debug_v0
);
    localparam FH=3'd0, FL=3'd1, EXEC=3'd2, READ=3'd3, WRITE=3'd4, STOP=3'd5;
    localparam integer DIVISOR=CLOCK_HZ/60;
    localparam integer TIMER_BITS=$clog2(DIVISOR);
    reg [2:0] state;
    reg [11:0] pc;
    reg [12:0] pointer;
    reg [15:0] instruction;
    reg [7:0] accumulator;
    reg zero, carry;
    reg [7:0] delay_timer, sound_timer;
    reg [TIMER_BITS-1:0] tick_count;
    reg [15:0] random_state;
    wire [3:0] operation=instruction[15:12];
    wire [3:0] subop=instruction[11:8];
    wire [7:0] immediate=instruction[7:0];
    reg [12:0] lhs, rhs;
    reg subtract;
    wire [12:0] sum=lhs + (rhs ^ {13{subtract}}) + {{12{1'b0}}, subtract};
    wire [7:0] operand=(state==READ) ? mem_rdata : immediate;
    wire alu_sub=(state==READ) ? (operation==4) : (subop==5);
    reg [7:0] result;
    always @* begin
        lhs={5'd0,accumulator}; rhs={5'd0,operand}; subtract=alu_sub;
        if (state==FH || state==FL) begin
            lhs={1'b0,pc}; rhs=13'd1; subtract=0;
        end else if (state==EXEC && operation==0 && subop==10) begin
            lhs=pointer; rhs=13'd1; subtract=0;
        end
        result=sum[7:0];
        if (state==READ) begin
            case(operation)
                4'h1,4'hf: result=mem_rdata;
                4'h5: result=accumulator & mem_rdata;
                4'h6: result=accumulator | mem_rdata;
                4'h7: result=accumulator ^ mem_rdata;
                default: result=sum[7:0];
            endcase
        end else begin
            case(subop)
                4'h0: result=immediate;
                4'h2: result=accumulator & immediate;
                4'h3: result=accumulator | immediate;
                4'h4: result=accumulator ^ immediate;
                4'hb: result={accumulator[6:0],1'b0};
                4'hc: result={1'b0,accumulator[7:1]};
                default: result=sum[7:0];
            endcase
        end
    end
    always @* begin
        mem_valid=rst_n && (state==FH || state==FL || state==READ || state==WRITE);
        mem_write=(state==WRITE);
        mem_addr=pointer;
        if (state==FH || state==FL) mem_addr={1'b1,pc};
        else if (operation==12 || operation==15) mem_addr={5'h11,immediate};
    end
    assign mem_wdata=accumulator;
    assign halted=(state==STOP);
    assign sound_active=(sound_timer!=0) && !halted && rst_n;
    assign debug_pc=pc;
    assign debug_v0=accumulator;
    always @(posedge clk) begin
        if (!rst_n) begin
            state<=FH; pc<=12'h200; pointer<=0; instruction<=0;
            accumulator<=0; zero<=1; carry<=0;
            delay_timer<=0; sound_timer<=0; tick_count<=0; random_state<=16'hace1;
        end else begin
            if (tick_count==0) begin
                tick_count<=TIMER_BITS'(DIVISOR-1);
                if (delay_timer!=0) delay_timer<=delay_timer-8'd1;
                if (sound_timer!=0) sound_timer<=sound_timer-8'd1;
            end else tick_count<=tick_count-1'b1;
            case(state)
                FH: if(mem_ready) begin instruction[15:8]<=mem_rdata;pc<=sum[11:0];state<=FL;end
                FL: if(mem_ready) begin instruction[7:0]<=mem_rdata;pc<=sum[11:0];state<=EXEC;end
                EXEC: begin
                    state<=FH;
                    case(operation)
                        4'h0: case(subop)
                            0,1,2,3,4,5,11,12: begin
                                accumulator<=result; zero<=(result==0);
                                if(subop==1) carry<=sum[8];
                                if(subop==5) carry<=!sum[12];
                                if(subop==11) carry<=accumulator[7];
                                if(subop==12) carry<=accumulator[0];
                            end
                            6: pointer[7:0]<=accumulator;
                            7: pointer[12:8]<=accumulator[4:0];
                            8: pc<={immediate[3:0],accumulator};
                            9: begin accumulator<=pointer[7:0];zero<=(pointer[7:0]==0);end
                            10: pointer<=sum;
                            13: begin
                                accumulator<=random_state[7:0];zero<=(random_state[7:0]==0);
                                random_state<={random_state[14:0],random_state[15]^random_state[13]^random_state[12]^random_state[10]};
                            end
                            14: case(immediate[1:0])
                                0: begin accumulator<=delay_timer;zero<=(delay_timer==0);end
                                1: delay_timer<=accumulator;
                                2: sound_timer<=accumulator;
                                default: state<=STOP;
                            endcase
                            default: state<=STOP;
                        endcase
                        1,3,4,5,6,7: state<=READ;
                        2,12: state<=WRITE;
                        8: pc<=instruction[11:0];
                        9: if(zero) pc<=instruction[11:0];
                        10: if(!zero) pc<=instruction[11:0];
                        11: if(carry) pc<=instruction[11:0];
                        13,14: pointer<={operation[0] ^ 1'b1,instruction[11:0]};
                        15: begin
                            if(instruction[8]) begin
                                accumulator<={3'd0,pointer[12:8]};zero<=(pointer[12:8]==0);
                            end else state<=READ;
                        end
                        default: state<=STOP;
                    endcase
                end
                READ: if(mem_ready) begin
                    accumulator<=result;zero<=(result==0);
                    if(operation==3) carry<=sum[8];
                    if(operation==4) carry<=!sum[12];
                    state<=FH;
                end
                WRITE: if(mem_ready) state<=FH;
                default: state<=STOP;
            endcase
        end
    end
endmodule
`default_nettype wire
