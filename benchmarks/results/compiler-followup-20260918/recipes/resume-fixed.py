from pathlib import Path
import os,subprocess,json,time,shutil
b=Path('/work/build');cost={}
def run(args,label,extra=None):
 start=time.monotonic()
 with (b/(label+'.log')).open('w') as f:r=subprocess.run(args,env=dict(os.environ,**(extra or {})),stdout=f,stderr=f)
 cost[label]={'seconds':time.monotonic()-start,'exit_code':r.returncode};(b/'fixed-costs.json').write_text(json.dumps(cost,indent=2))
 if r.returncode:raise SystemExit(label+' failed')
 print(label,'completed',flush=True)
def build(label,mode,profile):
 run(['python3','research/build-fixed.py'],label,{'PGO':mode,'PROFILE_FILE':str(profile),'JOBS':'18'})
 bundle=Path('/work')/(b/'current-bundle').read_text().strip();(b/(label+'-bundle')).write_text(str(bundle)+'\n');return bundle
bundle=build('cs-link-generate','cs-generate',b/'merged.profdata')
run(['python3','scripts/pgo-train.py',str(bundle)],'cs-link-training')
shutil.copy2(b/'cs.profdata',b/'cs-link.profdata')
run(['llvm-profdata-23','merge',str(b/'merged.profdata'),str(b/'cs-link.profdata'),'-o',str(b/'cs-link-combined.profdata')],'cs-link-merge')
build('cs-link-fixed','use',b/'cs-link-combined.profdata')
