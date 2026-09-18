import os,subprocess,time,json,shutil
from pathlib import Path
root=Path('/work');b=root/'build';records={}
def command(args,label,extra=None):
 start=time.monotonic()
 with (b/(label+'.log')).open('w') as out:
  p=subprocess.run(args,cwd=root,env=dict(os.environ,**(extra or {})),stdout=out,stderr=subprocess.STDOUT)
 records[label]={'elapsed_seconds':time.monotonic()-start,'exit_code':p.returncode}
 (b/'followup-costs.json').write_text(json.dumps(records,indent=2))
 if p.returncode:raise RuntimeError(label+' failed; inspect its log')
 print(label,'completed',round(time.monotonic()-start,1),'s',flush=True)
def build(label,mode,profile=None,stable=False):
 env={'PGO':mode,'STABLE_LOCALS':str(int(stable)),'JOBS':'18'}
 if profile:env['PROFILE_FILE']=str(profile)
 command(['python3','scripts/build.py'],label,env)
 bundle=root/(b/'current-bundle').read_text().strip()
 (b/(label+'-bundle')).write_text(str(bundle)+'\n')
 return bundle
normal_bundle=root/(b/'current-bundle').read_text().strip()
assert json.loads((normal_bundle/'BUILD-INFO.json').read_text())['pgo']=='generate'
(b/'normal-generate-bundle').write_text(str(normal_bundle)+'\n')
command(['python3','scripts/pgo-train.py',str(normal_bundle)],'normal-training')
normal=b/'merged.profdata'
build('ordinary','use',normal)
for stable,label in [(False,'cs-original'),(True,'cs-fixed')]:
 if (b/'pgo-training-cs').exists():shutil.move(b/'pgo-training-cs',b/'pgo-training-cs-original')
 bundle=build(label+'-generate','cs-generate',normal,stable)
 command(['python3','scripts/pgo-train.py',str(bundle)],label+'-training')
 shutil.copy2(b/'cs.profdata',b/(label+'.profdata'))
 merged=b/(label+'-combined.profdata')
 command(['llvm-profdata-23','merge',str(normal),str(b/'cs.profdata'),'-o',str(merged)],label+'-merge')
 build(label,'use',merged,stable)
build('ordinary-stable','use',normal,True)
