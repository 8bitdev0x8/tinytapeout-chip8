# Live RTL ROM debugger

The browser frontend uses the actual src/project.v and src/chip8_core.v,
compiled by Icarus Verilog. JavaScript does not emulate CHIP-8. The Verilog
companion supplies the same memory map as the future Feather firmware.

## Start

On this Windows workspace, the portable runtime is in build/iverilog/ucrt64.
It is automatically selected without changing the machine PATH:

```powershell
python sim/server.py
```

Open http://127.0.0.1:8765 in a browser. The server binds only to loopback.
On Linux/macOS install Icarus Verilog (iverilog and vvp) on PATH, then run the
same command. No Python packages are required by the server.

For a fresh Windows setup, `python sim/setup_iverilog.py` downloads official
MSYS2 UCRT64 packages, verifies their repository SHA-256 checksums and extracts
only into build/iverilog. This helper currently requires the existing MSYS2
zstd executable at C:/msys64/usr/bin/zstd.exe to unpack the packages.
Downloaded GPL runtime binaries and licenses remain under ignored build/;
they are not included in the Git repository.

## Controls

- Load an included test ROM or a local classic CHIP-8 ROM (1-3584 bytes).
- Run advances RTL clock batches. Pause stops after the current batch; no
  simulation time elapses while paused.
- Step clock advances exactly one full 1 MHz clock period.
- Step CHIP-8 advances to the next interpreter fetch boundary. Its first use
  completes boot. A 250,000-clock cap lets a key-wait instruction yield control.
- Hold the on-screen keypad or use 1234/QWER/ASDF/ZXCV. Key changes are supplied
  to the memory server on the next step/batch. Release a held key to finish Fx0A.
- Waveforms show up to 128 recent clocks, sampled 1 ns after each clock edge.
  Hover to inspect values; zoom to 16/32/64/128 clocks. A gap between batches
  replaces the displayed window rather than inventing intermediate values.
- Capture 128 clocks enables Icarus's real event-level VCD dump for that window.
  Download VCD includes all internal DUT signals and exact RTL event timestamps,
  including any initial/reset events and earlier captures in the same session.
  Normal running does not dump a huge event trace. Reset starts a new VCD file.

CHIP-8 PC and V registers come from real companion RAM; they may be partially
updated during interpreter execution. Native PC, IR, A, P and state come from
actual RTL registers. Memory transactions are recorded at valid/ready clock
edges. The display comes directly from the simulated 256-byte framebuffer.

This is digital RTL simulation, with modeled Feather response waits. It is
not an analog transistor simulator or a live view of a manufactured chip.
Wall-clock speed depends on the host; the design clock remains 1 MHz.

## Verify

```powershell
python sim/check_live.py
```

The live runner must render all four independent test ROMs exactly like their
reference screens, step clocks accurately, drive keys, and generate a real VCD.
