#!/usr/bin/env python3
"""Extract and byte-compile locked workload packages in an isolated directory."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BUILD=Path(os.environ.get('EMACS_BUILD_ROOT',ROOT/'build'))
p=argparse.ArgumentParser();p.add_argument('bundle',type=Path);a=p.parse_args()
lock=json.loads((ROOT/'benchmarks/sources.json').read_text())
names=['compat','cond-let','llama','transient','with-editor','magit','evil']
identity=hashlib.sha256(json.dumps({n:lock[n] for n in names},sort_keys=True).encode()).hexdigest()[:12]
base=BUILD/'workload-packages'/identity;base.mkdir(parents=True,exist_ok=True)
paths=[]
for name in names:
 spec=lock[name];archive=ROOT/'cache/sources'/(name+'-'+spec['version']+'.tar')
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==spec['sha256'],name
 target=base/name
 if not target.exists():
  target.mkdir();subprocess.run(['tar','-xf',str(archive),'--strip-components=1','-C',str(target)],check=True)
 paths.append(target/'lisp' if (target/'lisp').is_dir() else target)
if not (base/'compiled').exists():
 env=dict(os.environ,HOME=str(base/'home'));Path(env['HOME']).mkdir(exist_ok=True)
 for key in ('LLVM_PROFILE_FILE','EMACSLOADPATH','EMACSDATA','EMACSDOC','EMACSPATH','LD_LIBRARY_PATH'):env.pop(key,None)
 forms='(progn (setq load-prefer-newer t) '+''.join('(add-to-list \'load-path '+json.dumps(str(path))+')' for path in reversed(paths))
 forms+=''.join('(byte-recompile-directory '+json.dumps(str(path))+' 0 t)' for path in paths)
 forms+=" (require 'magit) (princ (format \"MAGIT-READY %s\\n\" (symbol-file 'magit-status))))"
 with (base/'compile.log').open('w') as log:
  subprocess.run([str(a.bundle.resolve()/'bin/emacs'),'-Q','--batch','--eval',forms],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 if 'MAGIT-READY' not in (base/'compile.log').read_text():raise SystemExit('Magit failed to load')
 (base/'compiled').touch()
(BUILD/'workload-packages/paths.json').write_text(json.dumps(list(map(str,paths)),indent=2)+'\n')
print(base)
