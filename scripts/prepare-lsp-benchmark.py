#!/usr/bin/env python3
"""Copy a personal config for validation only; never change its original."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser()
p.add_argument('config', type=Path)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
base = root/'build/lsp-load'
original = a.config.expanduser().resolve()
target = base/'home/.emacs.d'
shutil.copytree(original, target, symlinks=True, ignore=shutil.ignore_patterns('.git', 'eln-cache'))
for path in target.rglob('*'):
    if path.is_symlink():
        link = path.readlink()
        if link.is_absolute() and link.is_relative_to(original):
            path.unlink()
            path.symlink_to(os.path.relpath(target/link.relative_to(original), path.parent))
(base/'config-hashes.json').write_text(json.dumps({
    name:hashlib.sha256((original/name).read_bytes()).hexdigest()
    for name in ['init.el', 'early-init.el', 'elpaca-lock.el']}, indent=2)+'\n')
wrapper = base/'emacs'
wrapper.write_text('#!/usr/bin/python3\nimport os,sys\n'
                  'os.execv("/bundle/bin/emacs",["/bundle/bin/emacs",'
                  '"--init-directory=/work/build/lsp-load/home/.emacs.d"]'
                  '+[x for x in sys.argv[1:] if x!="-Q"])\n')
wrapper.chmod(0o755)
fixture = base/'project'
fixture.mkdir(exist_ok=True)
subprocess.run(['git', 'init', '-q', str(fixture)], check=True)
for i in range(64):
    (fixture/f'file-{i}.txt').write_text(''.join(
        f'line {j}: diagnostic workload text\n' for j in range(512)))
