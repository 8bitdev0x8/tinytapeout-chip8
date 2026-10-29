"""Exercise only physical ports, so the same test works on RTL and gates."""
import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def program_with_memory_stalls(dut):
    dut.clk.value = 0
    dut.rst_n.value = 0
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0

    async def edge():
        dut.clk.value = 0
        await Timer(500, unit="ns")
        dut.clk.value = 1
        await Timer(500, unit="ns")

    for _ in range(3):
        await edge()
    dut.rst_n.value = 1
    memory = dict(enumerate(bytes.fromhex("60 ff 70 02 70 02 12 06"), 0x200))
    previous_stall = None
    transfers = 0
    loop_fetches = 0
    saw_result = False
    for cycle in range(160):
        dut.clk.value = 0
        await Timer(100, unit="ns")
        assert int(dut.uio_oe.value) == 0x7f
        control = int(dut.uio_out.value)
        assert not control & 0x40, "Unexpected halt"
        valid = bool(control & 0x20)
        address = ((control & 0x1f) << 8) | int(dut.uo_out.value)
        if previous_stall is not None:
            assert valid and address == previous_stall, "Request changed while stalled"
        ready = valid and cycle % 5 == 0
        previous_stall = address if valid and not ready else None
        dut.ui_in.value = memory.get(address, 0)
        dut.uio_in.value = 0x80 if ready else 0
        if ready:
            transfers += 1
            loop_fetches += address == 0x206
        if not valid and int(dut.uo_out.value) == 3:
            saw_result = True
        await Timer(400, unit="ns")
        dut.clk.value = 1
        await Timer(500, unit="ns")
    assert transfers >= 12 and loop_fetches >= 2 and saw_result

    # Force an unsupported opcode into the loop and verify halt through pins.
    for cycle in range(30):
        dut.clk.value = 0
        await Timer(100, unit="ns")
        valid = bool(int(dut.uio_out.value) & 0x20)
        dut.ui_in.value = 0
        dut.uio_in.value = 0x80 if valid else 0
        await Timer(400, unit="ns")
        dut.clk.value = 1
        await Timer(500, unit="ns")
    assert int(dut.uio_out.value) & 0x40
    assert not int(dut.uio_out.value) & 0x20
    dut.rst_n.value = 0
    dut.uio_in.value = 0
    for _ in range(3):
        await edge()
    assert not int(dut.uio_out.value) & 0x60
    assert int(dut.uo_out.value) == 0
