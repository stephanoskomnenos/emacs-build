from pathlib import Path
import subprocess,os
p=Path('/work/research/minimal');os.chdir(p)
def run(args):
 r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);assert r.returncode==0,r.stdout;return r.stdout
for src in ['a','main']:run(['clang-23','-O2','-flto=thin','-fprofile-use=normal.profdata','-c',src+'.c','-o',src+'.o'])
base=['clang-23','-O2','-flto=thin','-fuse-ld=lld','a.o','main.o']
run(base+['-fprofile-use=normal.profdata','-fcs-profile-generate='+str(p/'link-raw'),'-o','link-gen']);run(['./link-gen'])
run(['llvm-profdata-23','merge','normal.profdata',*map(str,(p/'link-raw').glob('*.profraw')),'-o','link.profdata'])
log=run(base+['-fprofile-use=link.profdata','-Wl,-mllvm,-pgo-warn-missing-function','-o','link-use'])
(p/'link-use.log').write_text(log)
print(log or 'Identical pre-link objects: no missing-profile warnings')
