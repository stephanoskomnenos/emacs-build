#!/usr/bin/env python3
"""Held-out real-PTY regression scenarios; never collects PGO profiles."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pty_driver import Session

ROOT=Path(__file__).resolve().parents[2]
BUILD=Path(os.environ.get('EMACS_BUILD_ROOT', ROOT/'build')).resolve()
p=argparse.ArgumentParser()
p.add_argument('bundle',type=Path)
p.add_argument('--label',required=True)
p.add_argument('--runs',type=int,default=7)
p.add_argument('--cpu',type=int,default=0)
p.add_argument('--workspace',type=Path,default=BUILD/'interactive-validation')
a=p.parse_args()
if a.runs<1:p.error('--runs must be positive')
a.bundle=a.bundle.resolve();a.workspace=a.workspace.resolve()
info=json.loads((a.bundle/'BUILD-INFO.json').read_text())
if info.get('pgo') in ('generate','cs-generate'):raise SystemExit('Validation must never run an instrumented binary')
os.sched_setaffinity(0,{a.cpu})
spec_path=ROOT/'benchmarks/interactive/validation.json'
spec=json.loads(spec_path.read_text())
a.workspace.mkdir(parents=True,exist_ok=True)
values=list(range(spec['rows']));random.Random(spec['seed']).shuffle(values)
text_path=a.workspace/'held-out.txt';json_path=a.workspace/'held-out.json'
text_path.write_text(''.join(f'item-{i} description=验证 value={v}\n' for i,v in enumerate(values)))
json_path.write_text(json.dumps({'items':[{'value':v,'label':'测试-'+str(v)} for v in values]},ensure_ascii=False))
env=dict(os.environ,GIT_AUTHOR_DATE='2025-01-02T03:04:05Z',GIT_COMMITTER_DATE='2025-01-02T03:04:05Z',GIT_CEILING_DIRECTORIES=str(ROOT),GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',WORKLOAD_PACKAGES=str(BUILD/'workload-packages/paths.json'),HOME=str(a.workspace/'home'),WORKLOAD_SPEC=str(spec_path),WORKLOAD_TEXT=str(text_path),WORKLOAD_JSON=str(json_path),WORKLOAD_PRODUCER=str(ROOT/'benchmarks/interactive/producer.py'))
Path(env['HOME']).mkdir(exist_ok=True)
for key in ('LLVM_PROFILE_FILE','EMACSLOADPATH','EMACSDATA','EMACSDOC','EMACSPATH','LD_LIBRARY_PATH'):
    env.pop(key,None)
runs=[]
for index in range(a.runs+1):
    repository=a.workspace/f'{a.label}-{index}-repo'
    if repository.exists():shutil.rmtree(repository)
    repository.mkdir()
    def git(*args):
        return subprocess.check_output(['git','-C',str(repository),*args],env=env,stderr=subprocess.STDOUT,text=True)
    git('init','-q','-b','main');git('config','user.name','Workload Fixture');git('config','user.email','fixture@example.invalid')
    git('config','commit.gpgsign','false')
    for n in range(spec['git_files']):
        (repository/f'module-{n}.el').write_text(''.join(f'(defvar fixture-{n}-{i} {i})\n' for i in range(spec['git_lines'])))
    git('add','.');git('commit','-qm','Initial fixture')
    for n in range(spec['git_commits']):
        path=repository/f'module-{n}.el';path.write_text(path.read_text()+f'; history {n}\n')
        git('add','.');git('commit','-qm',f'Fixture revision {n}')
    for n in range(spec['git_files']):
        path=repository/f'module-{n}.el';path.write_text(path.read_text().replace(' 12)',' 92831)')+f'; working change {n}\n')
    session=Session(a.bundle/'bin/emacs',a.workspace/f'{a.label}-{index}',ROOT/'benchmarks/interactive/observer.el',env)
    result={}
    try:
        def action(name,keys,check):
            measurement=session.action(keys)
            if not check(measurement['state']):raise RuntimeError(f'{name}: invalid result {measurement}')
            result[name]={'seconds':measurement['seconds'],'state':{k:v for k,v in measurement['state'].items() if k!='text'},'text_sha256':hashlib.sha256(measurement['state']['text'].encode()).hexdigest()}
            return measurement['state']
        action('acknowledgement-only',b'',lambda s:True)
        action('open-file',b'\x18\x06'+str(text_path).encode()+b'\r',lambda s:s['buffer']=='held-out.txt' and s['size']==len(text_path.read_text()))
        action('new-buffer',b'\x18bpgo-edit\r\x1bxtext-mode\r',lambda s:s['mode']=='text-mode')
        typed=spec['typing_text']*spec['typing_repeats']
        action('typing-burst',typed.encode(),lambda s:s['text']==typed)
        action('delete',b'\x7f',lambda s:s['text']==typed[:-1])
        action('undo',b'\x1f',lambda s:s['text']==typed)
        action('isearch',b'\x1b<\x13editing\r',lambda s:s['point']==typed.index('editing')+len('editing')+1)
        action('minibuffer-completion',b'\x1b<\x1bxforward-cha\t\r',lambda s:s['point']==2)
        action('regexp',b'\x1b[17~',lambda s:s['value']==sum(values)*spec['regexp_repeats'])
        action('json',b'\x1b[18~',lambda s:s['value']==sum(values)*spec['json_repeats'])
        action('process-json',b'\x1b[19~',lambda s:s['frames']==spec['process_frames'] and s['value']==spec['process_frames']*(spec['process_frames']-1)//2)
        action('allocation-gc',b'\x1b[20~',lambda s:s['value']==spec['gc_repeats']*spec['gc_items'])
        action('magit-status',b'\x15\x1bxmagit-status\r'+str(repository).encode()+b'\r',lambda s:s['mode']=='magit-status-mode' and s['buffer']=='magit: '+repository.name and 'Unstaged changes' in s['text'])
        action('magit-expand',b'\x1bxmagit-jump-to-unstaged\rn\t',lambda s:s['mode']=='magit-status-mode' and 'module-' in s['text'] and '@@' in s['text'])
        action('magit-stage',b'\x1bxmagit-stage-modified\r',lambda s:s['mode']=='magit-status-mode')
        assert len(git('diff','--cached','--name-only').splitlines())==spec['git_files']
        action('magit-unstage',b'\x1bxmagit-unstage-all\r',lambda s:s['mode']=='magit-status-mode')
        assert not git('diff','--cached','--name-only').strip()
        action('magit-log',b'\x1bxmagit-log-current\r',lambda s:s['mode']=='magit-log-mode' and 'Fixture revision' in s['text'])
        action('magit-revision',b'\r',lambda s:s['mode']=='magit-revision-mode')
        result['magit-workflow']={'seconds':sum(result[k]['seconds'] for k in ('magit-status','magit-expand','magit-stage','magit-unstage','magit-log','magit-revision'))}
        action('return-to-edit',b'\x18bpgo-edit\r',lambda s:s['buffer']=='pgo-edit')
        # Held-out Evil editing: same broad behavior as training, with a
        # different command order and a different starting position.
        action('evil-enable',b'\x1b[23~',lambda s:s['evil_state']=='normal')
        action('evil-normal',b'Gk0',lambda s:s['evil_state']=='normal')
        action('evil-motion',b'0wwbllh',lambda s:s['evil_state']=='normal')
        action('evil-insert',b'iValidation edit\x1b',lambda s:s['evil_state']=='normal')
        action('evil-operator-position',b'0w',lambda s:s['evil_state']=='normal')
        action('evil-operator',b'daw',lambda s:s['evil_state']=='normal')
        action('evil-change-position',b'0w',lambda s:s['evil_state']=='normal')
        action('evil-change',b'ciwheld-out\x1b',lambda s:s['evil_state']=='normal')
        action('evil-yank-paste',b'yyGpk',lambda s:s['evil_state']=='normal')
        action('evil-visual-char',b'0vllly',lambda s:s['evil_state']=='normal')
        action('evil-visual-line',b'0Vjy',lambda s:s['evil_state']=='normal')
        action('evil-undo-redo',b'u\x12',lambda s:s['evil_state']=='normal')
        action('evil-search-forward',b'/held-out\r',lambda s:s['evil_state']=='normal')
        action('evil-search-backward',b'?held-out\r',lambda s:s['evil_state']=='normal')
        # Separate stop-and-wait latency from queued typing throughput.
        latency=[]
        before=session.action(b'\x1b>')['state']['size']
        for n in range(40):
            m=session.action(b'z')
            assert m['state']['size']==before+n+1
            latency.append(m['seconds'])
        result['typing-latency']={'seconds':statistics.median(latency),'samples':latency}
    finally:session.close()
    (a.workspace/f'{a.label}-{index}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(a.label,index,{k:round(v['seconds']*1000,3) for k,v in result.items()},flush=True)
    if index:runs.append(result)
report={'label':a.label,'build':{k:v for k,v in info.items() if k!='packages'},'cpu':a.cpu,'warmup_runs':1,'runs':runs,'validation_sha256':hashlib.sha256(spec_path.read_bytes()).hexdigest(),'medians':{name:statistics.median(run[name]['seconds'] for run in runs) for name in runs[0]}}
(a.workspace/f'{a.label}-summary.json').write_text(json.dumps(report,indent=2)+'\n')
