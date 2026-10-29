# Classic CHIP-8 processor

## Scope and compatibility

All 35 conventional CHIP-8 instructions are implemented. Legacy 0nnn RCA
machine-code calls are ignored because this is not a CDP1802 processor.
Unsupported encodings halt until reset. Super-CHIP and XO-CHIP extensions
are not implemented. The core has sixteen 8-bit registers, a 12-bit PC and
I register, 16 call levels, and independent 8-bit delay and sound timers.

The fixed compatibility profile is:

- 8xy6 and 8xyE shift Vx; Vy is ignored.
- OR/AND/XOR preserve VF unless VF is the destination.
- Flag-producing ALU operations read their operands before changing VF.
  If x=F, the final VF flag takes priority over the arithmetic result.
- Fx55/Fx65 leave I unchanged. Bnnn adds V0.
- I and program/data addresses wrap modulo 4096. Fx1E does not change VF.
- Fx29 uses the low nibble and the five-byte font at 0x050.
- Sprite starting coordinates wrap to 64x32; pixels past the right or bottom
  edge are clipped. Dxy0 draws no pixels and clears VF.
- Drawing does not wait for vertical blank. The companion may pace execution.
- Fx0A selects the lowest held key and finishes when that key is released.
  A key already held when the instruction starts is accepted.
- Ex9E treats values above 15 as not pressed; ExA1 treats them as not pressed.
- Cxkk uses a nonzero 16-bit LFSR seeded to 0xACE1 on reset. It advances once
  per random instruction. This is deterministic pseudorandomness, not entropy.

These choices run conventional modern CHIP-8 programs but do not reproduce
all original COSMAC VIP quirks. Some games need a different profile.

## Memory owned by the companion

| Address | Meaning |
| --- | --- |
| 0x0000–0x0FFF | CHIP-8 program/data memory |
| 0x1000–0x10FF | 64x32 monochrome framebuffer, 8 bytes per row, MSB left |
| 0x1100–0x111F | 16 return addresses, big endian, two bytes each |
| 0x1120 | Keypad bitmap bits 7:0, read only |
| 0x1121 | Keypad bitmap bits 15:8, read only |

Before releasing reset the companion must initialize RAM, load the 80-byte
font at 0x050, load the ROM at 0x200, and clear the framebuffer. Reset clears
internal processor state; it does not clear external memory. Stack RAM need
not be initialized. Overflow and underflow halt before an invalid stack access.
Reading 0x1120 should latch the full keypad bitmap until 0x1121 has been read,
so a changing controller report cannot tear the two-byte snapshot.

## Internal core interface

`mem_valid`, `mem_write`, `mem_addr[12:0]`, `mem_wdata[7:0]`, `mem_ready`, and
`mem_rdata[7:0]` form a byte request/response bus. A transfer completes at a
rising edge with valid and ready. Address, operation, and write data remain
stable while waiting. The core may issue consecutive transactions without
an idle cycle. Do not respond twice to the same transaction.

## Physical Tiny Tapeout interface

The standard top module serializes each byte transaction into three phases:

| Pin | Direction | Meaning |
| --- | --- | --- |
| ui[7:0] | Into chip | Read response byte |
| uo[7:0] | Out of chip | Request byte for the current phase |
| uio[1:0] | Out | Phase 0=address low, 1=address high, 2=data |
| uio[2] | Out | Request valid |
| uio[3] | Out | Write operation |
| uio[4] | Out | Sound timer active (tone enable) |
| uio[5] | Out | Halted |
| uio[6] | In | Companion acknowledgement |
| uio[7] | In | Unused |

Each phase uses a four-phase level handshake:

1. The chip asserts request with a stable phase, byte, and operation.
2. The companion consumes the byte and raises acknowledgement. On a phase-2
   read it must first drive the response byte, then raise acknowledgement.
3. The chip lowers request after recognizing acknowledgement.
4. The companion lowers acknowledgement after seeing request go low.
   The chip waits for that low level before starting another phase.

Phase 1 sends {000, address[12:8]}. Phase 2 sends write data for writes;
its output byte is ignored for reads. Complete the write exactly once at
phase 2, even if acknowledgement stays high for many clocks. Keep read data
stable from before acknowledgement rises until after request falls.

Acknowledgement passes through two synchronizer flip-flops. The byte data
uses the stable-bus handshake above rather than independent bit synchronizers.
Hold acknowledgement low through reset. Keep ena high during execution;
selection is not an architectural pause. The chip uses a 1 MHz external clock
by default. No FPGA/Feather pin numbers have yet been assigned to this bus.
The bus needs 8 input, 8 output, and 7 control/status signals in addition to
clock/reset; not all signals need direct Feather pins (e.g. status outputs
may be left unconnected). A real wiring/PIO allocation remains to be checked
against HSTX and UART usage before connecting hardware.

## Timers and sound

A fractional divider produces exactly 60 timer ticks per CLOCK_HZ clocks.
CLOCK_HZ must be at least 60; the top module defaults to 1,000,000. Timers
continue during memory stalls and key waits. Timer writes take priority over
a simultaneous tick. Sound output is an enable while ST>0, not an audio
waveform. The Feather should synthesize a tone while enabled. The timer
frequency assumes that the external clock matches CLOCK_HZ.

## Verification and physical build

The cocotb companion drives only top-level pins, inserts response delays,
and checks handshake stability. An independent instruction-level model
checks every memory write for arithmetic/flag vectors, control flow, BCD,
register transfers, random masks, sprites, collisions, and clipping. Other
tests cover keypad skips/waits, timers, stack faults, and invalid instructions.
The same suite runs on the synthesized gate-level netlist.

The IHP allocation is provisionally 4x2 tiles for the expanded processor.
This is an experiment, not a purchase or area guarantee. The complete layout
must pass routing, timing, gate-level tests and precheck before submission.
Feather UART decoding, RAM server, video and audio firmware remain separate
work; this repository currently implements and simulates the ASIC side.

Reference: https://github.com/Timendus/chip8-test-suite
