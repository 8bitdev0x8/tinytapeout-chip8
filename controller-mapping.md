# Default CHIP-8 controller mapping

The Feather translates logical DualSense buttons into a 16-bit CHIP-8 key
mask. Bit N represents CHIP-8 key N. Multiple keys may be held together.
These assignments are provisional and can be changed per game.

| DualSense control | CHIP-8 key |
| --- | --- |
| D-pad Up | 2 |
| D-pad Left | 4 |
| D-pad Down | 8 |
| D-pad Right | 6 |
| Cross | 5 |
| Circle | A |
| Square | 7 |
| Triangle | 9 |
| L1 | 1 |
| R1 | 3 |
| L2 (digital button) | C |
| R2 (digital button) | D |
| Create | E |
| Options | F |
| L3 | 0 |
| R3 | B |

Diagonal D-pad input holds both corresponding directional keys.
PS, touchpad click, microphone button, analog sticks, and analog trigger
values are unassigned initially.

## Input transport

- ESP32 GPIO25 TX to Feather RX, with common ground.
- UART: 230400 baud, 8N1.
- Use the supplied PadWire version 1 parser with COBS and CRC validation.
- Accept controller state only from valid online frames.
- Clear all keys immediately on a valid offline frame.
- Clear all keys if no valid frame arrives for 100 ms.
- Invalid frames do not refresh the receive timeout.

The mapping is defined in terms of logical controls. Raw report bit offsets
must be checked against the esp-ps5 report layout when implementing the
Feather decoder.
