## How it works

This experimental CHIP-8 core currently implements 1nnn, 6xkk, and 7xkk.
Unsupported instructions halt. Reset starts fetching at address 0x200.
The planned companion is an Adafruit Feather RP2350 with HSTX video and
controller reports received from an ESP32 over UART.

The current wrapper is a read-only parallel simulation/bring-up interface.
It is not the final hardware transport. The IHP process, 1 MHz clock target,
1x1 tile setting, and project name are provisional. The complete processor
will need new area measurements. Synthesis may remove unused register state
in this partial implementation; its area does not predict the final core.

## How to test

Hold rst_n low for at least two clock edges, then release it with ena high.
When uio[5] is high, concatenate uio[4:0] and uo[7:0] to obtain the byte
address. Drive the response byte on ui[7:0], then assert uio[7] for a rising
clock edge. Each edge with request and response high completes one read.
Deassert response ready before the next edge unless supplying the next byte.
The address remains stable during wait states. When no request is active,
uo[7:0] exposes V0. uio[6] indicates halt.

All responder signals must meet setup/hold relative to clk. This interface
assumes synchronous input; do not directly wire asynchronous acknowledgments
without a clocking/CDC plan. Keep ena high during execution. It gates memory
transfers but is not a processor pause input. Reset is synchronous, active low.

Load these bytes at 0x200: 60 FF 70 02 70 02 12 06. The core must reach V0=3
and repeatedly fetch the jump at 0x206. The automated tests insert wait states
and verify reset and unsupported-opcode handling.

## External hardware

Final hardware: Feather RP2350, HSTX video adapter and monitor, and an ESP32
receiving DualSense input over Bluetooth. Feather firmware and final wiring
are not implemented. No hardware is required for the automated simulation.
