# Tiny Tapeout CHIP-8

A classic CHIP-8 processor in Verilog with an external-memory companion bus.
The companion target is an Adafruit Feather RP2350 (product 6130), with HSTX
video and DualSense controller input forwarded over UART by an ESP32.

The core implements the complete conventional CHIP-8 instruction set,
including arithmetic, calls, memory transfers, timers, keypad instructions,
and sprite drawing/collision. It does not implement Super-CHIP or XO-CHIP.
Legacy 0nnn machine-code calls are ignored. Compatibility choices, memory
layout, reset requirements, and the pin protocol are described in
[docs/architecture.md](docs/architecture.md).

## Files

- `src/chip8_core.v`: processor and independent 60 Hz timers.
- `src/project.v`: Tiny Tapeout wrapper and read/write handshake bus.
- `test/test.py`: pin-level cocotb tests and instruction-level oracle.
- `test/tb_chip8_core.v`: minimal standalone core smoke test.
- `controller-mapping.md`: provisional DualSense mapping.
- `info.yaml`: provisional 2x2 IHP allocation and 1 MHz clock target.

## Simulation

With Icarus Verilog and make in a Linux environment:

```sh
python -m pip install -r test/requirements.txt
cd test
make
python -m cocotb_tools.check_results results.xml
```

Standalone core smoke test (PowerShell with Icarus installed):

```powershell
New-Item -ItemType Directory -Force build | Out-Null
iverilog -g2012 -s tb_chip8_core -o build/chip8_tb src/chip8_core.v test/tb_chip8_core.v
vvp build/chip8_tb
```

GitHub Actions runs RTL tests, builds the layout with LibreLane, runs the
same pin-level tests on the gate-level netlist, and runs Tiny Tapeout precheck.
The setup derives from the official IHP template using ttihp27a actions and
the ihp-sg13g2 PDK. The project is not a shuttle reservation.

## Hardware status

The ASIC side is implemented; companion firmware and final pin wiring are
not implemented yet. The Feather must supply RAM, font, framebuffer and
keypad registers over the documented bus. Clock frequency, bus throughput,
and pin allocation must be validated with real companion firmware before
manufacture. The prior three-instruction layout is not the full processor.
