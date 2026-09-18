from pathlib import Path
import json,hashlib,subprocess,struct
b=Path('/work/build');out=b/'balanced-audit';out.mkdir(exist_ok=True);bundle=Path((b/'cs-balanced-bundle').read_text().strip());info=json.loads((bundle/'BUILD-INFO.json').read_text());obj=bundle.parents[1].with_name(bundle.parents[1].name.replace('stage-','emacs-build-'))/'src'
old=b/'f98bb6bda8b6/emacs-build-llvm-use-cccs-85f4e30c6997/src';report={'object_hashes':{},'raw_headers':{}}
for n in ['marker.o','regex-emacs.o','search.o','eval.o','bytecode.o','alloc.o']:
 h=hashlib.sha256((obj/n).read_bytes()).hexdigest();assert h==hashlib.sha256((old/n).read_bytes()).hexdigest();report['object_hashes'][n]=h
for p in (b/'pgo-training-cs/profiles').glob('*.profraw'):
 h=struct.unpack('<Q',p.read_bytes()[8:16])[0];assert h==0x30000000000000b;report['raw_headers'][p.name]=hex(h)
assert len(report['raw_headers'])==15
cmd=['opt-23','-passes=function(instnamer),thinlto<O2>','-pgo-kind=pgo-instr-use-pipeline','-cspgo-kind=cspgo-instr-use-pipeline','-profile-file='+str(b/'cs-balanced-combined.profdata'),'-pgo-warn-missing-function','-pgo-view-raw-counts=text','-view-bfi-func-name=buf_bytepos_to_charpos','-disable-output',str(obj/'marker.o.3.import.bc')]
r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=True);assert 'Count=' in r.stdout and 'warning:' not in r.stdout;(out/'bytepos-counts.txt').write_text(r.stdout);report['replay_command']=cmd
exe=bundle/'bin'/('emacs-'+info['sources']['emacs']['emacs_version']);dis=subprocess.check_output(['llvm-objdump-23','-d','--disassemble-symbols=buf_bytepos_to_charpos',str(exe)],text=True);(out/'bytepos-disassembly.txt').write_text(dis)
report['binary_sha256']=hashlib.sha256(exe.read_bytes()).hexdigest();(out/'audit.json').write_text(json.dumps(report,indent=2));print('balanced audit passed')
