"""Black-box tests of the synthesized pin interface, shared by RTL and gates."""
import random
from pathlib import Path
import cocotb
from cocotb.triggers import Timer, RisingEdge, with_timeout

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
    blob = (Path(__file__).parents[1]/'firmware/interpreter.bin').read_bytes()
    ram[0x1200:0x1200+len(blob)] = blob
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
                self.loop_pc = None
                return
            if op == (0x1000 | ((self.pc-2)&4095)):
                self.loop_pc = self.pc-2
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
    """The Verilog companion services pins; Python only loads and checks images.
    Keeping the memory server inside the testbench avoids a Python callback on
    every native clock, while testing the same external protocol on RTL/gates.
    """
    def __init__(self, dut, ram, key_profile=None):
        self.dut, self.ram = dut, bytearray(ram)
        self.key_profile = key_profile or {}
        self.writes=[]

    async def run(self, limit=30000000, watch_addr=None):
        d=self.dut
        d.rst_n.value=0
        await Timer(4000,unit='ns')
        for address,value in enumerate(self.ram): d.memory[address].value=value
        d.max_cycles.value=limit
        d.watch_enable.value=int(watch_addr is not None)
        d.watch_addr.value=watch_addr or 0
        for name in ('key_initial','key_later','key_switch_poll','timed_keys','key_on_cycle','key_off_cycle'):
            getattr(d,name).value=self.key_profile.get(name,0)
        d.rst_n.value=1
        await with_timeout(RisingEdge(d.finished), (limit+10)*1000, 'ns')
        await Timer(1,unit='ns')
        assert not int(d.error.value), 'Companion model reported protocol error or cycle limit'
        self.cycles=int(d.cycle_count.value)
        self.polls=int(d.poll_count.value)
        self.sound_seen=int(d.sound_start.value)!=0
        self.sound_start=int(d.sound_start.value)
        self.sound_stop=int(d.sound_stop.value)
        for address in range(8192): self.ram[address]=int(d.memory[address].value)
        self.writes=[(int(d.trace[i].value)>>8,int(d.trace[i].value)&255)
                     for i in range(int(d.write_count.value))]


async def compare(dut, ops, data=None):
    ram = image(ops, data)
    reference = Reference(ram)
    reference.run()
    companion = Companion(dut, ram)
    await companion.run()
    assert companion.writes == reference.writes, 'Memory write trace differs from instruction model'
    assert companion.ram[:0x1122] == reference.ram[:0x1122]
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
    c = Companion(dut, ram, {'key_initial':1<<10,'key_switch_poll':10})
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
    c = Companion(dut, ram, {'timed_keys':1,'key_initial':1,
                            'key_on_cycle':300000,'key_off_cycle':350000})
    await c.run(limit=2000000)
    assert c.sound_seen and not int(dut.uo_out.value)&16
    assert c.ram[0x900:0x903] == bytes([2,0,0])
    # Integer divider ticks every 16666 clocks; timer writes may occur at any phase.
    expected_stop = ((c.sound_start-1)//16666+2)*16666+1
    assert abs(c.sound_stop-expected_stop) <= 4, (c.sound_start,c.sound_stop,expected_stop)


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


@cocotb.test()
async def nested_stack_and_address_boundaries(dut):
    ops = [0x2300, 0xa900, 0xff55, 0xffff]
    ops += [0]*((0x300-0x200)//2-len(ops))
    for level in range(15):
        ops += [0x7301, 0x2000|(0x300+(level+1)*6), 0x00ee]
    ops += [0x7301, 0x00ee]
    c = await compare(dut, ops)
    assert c.ram[0x903] == 16
    # Fetch through the end of RAM and wrap PC to zero; load/store wrap too.
    await compare(dut, [0x1ffe], {
        0xffe: bytes.fromhex('60 07'),
        0x000: bytes.fromhex('13 00'),
        0x300: bytes.fromhex('a9 00 f0 55 ff ff')})
    await compare(dut, [0xafff, 0xf165, 0xa900, 0xf155, 0xffff],
                  {0xfff: bytes([0x72]), 0: bytes([0x36])})
    await compare(dut, [0x6072, 0x6136, 0xafff, 0xf155, 0xffff])


@cocotb.test()
async def independent_test_rom_screens(dut):
    fixtures = Path(__file__).parent/'roms'
    for name in ('1-chip8-logo.ch8','2-ibm-logo.ch8','3-corax.ch8','4-flags.ch8'):
        initial = image([], {0x200: (fixtures/name).read_bytes()})
        reference = Reference(initial)
        reference.run(limit=20000)
        expected = (fixtures/(name+'.frame')).read_bytes()
        assert reference.ram[0x1000:0x1100] == expected, name+' reference screen mismatch'
        assert reference.loop_pc is not None
        companion = Companion(dut, initial)
        await companion.run(watch_addr=reference.loop_pc)
        assert not int(dut.uo_out.value)&32, name+' unexpectedly halted' 
        assert companion.ram[0x1000:0x1100] == expected, name+' hardware screen mismatch'
        assert companion.writes == reference.writes, name+' write trace mismatch'
        Path('output').mkdir(exist_ok=True)
        Path('output', name+'.frame').write_bytes(companion.ram[0x1000:0x1100])
        dut._log.info('%s matches all 2048 reference pixels in %d clocks', name, companion.cycles)
