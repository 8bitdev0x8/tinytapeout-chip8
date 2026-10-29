"""Instruction-level model of the small native engine, for ROM development."""
class Engine:
    def __init__(self, ram):
        self.ram=bytearray(ram);self.pc=0x1200;self.p=0;self.a=0
        self.zero=True;self.carry=False;self.rng=0xace1
        self.halted=False;self.writes=[];self.steps=0
    def store(self,address):
        self.ram[address]=self.a
        if not 0x1130<=address<0x1200:self.writes.append((address,self.a))
    def step(self):
        op=self.ram[self.pc]*256+self.ram[0x1000|((self.pc+1)&4095)]
        self.pc=0x1000|((self.pc+2)&4095);self.steps+=1
        n,sub,k=op>>12,(op>>8)&15,op&255
        if n==0:
            if sub==0:self.a=k
            elif sub==1:self.carry=self.a+k>255;self.a=(self.a+k)&255
            elif sub==2:self.a&=k
            elif sub==3:self.a|=k
            elif sub==4:self.a^=k
            elif sub==5:self.carry=self.a>=k;self.a=(self.a-k)&255
            elif sub==6:self.p=(self.p&0x1f00)|self.a;return
            elif sub==7:self.p=((self.a&31)<<8)|(self.p&255);return
            elif sub==8:self.pc=0x1000|((k&15)<<8)|self.a;return
            elif sub==9:self.a=self.p&255
            elif sub==10:self.p=(self.p+1)&8191;return
            elif sub==11:self.carry=bool(self.a&128);self.a=(self.a<<1)&255
            elif sub==12:self.carry=bool(self.a&1);self.a>>=1
            elif sub==13:
                self.a=self.rng&255
                b=((self.rng>>15)^(self.rng>>13)^(self.rng>>12)^(self.rng>>10))&1
                self.rng=((self.rng<<1)|b)&65535
            elif sub==14:self.a=0
            else:self.halted=True;return
            self.zero=self.a==0
        elif n in (1,3,4,5,6,7):
            b=self.ram[self.p]
            if n==1:self.a=b
            elif n==3:self.carry=self.a+b>255;self.a=(self.a+b)&255
            elif n==4:self.carry=self.a>=b;self.a=(self.a-b)&255
            elif n==5:self.a&=b
            elif n==6:self.a|=b
            else:self.a^=b
            self.zero=self.a==0
        elif n==2:self.store(self.p)
        elif n==12:self.store(0x1100|k)
        elif n in (8,9,10,11):
            if n==8 or (n==9 and self.zero) or (n==10 and not self.zero) or (n==11 and self.carry):
                self.pc=0x1000|(op&4095)
        elif n in (13,14):self.p=((n-13)<<12)|(op&4095)
        elif n==15:
            self.a=(self.p>>8) if op&256 else self.ram[0x1100|k]
            self.zero=self.a==0
