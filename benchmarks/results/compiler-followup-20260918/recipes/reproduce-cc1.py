import os,subprocess,struct
from pathlib import Path
p=Path('/work/research/minimal');os.chdir(p)
def run(args,env=None):
 r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env);assert r.returncode==0,r.stdout;return r.stdout
flags=['-O2','-flto=thin','-Xclang','-fprofile-instrument=csllvm']
for n in ['a','main']:run(['clang-23',*flags,'-fprofile-use=normal.profdata','-c',n+'.c','-o',n+'-cc.o'])
base=['clang-23',*flags,'-fuse-ld=lld','a-cc.o','main-cc.o']
run(base+['-fprofile-use=normal.profdata','-fcs-profile-generate','-o','cc-gen'])
run(['./cc-gen'],dict(os.environ,LLVM_PROFILE_FILE=str(p/'cc-raw/%m.profraw')))
print('raw versions',[hex(struct.unpack('<QQ',f.read_bytes()[:16])[1]) for f in (p/'cc-raw').glob('*')])
run(['llvm-profdata-23','merge','normal.profdata',*map(str,(p/'cc-raw').glob('*')),'-o','cc.profdata'])
print(run(base+['-fprofile-use=cc.profdata','-Wl,-mllvm,-pgo-warn-missing-function','-Wl,--save-temps','-o','cc-use']))
nm=run(['llvm-nm-23','cc-use']);print('final profile runtime linked?', '__llvm_profile_runtime' in nm)
print(run(['llvm-profdata-23','show','--showcs','--function=local','cc.profdata']))
