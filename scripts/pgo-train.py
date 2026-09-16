#!/usr/bin/env python3
"""Train LLVM PGO with generic terminal sessions, never the user's configuration."""
import argparse
import hashlib
import json
import os
import pathlib
import pty
import shutil
import re
import math
import select
import signal
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('bundle', type=pathlib.Path)
p.add_argument('--sessions', type=int, default=8)
a = p.parse_args()
base = ROOT / 'build/pgo-training'
corpus = base / 'corpus'
profiles = base / 'profiles'
for d in (corpus, profiles, base / 'home'): d.mkdir(parents=True, exist_ok=True)
if list(profiles.glob('*.profraw')):
    raise SystemExit('Training profiles already exist; use a fresh build/pgo-training directory')
info = json.loads((a.bundle / 'BUILD-INFO.json').read_text())
if info.get('pgo') != 'generate': raise SystemExit('An instrumented build is required')
source = a.bundle.resolve().parents[2] / 'src/emacs'
for source_name, target_name in [('src/buffer.c','buffer.c'), ('lisp/files.el','files.el'),
                                  ('etc/ORG-NEWS','org-news.org'), ('etc/NEWS','news.txt')]:
    shutil.copy2(source / source_name, corpus / target_name)
initdir = base / 'home/.emacs.d'
initdir.mkdir(exist_ok=True)
(initdir / 'early-init.el').write_text('(setq package-enable-at-startup nil)\n')
(initdir / 'init.el').write_text("(setq inhibit-startup-screen t)\n"
    "(dolist (library '(project xref compile recentf savehist icomplete)) (require library))\n"
    "(icomplete-mode 1)\n")
for iteration in range(a.sessions):
    env = dict(os.environ, HOME=str(base / 'home'), TERM='xterm-256color', LC_ALL='C.UTF-8',
               LLVM_PROFILE_FILE=str(profiles / 'session-%m-%p.profraw'), PGO_CORPUS=str(corpus))
    for key in ('EMACSLOADPATH','EMACSDATA','EMACSDOC','EMACSPATH','LD_LIBRARY_PATH'):
        env.pop(key, None)
    binary = str(a.bundle.resolve() / 'bin/emacs')
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(base / 'home')
        os.execve(binary, [binary, '--init-directory=' + str(initdir), '-nw', '-l', str(ROOT / 'benchmarks/train.el')], env)
    output = bytearray(); deadline = time.monotonic() + 180; status = None
    try:
        while time.monotonic() < deadline:
            if select.select([fd], [], [], 0.1)[0]:
                try: output.extend(os.read(fd, 65536))
                except OSError: pass
            done, code = os.waitpid(pid, os.WNOHANG)
            if done:
                status = os.waitstatus_to_exitcode(code); break
        if status is None:
            os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
        (base / f'train-{iteration}.log').write_bytes(output)
        if status != 0: raise SystemExit(f'Training session {iteration} failed')
    finally: os.close(fd)
    print('Training session', iteration + 1, 'passed', flush=True)
# Complement interactive training with a locked, byte-compiled benchmark subset.
spec = json.loads((ROOT / 'benchmarks/sources.json').read_text())['elisp-benchmarks']
archive = ROOT / 'cache/sources' / ('elisp-benchmarks-' + spec['version'] + '.tar')
if hashlib.sha256(archive.read_bytes()).hexdigest() != spec['sha256']:
    raise SystemExit('Benchmark archive checksum mismatch')
suite = base / 'elisp-benchmarks'
suite.mkdir(exist_ok=True)
subprocess.run(['tar','-xf',str(archive),'--strip-components=1','-C',str(suite)],check=True)
selector = 'elb-bytecomp\\|elb-pcase\\|elb-smie\\|elb-scroll\\|inclist\\|map-closure\\|pack-unpack'
env.update(LLVM_PROFILE_FILE=str(profiles / 'benchmark-%m-%p.profraw'), BENCHMARK_SUITE=str(suite), BENCHMARK_SELECTOR=selector, BENCHMARK_RUNS='1',
           BENCHMARK_RESULT=str(base / 'training-benchmarks.json'))
with (base / 'training-benchmarks.log').open('w') as output:
    subprocess.run([binary,'-Q','--batch','-l',str(ROOT/'benchmarks/runtime.el')],
                   env=env,check=True,stdout=output,stderr=subprocess.STDOUT,timeout=600)
print('Benchmark training passed', flush=True)
raw = sorted(profiles.glob('*.profraw'))
if len(raw) < a.sessions: raise SystemExit('Missing session profile data')
merged = ROOT / 'build/merged.profdata'
# Normalize group execution counts so tight microbenchmark loops do not drown
# out interactive file workflows. The target mix is 75% interactive, 25% suite.
groups = []
counts = []
for group in ('session', 'benchmark'):
    grouped = base / (group + '.profdata')
    subprocess.run(['llvm-profdata-23','merge','-o',str(grouped),
                    *map(str, sorted(profiles.glob(group + '-*.profraw')))],check=True)
    detail = subprocess.check_output(['llvm-profdata-23','show',str(grouped)],text=True)
    counts.append(int(re.search(r'^Total count: (\d+)',detail,re.M)[1]))
    groups.append(grouped)
weights = [max(1, math.ceil(3 * counts[1] / counts[0])), 1]
subprocess.run(['llvm-profdata-23','merge','-o',str(merged),
                *[f'--weighted-input={w},{g}' for w,g in zip(weights,groups)]],check=True)
summary = subprocess.check_output(['llvm-profdata-23','show',str(merged)], text=True)
(base / 'profile-summary.txt').write_text(summary)
(base / 'provenance.json').write_text(json.dumps({'build':info, 'sessions':a.sessions,
    'configuration':'generic built-in libraries only; no user configuration',
    'group_execution_counts':dict(zip(('interactive','benchmark'),counts)),
    'group_merge_weights':dict(zip(('interactive','benchmark'),weights)), 'benchmark_source':spec, 'benchmark_selector':selector,
    'corpus_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in corpus.iterdir()},
    'training_script_sha256':hashlib.sha256((ROOT/'benchmarks/train.el').read_bytes()).hexdigest(),
    'profile_sha256':hashlib.sha256(merged.read_bytes()).hexdigest()},indent=2)+'\n')
print(summary)
