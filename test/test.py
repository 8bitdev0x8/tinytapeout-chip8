"""Black-box tests of the synthesized pin interface, shared by RTL and gates."""
import random
import cocotb
from cocotb.triggers import Timer

FONT = bytes.fromhex(
    "f0909090f0 2060202070 f010f080f0 f010f010f0 9090f01010 "
    "f080f010f0 f080f090f0 f010204040 f090f090f0 f090f010f0 "
    "f090f09090 e090e090e0 f0808080f0 e0909090e0 f080f080f0 f080f08080")


def image(ops, data=None):
    ram = bytearray(8192)
    ram[0x50:0xa0] = FONT
    for i, op in enumerate(ops):
        ram[0x200 + 2*i:0x202 + 2*i] = op.to_bytes(2, 'big')
    for address, values in (data or {}).items():
        ram[address:address+len(values)] = values
    return ram


class Reference:
    """Instruction-level oracle; no implementation of the RTL state machine."""
    def __init__(self, ram):
        self.ram = bytearray(ram)
        self.v = [0]*16
        self.i = 0
        self.pc = 0x200
        self.stack = []
        self.writes = []
        self.rng = 0xace1

    def write(self, address, value):
        self.ram[address] = value
        self.writes.append((address, value))

    def run(self, limit=2000):
        for _ in range(limit):
            op = self.ram[self.pc]*256 + self.ram[(self.pc+1)&4095]
            self.pc = (self.pc+2)&4095
            n, x, y, k = op>>12, (op>>8)&15, (op>>4)&15, op&15
            kk, addr = op&255, op&4095
            a, b = self.v[x], self.v[y]
            if op == 0xffff:
                return
            if op == 0xe0:
                for z in range(256): self.write(0x1000+z, 0)
            elif op == 0xee:
                self.pc = self.stack.pop()
            elif n == 0: pass
            elif n == 1: self.pc = addr
            elif n == 2:
                slot = 0x1100+2*len(self.stack)
                self.write(slot, self.pc>>8)
                self.write(slot+1, self.pc&255)
                self.stack.append(self.pc)
                self.pc = addr
            elif n == 3: self.pc += 2*(a == kk)
            elif n == 4: self.pc += 2*(a != kk)
            elif n == 5: self.pc += 2*(a == b)
            elif n == 6: self.v[x] = kk
            elif n == 7: self.v[x] = (a+kk)&255
            elif n == 8:
                flag = None
                if k == 0: result = b
                elif k == 1: result = a|b
                elif k == 2: result = a&b
                elif k == 3: result = a^b
                elif k == 4: result, flag = a+b, int(a+b > 255)
                elif k == 5: result, flag = a-b, int(a >= b)
                elif k == 6: result, flag = a>>1, a&1
                elif k == 7: result, flag = b-a, int(b >= a)
                elif k == 14: result, flag = a<<1, a>>7
                else: raise AssertionError(hex(op))
                self.v[x] = result&255
                if flag is not None: self.v[15] = flag
            elif n == 9: self.pc += 2*(a != b)
            elif n == 10: self.i = addr
            elif n == 11: self.pc = (addr+self.v[0])&4095
            elif n == 12:
                self.v[x] = (self.rng&255)&kk
                feedback = ((self.rng>>15)^(self.rng>>13)^(self.rng>>12)^(self.rng>>10))&1
                self.rng = ((self.rng<<1)|feedback)&65535
            elif n == 13:
                px, py = a%64, b%32
                collision = 0
                for row in range(k):
                    sprite = self.ram[(self.i+row)&4095]
                    for col in range(8):
                        if py+row >= 32 or px+col >= 64 or not sprite & (128>>col):
                            continue
                        dst = 0x1000+(py+row)*8+(px+col)//8
                        mask = 128>>((px+col)%8)
                        collision |= bool(self.ram[dst]&mask)
                        self.write(dst, self.ram[dst]^mask)
                self.v[15] = int(collision)
            elif n == 15:
                if kk == 0x1e: self.i = (self.i+a)&4095
                elif kk == 0x29: self.i = 0x50+(a&15)*5
                elif kk == 0x33:
                    for z, digit in enumerate((a//100, (a//10)%10, a%10)):
                        self.write((self.i+z)&4095, digit)
                elif kk == 0x55:
                    for z in range(x+1): self.write((self.i+z)&4095, self.v[z])
                elif kk == 0x65:
                    self.v[:x+1] = [self.ram[(self.i+z)&4095] for z in range(x+1)]
                else: raise AssertionError(hex(op))
            else: raise AssertionError(hex(op))
        raise AssertionError('Reference did not halt')


class Companion:
    def __init__(self, dut, ram, key_source=None):
        self.dut, self.ram = dut, bytearray(ram)
        self.key_source = key_source or (lambda cycle, polls: 0)
        self.cycles = 0
        self.polls = 0
        self.key_snapshot = 0
        self.writes = []
        self.ack = False
        self.parts = []
        self.stable = None
        self.sound_seen = False
        self.delay = 0

    async def cycle(self):
        d = self.dut
        d.clk.value = 0
        await Timer(100, unit='ns')
        status, output = int(d.uio_out.value), int(d.uo_out.value)
        assert int(d.uio_oe.value) == 0x3f
        request, phase, write = bool(status&4), status&3, bool(status&8)
        self.sound_seen |= bool(status&16)
        if request and self.stable is not None:
            assert (phase, write, output) == self.stable, 'Bus changed before acknowledge'
        if not request:
            self.ack = False
            self.stable = None
            self.delay = 0
        elif not self.ack:
            self.stable = (phase, write, output)
            self.delay += 1
            # Deliberate varying delays before acknowledgement.
            if self.delay >= 1+(self.cycles%4):
                if phase == 0:
                    assert not self.parts
                    self.parts = [output]
                elif phase == 1:
                    assert len(self.parts) == 1
                    self.parts.append(output)
                else:
                    assert phase == 2 and len(self.parts) == 2
                    address = self.parts[0] | (self.parts[1]<<8)
                    self.parts = []
                    if write:
                        assert address < 0x1120, 'Write to read-only keypad'
                        self.ram[address] = output
                        self.writes.append((address, output))
                    else:
                        if address == 0x1120:
                            self.polls += 1
                            self.key_snapshot = self.key_source(self.cycles, self.polls)
                            value = self.key_snapshot&255
                        elif address == 0x1121:
                            value = self.key_snapshot>>8
                        else: value = self.ram[address]
                        d.ui_in.value = value
                self.ack = True
        d.uio_in.value = 0x40 if self.ack else 0
        await Timer(400, unit='ns')
        d.clk.value = 1
        await Timer(500, unit='ns')
        self.cycles += 1
        return bool(int(d.uio_out.value)&32)

    async def reset(self):
        d = self.dut
        d.clk.value = 0
        d.ena.value = 1
        d.rst_n.value = 0
        d.ui_in.value = 0
        d.uio_in.value = 0
        for _ in range(4):
            d.clk.value = 0
            await Timer(500, unit='ns')
            d.clk.value = 1
            await Timer(500, unit='ns')
        d.rst_n.value = 1

    async def run(self, limit=100000):
        await self.reset()
        for _ in range(limit):
            if await self.cycle(): return
        raise AssertionError(f'Core did not halt after {limit} cycles')


async def compare(dut, ops, data=None):
    ram = image(ops, data)
    reference = Reference(ram)
    reference.run()
    companion = Companion(dut, ram)
    await companion.run()
    assert companion.writes == reference.writes, 'Memory write trace differs from instruction model'
    assert companion.ram == reference.ram
    return companion


@cocotb.test()
async def arithmetic_and_flags(dut):
    rng = random.Random(0xc8)
    # Include equal operands, overflow, borrow and VF as either destination or source.
    for batch in range(6):
        ops = []
        for trial in range(16):
            k = [0,1,2,3,4,5,6,7,14][(trial+batch)%9]
            x, y = [(0,1),(0,15),(15,1),(15,15)][trial%4]
            a, b = rng.randrange(256), rng.randrange(256)
            if trial < 4: a, b = [(0,0),(255,1),(1,255),(128,128)][trial]
            ops += [0x6f03, 0x6000|(x<<8)|a, 0x6000|(y<<8)|b,
                    0x8000|(x<<8)|(y<<4)|k,
                    0xa800+16*trial, 0xff55]
        ops += [0xffff]
        await compare(dut, ops)


@cocotb.test()
async def control_memory_bcd_random(dut):
    ops = [0x0123, 0x6001, 0x7002, 0x3003, 0x60ee,
           0x4004, 0x60ee, 0x6103, 0x5010, 0x60ee,
           0x6204, 0x9020, 0x60ee,
           0x2240, 0x6002, 0xb242]
    # Address 0x240 subroutine; B242+V0 lands at 0x244.
    ops += [0x0000]*((0x240-0x200)//2-len(ops))
    ops += [0x7301, 0x00ee,
            0xa800, 0xff55, 0x60ff, 0x6100, 0x6200, 0xff65,
            0xa900, 0xff55,
            0x60e7, 0xa920, 0xf033,
            0x600a, 0xf029, 0xf465, 0xa930, 0xf455,
            0x6003, 0xafff, 0xf01e, 0x6109, 0xf155,
            0xc2ff, 0xc30f, 0xa940, 0xf355, 0xffff]
    await compare(dut, ops)
    # BCD boundary values and memory wrapping without overwriting code.
    for value in (0, 9, 10, 99, 100, 199, 255):
        await compare(dut, [0x6000|value, 0xafff, 0xf033, 0xffff])


@cocotb.test()
async def sprites_clear_collision_clipping(dut):
    await compare(dut, [
        0x00e0, 0x6005, 0x6103, 0xa700, 0xd013,
        0xa800, 0xff55, 0xa700, 0xd013, 0xa810, 0xff55,
        0x603f, 0x611f, 0xa700, 0xd013, 0xa820, 0xff55,
        0x607f, 0x613f, 0xa700, 0xd013, 0xa830, 0xff55,
        0x6f05, 0x6100, 0xa700, 0xdf11, 0xa840, 0xff55,
        0xd010, 0xa850, 0xff55, 0xffff], {0x700: bytes.fromhex('ff81ff')})


@cocotb.test()
async def keypad_skip_and_wait_release(dut):
    ram = image([0x600a, 0xe09e, 0x61ee, 0xe0a1, 0x6207,
                 0xf30a, 0xa900, 0xf355, 0xffff])
    c = Companion(dut, ram, lambda cycle, polls: (1<<10) if polls < 10 else 0)
    await c.run()
    assert c.ram[0x900:0x904] == bytes([10,0,7,10])
    assert c.polls >= 10
    # No key pressed, then an out-of-range Vx: skip on not-pressed only.
    ram = image([0x6001, 0xe09e, 0x6107, 0xe0a1, 0x61ee,
                 0x6020, 0xe09e, 0x6208, 0xe0a1, 0x62ee,
                 0xa900, 0xf255, 0xffff])
    c = Companion(dut, ram)
    await c.run()
    assert c.ram[0x900:0x903] == bytes([32,7,8])


@cocotb.test()
async def timers_run_during_key_wait(dut):
    # Timers must keep running while execution is waiting on external input.
    ram = image([0x6002, 0xf015, 0xf018, 0xf10a, 0xf207,
                 0xa900, 0xf255, 0xffff])
    def key_source(cycle, polls):
        return 1 if 51000 <= cycle < 53000 else 0
    c = Companion(dut, ram, key_source)
    await c.run(limit=60000)
    assert c.sound_seen and not int(dut.uio_out.value)&16
    assert c.ram[0x900:0x903] == bytes([2,0,0])


@cocotb.test()
async def stack_faults_and_invalid_opcodes(dut):
    # Exactly 16 nested calls are allowed; a seventeenth traps before writing.
    ram = image([0x2200])
    c = Companion(dut, ram)
    await c.run()
    assert len(c.writes) == 32
    assert all(0x1100 <= address < 0x1120 for address, _ in c.writes)
    for op in (0x00ee, 0x5121, 0x9121, 0x8128, 0xe000, 0xf000):
        c = Companion(dut, image([op]))
        await c.run()
        assert not c.writes
    # Halt and an outstanding bus request can both be recovered by reset.
    c = Companion(dut, image([0x6007, 0xa900, 0xf055, 0xffff]))
    await c.run()
    assert c.ram[0x900] == 7
