"""Local-only BOLT instrumentation and fresh portable-dump attempt."""
from pathlib import Path
import json,os,shutil,subprocess
b=Path('/work/build');base=Path((b/'ordinary-bundle').read_text().strip());dest=b/'bolt-instrumented';out=b/'bolt';out.mkdir(exist_ok=True)
if dest.exists():raise SystemExit('Refusing to overwrite existing BOLT experiment')
shutil.copytree(base,dest,symlinks=True)
info=json.loads((base/'BUILD-INFO.json').read_text());v=info['sources']['emacs']['emacs_version'];exe=dest/'bin'/('emacs-'+v)
args=['llvm-bolt-23',str(base/'bin'/('emacs-'+v)),'-instrument','-instrumentation-file='+str(out/'training'),'-instrumentation-file-append-pid','-o',str(exe)+'.new']
with (out/'instrument.log').open('w') as log:subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True)
os.replace(str(exe)+'.new',exe)
# Never load the original dump with rewritten code.
old=next(dest.glob('libexec/emacs/*/*/*.pdmp'));old.unlink()
env=dict(os.environ,EMACSDATA=str(dest/'share/emacs'/v/'etc'),EMACSDOC=str(dest/'share/emacs'/v/'etc'),EMACSLOADPATH=str(dest/'share/emacs'/v/'lisp'),EMACSPATH=str(old.parent),LC_ALL='C.UTF-8')
args=[str(exe),'-batch','--no-build-details','-l','loadup','--temacs=pdump']
(out/'dump-command.json').write_text(json.dumps({'args':args,'environment':{k:env[k] for k in ['EMACSDATA','EMACSDOC','EMACSLOADPATH','EMACSPATH']}},indent=2))
with (out/'dump.log').open('w') as log:subprocess.run(args,env=env,cwd=base.parents[2]/('emacs-build-llvm-use-'+info['profile_sha256'][:12])/'src',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
shutil.move(exe.parent/'emacs.pdmp',old)
with (out/'smoke.log').open('w') as log:subprocess.run([str(dest/'bin/emacs'),'-Q','--batch','--eval','(princ (list emacs-version (+ 20 22) (string-match "[a-z]+" "abc")))'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
# Bootstrap and smoke profiles are deliberately excluded from training.
for p in out.glob('training.*'):p.unlink()
print('BOLT instrumented executable and regenerated dump passed batch smoke.',flush=True)
