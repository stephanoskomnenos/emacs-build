#!/usr/bin/env python3
"""Build static dependencies and a dynamically glibc-linked terminal Emacs."""
import argparse
import fcntl
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
from dependencies import build_dependencies, run_command, source as extract_source, toolchain_env

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = pathlib.Path(os.environ.get('EMACS_BUILD_ROOT', ROOT / 'build')).resolve()
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--rebuild', action='store_true', help='replace the selected Emacs stage; keep dependency cache')
a = p.parse_args()
manifest = json.loads((ROOT / 'sources.json').read_text())
jobs = os.environ.get('JOBS', str(len(os.sched_getaffinity(0))))
lto = os.environ.get('LTO', '1') == '1'
profile_mode = os.environ.get('PGO', 'off')
if profile_mode not in ('off', 'generate', 'use', 'cs-generate', 'cs-use'):
    raise RuntimeError('PGO must be off, generate, use, cs-generate or cs-use')
compiler = subprocess.check_output(['clang-23', '--version'], text=True).splitlines()[0]
packages = subprocess.check_output(['dpkg-query', '-W'], text=True)
dependency_settings = (str(lto) + compiler + packages + (ROOT / 'scripts/linux/dependencies.py').read_text()
                  + (ROOT / 'containers/Containerfile').read_text())
build_settings = dependency_settings + pathlib.Path(__file__).read_text()
identity = hashlib.sha256((json.dumps(manifest, sort_keys=True) + build_settings).encode()).hexdigest()[:12]
dependency_manifest = {name: spec for name, spec in manifest.items() if name != 'emacs'}
dependency_id = hashlib.sha256((json.dumps(dependency_manifest, sort_keys=True) + dependency_settings).encode()).hexdigest()[:12]
work = BUILD / identity
dependency_work = ROOT / 'build/dependencies' / dependency_id
prefix = dependency_work / 'prefix'
logs = work / 'logs'
logs.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, **toolchain_env(prefix, lto))
dependency_work.mkdir(parents=True, exist_ok=True)
with (dependency_work / '.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    build_dependencies(dependency_manifest, dependency_work, env, jobs)


def run(cmd, cwd, log, extra=None):
    return run_command(cmd, cwd, log, env, extra)


def source(name):
    return extract_source(name, manifest, work)


src = source('emacs')
variant = 'llvm-' + profile_mode
cs = profile_mode in ('cs-generate', 'cs-use')
if cs and not lto:
    raise RuntimeError('CSPGO requires ThinLTO')
normal_profile = BUILD / 'merged.profdata'
profile = pathlib.Path(os.environ.get('PROFILE_FILE', str(
    BUILD / ('combined.profdata' if profile_mode == 'cs-use' else 'merged.profdata')))).resolve()
if profile_mode in ('use', 'cs-use') and not profile.is_file():
    raise RuntimeError('Missing merged profile: ' + str(profile))
if cs and not normal_profile.is_file():
    raise RuntimeError('Missing ordinary profile: ' + str(normal_profile))
if cs or profile_mode == 'use':
    provenance = json.loads((BUILD / 'pgo-training/provenance.json').read_text())
    trained = provenance['build']
    if (trained['sources']['emacs']['sha256'] != manifest['emacs']['sha256'] or
            trained['compiler'] != compiler or trained['cflags'] != env['CFLAGS'] or
            provenance['profile_sha256'] != hashlib.sha256(normal_profile.read_bytes()).hexdigest()):
        raise RuntimeError('Ordinary profile does not match this source/toolchain; retrain in this build root')
pgo_flags = (' -fprofile-generate=' + str(work / 'profiles') if profile_mode == 'generate' else
             ' -fprofile-use=' + str(profile) if profile_mode in ('use', 'cs-use') else '')
compile_pgo_flags = pgo_flags
if cs:
    # Identical CS-ready prelink bitcode preserves ThinLTO promoted names.
    # The frontend flag also marks raw profiles as IR+CS; link-only setup does not.
    compile_pgo_flags = ' -fprofile-use=' + str(normal_profile) + ' -Xclang -fprofile-instrument=csllvm'
    if profile_mode == 'cs-generate':
        pgo_flags = ' -fprofile-use=' + str(normal_profile) + ' -fcs-profile-generate=' + str(work / 'cs-profiles')
    variant += '-' + hashlib.sha256(normal_profile.read_bytes()).hexdigest()[:12]
if profile_mode in ('use', 'cs-use'):
    variant += '-' + hashlib.sha256(profile.read_bytes()).hexdigest()[:12]
obj = work / ('emacs-build-' + variant)
log = logs / ('emacs-' + variant + '.log')
stage = work / ('stage-' + variant)
if a.rebuild:
    for directory in (obj, stage):
        if directory.exists():
            shutil.rmtree(directory)
    (work / ('emacs-' + variant + '.done')).unlink(missing_ok=True)
obj.mkdir(exist_ok=True)
options = ['--prefix=/opt/emacs', '--without-all', '--without-x', '--without-native-compilation',
           '--with-modules', '--with-threads', '--with-file-notification=inotify',
           '--with-gnutls', '--with-libgmp', '--with-xml2', '--with-sqlite3',
           '--with-tree-sitter', '--with-zlib', '--with-dbus', '--with-compress-install',
           '--disable-build-details', '--disable-gc-mark-trace']
if not (work / ('emacs-' + variant + '.done')).exists():
    if not (src / 'configure').exists():
        run(['sh', 'autogen.sh', 'autoconf'], src, log)
    run([str(src / 'configure'), *options], obj, log,
        {'LDFLAGS': env['LDFLAGS'] + ' -Wl,--exclude-libs,ALL' + (' -Wl,--save-temps' if lto else '') + pgo_flags, 'LIBS': '-lm',
         'emacs_cv_tputs_lib': '-lncursesw',
         'CFLAGS': env['CFLAGS'].replace('-fPIC', '-fPIE') + compile_pgo_flags})
    run(['make', '-j' + jobs], obj, log)
    run(['make', 'install', 'DESTDIR=' + str(stage)], obj, log)
    (work / ('emacs-' + variant + '.done')).touch()
if lto:
    if not list((obj / 'src').glob('*.index.bc')) or not list((obj / 'src').glob('*.3.import.bc')):
        raise RuntimeError('Missing lld ThinLTO link output')
    print('PASS: lld ThinLTO link output', flush=True)
if profile_mode in ('use', 'cs-use') and lto:
    ir = subprocess.check_output(['llvm-dis-23', str(obj / 'src/bytecode.o.0.preopt.bc'), '-o', '-'], text=True)
    if 'function_entry_count' not in ir or 'ProfileSummary' not in ir:
        raise RuntimeError('Missing LLVM profile metadata in bytecode interpreter')
    print('PASS: LLVM profile counts and summary in bytecode interpreter', flush=True)
if profile_mode == 'cs-use':
    generate_obj = work / ('emacs-build-llvm-cs-generate-' + hashlib.sha256(normal_profile.read_bytes()).hexdigest()[:12])
    # If the instrumented build is present, catch the promoted-name mismatch
    # that motivated the identical prelink recipe. Source-package rebuilds may omit it.
    if generate_obj.is_dir():
        for filename in ('marker.o', 'regex-emacs.o', 'search.o', 'eval.o', 'bytecode.o', 'alloc.o'):
            if hashlib.sha256((obj / 'src' / filename).read_bytes()).digest() != hashlib.sha256((generate_obj / 'src' / filename).read_bytes()).digest():
                raise RuntimeError('CS prelink bitcode differs: ' + filename)
    ir = subprocess.check_output(['llvm-dis-23', str(obj / 'src/marker.o.4.opt.bc'), '-o', '-'], text=True)
    if 'CSProfileSummary' not in ir:
        raise RuntimeError('Missing applied CS profile summary')
    print('PASS: context-sensitive profile applied with stable prelink bitcode', flush=True)
bundle = stage / 'opt/emacs'
# Emacs embeds absolute data and dump paths; resolve the launcher even through
# user-created symlinks and pass the relocated installation explicitly.
launcher = bundle / 'bin/emacs'
if launcher.is_symlink():
    launcher.unlink()
version = manifest['emacs'].get('emacs_version', manifest['emacs']['version'])
execdir = next((bundle / 'libexec/emacs' / version).iterdir()).relative_to(bundle)
dump = next((bundle / execdir).glob('emacs-*.pdmp')).name
launcher.write_text(f'''#!/bin/sh
set -eu
self=$(readlink -f -- "$0")
root=$(dirname -- "$(dirname -- "$self")")
export EMACSDATA="${{EMACSDATA-$root/share/emacs/{version}/etc}}"
export EMACSDOC="${{EMACSDOC-$root/share/emacs/{version}/etc}}"
export EMACSLOADPATH="${{EMACSLOADPATH-$root/share/emacs/{version}/lisp}}"
export EMACSPATH="${{EMACSPATH-$root/{execdir}}}"
exec "$root/bin/emacs-{version}" --dump-file="$root/{execdir}/{dump}" "$@"
''')
launcher.chmod(0o755)
info = {'emacs': manifest['emacs']['version'], 'sources': manifest,
        'compiler': compiler, 'dependency_build_id': dependency_id,
        'glibc': subprocess.check_output(['getconf', 'GNU_LIBC_VERSION'], text=True).strip(),
        'configure': options, 'lto': lto, 'pgo': profile_mode,
        'profile_sha256': hashlib.sha256(profile.read_bytes()).hexdigest() if profile_mode in ('use', 'cs-use') else None, 'build_id': identity,
        'compile_profile_sha256': hashlib.sha256(normal_profile.read_bytes()).hexdigest() if cs else None,
        'emacs_cflags': env['CFLAGS'].replace('-fPIC', '-fPIE') + compile_pgo_flags,
        'profile_link_flags': pgo_flags,
        'cpu_baseline': 'x86-64-v3', 'cflags': env['CFLAGS'], 'ldflags': env['LDFLAGS'],
        'packages': packages}
(bundle / 'BUILD-INFO.json').write_text(json.dumps(info, indent=2) + '\n')
# Stable, explicit stage entries; relative symlinks work both on host and in /work.
entry = BUILD / 'bundles' / profile_mode
entry.parent.mkdir(parents=True, exist_ok=True)
entry.unlink(missing_ok=True)
entry.symlink_to(os.path.relpath(bundle, entry.parent), target_is_directory=True)
print('Bundle staged at ' + str(bundle), flush=True)
