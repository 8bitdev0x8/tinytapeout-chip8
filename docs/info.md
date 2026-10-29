## How it works

A one-tile accumulator processor executes an external 2,080-byte interpreter
that implements the conventional CHIP-8 instruction set. The Feather RP2350
serves memory, displays the 64x32 framebuffer over HSTX, and supplies UART
controller state from an ESP32. CHIP-8 execution takes place on the ASIC.
All V registers and interpreter working state reside in external RAM.
The ASIC retains a shared arithmetic datapath, timers and native control.

## How to test

Load firmware/interpreter.bin at 0x1200, the CHIP-8 font at 0x050, and a game
at 0x200. Clear game RAM/framebuffer, hold reset low with acknowledge low,
then release reset with ena high. The native processor boots at 0x1200.
The 13-bit memory map and pin-level protocol are documented in
 docs/architecture.md in the project repository.

The shared byte bus is uio[7:0]; uo[1:0] selects address-low, address-high,
or data phase. uo[2] is request, ui[0] is ack. Each phase uses a four-phase
handshake. The companion drives the byte bus only during a phase-2 read,
releasing it before lowering ack. uo[4] is sound enable; uo[5] is halt.

Run the physical-port test suite on both RTL and the gate-level netlist.
Independent logo/opcode/flags ROMs must match their reference screenshots.

## External hardware

Adafruit Feather RP2350 with HSTX adapter and monitor; ESP32 forwarding
Bluetooth DualSense reports at 230400 baud to Feather RX. The Feather must
provide an 8 KB memory map including native ROM and working RAM. Real firmware,
physical wiring, and gameplay throughput have not yet been validated.
