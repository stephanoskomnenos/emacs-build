#!/usr/bin/env python3
"""Install the pinned upstream macOS LLVM binaries outside Homebrew."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if sys.platform != 'darwin':
    raise SystemExit('Requires macOS')
spec = json.loads((ROOT / 'scripts/macos/llvm.json').read_text())
archive = ROOT / 'cache/llvm' / spec['url'].rsplit('/', 1)[1]
archive.parent.mkdir(parents=True, exist_ok=True)
if not archive.exists():
    part = archive.with_suffix('.part')
    subprocess.run(['curl', '-fL', '--retry', '3', '--connect-timeout', '30',
                    '--max-time', '1200', spec['url'], '-o', str(part)], check=True)
    part.replace(archive)
digest = hashlib.sha256()
with archive.open('rb') as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
if digest.hexdigest() != spec['sha256']:
    raise SystemExit('LLVM archive checksum mismatch')
prefix = Path(os.environ['RUNNER_TEMP']) / 'emacs-llvm'
prefix.mkdir(parents=True, exist_ok=True)
subprocess.run(['tar', '-xf', str(archive), '--strip-components=1', '-C', str(prefix)], check=True)
for tool in ('clang', 'ld64.lld', 'llvm-profdata', 'llvm-ar', 'llvm-ranlib'):
    subprocess.run([str(prefix / 'bin' / tool), '--version'], check=True)
with open(os.environ['GITHUB_ENV'], 'a') as output:
    output.write(f'EMACS_LLVM_ROOT={prefix}\nLLVM_PROFDATA={prefix}/bin/llvm-profdata\n')
print(f'Installed verified LLVM {spec["version"]}: {prefix}')
