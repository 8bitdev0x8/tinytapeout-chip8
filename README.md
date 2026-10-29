# One-tile Tiny Tapeout CHIP-8

A compact accumulator processor executes a CHIP-8 interpreter on the ASIC,
using an Adafruit Feather RP2350 as its external ROM/RAM and I/O companion.
The hard area budget is one IHP tile. See [architecture](docs/architecture.md)
for the execution model, compatibility profile, memory map and bus protocol.

The game retains 4 KB of CHIP-8 memory and a 64x32 display. The 1,824-byte
interpreter and 45 bytes of live working state occupy additional companion
memory. V registers are external; arithmetic/drawing/decoding execute on chip.
The interpreter ROM must be loaded at 0x1200 before releasing reset.

## Build and simulation

```sh
python firmware/build_interpreter.py
python -m pip install -r test/requirements.txt
cd test
make
python -m cocotb_tools.check_results results.xml
```

The same physical-port tests run on RTL and the generated gate-level netlist.
A Verilog companion model makes long interpreter simulations efficient.
A standalone native-engine smoke test is also included. GitHub Actions builds
IHP SG13G2 layout, runs gate-level tests, precheck and publishes a layout viewer.

## Files

- src/chip8_core.v: native accumulator engine, shared adder and timers.
- src/project.v: Tiny Tapeout wrapper and bidirectional handshake bus.
- firmware/build_interpreter.py: auditable CHIP-8 interpreter assembler source.
- firmware/interpreter.bin: required ROM image, generated deterministically.
- firmware/emulate.py: native instruction model for ROM development.
- test/test.py: CHIP-8 reference model and physical-interface checks.
- test/roms: independent reference ROMs/screens, separately licensed.
- controller-mapping.md: provisional DualSense mapping.

The earlier direct CHIP-8 decoder remains in Git history at 82f1b8e.
No chip has been ordered. Feather RAM-server/video/controller firmware and
actual wiring remain to be implemented and checked. One-tile fit and speed
are experimental until verified by the current build and hardware testing.
