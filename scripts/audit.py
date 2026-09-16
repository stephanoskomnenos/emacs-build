#!/usr/bin/env python3
"""Audit every shipped ELF, not only the main executable."""
import json
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(sys.argv[1]).resolve()
allowed = {'libc.so.6', 'libm.so.6', 'libdl.so.2', 'libpthread.so.0',
           'librt.so.1', 'libutil.so.1', 'libanl.so.1', 'ld-linux-x86-64.so.2'}
report = []
for f in sorted(root.rglob('*')):
    if f.is_symlink() or not f.is_file():
        continue
    with f.open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            continue
    dynamic = subprocess.check_output(['readelf', '-dW', str(f)], text=True)
    needed = re.findall(r'\(NEEDED\).*\[(.*?)\]', dynamic)
    unexpected = set(needed) - allowed
    if unexpected:
        raise SystemExit(f'{f}: unexpected dynamic dependencies: {unexpected}')
    if re.search(r'\((?:RPATH|RUNPATH)\)', dynamic):
        raise SystemExit(f'{f}: unexpected runtime search path')
    symbols = subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(f)], text=True)
    versions = {tuple(map(int, v.split('.'))) for v in re.findall(r'@GLIBC_([0-9.]+)', symbols)}
    if any(v > (2, 41) for v in versions):
        raise SystemExit(f'{f}: exceeds glibc 2.41 baseline')
    if 'GLIBC_PRIVATE' in symbols:
        raise SystemExit(f'{f}: references private glibc ABI')
    report.append({'file': str(f.relative_to(root)), 'needed': needed,
                   'max_glibc': '.'.join(map(str, max(versions))) if versions else None})
if not report:
    raise SystemExit('No ELF binaries found')
print(json.dumps(report, indent=2))
