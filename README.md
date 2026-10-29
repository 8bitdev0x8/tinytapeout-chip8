# Tiny Tapeout CHIP-8

CHIP-8 processor RTL with an Adafruit Feather RP2350 (product 6130)
as memory and I/O companion. The Feather receives controller packets from
an ESP32 over UART at 230400 baud and outputs video using its HSTX adapter.
See [controller-mapping.md](controller-mapping.md) for provisional keys.

## Current milestone

`src/chip8_core.v` implements reset, instruction fetching, `1nnn` (jump),
`6xkk` (load), and `7xkk` (add immediate, wrapping without changing VF).
Other opcodes halt until reset. This is an initial core, not a complete
CHIP-8 implementation or a submission-ready Tiny Tapeout project.

The core uses a synchronous active-low reset. Memory requests remain valid
and stable until a rising clock edge with `mem_valid && mem_ready`.
The responder supplies `mem_rdata` for that edge. Responses must not arrive
after a request has completed. Consecutive fetches can keep valid asserted;
each valid/ready edge is a distinct byte transfer. Addressing wraps at 4 KB.

The 13-bit memory interface reserves space beyond the CHIP-8 address range
for a future framebuffer and call stack. Current instructions only read
addresses 0x0000–0x0FFF. Debug outputs are for simulation; they are not a
Tiny Tapeout physical pin assignment.

## Simulation

With Icarus Verilog installed, run from this directory in PowerShell:

```powershell
New-Item -ItemType Directory -Force build | Out-Null
iverilog -g2012 -s tb_chip8_core -o build/chip8_tb src/chip8_core.v test/tb_chip8_core.v
vvp build/chip8_tb
```

The testbench exercises delayed memory responses, loads, addition overflow,
jumps, unsupported-instruction halt, and reset recovery.

## Next steps

1. Implement remaining arithmetic, branches, and stack operations.
2. Add memory transfers, timers, keypad state, and drawing.
3. Verify compatibility quirks and run CHIP-8 test ROMs.
4. Implement and test the Feather transport and UART controller decoder.
5. Measure area using the provisional IHP template, then select a final shuttle.

The final physical transport, GPIO allocation, clock frequency, tile count,
and display firmware are not yet selected. The transport must account for the
Feather servicing video and controller input while memory requests wait.

## Tiny Tapeout build setup

The project now includes configuration and workflows adapted from the
[official IHP Verilog template](https://github.com/TinyTapeout/ttihp-verilog-template).
The downloaded template uses the `ttihp27a` action series; this project sets
the PDK to `ihp-sg13g2`. This is a provisional build target, not a shuttle
reservation. The 1x1 tile and 1 MHz values are experimental starting settings,
not verified capacity or timing results. Author `jojys` is provisional.

- `info.yaml`: sources, top module, pins, and provisional build settings.
- `src/project.v`: standard Tiny Tapeout wrapper, exposing a read-only memory
  interface for the current instruction subset. V0 appears on the output
  byte when no request is active. See `docs/info.md` for protocol details.
- `.github/workflows/test.yaml`: standalone core test and cocotb pin-level test.
- `.github/workflows/gds.yaml`: layout, precheck, gate-level test, and viewer.
- `.github/workflows/docs.yaml`: project documentation build.

To run the cocotb RTL test in a Linux environment with Icarus and make:

```sh
python -m pip install -r test/requirements.txt
cd test
make
python -m cocotb_tools.check_results results.xml
```

To run in GitHub Actions, upload this project to a GitHub repository, enable
Actions, and configure Settings > Pages > Source as GitHub Actions for the
layout viewer. No repository has been created or pushed by this setup.
The files are prepared locally; no GitHub workflow or physical-layout build
has run yet. The final pin bus will need writes and keypad/peripheral access;
the present wrapper supports only read-only bring-up.
