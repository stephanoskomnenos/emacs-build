#!/usr/bin/env python3
"""Run genuine NS windows; alternate matched builds for warm-cache comparisons."""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
BUILD = Path(os.environ.get('EMACS_BUILD_ROOT', ROOT / 'build/macos')).resolve()
p = argparse.ArgumentParser()
p.add_argument('mode', choices=['train', 'compare', 'smoke'])
p.add_argument('bundle', type=Path)
p.add_argument('--baseline', type=Path)
p.add_argument('--runs', type=int, default=10)
a = p.parse_args()
base = BUILD / ('gui-' + a.mode)
base.mkdir(parents=True, exist_ok=True)
corpus = BUILD / 'pgo-training/corpus' if a.mode == 'train' else base / 'corpus'
if a.mode != 'train':
    corpus.mkdir(exist_ok=True)
    (corpus / 'held-out.el').write_text(';;; Held-out generated fixture -*- lexical-binding: t; -*-\n' +
        ''.join(f'(defun held-out-{i} (x) (+ x {i}))\n' for i in range(1800)))
    (corpus / 'held-out.org').write_text(''.join(f'* Section {i}\nSome held-out text-123 with *markup*.\n** Child\n- entry\n' for i in range(1600)))
    (corpus / 'held-out.txt').write_text('held-out record_123 searchable text\n' * 24000)
def run(bundle, label, index):
    info = json.loads((bundle / 'BUILD-INFO.json').read_text())
    if a.mode != 'train' and info['pgo'] == 'generate':
        raise RuntimeError('Instrumented builds cannot run validation')
    output = base / f'{index:02d}-{label}'
    output.mkdir()
    home = output / 'home'
    home.mkdir()
    env = dict(os.environ, HOME=str(home), GUI_MODE=a.mode, GUI_OUTPUT=str(output),
               GUI_CORPUS=str(corpus), GUI_APP=str(bundle / 'Emacs.app'), LC_ALL='en_US.UTF-8')
    for key in ('EMACSLOADPATH','EMACSDATA','EMACSDOC','EMACSPATH','DYLD_LIBRARY_PATH'):
        env.pop(key, None)
    if a.mode != 'train':
        env.pop('LLVM_PROFILE_FILE', None)
    binary = bundle / 'Emacs.app/Contents/MacOS/Emacs'
    with (output / 'emacs.log').open('w') as log:
        start = time.time()
        subprocess.run([str(binary), '-Q', '-l', str(ROOT / 'benchmarks/macos/gui.el')],
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    result = json.loads((output / 'result.json').read_text())
    result['gui-ready'] = (json.loads((output / 'ready.json').read_text())['time'] - start) * 1000
    shutil.rmtree(home)
    return result
if a.mode != 'compare':
    print(json.dumps(run(a.bundle.resolve(), a.mode, 0), indent=2))
else:
    if a.baseline is None:
        p.error('--baseline is required for compare')
    bundles = {'off': a.baseline.resolve(), 'use': a.bundle.resolve()}
    info = {label: json.loads((bundle / 'BUILD-INFO.json').read_text()) for label,bundle in bundles.items()}
    for key in ('source', 'compiler', 'sdk', 'architecture', 'dependency_recipe', 'extra_dependencies'):
        if info['off'][key] != info['use'][key]:
            raise RuntimeError('Unmatched builds: ' + key)
    if info['off']['pgo'] != 'off' or info['use']['pgo'] != 'use':
        raise RuntimeError('Expected off/use comparison')
    # Relocate both apps away from their build trees before measurements.
    with tempfile.TemporaryDirectory(prefix='emacs-ab-') as tmp:
        for label in bundles:
            relocated = Path(tmp) / label
            subprocess.run(['ditto',str(bundles[label]),str(relocated)],check=True)
            bundles[label] = relocated
        samples = {'off': [], 'use': []}
        for label in bundles:
            run(bundles[label], label, 0)  # Unrecorded warmup.
        for index in range(1, a.runs + 1):
            for label in (['off','use'] if index % 2 else ['use','off']):
                samples[label].append(run(bundles[label],label,index))
    summary = {}
    for metric in samples['off'][0]:
        medians = {label:statistics.median(s[metric] for s in values) for label,values in samples.items()}
        summary[metric] = dict(medians, improvement_percent=100*(1-medians['use']/medians['off']))
    report = dict(units='milliseconds', method='alternating warm-cache NS sessions; -Q fixed held-out fixtures; ready after first redisplay, before smoke checks; no personal configuration',
                  builds=info, samples=samples, summary=summary)
    (BUILD / 'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
