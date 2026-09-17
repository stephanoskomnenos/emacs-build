#!/usr/bin/env python3
"""Reject non-system dylibs in every shipped Mach-O, including helper executables."""
import argparse
import json
import re
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument('app', type=Path)
a = p.parse_args()
found = {}
root = a.app.resolve()
static_libraries = re.compile(r'^lib(?:xml2|iconv|charset|intl|unistring|ncursesw?|tinfow?|z|gmp|nettle|hogweed|idn2|gnutls|sqlite3|tree-sitter)(?:[.-])')
for path in sorted(a.app.rglob('*')):
    if path.is_symlink() and (not path.exists() or not path.resolve().is_relative_to(root)):
        raise SystemExit(f'{path}: broken or external bundle symlink')
    if not path.is_file():
        continue
    with path.open('rb') as file:
        magic = file.read(4)
    if magic not in (bytes.fromhex(h) for h in ('feedface','cefaedfe','feedfacf','cffaedfe','cafebabe','bebafeca','cafebabf','bfbafeca')):
        continue
    deps = [line.strip().split(' (compatibility')[0]
            for line in subprocess.check_output(['otool', '-L', str(path)], text=True).splitlines()[1:]]
    bad = [dep for dep in deps if not dep.startswith(('/usr/lib/', '/System/Library/'))
           or static_libraries.match(Path(dep).name)]
    if bad:
        raise SystemExit(f'{path}: non-system dynamic dependencies: {bad}')
    found[str(path.relative_to(a.app))] = deps
if 'Contents/MacOS/Emacs' not in found:
    raise SystemExit('Missing Mach-O Emacs executable')
print(json.dumps(found, indent=2))
