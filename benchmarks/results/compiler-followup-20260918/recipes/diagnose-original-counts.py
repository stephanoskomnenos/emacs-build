"""Diagnostic counters on the frozen regexp test; NEVER training input."""
from pathlib import Path
import os,sys,subprocess,json
sys.path.insert(0,'/work/scripts')
from pty_driver import Session
b=Path('/work/build');out=b/'diagnostic-only-original-regexp';out.mkdir(exist_ok=True)
bundle=Path((b/'cs-original-generate-bundle').read_text().strip())
env=dict(os.environ,LLVM_PROFILE_FILE=str(out/'validation-%m-%p.profraw'),WORKLOAD_SPEC='/work/benchmarks/interactive/validation.json',WORKLOAD_TEXT=str(b/'interactive-validation/held-out.txt'),WORKLOAD_PACKAGES=str(b/'workload-packages/paths.json'))
s=Session(bundle/'bin/emacs',out/'pty',Path('/work/benchmarks/interactive/observer.el'),env)
records=[]
for _ in range(10):records.append(s.action(b'\x1b[17~'))
s.close()
(out/'checkpoints.json').write_text(json.dumps(records,indent=2))
subprocess.run(['llvm-profdata-23','merge',*map(str,out.glob('validation-*.profraw')),'-o',str(out/'validation-only.profdata')],check=True)
# Standalone inspection only; this profile is never passed to a binary build.
print('Diagnostic counters collected, isolated from all training profiles.',flush=True)
