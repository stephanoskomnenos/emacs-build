import os,subprocess,json
from pathlib import Path
p=Path('/work/research/minimal');p.mkdir(exist_ok=True);os.chdir(p)
(p/'a.c').write_text('__attribute__((noinline)) static int local(int x) {return x>8?x*3:x+2;}\nint wrap(int x){return local(x);}\n')
(p/'main.c').write_text('extern int wrap(int); int main(void){volatile int s=0;for(int i=0;i<10000;i++)s+=wrap(i);return s==0;}\n')
def run(args,env=None):
 r=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env);assert r.returncode==0,r.stdout;return r.stdout
base=['clang-23','-O2','-flto=thin','-fuse-ld=lld','a.c','main.c']
run(base+['-fprofile-generate='+str(p/'raw'),'-o','gen']);run(['./gen'])
run(['llvm-profdata-23','merge',*map(str,(p/'raw').glob('*.profraw')),'-o','normal.profdata'])
for kind,flags in [('hash',[]),('source',['-Wl,-mllvm,-use-source-filename-for-promoted-locals'])]:
 raw=p/(kind+'-raw');run(base+flags+['-fprofile-use=normal.profdata','-fcs-profile-generate='+str(raw),'-o',kind+'-gen']);run(['./'+kind+'-gen'])
 run(['llvm-profdata-23','merge','normal.profdata',*map(str,raw.glob('*.profraw')),'-o',kind+'.profdata'])
 log=run(base+flags+['-fprofile-use='+kind+'.profdata','-Wl,-mllvm,-pgo-warn-missing-function','-o',kind+'-use'])
 (p/(kind+'-use.log')).write_text(log)
 (p/(kind+'-profile.txt')).write_text(run(['llvm-profdata-23','show','--showcs','--all-functions',kind+'.profdata']))
 print(kind,log or 'no missing-profile warnings',flush=True)
