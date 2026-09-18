from pathlib import Path
import json,subprocess,time
b=Path('/work/build');names=['ordinary','cs-original','cs-link-fixed','bolt-optimized'];bundles={n:Path((b/(n+'-bundle')).read_text().strip()) for n in names}
rows=[[0,1,3,2],[1,2,0,3],[2,3,1,0],[3,0,2,1]]
order=[]
for rnd in range(2):
 for row,indices in enumerate(rows):
  for idx in (indices if rnd==0 else list(reversed(indices))):order.append({'round':rnd+1,'block':row+1,'variant':names[idx]})
(b/'measurement-order.json').write_text(json.dumps(order,indent=2))
for entry in order:
 name=entry['variant'];label=f"r{entry['round']}-b{entry['block']}-{name}"
 for kind in ['startup','interactive']:
  cmd=['python3','scripts/benchmark-'+kind+'.py',str(bundles[name]),'--label',label,'--runs','3','--cpu','0']
  if kind=='startup':cmd+=['--files',*map(str,sorted((b/'validation-files').glob('held-out.*'))) ]
  with (b/(label+'-'+kind+'.log')).open('w') as f:subprocess.run(cmd,stdout=f,stderr=f,check=True)
 print(label,'completed',flush=True)
