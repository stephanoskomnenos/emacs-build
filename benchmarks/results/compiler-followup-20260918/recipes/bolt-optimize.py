from pathlib import Path
import json,os,shutil,subprocess
b=Path('/work/build');base=Path((b/'ordinary-bundle').read_text().strip());dest=b/'bolt-optimized';out=b/'bolt'
if dest.exists():raise SystemExit('Refusing to overwrite existing optimized bundle')
shutil.copytree(base,dest,symlinks=True)
info=json.loads((base/'BUILD-INFO.json').read_text());v=info['sources']['emacs']['emacs_version'];exe=dest/'bin'/('emacs-'+v)
args=['llvm-bolt-23',str(base/'bin'/('emacs-'+v)),'-data='+str(out/'merged.fdata'),'-reorder-blocks=ext-tsp','-reorder-functions=cdsort','-split-functions','-split-all-cold','-split-eh','-dyno-stats','-o',str(exe)+'.new']
(out/'optimize-command.json').write_text(json.dumps(args,indent=2))
with (out/'optimize.log').open('w') as f:subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True)
os.replace(str(exe)+'.new',exe)
old=next(dest.glob('libexec/emacs/*/*/*.pdmp'));old.unlink()
env=dict(os.environ,EMACSDATA=str(dest/'share/emacs'/v/'etc'),EMACSDOC=str(dest/'share/emacs'/v/'etc'),EMACSLOADPATH=str(dest/'share/emacs'/v/'lisp'),EMACSPATH=str(old.parent),LC_ALL='C.UTF-8')
cwd=base.parents[2]/('emacs-build-llvm-use-'+info['profile_sha256'][:12])/'src'
with (out/'optimized-dump.log').open('w') as f:subprocess.run([str(exe),'-batch','--no-build-details','-l','loadup','--temacs=pdump'],cwd=cwd,env=env,stdout=f,stderr=f,check=True,timeout=120)
shutil.move(exe.parent/'emacs.pdmp',old)
info.update(bolt=True,bolt_options=args)
(dest/'BUILD-INFO.json').write_text(json.dumps(info,indent=2))
(b/'bolt-optimized-bundle').write_text(str(dest)+'\n')
with (out/'optimized-smoke.log').open('w') as f:subprocess.run([str(dest/'bin/emacs'),'-Q','--batch','--eval','(princ (list emacs-version (+ 20 22)))'],stdout=f,stderr=f,check=True,timeout=30)
print('BOLT optimized executable and fresh dump passed batch smoke.',flush=True)
