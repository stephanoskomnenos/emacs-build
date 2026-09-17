#!/usr/bin/env python3
"""Build independent Cocoa stages using the ebuild dependency installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BUILD = Path(os.environ.get('EMACS_BUILD_ROOT', ROOT / 'build/macos')).resolve()
p = argparse.ArgumentParser()
p.add_argument('mode', choices=['off', 'generate', 'use'])
a = p.parse_args()
if sys.platform != 'darwin':
    raise SystemExit('Requires macOS with Xcode command-line tools')
spec = json.loads((ROOT / 'sources.json').read_text())['emacs']
archive = ROOT / 'cache/sources' / f"emacs-{spec['version']}.tar"
if hashlib.sha256(archive.read_bytes()).hexdigest() != spec['sha256']:
    raise SystemExit('Emacs source checksum mismatch')
stage = BUILD / a.mode
stage.mkdir(parents=True, exist_ok=False)
source = stage / 'source'
source.mkdir()
subprocess.run(['tar', '-xf', str(archive), '--strip-components=1', '-C', str(source)], check=True)
# The Darwin configure probe otherwise selects the non-wide ncurses library.
configure = source / 'configure.ac'
configure.write_text(''.join(line.replace('lncurses', 'lncursesw') if 'darwin' in line else line
                            for line in configure.read_text().splitlines(keepends=True)))
def xcrun(*args):
    return subprocess.check_output(['xcrun', *args], text=True).strip()
clang = xcrun('--find', 'clang')
flags = '-O2 -g0 -flto=thin -isysroot ' + shlex.quote(xcrun('--sdk', 'macosx', '--show-sdk-path'))
profile = BUILD / 'merged.profdata'
if a.mode == 'generate':
    flags += ' -fprofile-generate=' + str(stage / 'bootstrap-profiles')
elif a.mode == 'use':
    if not profile.is_file():
        raise SystemExit('Missing fresh training profile')
    flags += ' -fprofile-use=' + str(profile) + ' -Werror=profile-instr-out-of-date'
env = dict(os.environ, CC=clang, OBJC=clang, CFLAGS=flags, OBJCFLAGS=flags,
           LDFLAGS=flags, PKG_CONFIG='pkgconf -static',
           PKG_CONFIG_LIBDIR='/usr/local/lib/pkgconfig:/usr/local/share/pkgconfig',
           LC_ALL='en_US.UTF-8')
for key in ('LLVM_PROFILE_FILE', 'CPATH', 'LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'PKG_CONFIG_PATH'):
    env.pop(key, None)
args = ['--prefix=' + str(stage / 'install'), '--disable-build-details', '--disable-gc-mark-trace',
        '--without-all', '--with-compress-install', '--with-file-notification=kqueue',
        '--with-libgmp', '--with-gnutls', '--with-modules', '--with-native-image-api', '--with-ns',
        '--with-small-ja-dic', '--with-threads', '--with-toolkit-scroll-bars', '--with-tree-sitter',
        '--with-xml2', '--with-zlib']
with (stage / 'build.log').open('w') as log:
    for command in [['./autogen.sh'], ['./configure', *args], ['make', '-j' + os.environ.get('JOBS', '3')], ['make', 'install']]:
        print(shlex.join(command), flush=True)
        result = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            print((stage / 'build.log').read_text()[-24000:])
            raise SystemExit(result.returncode)
bundle = stage / 'bundle'
bundle.mkdir()
subprocess.run(['ditto', str(source / 'nextstep/Emacs.app'), str(bundle / 'Emacs.app')], check=True)
(bundle / 'bin').mkdir()
# Compatibility entry for shared PTY training; this is not shipped in the app.
wrapper = bundle / 'bin/emacs'
wrapper.write_text('#!/bin/sh\nexport LC_ALL=en_US.UTF-8\nexec "$(dirname "$0")/../Emacs.app/Contents/MacOS/Emacs" "$@"\n')
wrapper.chmod(0o755)
info = dict(platform='macOS', architecture=os.uname().machine, source=spec, pgo=a.mode,
            flags=flags, configure=args, compiler=subprocess.check_output([clang, '--version'], text=True),
            profdata=xcrun('llvm-profdata', '--version'), sdk=xcrun('--show-sdk-version'),
            dependency_recipe='RadioNoiseE/ebuild@5f2e2c6229989d986f1072c7727a586d92bb8523')
if a.mode == 'use':
    info['profile_sha256'] = hashlib.sha256(profile.read_bytes()).hexdigest()
(bundle / 'BUILD-INFO.json').write_text(json.dumps(info, indent=2) + '\n')
print(bundle)
