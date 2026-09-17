#!/usr/bin/env python3
"""Exercise training cancellation repeatedly without asynchronous C-g races."""
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pty_driver import Session
from training_input import cancel_minibuffer
ROOT=Path(__file__).resolve().parents[1]
BUILD=Path(os.environ.get('EMACS_BUILD_ROOT',ROOT/'build'))
p=argparse.ArgumentParser();p.add_argument('bundle',type=Path);a=p.parse_args()
base=BUILD/'cancel-regression';(base/'home').mkdir(parents=True,exist_ok=True)
env=dict(os.environ,HOME=str(base/'home'),TRAIN_PACKAGES=str(BUILD/'workload-packages/paths.json'))
for key in ('LLVM_PROFILE_FILE','EMACSLOADPATH','EMACSDATA','EMACSDOC','EMACSPATH','LD_LIBRARY_PATH'):env.pop(key,None)
affinities=[{min(os.sched_getaffinity(0))},set(os.sched_getaffinity(0))] if hasattr(os,'sched_getaffinity') else [None]
for affinity in affinities:
    pid=os.fork()
    if pid==0:
        if affinity is not None:os.sched_setaffinity(0,affinity)
        session=Session(a.bundle.resolve()/'bin/emacs',base/str(len(affinity) if affinity else 'default'),ROOT/'benchmarks/interactive/training.el',env)
        try:
            for _ in range(100):
                state=session.action(b'\x1bxbeginn\t\x1bOR')['state']
                assert state['minibuffer_depth']==1
                cancel_minibuffer(session)
                assert session.action(b'')['state']['minibuffer_depth']==0
        finally:session.close()
        print(f'PASS: 100 cancellations with {len(affinity) if affinity else "default"} allowed CPUs',flush=True)
        os._exit(0)
    _,status=os.waitpid(pid,0)
    if os.waitstatus_to_exitcode(status)!=0:raise SystemExit('Cancellation regression failed')
