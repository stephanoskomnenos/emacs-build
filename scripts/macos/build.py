#!/usr/bin/env python3
"""Build independent Cocoa stages using the ebuild dependency installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sources import load_sources
from pgo import compiler_tools, profile_flags, build_environment

ROOT = Path(__file__).resolve().parents[2]
BUILD = Path(os.environ.get('EMACS_BUILD_ROOT', ROOT / 'build/macos')).resolve()
p = argparse.ArgumentParser()
p.add_argument('mode', choices=['off', 'generate', 'use', 'cs-generate', 'cs-use'])
p.add_argument('--rebuild', action='store_true', help='replace only the selected build stage')
a = p.parse_args()
if sys.platform != 'darwin':
    raise SystemExit('Requires macOS with Xcode command-line tools')
spec = json.loads((ROOT / 'sources.json').read_text())['emacs']
archive = ROOT / 'cache/sources' / f"emacs-{spec['version']}.tar"
if hashlib.sha256(archive.read_bytes()).hexdigest() != spec['sha256']:
    raise SystemExit('Emacs source checksum mismatch')
stage = BUILD / a.mode
if a.rebuild and stage.exists():
    shutil.rmtree(stage)
if stage.exists():
    p.error(f'{stage} already exists; use --rebuild to restart this stage')
stage.mkdir(parents=True, exist_ok=False)
cs = a.mode in ('cs-generate', 'cs-use')
# A fixed source/configure path preserves ThinLTO local symbol identities.
source = BUILD / 'cs-source' if cs else stage / 'source'
if cs and source.exists():
    shutil.rmtree(source)
source.mkdir()
subprocess.run(['tar', '-xf', str(archive), '--strip-components=1', '-C', str(source)], check=True)
def xcrun(*args):
    return subprocess.check_output(['xcrun', *args], text=True).strip()
clang, profdata, linker_flags = compiler_tools()
toolchain = build_environment()
flags = toolchain['CFLAGS']
profile = BUILD / 'merged.profdata'
if a.mode in ('use', 'cs-generate', 'cs-use'):
    if not profile.is_file():
        raise SystemExit('Missing fresh training profile')
    provenance = json.loads((BUILD / 'pgo-training/provenance.json').read_text())
    trained = provenance['build']
    if (trained['source']['sha256'] != spec['sha256'] or
            trained['compiler'] != subprocess.check_output([clang, '--version'], text=True) or
            trained['sdk'] != xcrun('--show-sdk-version') or
            trained['extra_dependencies'] != load_sources('macos') or
            provenance['profile_sha256'] != hashlib.sha256(profile.read_bytes()).hexdigest()):
        raise SystemExit('Profile does not match this source/toolchain; retrain in this build root')
if a.mode == 'cs-use':
    cs_provenance = json.loads((BUILD / 'pgo-training-cs/provenance.json').read_text())
    if cs_provenance['compile_profile_sha256'] != hashlib.sha256(profile.read_bytes()).hexdigest():
        raise SystemExit('Ordinary profile changed since CS training')
    if cs_provenance['profile_sha256'] != hashlib.sha256((BUILD / 'cs.profdata').read_bytes()).hexdigest():
        raise SystemExit('CS profile changed since training')
    # Recreate the combined profile from the checked inputs, excluding stale merges.
    subprocess.run([profdata, 'merge', str(profile),
                    str(BUILD / 'cs.profdata'), '-o', str(BUILD / 'combined.profdata')], check=True)
compile_profile, link_profile = profile_flags(a.mode, BUILD, stage / 'bootstrap-profiles')
compile_flags = flags + ' ' + shlex.join(compile_profile)
link_flags = flags + ' ' + shlex.join(linker_flags + link_profile)
env = dict(os.environ, **toolchain)
env.update(CFLAGS=compile_flags, OBJCFLAGS=compile_flags,
           CPPFLAGS='-I/usr/local/include', LDFLAGS=link_flags + ' -L/usr/local/lib', PKG_CONFIG='pkgconf -static',
           PKG_CONFIG_LIBDIR='/usr/local/lib/pkgconfig:/usr/local/share/pkgconfig',
           LC_ALL='en_US.UTF-8')
for key in ('LLVM_PROFILE_FILE', 'CPATH', 'LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'PKG_CONFIG_PATH'):
    env.pop(key, None)
args = ['--prefix=' + str(BUILD / 'cs-install' if cs else stage / 'install'), '--disable-build-details', '--disable-gc-mark-trace',
        '--without-all', '--without-native-compilation', '--with-compress-install', '--with-file-notification=kqueue',
        '--with-libgmp', '--with-gnutls', '--with-modules', '--with-native-image-api', '--with-ns',
        '--with-threads', '--with-toolkit-scroll-bars', '--with-tree-sitter',
        '--with-xml2', '--with-zlib', '--with-sqlite3']
with (stage / 'build.log').open('w') as log:
    for command in [['./autogen.sh'], ['./configure', *args], ['make', '-j' + os.environ.get('JOBS', str(os.cpu_count() or 1))], ['make', 'install']]:
        print(shlex.join(command), flush=True)
        result = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            print((stage / 'build.log').read_text()[-24000:])
            raise SystemExit(result.returncode)
if cs:
    objects = ('marker.o', 'regex-emacs.o', 'search.o', 'eval.o', 'bytecode.o', 'alloc.o', 'nsterm.o')
    prelink = {name: hashlib.sha256((source / 'src' / name).read_bytes()).hexdigest() for name in objects}
    if a.mode == 'cs-use':
        collected = json.loads((BUILD / 'cs-generate/prelink-sha256.json').read_text())
        if prelink != collected:
            raise SystemExit('CS prelink bitcode changed between collection and use')
    (stage / 'prelink-sha256.json').write_text(json.dumps(prelink, indent=2) + '\n')
bundle = stage / 'bundle'
bundle.mkdir()
subprocess.run(['ditto', str(source / 'nextstep/Emacs.app'), str(bundle / 'Emacs.app')], check=True)
(bundle / 'bin').mkdir()
# Compatibility entry for shared PTY training; this is not shipped in the app.
wrapper = bundle / 'bin/emacs'
wrapper.write_text('#!/bin/sh\nexport LC_ALL=en_US.UTF-8\nexec "$(dirname "$0")/../Emacs.app/Contents/MacOS/Emacs" "$@"\n')
wrapper.chmod(0o755)
info = dict(platform='macOS', architecture=os.uname().machine, source=spec, pgo=a.mode,
            flags=compile_flags, link_flags=link_flags, source_directory=str(source), configure=args, extra_dependencies=load_sources('macos'), compiler=subprocess.check_output([clang, '--version'], text=True),
            profdata=subprocess.check_output([profdata, '--version'], text=True), sdk=xcrun('--show-sdk-version'),
            dependency_recipe='RadioNoiseE/ebuild@5f2e2c6229989d986f1072c7727a586d92bb8523',
            dependency_recipe_sha256=hashlib.sha256((ROOT / 'scripts/macos/dependencies.sh').read_bytes()).hexdigest())
if cs:
    info['compile_profile_sha256'] = hashlib.sha256(profile.read_bytes()).hexdigest()
if a.mode in ('use', 'cs-use'):
    final_profile = BUILD / 'combined.profdata' if cs else profile
    info['profile_sha256'] = hashlib.sha256(final_profile.read_bytes()).hexdigest()
(bundle / 'BUILD-INFO.json').write_text(json.dumps(info, indent=2) + '\n')
print(bundle)
