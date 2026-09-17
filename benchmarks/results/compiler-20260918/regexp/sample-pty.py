import os,sys,json,time,subprocess
from pathlib import Path
sys.path.insert(0,'/work/scripts')
from pty_driver import Session
base=Path('/work/build/regexp-investigation')
for kind in ['thin','cs']:
 bundle=Path('/work')/Path('/work/build/'+kind+'-pgo-bundle').read_text().strip()
 wrapper=base/(kind+'-sampled-emacs')
 wrapper.write_text('#!/bin/sh\nexec taskset -c 0 perf record -e cpu-clock:u -F 997 -o '+str(base/(kind+'.perf.data'))+' -- '+str(bundle/'bin/emacs')+' "$@"\n')
 wrapper.chmod(0o755)
 env=dict(os.environ,WORKLOAD_SPEC='/work/benchmarks/interactive/validation.json',WORKLOAD_TEXT='/work/build/interactive-validation/held-out.txt',WORKLOAD_PACKAGES='/work/build/workload-packages/paths.json')
 session=Session(wrapper,base/(kind+'-pty'),Path('/work/benchmarks/interactive/observer.el'),env)
 samples=[]
 for i in range(150):
  samples.append(session.action(b'\x1b[17~'))
 session.close()
 (base/(kind+'-pty-samples.json')).write_text(json.dumps(samples,indent=2))
 with (base/(kind+'-perf-report.txt')).open('w') as out:
  subprocess.run(['perf','report','--stdio','--no-children','-i',str(base/(kind+'.perf.data')),'--sort','symbol'],stdout=out,stderr=subprocess.STDOUT,check=True)
 print(kind,'done',flush=True)
