# Native-ROM regression; run from the repository root. No third-party dependencies.
import ast,random,sys
from pathlib import Path
sys.path.insert(0,'firmware')
from build_interpreter import build
from emulate import Engine
blob,labels=build()
def execute(coro):
    try: coro.send(None)
    except StopIteration as result: return result.value
    raise AssertionError('unexpected suspension')
source=ast.parse(Path('test/test.py').read_text()); ns={'random':random,'Path':Path,'__file__':str(Path('test/test.py').resolve())}
nodes=[n for n in source.body if (isinstance(n,ast.ClassDef) and n.name=='Reference') or (isinstance(n,ast.FunctionDef) and n.name=='image') or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FONT' for t in n.targets))]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'tests','exec'),ns)
async def compare(dut,ops,data=None):
    ram=ns['image'](ops,data);ram[0x1200:0x1200+len(blob)]=blob
    ref=ns['Reference'](ram);ref.run(limit=20000)
    cpu=Engine(ram);visits=0
    for _ in range(3000000):
        if cpu.pc==labels['fetch'] and ref.loop_pc is not None and cpu.ram[0x1152]+256*cpu.ram[0x1153]==ref.loop_pc:
            visits+=1
            if visits==2:break
        if cpu.halted:break
        cpu.step()
    else:raise AssertionError('Native timeout')
    if [(a,v) for a,v in cpu.writes if not 0x1000<=a<0x1100]!=[(a,v) for a,v in ref.writes if not 0x1000<=a<0x1100]:
        for i,(a,b) in enumerate(zip(cpu.writes,ref.writes)):
            if a!=b:raise AssertionError(f'Write {i}: {a} vs {b}; native PC={cpu.pc:x}')
        raise AssertionError(f'Write count {len(cpu.writes)} vs {len(ref.writes)}; PC {cpu.pc:x}')
    assert cpu.ram[:0x1122]==ref.ram[:0x1122]
    return cpu
ns['compare']=compare
for node in source.body:
    if isinstance(node,ast.AsyncFunctionDef) and node.name in ('arithmetic_and_flags','control_memory_bcd_random','sprites_clear_collision_clipping','nested_stack_and_address_boundaries'):
        node.decorator_list=[]
        exec(compile(ast.Module(body=[node],type_ignores=[]),'tests','exec'),ns)
        execute(ns[node.name](None));print(node.name,'PASS',flush=True)
for name in ('1-chip8-logo.ch8','2-ibm-logo.ch8','3-corax.ch8','4-flags.ch8'):
    cpu=execute(compare(None,[],{0x200:Path('test/roms',name).read_bytes()}))
    assert cpu.ram[0x1000:0x1100]==Path('test/roms',name+'.frame').read_bytes()
    print(name,'PASS',cpu.steps,'native instructions',flush=True)
