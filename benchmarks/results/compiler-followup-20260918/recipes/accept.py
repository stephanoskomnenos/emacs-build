from pathlib import Path
import subprocess
b=Path('/work/build')
for i,name in enumerate(['ordinary','cs-original','cs-link-fixed','bolt-optimized']):
 bundle=(b/(name+'-bundle')).read_text().strip();args=['python3','tests/run.py',bundle]
 if i==0:args.append('--prepare')
 with (b/(name+'-acceptance.log')).open('w') as f:subprocess.run(args,stdout=f,stderr=f,check=True)
 print(name,'acceptance passed',flush=True)
