"""Download a checksum-verified portable MSYS2 Icarus runtime on Windows.
Installs only into build/iverilog; does not modify the machine's PATH.
"""
import hashlib,io,re,subprocess,tarfile
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
BASE='https://repo.msys2.org/mingw/ucrt64/'
def main():
    packages=ROOT/'build/iverilog-packages';packages.mkdir(parents=True,exist_ok=True)
    db=urlopen(BASE+'ucrt64.db',timeout=60).read()
    if db[:4]==bytes.fromhex('28b52ffd'):
        dbfile=packages/'ucrt64.db.zst';dbfile.write_bytes(db)
        db=subprocess.check_output(['C:/msys64/usr/bin/zstd.exe','-d','-q','-c',str(dbfile)])
    catalog={}
    with tarfile.open(fileobj=io.BytesIO(db),mode='r:*') as tar:
        for member in tar:
            if member.name.endswith('/desc'):
                fields={}
                for section in tar.extractfile(member).read().decode().strip().split('\n\n'):
                    lines=section.splitlines();fields[lines[0].strip('%')]=lines[1:]
                catalog[fields['NAME'][0]]=fields
    wanted=['mingw-w64-ucrt-x86_64-'+x for x in ('iverilog','gcc-libs','libwinpthread')]
    selected={}
    while wanted:
        name=re.split('[<>=]',wanted.pop())[0]
        if name in selected:continue
        if name not in catalog:raise RuntimeError('Unknown dependency: '+name)
        selected[name]=catalog[name];wanted+=catalog[name].get('DEPENDS',[])
    size=sum(int(x['CSIZE'][0]) for x in selected.values())
    print(f'Portable runtime: {len(selected)} packages, {size/1048576:.1f} MiB',flush=True)
    if size>100*1048576:raise RuntimeError('Unexpectedly large runtime')
    dest=(ROOT/'build/iverilog').resolve();dest.mkdir(parents=True,exist_ok=True)
    zstd=Path('C:/msys64/usr/bin/zstd.exe')
    if not zstd.exists():raise RuntimeError('Need zstd.exe from MSYS2 to unpack .zst packages')
    for name,info in selected.items():
        filename=info['FILENAME'][0];target=packages/filename
        if not target.exists():target.write_bytes(urlopen(BASE+filename,timeout=60).read())
        if hashlib.sha256(target.read_bytes()).hexdigest()!=info['SHA256SUM'][0]:raise RuntimeError('Checksum: '+filename)
        raw=subprocess.check_output([str(zstd),'-d','-q','-c',str(target)])
        with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
            for member in tar:
                if not member.name.startswith('ucrt64/'):continue
                if member.issym() or member.islnk():continue
                path=(dest/member.name).resolve()
                if not path.is_relative_to(dest):raise RuntimeError('Invalid archive path')
                tar.extract(member,dest,filter='data')
        print(name,flush=True)
    print('Ready: '+str(dest/'ucrt64/bin/iverilog.exe'),flush=True)
if __name__=='__main__':main()
