from pathlib import Path
import json,hashlib,subprocess,struct,re
b=Path('/work/build');out=b/'final-audit';out.mkdir(exist_ok=True)
names=['cs-cc-generate','cs-cc-fixed','ordinary-cc-control']
bundles={n:Path((b/(n+'-bundle')).read_text().strip()) for n in names}
objects={n:p.parents[1].with_name(p.parents[1].name.replace('stage-','emacs-build-'))/'src' for n,p in bundles.items()}
report={'objects':{},'raw_headers':{},'profile_checks':{}}
for f in ['marker.o','regex-emacs.o','search.o','eval.o','bytecode.o','alloc.o']:
 hs={n:hashlib.sha256((p/f).read_bytes()).hexdigest() for n,p in objects.items()};assert len(set(hs.values()))==1,(f,hs);report['objects'][f]=hs
for p in (b/'pgo-training-cs/profiles').rglob('*.profraw'):
 h=struct.unpack('<Q',p.read_bytes()[8:16])[0];assert h==0x30000000000000b,(p,hex(h));report['raw_headers'][p.name]=hex(h)
assert len(report['raw_headers'])==15
profile=b/'cs-cc-combined.profdata'
for fn,obj in [('buf_bytepos_to_charpos','marker.o'),('re_match_2_internal.llvm.10747944231370379322','regex-emacs.o'),('search_buffer','search.o')]:
 p=objects['cs-cc-fixed']/(obj+'.3.import.bc')
 cmd=['opt-23','-passes=function(instnamer),thinlto<O2>','-pgo-kind=pgo-instr-use-pipeline','-cspgo-kind=cspgo-instr-use-pipeline','-profile-file='+str(profile),'-pgo-warn-missing-function','-pgo-view-raw-counts=text','-view-bfi-func-name='+fn,'-disable-output',str(p)]
 r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);assert r.returncode==0
 assert len(r.stdout)>1000,fn
 (out/(fn+'-replay.txt')).write_text(r.stdout)
 report['profile_checks'][fn]={'command':cmd,'exit_code':r.returncode,'diagnostic_lines':[l for l in r.stdout.splitlines() if 'warning:' in l],'raw_count_output':len(r.stdout)}
for n in names[1:]:
 p=bundles[n];info=json.loads((p/'BUILD-INFO.json').read_text());exe=p/'bin'/('emacs-'+info['sources']['emacs']['emacs_version']);nm=subprocess.check_output(['llvm-nm-23',str(exe)],text=True);assert '__llvm_profile_runtime' not in nm and '__llvm_profile_write_file' not in nm
 if n=='cs-cc-fixed':
  dis=subprocess.check_output(['llvm-objdump-23','-d','--disassemble-symbols=buf_bytepos_to_charpos',str(exe)],text=True);(out/'fixed-bytepos-disassembly.txt').write_text(dis)
report['training_provenance']={}
ps=[b/'pgo-training/provenance.json',b/'pgo-training-cs/provenance.json']
a,c=[json.loads(p.read_text()) for p in ps]
for k in ['configuration','target_share_units','benchmark_sources','benchmark_selector','fixture_sha256','corpus_sha256','training_script_sha256']:
 assert a[k]==c[k],k;report['training_provenance'][k]=a[k]
(out/'audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report['profile_checks'],indent=2))
