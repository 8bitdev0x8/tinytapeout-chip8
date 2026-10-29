## How it works

A classic CHIP-8 CPU with sixteen registers, a 16-level external call stack,
60 Hz timers, and an external 64x32 framebuffer. The Feather RP2350 companion
supplies RAM and keypad state and renders video. All conventional CHIP-8
instructions are implemented; legacy 0nnn calls are ignored. No Super-CHIP
or XO-CHIP extensions. See docs/architecture.md in the repository for the
complete compatibility profile and memory protocol.

The 2x2 IHP allocation and 1 MHz clock are provisional build targets.

## How to test

Initialize the companion RAM and font, load a ROM at 0x200, and clear the
framebuffer. Hold reset low for multiple clock edges with acknowledgement
low. Release reset with ena high. Service the three-phase byte bus using
four-phase request/acknowledge handshakes. Phase 0 sends address low, phase 1
address high, and phase 2 transfers data. uo[2] is request; ui[0] is ack. The shared byte bus is uio[7:0].
The companion drives it only during a phase-2 read, releasing it before ack
falls.
The chip synchronizes ack. Hold response data stable throughout acknowledge.

Run the cocotb suite for instruction-level comparison, framebuffer writes,
keypad behavior, timer operation and stack faults. The GitHub GDS workflow
also runs the suite against the physical gate-level netlist.

## External hardware

Adafruit Feather RP2350 with HSTX adapter and HDMI monitor; ESP32 with a
Bluetooth DualSense controller forwards reports at 230400 baud to Feather
RX. Companion firmware and final physical wiring remain to be implemented.
The simulation supplies a memory/controller model without external hardware.
