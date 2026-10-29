# One-tile CHIP-8 architecture

## Budget and execution model

The hard allocation limit is 1x1 IHP SG13G2 tile. This is a redesign of the
larger direct-decoder core preserved at Git commit 82f1b8e. Fit is established
only by a successful layout, gate-level test, and physical precheck.

The ASIC is a small 8-bit accumulator processor. It fetches and executes an
external native interpreter ROM that implements CHIP-8. The RP2350 only
serves reads/writes, supplies keypad state, and displays the framebuffer;
it does not execute the interpreter. CHIP-8 arithmetic, instruction decoding,
stack operations, BCD conversion, sprite XOR and collisions execute on ASIC.
The interpreter ROM is required alongside every game image.

On-chip state consists of an 8-bit accumulator, 13-bit memory pointer,
12-bit native program counter, 16-bit instruction register, zero/carry flags,
control state, 16-bit random generator, timer divider, and two 8-bit timers.
A five-bit sprite-row controller shares the accumulator, pointer, add/subtract
unit and instruction register. It XORs an aligned/shifted 8-bit sprite row
into one or two framebuffer bytes and reports collisions, clipping the
second byte at the right edge. This avoids interpreting every pixel.
There is one shared 13-bit add/subtract datapath for native PC increments,
pointer increments, and accumulator arithmetic. CHIP-8 V registers, PC, I,
stack pointer and drawing temporaries reside in companion RAM.

## External memory map

| Address | Meaning |
| --- | --- |
| 0x0000–0x0FFF | 4 KB CHIP-8 program/data memory; games start at 0x200 |
| 0x0050–0x009F | Standard 80-byte font within CHIP-8 memory |
| 0x1000–0x10FF | 64x32 framebuffer, 8 bytes/row, MSB left |
| 0x1100–0x111F | 16 big-endian return addresses |
| 0x1120, 0x1121 | Read-only keypad bitmap, low/high bytes |
| 0x1130–0x11FF | Reserved interpreter working RAM |
| 0x1140–0x114F | V0 through VF within working RAM |
| 0x1150–0x116C | Interpreter PC, I, stack pointer and temporaries |
| 0x1200–0x191F | Required 1,824-byte interpreter ROM |
| 0x1920–0x1FFF | Unused/reserved |

An 8 KB memory array is sufficient. Occupied storage is approximately 6.1 KiB;
the game still has the same 4 KB address space. The native ROM is generated
by firmware/build_interpreter.py, with a label map for debugging. It must be
served unchanged at 0x1200. Interpreter RAM is initialized by the ASIC's boot
code. The companion initializes game RAM/font/framebuffer before reset release.
Reading 0x1120 latches both keypad bytes until 0x1121 is read.

## CHIP-8 compatibility

All conventional CHIP-8 instructions are provided by the interpreter. Legacy
0nnn RCA machine-code calls are ignored. Invalid encodings and stack faults
halt the engine until reset. No Super-CHIP or XO-CHIP extensions.

- Shifts use Vx. OR/AND/XOR leave VF unchanged unless VF is the destination.
- Flag-producing operations read old operands first; final VF takes priority
  if VF is also the destination.
- Fx55/Fx65 leave I unchanged; Bnnn adds V0.
- Addresses and I wrap modulo 4096; Fx1E does not modify VF.
- Fx29 uses the low nibble and the five-byte font at 0x050.
- Sprite origins wrap to 64x32, but right/bottom overrun pixels are clipped.
  Dxy0 draws nothing and clears VF. There is no vertical-blank drawing wait.
- Fx0A accepts the lowest held key, then waits for its release.
- Values above 15 are treated as not pressed by Ex9E/ExA1.
- Cxkk uses the same 16-bit LFSR sequence seeded to 0xACE1 on reset.

## Timers and speed

The native engine holds DT/ST on chip and decrements them independently of
memory/interpreter progress. At the 1 MHz clock target, an integer divider
of 16666 gives 60.0024 Hz (0.004% above 60 Hz). Timer writes take priority
over a coincident tick. Sound output is a tone enable, not an audio waveform.
CLOCK_HZ must be at least 120. Reset clears DT/ST and restarts the divider.

The extra interpreter instructions and memory accesses reduce CHIP-8 speed.
Actual throughput must be measured with the physical bus and Feather RAM
server; no real-hardware frame-rate guarantee is made. Simulation logs include
clock counts for independent test ROMs, with intentional memory wait states.

## Physical interface

| Pin | Direction | Meaning |
| --- | --- | --- |
| uio[7:0] | Bidirectional | Shared byte bus |
| uo[1:0] | Out | Phase: 0=address low, 1=address high, 2=data |
| uo[2] | Out | Request valid |
| uo[3] | Out | Write operation |
| uo[4] | Out | Sound enable |
| uo[5] | Out | Halted |
| ui[0] | In | Acknowledge |
| ui[7:1], uo[7:6] | Unused | Reserved |

Each phase uses a four-phase level handshake: request rises with stable
phase/byte/operation; companion raises ack; chip lowers request; companion
lowers ack. The chip waits for ack low before advancing phases. Phase 1
sends address bits 12:8, zero padded. A phase-2 write transfers one byte
exactly once. In a phase-2 read the chip releases uio; the companion drives
the read byte before raising ack and releases the bus before lowering ack,
after request has fallen. Keep data stable throughout that acknowledgement.

Ack passes through two synchronizer flip-flops. Byte data crosses using
the stable-bus handshake. Hold ack low during reset. Keep ena high during
execution. The default external clock is 1 MHz. The bus needs 15 Feather
GPIOs including clock/reset, or 17 including optional sound/halt outputs;
UART/HSTX pin allocation and companion firmware still need hardware testing.

The core debug_pc/debug_v0 ports now expose the native PC/accumulator,
not the external CHIP-8 PC/V0. CHIP-8 state can be inspected in working RAM.

## Verification

A native instruction emulator validates the generated ROM against an
independent CHIP-8 model. RTL and gate-level tests use a Verilog companion
that services only physical ports, checks bus stability and direction,
inserts waits, and records architectural memory writes. Interpreter RAM writes are excluded
from reference traces. Framebuffer writes are coalesced by the row engine,
so data/stack write ordering is checked while framebuffer contents and
collision results are compared exactly against the reference.

Tests cover all opcodes, VF aliases, address wrapping, stack faults, clipped
sprites, keypad waits and timers. Four independent Timendus ROMs must match
every pixel of the published reference screenshots. Assets are pinned and
retain their GPL-3.0 license under test/roms. The chosen compatibility profile
is not claimed to reproduce every historical COSMAC VIP quirk.

## Native sprite operations

Native word F200 sets the sprite bit offset from accumulator bits 2:0.
F300 takes the sprite byte in A and framebuffer-byte address in P. It performs
read/XOR/write operations on the ASIC and returns collision 0/1 in A, setting
zero accordingly. P advances if a second byte is touched. The row engine
reuses the low instruction byte for writeback data. Vertical clipping and
sprite origin normalization are handled by the interpreter before F300.
