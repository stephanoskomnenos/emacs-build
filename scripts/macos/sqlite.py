#!/usr/bin/env python3
"""Add the same pinned SQLite as Linux without invalidating the ebuild cache."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BUILD = Path(os.environ.get('EMACS_BUILD_ROOT', ROOT / 'build/macos')).resolve()
if sys.platform != 'darwin' or os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Requires a disposable macOS CI runner')
spec = json.loads((ROOT / 'sources.json').read_text())['sqlite']
work = BUILD / 'sqlite'
work.mkdir(parents=True, exist_ok=False)
archive = work / 'sqlite.tar.gz'
subprocess.run(['curl', '--fail', '--location', '--retry', '3', '--connect-timeout', '30',
                '--max-time', '600', '--silent', '--show-error', spec['url'], '-o', str(archive)], check=True)
if hashlib.sha256(archive.read_bytes()).hexdigest() != spec['sha256']:
    raise SystemExit('SQLite source checksum mismatch')
source = work / 'source'
source.mkdir()
subprocess.run(['tar', '-xf', str(archive), '--strip-components=1', '-C', str(source)], check=True)
env = dict(os.environ, CC='/usr/bin/clang', CFLAGS='-O2 -g0')
for key in ('LLVM_PROFILE_FILE', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS'):
    env.pop(key, None)
with (work / 'build.log').open('w') as log:
    for command in [['./configure', '--prefix=/usr/local', '--disable-shared', '--enable-static'],
                    ['make', '-j' + os.environ.get('JOBS', '3')], ['sudo', 'make', 'install']]:
        result = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            print((work / 'build.log').read_text()[-16000:])
            raise SystemExit(result.returncode)
if not Path('/usr/local/lib/libsqlite3.a').is_file() or list(Path('/usr/local/lib').glob('libsqlite3*.dylib')):
    raise SystemExit('Expected a static-only SQLite installation')
print('Installed static SQLite', spec['version'])
