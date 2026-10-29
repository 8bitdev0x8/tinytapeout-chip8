"""End-to-end checks of the real RTL runner and bounded waveform capture."""
from pathlib import Path
import re
from server import Simulator,ROM_DIR,WORK

def main():
    sim=Simulator()
    try:
        cases=[('1-chip8-logo.ch8',1100000),('2-ibm-logo.ch8',650000),
               ('3-corax.ch8',2500000),('4-flags.ch8',5100000)]
        for name,clocks in cases:
            start=sim.load((ROM_DIR/name).read_bytes(),name)
            assert start['cycles']==0 and start['native_pc']==0x1200
            remaining=clocks
            while remaining:
                batch=min(remaining,1000000)
                result=sim.step(batch);remaining-=batch
            assert result['cycles']==clocks and not result['halted']
            assert bytes.fromhex(result['frame'])==(ROM_DIR/(name+'.frame')).read_bytes(),name
            assert len(result['wave'])==256
            assert all(len(row)==24 for row in result['wave'])
            assert all(b[0]-a[0]==500 for a,b in zip(result['wave'],result['wave'][1:]))
            assert result['transactions'] and all(0<=tx[2]<8192 for tx in result['transactions'])
            print(name,'PASS',result['cycles'],'clocks',flush=True)
        before=result['cycles'];result=sim.step(1)
        assert result['cycles']==before+1
        result=sim.step(128,keys=0x0401,kind='CAPTURE')
        assert result['wave'][-1][-1]==0x0401
        text=(WORK/'capture.vcd').read_text()
        assert '$enddefinitions' in text and 'mem_valid' in text and re.search(r'^#[0-9]+$',text,re.M)
        before=result['cycles'];result=sim.step(250000,kind='INST')
        assert before<result['cycles']<before+250000
        print('Clock step, instruction boundary, key bitmap and event-level VCD: PASS',flush=True)
    finally:sim.close()
if __name__=='__main__':main()
