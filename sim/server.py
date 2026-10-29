"""Local-only browser debugger backed by the actual Icarus Verilog simulation."""
import argparse,atexit,base64,json,os,queue,shutil,subprocess,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/live-sim'
ROM_DIR=ROOT/'test/roms'
BUILTINS={'chip8-logo':'1-chip8-logo.ch8','ibm-logo':'2-ibm-logo.ch8',
          'corax':'3-corax.ch8','flags':'4-flags.ch8'}
FONT=bytes.fromhex('f0909090f0 2060202070 f010f080f0 f010f010f0 9090f01010 '
 'f080f010f0 f080f090f0 f010204040 f090f090f0 f090f010f0 '
 'f090f09090 e090e090e0 f0808080f0 e0909090e0 f080f080f0 f080f08080')
SIGNALS=[('clk',1),('rst_n',1),('request',1),('ack',1),('phase',2),('write',1),
 ('data_bus',8),('output_enable',8),('mem_valid',1),('mem_ready',1),('mem_addr',13),
 ('mem_wdata',8),('mem_rdata',8),('native_pc',13),('pointer',13),('accumulator',8),
 ('core_state',3),('delay_timer',8),('sound_timer',8),('chip8_pc',12),
 ('chip8_opcode',16),('native_ir',16),('keys',16)]
def hx(value):
    try:return int(value,16)
    except ValueError:return None

class Simulator:
    def __init__(self):
        self.lock=threading.Lock();self.process=None;self.current={};self.name='';self.rom=b''
        WORK.mkdir(parents=True,exist_ok=True)
        portable=ROOT/'build/iverilog/ucrt64/bin'
        self.env=os.environ.copy()
        if portable.exists():self.env['PATH']=str(portable)+os.pathsep+self.env.get('PATH','')
        self.iverilog=shutil.which('iverilog',path=self.env['PATH'])
        self.vvp=shutil.which('vvp',path=self.env['PATH'])
        if not self.iverilog or not self.vvp:
            raise RuntimeError('Install Icarus Verilog or run python sim/setup_iverilog.py on this Windows PC')
        command=[self.iverilog,'-g2012','-s','live_tb','-o',str(WORK/'live.vvp'),
                 str(ROOT/'src/chip8_core.v'),str(ROOT/'src/project.v'),str(ROOT/'sim/live_tb.sv')]
        result=subprocess.run(command,capture_output=True,text=True,env=self.env)
        if result.returncode:raise RuntimeError(f'RTL compilation failed (exit {result.returncode}):\n'+result.stdout+result.stderr)
        self.fetch=json.loads((ROOT/'firmware/interpreter-map.json').read_text())['fetch']&4095
        atexit.register(self.close)
    def close(self):
        process=self.process
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        self.process=None
    def _reader(self,process,out):
        try:
            for line in process.stdout:out.put(line.rstrip())
        finally:out.put(None)
    def _response(self):
        state={'wave':[],'transactions':[],'name':self.name,'signals':SIGNALS,'backend':'Icarus Verilog / actual RTL'}
        logs=[];deadline=time.monotonic()+30
        while True:
            try:line=self.output.get(timeout=max(.1,deadline-time.monotonic()))
            except queue.Empty:
                self.close();raise RuntimeError('Simulation timed out: '+'\n'.join(logs[-5:]))
            if line is None:raise RuntimeError('Simulation exited: '+'\n'.join(logs[-10:]))
            if line=='END':break
            parts=line.split()
            if not parts:continue
            if parts[0]=='W':state['wave'].append([int(parts[1])]+[hx(x) for x in parts[2:]])
            elif parts[0]=='M':
                names=['cycles','time_ns','halted','sound','error','chip8_pc','chip8_opcode','native_pc','native_ir','accumulator','pointer','core_state','delay_timer','sound_timer']
                values=[int(parts[1]),int(parts[2])]+[hx(x) for x in parts[3:]]
                state.update(zip(names,values))
            elif parts[0]=='F':state['frame']=parts[1]
            elif parts[0]=='V':state['registers']=[int(parts[1][i:i+2],16) for i in range(0,32,2)]
            elif parts[0]=='T':state['transactions'].append([int(parts[1])]+[hx(x) for x in parts[2:]])
            else:logs.append(line)
        if state.get('error'):raise RuntimeError('Memory protocol error in Verilog companion')
        if 'frame' not in state or 'cycles' not in state:raise RuntimeError('Incomplete RTL response: '+'\n'.join(logs[-5:]))
        self.current=state
        return state
    def load(self,rom,name):
        if not 1<=len(rom)<=3584:raise ValueError('A classic CHIP-8 ROM must contain 1–3584 bytes')
        with self.lock:
            self.close();self.name=name;self.rom=bytes(rom)
            memory=bytearray(8192);memory[0x50:0xa0]=FONT;memory[0x200:0x200+len(rom)]=rom
            interpreter=(ROOT/'firmware/interpreter.bin').read_bytes()
            memory[0x1200:0x1200+len(interpreter)]=interpreter
            (WORK/'image.hex').write_text('\n'.join(f'{byte:02x}' for byte in memory)+'\n')
            self.output=queue.Queue()
            flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
            self.process=subprocess.Popen([self.vvp,'-n',str(WORK/'live.vvp'),'+IMAGE=image.hex',f'+FETCH={self.fetch:x}'],
                cwd=WORK,env=self.env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,bufsize=1,creationflags=flags)
            threading.Thread(target=self._reader,args=(self.process,self.output),daemon=True).start()
            return self._response()
    def step(self,cycles,keys=0,kind='RUN'):
        cycles=int(cycles);keys=int(keys)
        if not 0<=cycles<=1000000 or not 0<=keys<=65535:raise ValueError('Invalid cycles or key bitmap')
        if kind not in ('RUN','INST','CAPTURE'):raise ValueError('Invalid simulation operation')
        with self.lock:
            if not self.process or self.process.poll() is not None:raise RuntimeError('Load a ROM first')
            self.process.stdin.write(f'{kind} {cycles} {keys:x} 128\n');self.process.stdin.flush()
            return self._response()

SIM=None
class Handler(BaseHTTPRequestHandler):
    def log_message(self,format,*args):pass
    def send_bytes(self,data,kind='application/json',status=200):
        self.send_response(status);self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(data)
    def reply(self,obj,status=200):self.send_bytes(json.dumps(obj).encode(),status=status)
    def valid_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
    def do_GET(self):
        if not self.valid_host():self.reply({'error':'Use the local simulator URL'},403);return
        if self.path in ('/','/index.html'):
            self.send_bytes((ROOT/'sim/index.html').read_bytes(),'text/html; charset=utf-8')
        elif self.path=='/api/state':self.reply(SIM.current)
        elif self.path=='/api/roms':self.reply([{'id':k,'name':v} for k,v in BUILTINS.items()])
        elif self.path=='/api/wave.vcd':
            path=WORK/'capture.vcd'
            if path.exists():self.send_bytes(path.read_bytes(),'text/plain; charset=utf-8')
            else:self.reply({'error':'Capture a trace first'},404)
        elif self.path=='/favicon.ico':self.send_bytes(b'','image/x-icon')
        else:self.reply({'error':'Not found'},404)
    def do_POST(self):
        if not self.valid_host():self.reply({'error':'Use the local simulator URL'},403);return
        origin=self.headers.get('Origin')
        allowed={f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}
        if origin and origin not in allowed:self.reply({'error':'Local simulator accepts same-origin requests only'},403);return
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<65536:raise ValueError('Invalid request size')
            body=json.loads(self.rfile.read(length))
            if self.path=='/api/load':
                if body.get('builtin') in BUILTINS:
                    name=BUILTINS[body['builtin']];rom=(ROM_DIR/name).read_bytes()
                else:
                    name=str(body.get('name','uploaded.ch8'))[:120]
                    rom=base64.b64decode(body.get('rom',''),validate=True)
                result=SIM.load(rom,name)
            elif self.path=='/api/reset':result=SIM.load(SIM.rom,SIM.name)
            elif self.path=='/api/step':result=SIM.step(body.get('cycles',1),body.get('keys',0),body.get('kind','RUN'))
            else:self.reply({'error':'Not found'},404);return
            self.reply(result)
        except (ValueError,RuntimeError,OSError,queue.Empty) as exc:self.reply({'error':str(exc)},400)

def main():
    global SIM
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);args=parser.parse_args()
    SIM=Simulator();SIM.load((ROM_DIR/BUILTINS['ibm-logo']).read_bytes(),BUILTINS['ibm-logo'])
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Actual RTL simulator: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();SIM.close()
if __name__=='__main__':main()
