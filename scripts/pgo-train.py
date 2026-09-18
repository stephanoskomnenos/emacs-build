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
from training_fixtures import prepare
from training_scenarios import GROUPS, exercise

ROOT=Path(__file__).resolve().parents[1]
BUILD=Path(os.environ.get('EMACS_BUILD_ROOT',ROOT/'build')).resolve()
p=argparse.ArgumentParser();p.add_argument('bundle',type=Path)
p.add_argument('--check-workloads',action='store_true',help='Check PTY assertions with a non-instrumented build; never produce profiles')
p.add_argument('--restart',action='store_true',help='discard this training stage and its generated profiles before retraining')
a=p.parse_args()
a.bundle=a.bundle.resolve();info=json.loads((a.bundle/'BUILD-INFO.json').read_text())
if a.check_workloads:
    if info.get('pgo') in ('generate','cs-generate'):raise SystemExit('Use a non-instrumented build for workload checks')
elif info.get('pgo') not in ('generate','cs-generate'):raise SystemExit('An instrumented build is required')
cs=info.get('pgo')=='cs-generate'
base=BUILD/('workload-checks' if a.check_workloads else 'pgo-training-cs' if cs else 'pgo-training');profiles=base/'profiles';corpus=base/'corpus'
if a.restart:
    if base.exists():shutil.rmtree(base)
    if not a.check_workloads:
        for name in (('cs.profdata','combined.profdata') if cs else ('merged.profdata','cs.profdata','combined.profdata')):
            (BUILD/name).unlink(missing_ok=True)
        if os.environ.get('EMACS_TRAIN_GUI')=='1' and (BUILD/'gui-train').exists():
            shutil.rmtree(BUILD/'gui-train')
if base.exists():
    raise SystemExit('Training directory already exists; use --restart to rerun this stage')
for directory in (profiles,corpus,base/'home'):directory.mkdir(parents=True,exist_ok=True)
source=Path(os.environ.get('EMACS_TRAIN_SOURCE',a.bundle.parents[2]/'src/emacs'))
profdata=os.environ.get('LLVM_PROFDATA','llvm-profdata-23')
if cs and hashlib.sha256((BUILD/'merged.profdata').read_bytes()).hexdigest()!=info['compile_profile_sha256']:
    raise SystemExit('Ordinary profile changed since the CS instrumented build')
for original,target in [('src/buffer.c','buffer.c'),('lisp/files.el','files.el'),('etc/ORG-NEWS','org-news.org'),('etc/NEWS','news.txt')]:
    shutil.copy2(source/original,corpus/target)
print('Preparing workload packages',flush=True)
subprocess.run(['python3',str(ROOT/'scripts/prepare-workload-packages.py'),str(a.bundle)],check=True,timeout=660)
env=dict(os.environ,HOME=str(base/'home'),GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_CEILING_DIRECTORIES=str(ROOT),
         GIT_AUTHOR_DATE='2025-03-04T05:06:07Z',GIT_COMMITTER_DATE='2025-03-04T05:06:07Z',
         TRAIN_CORPUS=str(corpus),TRAIN_PACKAGES=str(BUILD/'workload-packages/paths.json'),
         TRAIN_PRODUCER=str(ROOT/'benchmarks/interactive/training-producer.py'))
env['TRAIN_BALANCED_GAP']='1' if cs else '0'
for key in ('LLVM_PROFILE_FILE','EMACSLOADPATH','EMACSDATA','EMACSDOC','EMACSPATH','LD_LIBRARY_PATH'):env.pop(key,None)
def git(repo,*args):
    return subprocess.check_output(['git','-C',str(repo),*args],env=env,stderr=subprocess.STDOUT,text=True)
fixtures=base/'fixtures'
repos=prepare(fixtures,env)
# Preserve outer shares: six groups at 12.5%, ELPA at 25% (before optional GUI).
targets={name:1 for name in GROUPS}
targets['benchmark']=2
checks={}
for group,names in GROUPS.items():
    for name in names:
        print('Starting training scenario',name,flush=True)
        session_env=dict(env,TRAIN_PROCESS_VARIANT=name.removeprefix('process-'))
        if not a.check_workloads:
            session_env['LLVM_PROFILE_FILE']=str(profiles/(name+'-%m-%p.profraw'))
        session=Session(a.bundle/'bin/emacs',base/name,ROOT/'benchmarks/interactive/training.el',session_env)
        try:
            checks[name]=exercise(name,session,corpus,fixtures,repos,git,ROOT/'benchmarks/interactive/training-producer.py')
        finally:session.close()
        print('Training scenario',name,'passed',flush=True)
if a.check_workloads:
    (base/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    print('All PTY workload assertions passed; no profiles generated',flush=True)
    raise SystemExit(0)
lock=json.loads((ROOT/'benchmarks/sources.json').read_text());spec=lock['elisp-benchmarks']
archive=ROOT/'cache/sources'/('elisp-benchmarks-'+spec['version']+'.tar')
if hashlib.sha256(archive.read_bytes()).hexdigest()!=spec['sha256']:raise SystemExit('Benchmark checksum mismatch')
suite=base/'elisp-benchmarks';suite.mkdir(exist_ok=True)
subprocess.run(['tar','-xf',str(archive),'--strip-components=1','-C',str(suite)],check=True)
selector='elb-bytecomp\\|elb-pcase\\|elb-smie\\|elb-scroll\\|inclist\\|map-closure\\|pack-unpack'
env.update(LLVM_PROFILE_FILE=str(profiles/'benchmark-%m-%p.profraw'),BENCHMARK_SUITE=str(suite),BENCHMARK_SELECTOR=selector,BENCHMARK_RUNS='1',BENCHMARK_RESULT=str(base/'training-benchmarks.json'))
with (base/'training-benchmarks.log').open('w') as log:
    print('Starting ELPA benchmarks (timeout: 600 seconds)',flush=True)
    subprocess.run([str(a.bundle/'bin/emacs'),'-Q','--batch','-l',str(ROOT/'benchmarks/runtime.el')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
print('Benchmark training passed',flush=True)
if os.environ.get('EMACS_TRAIN_GUI')=='1':
    print('Starting Cocoa GUI training',flush=True)
    targets['gui']=2
    subprocess.run(['python3',str(ROOT/'scripts/macos/gui.py'),'train',str(a.bundle)],
                   env=dict(env,TRAIN_FIXTURES=str(fixtures),LLVM_PROFILE_FILE=str(profiles/'gui-%m-%p.profraw')),check=True)
counts={};groups={};inner={}
def merge_case(name):
    raw=sorted(profiles.glob(name+'-*.profraw'))
    if not raw:raise RuntimeError('Missing profile for '+name)
    if cs:
        for path in raw:
            with path.open('rb') as stream: header=stream.read(16)
            if int.from_bytes(header[8:16],'little') & (3 << 56) != (3 << 56):
                raise RuntimeError('Raw profile lacks IR/CS flags: '+str(path))
    output=base/(name+'.profdata')
    subprocess.run([profdata,'merge','-o',str(output),*map(str,raw)],check=True)
    return output

def total_count(path):
    detail=subprocess.check_output([profdata,'show','--detailed-summary',*(['--showcs'] if cs else []),str(path)],text=True)
    return int(re.search(r'^Total count: (\d+)',detail,re.M)[1])

for group in targets:
    cases={name:merge_case(name) for name in GROUPS.get(group,[group])}
    subcounts={name:total_count(path) for name,path in cases.items()}
    subweights,subshares=weights_for_counts(subcounts,{name:1 for name in cases})
    groups[group]=base/(group+'-group.profdata')
    subprocess.run([profdata,'merge','-o',str(groups[group]),
                    *[f'--weighted-input={subweights[n]},{cases[n]}' for n in cases]],check=True)
    counts[group]=total_count(groups[group])
    inner[group]={'counts':subcounts,'weights':subweights,'shares':subshares}
if 'gui' in groups:
    gui_counts=subprocess.check_output([profdata,'show','--counts','--function=ns_draw_glyph_string',str(groups['gui'])],text=True)
    (base/'gui-profile.txt').write_text(gui_counts)
    blocks=re.findall(r'(?:Function count:|Block counts:)\s*(?:\[([^]]+)\]|(\d+))',gui_counts)
    if not any(int(n)>0 for values in blocks for value in values for n in re.findall(r'\d+',value)):
        raise RuntimeError('GUI profile did not exercise Cocoa glyph drawing')
weights,shares=weights_for_counts(counts,targets)
merged=BUILD/('cs.profdata' if cs else 'merged.profdata')
subprocess.run([profdata,'merge','-o',str(merged),*[f'--weighted-input={weights[n]},{groups[n]}' for n in targets]],check=True)
summary=subprocess.check_output([profdata,'show',*(['--showcs'] if cs else []),str(merged)],text=True)
(base/'profile-summary.txt').write_text(summary)
scripts=['scripts/training_fixtures.py','scripts/training_scenarios.py','scripts/prepare-workload-packages.py','scripts/pgo-train.py','scripts/profile_weights.py','scripts/pty_driver.py','benchmarks/interactive/training.el','benchmarks/interactive/training-producer.py','benchmarks/files.el','benchmarks/runtime.el']
if os.environ.get('EMACS_TRAIN_GUI')=='1':scripts+=['scripts/macos/gui.py','benchmarks/macos/gui.el','benchmarks/macos/training.el']
(base/'provenance.json').write_text(json.dumps({'build':info,'balanced_gap':cs,'compile_profile_sha256':info.get('compile_profile_sha256'),'configuration':'generic built-in and locked Magit scenarios only; no user configuration or held-out inputs','subscenario_profiles':inner,'group_execution_counts':counts,'target_share_units':targets,'group_merge_weights':weights,'actual_execution_shares':shares,'benchmark_sources':lock,'benchmark_selector':selector,'fixture_sha256':{str(f.relative_to(fixtures)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(fixtures.rglob('*')) if f.is_file() and '.git' not in f.parts},'corpus_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in corpus.iterdir()},'training_script_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in scripts},'scenario_checks':checks,'profile_sha256':hashlib.sha256(merged.read_bytes()).hexdigest()},indent=2)+'\n')
print(summary,flush=True)
print('Profile shares:',json.dumps(shares),flush=True)

if cs:
    subprocess.run([profdata,'merge',str(BUILD/'merged.profdata'),str(merged),'-o',str(BUILD/'combined.profdata')],check=True)
