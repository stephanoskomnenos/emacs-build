from pathlib import Path
import subprocess,re,json
b=Path('/work/build');out=b/'gap-groups';out.mkdir(exist_ok=True);p=json.loads((b/'pgo-training-cs/provenance.json').read_text());results={}
for group,weight in p['group_merge_weights'].items():
 prof=out/(group+'.profdata')
 subprocess.run(['llvm-profdata-23','merge',str(b/'merged.profdata'),str(b/'pgo-training-cs'/(group+'-group.profdata')),'-o',str(prof)],check=True)
 cmd=['opt-23','-passes=function(instnamer),thinlto<O2>','-pgo-kind=pgo-instr-use-pipeline','-cspgo-kind=cspgo-instr-use-pipeline','-profile-file='+str(prof),'-pgo-view-raw-counts=text','-view-bfi-func-name=buf_bytepos_to_charpos','-disable-output',str(b/'f98bb6bda8b6/emacs-build-llvm-use-cccs-85f4e30c6997/src/marker.o.3.import.bc')]
 r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=True);(out/(group+'.txt')).write_text(r.stdout)
 def count(edge):
  m=re.search(edge+r'[^\n]*Count=(\d+)',r.stdout);return int(m[1]) if m else None
 before=count('156-->137');after=count('136-->138');results[group]={'before':before,'after':after,'weight':weight,'weighted_total':(before+after)*weight,'after_share':after/(before+after)}
(out/'counts.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
