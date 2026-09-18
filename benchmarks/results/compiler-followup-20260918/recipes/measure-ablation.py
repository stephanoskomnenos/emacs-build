from pathlib import Path
import subprocess,json
b=Path('/work/build');ab=Path('/work')/(b/'current-bundle').read_text().strip()
assert '3b5293545ac8' in str(ab)
(b/'cs-no-bytepos-bundle').write_text(str(ab)+'\n')
with (b/'cs-no-bytepos-acceptance.log').open('w') as f:subprocess.run(['python3','tests/run.py',str(ab)],stdout=f,stderr=f,check=True)
order=['cs-link-fixed','cs-no-bytepos','cs-no-bytepos','cs-link-fixed','cs-no-bytepos','cs-link-fixed','cs-link-fixed','cs-no-bytepos']
(b/'ablation-order.json').write_text(json.dumps(order,indent=2))
for i,name in enumerate(order):
 label=f'bytepos-{i+1}-{name}';bundle=(b/(name+'-bundle')).read_text().strip()
 for kind in ['startup','interactive']:
  args=['python3','scripts/benchmark-'+kind+'.py',bundle,'--label',label,'--runs','5','--cpu','0']
  if kind=='startup':args+=['--files',*map(str,sorted((b/'validation-files').glob('held-out.*')))]
  with (b/(label+'-'+kind+'.log')).open('w') as f:subprocess.run(args,stdout=f,stderr=f,check=True)
 print(label,'completed',flush=True)
