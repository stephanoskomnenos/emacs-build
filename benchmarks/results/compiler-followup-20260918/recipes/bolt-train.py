from pathlib import Path
import os,subprocess,json,sys
root=Path('/work');b=root/'build';out=b/'bolt';dest=b/'bolt-instrumented'
# Reuse existing generic training and assertions; never use validation/config.
base=Path((b/'ordinary-bundle').read_text().strip())
os.environ['EMACS_TRAIN_SOURCE']=str(base.parents[2]/'src/emacs')
script=root/'scripts/pgo-train.py'
t=script.read_text()
t=t.replace("fixtures=base/'fixtures'", "\nfor old in (BUILD/'bolt').glob('training.*.fdata'): old.unlink()\nfixtures=base/'fixtures'")
sys.path.insert(0,str(root/'scripts'));sys.argv=[str(script),str(dest),'--check-workloads']
try:exec(compile(t,str(script),'exec'),{'__name__':'__main__','__file__':str(script)})
except SystemExit as e:
 if e.code not in (0,None):raise
suite=b/'pgo-training/elisp-benchmarks'
env=dict(os.environ,HOME=str(out/'home'),BENCHMARK_SUITE=str(suite),BENCHMARK_SELECTOR='elb-bytecomp\\|elb-pcase\\|elb-smie\\|elb-scroll\\|inclist\\|map-closure\\|pack-unpack',BENCHMARK_RUNS='1',BENCHMARK_RESULT=str(out/'training-benchmarks.json'))
(out/'home').mkdir(exist_ok=True)
with (out/'training-benchmarks.log').open('w') as f:
 subprocess.run([str(dest/'bin/emacs'),'-Q','--batch','-l',str(root/'benchmarks/runtime.el')],env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
profiles=sorted(out.glob('training.*.fdata'))
assert len(profiles)>=13,len(profiles)
with (out/'merge.log').open('w') as f:subprocess.run(['merge-fdata-23','-q','-o',str(out/'merged.fdata'),*map(str,profiles)],stdout=f,stderr=subprocess.STDOUT,check=True)
(out/'training-method.json').write_text(json.dumps({'profiles':[p.name for p in profiles],'workloads':'12 existing generic PTY scenarios plus existing ELPA selection; each once; preparation/dump/smoke excluded; no personal config or validation inputs','weighting':'merge-fdata sum; no additional execution-count normalization'},indent=2))
print('BOLT training and fdata merge completed',flush=True)
