#!/usr/bin/env python3
"""Train independent generic PTY scenarios plus the locked ELPA benchmarks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from pty_driver import Session
from profile_weights import weights_for_counts
from training_input import cancel_minibuffer

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('bundle',type=Path);a=p.parse_args()
a.bundle=a.bundle.resolve();info=json.loads((a.bundle/'BUILD-INFO.json').read_text())
if info.get('pgo')!='generate':raise SystemExit('An instrumented build is required')
base=ROOT/'build/pgo-training';profiles=base/'profiles';corpus=base/'corpus'
if profiles.exists() and list(profiles.glob('*.profraw')):
    raise SystemExit('Raw profiles already exist; use a fresh build/pgo-training directory')
for directory in (profiles,corpus,base/'home'):directory.mkdir(parents=True,exist_ok=True)
source=a.bundle.parents[2]/'src/emacs'
for original,target in [('src/buffer.c','buffer.c'),('lisp/files.el','files.el'),('etc/ORG-NEWS','org-news.org'),('etc/NEWS','news.txt')]:
    shutil.copy2(source/original,corpus/target)
subprocess.run(['python3',str(ROOT/'scripts/prepare-workload-packages.py'),str(a.bundle)],check=True)
# Preflight profiles use the compiler default directory, not the training groups.
subprocess.run(['python3',str(ROOT/'tests/minibuffer-cancel.py'),str(a.bundle)],check=True)
repo=base/'repository'
if repo.exists():shutil.rmtree(repo)
repo.mkdir()
env=dict(os.environ,HOME=str(base/'home'),GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_CEILING_DIRECTORIES=str(ROOT),
         GIT_AUTHOR_DATE='2025-03-04T05:06:07Z',GIT_COMMITTER_DATE='2025-03-04T05:06:07Z',
         TRAIN_CORPUS=str(corpus),TRAIN_PACKAGES=str(ROOT/'build/workload-packages/paths.json'),
         TRAIN_PRODUCER=str(ROOT/'benchmarks/interactive/training-producer.py'))
for key in ('LLVM_PROFILE_FILE','EMACSLOADPATH','EMACSDATA','EMACSDOC','EMACSPATH','LD_LIBRARY_PATH'):env.pop(key,None)
def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],env=env,stderr=subprocess.STDOUT,text=True)
git('init','-q','-b','main');git('config','user.name','Training Fixture');git('config','user.email','training@example.invalid');git('config','commit.gpgsign','false')
for n in range(5):(repo/f'unit-{n}.c').write_text(''.join(f'int value_{n}_{i} = {i};\n' for i in range(110)))
git('add','.');git('commit','-qm','Training initial')
for n in range(3):
    f=repo/f'unit-{n}.c';f.write_text(f.read_text()+f'/* revision {n} */\n');git('add','.');git('commit','-qm',f'Training revision {n}')
for n in range(5):
    f=repo/f'unit-{n}.c';f.write_text(f.read_text().replace(' = 9;',' = 471;')+'/* pending edit */\n')
# Equal initial shares for six generic scenarios, with 25% for the suite.
# These are count targets, not wall-time estimates or claimed optimal shares.
targets={name:1 for name in ('files','editing','minibuffer','org','process','magit')}
targets['benchmark']=2
checks={}
for name in targets:
    if name=='benchmark':continue
    session_env=dict(env,LLVM_PROFILE_FILE=str(profiles/(name+'-%m-%p.profraw')))
    session=Session(a.bundle/'bin/emacs',base/name,ROOT/'benchmarks/interactive/training.el',session_env)
    recorded=[]
    def action(keys,check=lambda state:True):
        result=session.action(keys)['state']
        if not check(result):raise RuntimeError(f'{name}: unexpected training result {result}')
        recorded.append({k:v for k,v in result.items() if k not in ('text','compilation_output')})
        return result
    try:
        if name=='files':
            action(b'\x1b[17~',lambda s:s['value']==4)
        elif name=='editing':
            action(b'\x18\x06'+str(corpus/'files.el').encode()+b'\r',lambda s:s['mode']=='emacs-lisp-mode')
            size=action(b'\x1b<')['size']
            action(b';; Training edit\n',lambda s:s['size']==size+17)
            action(b'\x15' + b'2\x1f',lambda s:s['size']==size)
            action(b'\x18btraining-notes\r\x1bxtext-mode\r')
            content='Training search needle: λ and 文本.\n'*35
            action(content.encode(),lambda s:s['text']==content)
            action(b'\x1b<\x13needle\r',lambda s:s['point']>1)
            action(b'\x1b>\x10\x01\x0b\x19',lambda s:s['size']==len(content))
            for _ in range(24):action(b'\x02\x06',lambda s:s['size']==len(content))
        elif name=='minibuffer':
            for filename in ('news.txt','buffer.c','files.el'):
                action(b'\x18\x06'+str(corpus/filename).encode()+b'\r',lambda s:s['buffer']==filename)
                action(b'\x1bxend-of-buff\t\r',lambda s:s['point']==s['size']+1)
                action(b'\x1bxbeginn\t\x1bOR',lambda s:s['minibuffer_depth']==1)
                cancel_minibuffer(session)
                action(b'\x18b*scratch*\r',lambda s:s['buffer']=='*scratch*')
        elif name=='org':
            action(b'\x1b[20~',lambda s:s['mode']=='org-mode')
            for _ in range(8):action(b'\t\x0e\x0e\x10',lambda s:s['mode']=='org-mode')
            action(b'\x1b>\r* Training heading\r- item one\r- item two\r',lambda s:s['mode']=='org-mode')
        elif name=='process':
            action(b'\x1b[19~',lambda s:s['frames']==360 and s['value']==360*359//2)
            command='python3 '+str(ROOT/'benchmarks/interactive/training-producer.py')+' compile'
            action(b'\x1bxcompile\r\x01\x0b'+command.encode()+b'\r',lambda s:s['compilation_status']=='finished' and 'training diagnostic' in s['compilation_output'])
        elif name=='magit':
            action(b'\x15\x1bxmagit-status\r'+str(repo).encode()+b'\r',lambda s:s['buffer']=='magit: repository')
            action(b'\x1bxmagit-log-current\r',lambda s:s['mode']=='magit-log-mode')
            action(b'q',lambda s:s['mode']=='magit-status-mode')
            action(b'\x1bxmagit-stage-modified\r')
            assert len(git('diff','--cached','--name-only').splitlines())==5
            action(b'\x1bxmagit-unstage-all\r')
            assert not git('diff','--cached','--name-only').strip()
            action(b'\x1bxmagit-jump-to-unstaged\rn\t',lambda s:'@@' in s['text'])
            action(b'g',lambda s:s['mode']=='magit-status-mode')
    finally:session.close()
    checks[name]=recorded
    print('Training scenario',name,'passed',flush=True)
lock=json.loads((ROOT/'benchmarks/sources.json').read_text());spec=lock['elisp-benchmarks']
archive=ROOT/'cache/sources'/('elisp-benchmarks-'+spec['version']+'.tar')
if hashlib.sha256(archive.read_bytes()).hexdigest()!=spec['sha256']:raise SystemExit('Benchmark checksum mismatch')
suite=base/'elisp-benchmarks';suite.mkdir(exist_ok=True)
subprocess.run(['tar','-xf',str(archive),'--strip-components=1','-C',str(suite)],check=True)
selector='elb-bytecomp\\|elb-pcase\\|elb-smie\\|elb-scroll\\|inclist\\|map-closure\\|pack-unpack'
env.update(LLVM_PROFILE_FILE=str(profiles/'benchmark-%m-%p.profraw'),BENCHMARK_SUITE=str(suite),BENCHMARK_SELECTOR=selector,BENCHMARK_RUNS='1',BENCHMARK_RESULT=str(base/'training-benchmarks.json'))
with (base/'training-benchmarks.log').open('w') as log:
    subprocess.run([str(a.bundle/'bin/emacs'),'-Q','--batch','-l',str(ROOT/'benchmarks/runtime.el')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
print('Benchmark training passed',flush=True)
counts={};groups={}
for name in targets:
    raw=sorted(profiles.glob(name+'-*.profraw'))
    if not raw:raise RuntimeError('Missing profile for '+name)
    groups[name]=base/(name+'.profdata')
    subprocess.run(['llvm-profdata-23','merge','-o',str(groups[name]),*map(str,raw)],check=True)
    detail=subprocess.check_output(['llvm-profdata-23','show',str(groups[name])],text=True)
    counts[name]=int(re.search(r'^Total count: (\d+)',detail,re.M)[1])
weights,shares=weights_for_counts(counts,targets)
merged=ROOT/'build/merged.profdata'
subprocess.run(['llvm-profdata-23','merge','-o',str(merged),*[f'--weighted-input={weights[n]},{groups[n]}' for n in targets]],check=True)
summary=subprocess.check_output(['llvm-profdata-23','show',str(merged)],text=True)
(base/'profile-summary.txt').write_text(summary)
scripts=['scripts/training_input.py','scripts/prepare-workload-packages.py','scripts/pgo-train.py','scripts/profile_weights.py','scripts/pty_driver.py','benchmarks/interactive/training.el','benchmarks/interactive/training-producer.py','benchmarks/files.el','benchmarks/runtime.el']
(base/'provenance.json').write_text(json.dumps({'build':info,'configuration':'generic built-in and locked Magit scenarios only; no user configuration or held-out inputs','group_execution_counts':counts,'target_share_units':targets,'group_merge_weights':weights,'actual_execution_shares':shares,'benchmark_sources':lock,'benchmark_selector':selector,'corpus_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in corpus.iterdir()},'training_script_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in scripts},'scenario_checks':checks,'profile_sha256':hashlib.sha256(merged.read_bytes()).hexdigest()},indent=2)+'\n')
print(summary,flush=True)
print('Profile shares:',json.dumps(shares),flush=True)
