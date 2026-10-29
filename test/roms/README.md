# Independent CHIP-8 test ROMs

From https://github.com/Timendus/chip8-test-suite
Commit: 742e9eac9f5d44466c1c9d83fcaa8158c6683cb1
Author: Timendus and contributors. Licensed GPL-3.0; see LICENSE.
The ROMs and reference screenshots are test assets only, not synthesized
into the ASIC. File 3-corax.ch8 corresponds to upstream 3-corax+.ch8.

The .frame files are 256-byte monochrome framebuffers sampled from the
upstream reference screenshots (center of each 12x12 display pixel; bright
pixels on). They provide independent expected results for both the Python
model and the RTL/gate-level implementation. Screenshots are preserved for
auditing the conversion.
