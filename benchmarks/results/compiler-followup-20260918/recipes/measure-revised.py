from pathlib import Path
import subprocess,json
b=Path('/work/build');(b/'cs-balanced-bundle').write_text('/work/'+(b/'current-bundle').read_text().strip()+'\n');names=['ordinary','cs-cc-fixed','cs-balanced'];bundles={n:Path((b/(n+'-bundle')).read_text().strip()) for n in names}
for name in []:
 with (b/(name+'-acceptance.log')).open('w') as f:subprocess.run(['python3','tests/run.py',str(bundles[name])],stdout=f,stderr=f,check=True)
 info=json.loads((bundles[name]/'BUILD-INFO.json').read_text());exe=bundles[name]/'bin'/('emacs-'+info['sources']['emacs']['emacs_version'])
 nm=subprocess.check_output(['llvm-nm-23',str(exe)],text=True)
 assert '__llvm_profile_runtime' not in nm
 assert '__llvm_profile_write_file' not in nm
 print(name,'acceptance passed; no profile runtime',flush=True)
rows=[[0,1,2],[1,2,0],[2,0,1],[2,1,0],[0,2,1],[1,0,2]]
order=[]
for block,row in enumerate(rows):
 for idx in row:order.append({'round':block//3+1,'block':block%3+1,'variant':names[idx]})
(b/'revised-measurement-order.json').write_text(json.dumps(order,indent=2))
for e in order:
 name=e['variant'];label=f"revised-r{e['round']}-b{e['block']}-{name}"
 for kind in ['interactive']:
  args=['python3','scripts/benchmark-'+kind+'.py',str(bundles[name]),'--label',label,'--runs','4','--cpu','0']
  if kind=='startup':args+=['--files',*map(str,sorted((b/'validation-files').glob('held-out.*')))]
  with (b/(label+'-'+kind+'.log')).open('w') as f:subprocess.run(args,stdout=f,stderr=f,check=True)
 print(label,'completed',flush=True)
