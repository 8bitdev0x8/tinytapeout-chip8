"""Assemble the CHIP-8 interpreter for the one-tile accumulator engine.
The returned image is ROM data served by the companion, never executed by it.
"""
from pathlib import Path
import json

V=0x1140
IL,IH,PL,PH,SP,OH,OL,X,Y,VX,VY,R,FLAG,CTR,AL,AH=range(0x1150,0x1160)
T,U,DX,DY,ROW,COL,SPR,COLL,KL,KH,HELD,MASK,BYTE=range(0x1160,0x116d)

class Assembler:
    def __init__(self): self.words=[]; self.labels={}; self.fixups=[]; self.serial=0
    @property
    def pc(self): return 0x1200+2*len(self.words)
    def emit(self, word): self.words.append(word)
    def label(self,name):
        assert name not in self.labels,name
        self.labels[name]=self.pc
    def fresh(self): self.serial+=1; return 'local_'+str(self.serial)
    def branch(self,op,label): self.fixups.append((len(self.words),op,label));self.emit(0)
    def jmp(self,label):self.branch(8,label)
    def jz(self,label):self.branch(9,label)
    def jnz(self,label):self.branch(10,label)
    def jc(self,label):self.branch(11,label)
    def jmpa(self,label):self.fixups.append((len(self.words),0,label));self.emit(0x0800)
    def imm(self,sub,value=0): self.emit((sub<<8)|(value&255))
    def ldi(self,x):self.imm(0,x)
    def addi(self,x):self.imm(1,x)
    def andi(self,x):self.imm(2,x)
    def subi(self,x):self.imm(5,x)
    def shl(self):self.imm(11)
    def shr(self):self.imm(12)
    def setp(self,addr):self.emit(((14 if addr&0x1000 else 13)<<12)|(addr&4095))
    def ld(self,addr):
        assert addr>>8==0x11
        self.emit(0xf000|(addr&255))
    def st(self,addr):
        assert addr>>8==0x11
        self.emit(0xc000|(addr&255))
    def read(self):self.emit(0x1000)
    def write(self):self.emit(0x2000)
    def plo(self):self.imm(6)
    def phi(self):self.imm(7)
    def incp(self):self.imm(10)
    def ptr(self,lo,hi):self.ld(lo);self.plo();self.ld(hi);self.phi()
    def memop(self,op,addr):self.setp(addr);self.emit(op<<12)
    def constant(self,addr,value):self.ldi(value);self.st(addr)
    def copy(self,src,dst):self.ld(src);self.st(dst)
    def regptr(self,index):
        self.ld(index);self.addi(0x40);self.plo();self.ldi(0x11);self.phi()
    def getv(self,index,dest):self.regptr(index);self.read();self.st(dest)
    def putv(self,index,src):self.regptr(index);self.ld(src);self.write()
    def getxy(self):
        self.getv(X,VX)
        self.ld(OL)
        for _ in range(4):self.shr()
        self.st(Y);self.getv(Y,VY)
    def inc16(self,lo,hi,amount=1):
        done=self.fresh()
        self.ld(lo);self.addi(amount);self.st(lo)
        self.jc(done+'_carry');self.jmp(done)
        self.label(done+'_carry');self.ld(hi);self.addi(1);self.andi(15);self.st(hi)
        self.label(done)
    def incp12(self):self.incp();self.emit(0xf100);self.andi(15);self.phi()
    def flag_result(self):
        one,end=self.fresh(),self.fresh()
        self.st(R);self.jc(one);self.ldi(0);self.jmp(end)
        self.label(one);self.ldi(1);self.label(end);self.st(FLAG)
        self.putv(X,R);self.setp(V+15);self.ld(FLAG);self.write();self.jmp('fetch')
    def result(self):self.st(R);self.putv(X,R);self.jmp('fetch')
    def finish(self):
        for i,op,label in self.fixups:
            target=self.labels[label]&4095
            self.words[i]=(op<<12)|target if op else 0x0800|(target>>8)
        blob=b''.join(x.to_bytes(2,'big') for x in self.words)
        assert len(blob)<=0xe00, f'Interpreter ROM exceeds 3584 bytes: {len(blob)}'
        return blob


def build():
    a=Assembler()
    a.label('boot');a.setp(V);a.ldi(0)
    for _ in range(16):a.write();a.incp()
    for dst in (IL,IH,PL,SP):a.st(dst)
    a.constant(PH,2)
    a.label('fetch')
    a.ptr(PL,PH);a.read();a.st(OH);a.incp12();a.read();a.st(OL);a.incp12()
    a.imm(9);a.st(PL);a.emit(0xf100);a.st(PH)
    a.ld(OH);a.andi(15);a.st(X)
    a.ld(OH);a.andi(0xf0)
    for _ in range(3):a.shr()
    a.jmpa('dispatch')

    a.label('op0');a.ld(OH);a.jnz('fetch')
    a.ld(OL);a.subi(0xe0);a.jz('clear')
    a.ld(OL);a.subi(0xee);a.jz('return');a.jmp('fetch')
    a.label('op1');a.copy(OL,PL);a.copy(X,PH);a.jmp('fetch')
    a.label('op2');a.ld(SP);a.subi(16);a.jc('halt')
    a.ld(SP);a.shl();a.plo();a.ldi(0x11);a.phi()
    a.ld(PH);a.write();a.incp();a.ld(PL);a.write()
    a.ld(SP);a.addi(1);a.st(SP);a.jmp('op1')
    a.label('return');a.ld(SP);a.jz('halt');a.subi(1);a.st(SP)
    a.shl();a.plo();a.ldi(0x11);a.phi();a.read();a.st(PH);a.incp();a.read();a.st(PL);a.jmp('fetch')
    for op in (3,4):
        a.label('op'+str(op));a.getv(X,VX);a.ld(VX);a.memop(4,OL)
        (a.jz if op==3 else a.jnz)('skip');a.jmp('fetch')
    for op in (5,9):
        a.label('op'+str(op));a.ld(OL);a.andi(15);a.jnz('halt')
        a.getxy();a.ld(VX);a.memop(4,VY)
        (a.jz if op==5 else a.jnz)('skip');a.jmp('fetch')
    a.label('skip');a.inc16(PL,PH,2);a.jmp('fetch')
    a.label('op6');a.copy(OL,R);a.putv(X,R);a.jmp('fetch')
    a.label('op7');a.getv(X,VX);a.ld(VX);a.memop(3,OL);a.result()
    a.label('op8');a.getxy();a.ld(OL);a.andi(15);a.st(CTR)
    for k in (0,1,2,3,4,5,6,7,14):
        a.ld(CTR);a.subi(k);a.jz('alu'+str(k))
    a.jmp('halt')
    a.label('alu0');a.ld(VY);a.result()
    for k,native in ((1,6),(2,5),(3,7),(4,3),(5,4)):
        a.label('alu'+str(k));a.ld(VX);a.memop(native,VY)
        a.flag_result() if k in (4,5) else a.result()
    a.label('alu6');a.ld(VX);a.shr();a.flag_result()
    a.label('alu7');a.ld(VY);a.memop(4,VX);a.flag_result()
    a.label('alu14');a.ld(VX);a.shl();a.flag_result()
    a.label('op10');a.copy(OL,IL);a.copy(X,IH);a.jmp('fetch')
    a.label('op11');a.setp(V);a.read();a.st(R)
    a.ld(OL);a.memop(3,R);a.st(PL);a.jc('jump_carry');a.copy(X,PH);a.jmp('fetch')
    a.label('jump_carry');a.ld(X);a.addi(1);a.andi(15);a.st(PH);a.jmp('fetch')
    a.label('op12');a.imm(13);a.memop(5,OL);a.result()

    a.label('clear');a.setp(0x1000);a.constant(CTR,0)
    a.label('clear_loop');a.ldi(0);a.write();a.incp()
    a.ld(CTR);a.addi(1);a.st(CTR);a.jnz('clear_loop');a.jmp('fetch')

    a.label('op13');a.getxy();a.ld(VX);a.andi(63);a.st(DX);a.ld(VY);a.andi(31);a.st(DY)
    a.constant(ROW,0);a.constant(COLL,0);a.ld(OL);a.andi(15);a.jz('draw_done')
    a.label('draw_row');a.ld(IL);a.memop(3,ROW);a.st(AL);a.jc('sprite_carry')
    a.copy(IH,AH);a.jmp('sprite_read')
    a.label('sprite_carry');a.ld(IH);a.addi(1);a.andi(15);a.st(AH)
    a.label('sprite_read');a.ptr(AL,AH);a.read();a.st(SPR);a.constant(COL,0)
    a.label('pixel');a.ld(DX);a.memop(3,COL);a.st(T);a.subi(64);a.jc('next_pixel')
    a.ld(DY);a.memop(3,ROW);a.st(U);a.subi(32);a.jc('next_pixel')
    a.ld(SPR);a.andi(128);a.jz('next_pixel')
    a.constant(MASK,128);a.ld(T);a.andi(7);a.st(BYTE)
    a.label('mask_loop');a.ld(BYTE);a.jz('mask_ready')
    a.subi(1);a.st(BYTE);a.ld(MASK);a.shr();a.st(MASK);a.jmp('mask_loop')
    a.label('mask_ready');a.ld(U)
    for _ in range(3):a.shl()
    a.st(AL);a.ld(T)
    for _ in range(3):a.shr()
    a.memop(6,AL);a.st(AL);a.constant(AH,0x10)
    a.ptr(AL,AH);a.read();a.st(BYTE);a.memop(5,MASK);a.jz('no_collision')
    a.constant(COLL,1)
    a.label('no_collision');a.ld(BYTE);a.memop(7,MASK);a.st(BYTE)
    a.ptr(AL,AH);a.ld(BYTE);a.write()
    a.label('next_pixel');a.ld(SPR);a.shl();a.st(SPR)
    a.ld(COL);a.addi(1);a.st(COL);a.subi(8);a.jnz('pixel')
    a.ld(ROW);a.addi(1);a.st(ROW);a.ld(OL);a.andi(15);a.memop(4,ROW)
    a.jz('draw_done');a.jmp('draw_row')
    a.label('draw_done');a.setp(V+15);a.ld(COLL);a.write();a.jmp('fetch')

    a.label('op14');a.getv(X,VX);a.ld(OL);a.subi(0x9e);a.jz('key_skip')
    a.ld(OL);a.subi(0xa1);a.jnz('halt')
    a.label('key_skip');a.ld(VX);a.subi(16);a.jc('key_absent')
    # Build the selected key mask, then read just the appropriate keypad byte.
    a.constant(MASK,1);a.ld(VX);a.andi(7);a.st(CTR)
    a.label('key_mask');a.ld(CTR);a.jz('key_mask_ready');a.subi(1);a.st(CTR)
    a.ld(MASK);a.shl();a.st(MASK);a.jmp('key_mask')
    a.label('key_mask_ready');a.ld(VX);a.subi(8);a.jc('key_upper')
    a.setp(0x1120);a.read();a.jmp('key_test')
    a.label('key_upper');a.setp(0x1120);a.read();a.incp();a.read()
    a.label('key_test');a.memop(5,MASK);a.jz('key_absent')
    a.ld(OL);a.subi(0x9e);a.jz('skip');a.jmp('fetch')
    a.label('key_absent');a.ld(OL);a.subi(0xa1);a.jz('skip');a.jmp('fetch')

    a.label('op15');a.getv(X,VX)
    for code,name in ((7,'timer_read'),(10,'key_wait'),(21,'delay_set'),(24,'sound_set'),
                      (30,'index_add'),(41,'font'),(51,'bcd'),(85,'save'),(101,'load')):
        a.ld(OL);a.subi(code);a.jz(name)
    a.jmp('halt')
    a.label('timer_read');a.imm(14,0);a.result()
    a.label('delay_set');a.ld(VX);a.imm(14,1);a.jmp('fetch')
    a.label('sound_set');a.ld(VX);a.imm(14,2);a.jmp('fetch')
    a.label('index_add');a.ld(IL);a.memop(3,VX);a.st(IL);a.jc('index_carry');a.jmp('fetch')
    a.label('index_carry');a.ld(IH);a.addi(1);a.andi(15);a.st(IH);a.jmp('fetch')
    a.label('font');a.ld(VX);a.andi(15);a.st(T);a.shl();a.shl();a.memop(3,T);a.addi(0x50);a.st(IL)
    a.constant(IH,0);a.jmp('fetch')

    a.label('bcd');a.copy(VX,R);a.constant(T,0);a.constant(U,0)
    a.label('bcd_h');a.ld(R);a.subi(100);a.jc('bcd_h_take');a.jmp('bcd_t')
    a.label('bcd_h_take');a.st(R);a.ld(T);a.addi(1);a.st(T);a.jmp('bcd_h')
    a.label('bcd_t');a.ld(R);a.subi(10);a.jc('bcd_t_take');a.jmp('bcd_out')
    a.label('bcd_t_take');a.st(R);a.ld(U);a.addi(1);a.st(U);a.jmp('bcd_t')
    a.label('bcd_out');a.ptr(IL,IH);a.ld(T);a.write();a.incp12();a.ld(U);a.write();a.incp12();a.ld(R);a.write();a.jmp('fetch')

    for name in ('save','load'):
        a.label(name);a.constant(CTR,0);a.copy(IL,AL);a.copy(IH,AH)
        a.label(name+'_loop')
        if name=='save':a.getv(CTR,R);a.ptr(AL,AH);a.ld(R);a.write()
        else:a.ptr(AL,AH);a.read();a.st(R);a.putv(CTR,R)
        a.ld(CTR);a.memop(4,X);a.jz('fetch')
        a.ld(CTR);a.addi(1);a.st(CTR);a.inc16(AL,AH);a.jmp(name+'_loop')

    a.label('key_wait');a.setp(0x1120);a.read();a.st(KL);a.incp();a.read();a.st(KH)
    a.memop(6,KL);a.jz('key_wait');a.constant(HELD,0);a.constant(MASK,1)
    a.label('key_select');a.ld(HELD);a.subi(8);a.jc('select_hi');a.ld(KL);a.jmp('select_test')
    a.label('select_hi');a.ld(KH)
    a.label('select_test');a.memop(5,MASK);a.jnz('key_release')
    a.ld(HELD);a.addi(1);a.st(HELD);a.ld(MASK);a.shl();a.jnz('select_mask');a.ldi(1)
    a.label('select_mask');a.st(MASK);a.jmp('key_select')
    a.label('key_release');a.setp(0x1120);a.read();a.st(KL);a.incp();a.read();a.st(KH)
    a.ld(HELD);a.subi(8);a.jc('release_hi');a.ld(KL);a.jmp('release_test')
    a.label('release_hi');a.ld(KH)
    a.label('release_test');a.memop(5,MASK);a.jnz('key_release')
    a.copy(HELD,R);a.putv(X,R);a.jmp('fetch')

    a.label('halt');a.imm(15)
    while a.pc%256:a.emit(0x0f00)
    a.label('dispatch')
    for i in range(16):a.jmp('op'+str(i))
    return a.finish(),a.labels

if __name__=='__main__':
    blob,labels=build();root=Path(__file__).parent
    (root/'interpreter.bin').write_bytes(blob)
    (root/'interpreter-map.json').write_text(json.dumps(labels,indent=2)+'\n')
    print(f'Interpreter: {len(blob)} bytes at 0x1200; {0xe00-len(blob)} bytes free')
