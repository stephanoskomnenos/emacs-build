#!/usr/bin/env python3
"""Reject non-system dylibs in every shipped Mach-O, including helper executables."""
import argparse
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument('app', type=Path)
a = p.parse_args()
found = {}
for path in sorted(a.app.rglob('*')):
    if not path.is_file():
        continue
    kind = subprocess.check_output(['file', '-b', str(path)], text=True)
    if 'Mach-O' not in kind:
        continue
    deps = [line.strip().split(' (compatibility')[0]
            for line in subprocess.check_output(['otool', '-L', str(path)], text=True).splitlines()[1:]]
    bad = [dep for dep in deps if not dep.startswith(('/usr/lib/', '/System/Library/'))]
    if bad:
        raise SystemExit(f'{path}: non-system dynamic dependencies: {bad}')
    found[str(path.relative_to(a.app))] = deps
if 'Contents/MacOS/Emacs' not in found:
    raise SystemExit('Missing Mach-O Emacs executable')
print(json.dumps(found, indent=2))
