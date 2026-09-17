#!/usr/bin/env python3
"""Build static dependencies and a dynamically glibc-linked terminal Emacs."""
import hashlib
import json
import os
import pathlib
import shutil
import shlex
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'sources.json').read_text())
jobs = os.environ.get('JOBS', '6')
lto = os.environ.get('LTO', '1') == '1'
llvm = os.environ.get('TOOLCHAIN', 'gcc') == 'llvm'
profile_mode = os.environ.get('PGO', 'off')
if profile_mode not in ('off', 'generate', 'use') or (profile_mode != 'off' and not llvm):
    raise RuntimeError('PGO must be off, or generate/use with TOOLCHAIN=llvm')
cc = 'clang-23 --gcc-toolchain=/usr/local' if llvm else 'gcc'
cxx = 'clang++-23 --gcc-toolchain=/usr/local' if llvm else 'g++'
ar = 'llvm-ar-23' if llvm else 'gcc-ar'
ranlib = 'llvm-ranlib-23' if llvm else 'gcc-ranlib'
compiler = subprocess.check_output(shlex.split(cc) + ['--version'], text=True).splitlines()[0]
gcc_version = subprocess.check_output(['gcc', '-dumpfullversion'], text=True).strip()
expected_compiler = json.loads((ROOT / 'toolchain-sources.json').read_text())['gcc']['version']
if gcc_version != expected_compiler:
    raise RuntimeError(f'Expected GCC {expected_compiler}, found {gcc_version}')
identity = hashlib.sha256((json.dumps(manifest, sort_keys=True) + str(lto)
                          + compiler + pathlib.Path(__file__).read_text()
                          + (ROOT / 'containers/Containerfile').read_text()).encode()).hexdigest()[:12]
work = ROOT / 'build' / identity
prefix = work / 'deps'
logs = work / 'logs'
logs.mkdir(parents=True, exist_ok=True)
prefix.mkdir(exist_ok=True)
env = dict(os.environ)
lto_flags = (' -flto=thin' if llvm else ' -flto=' + jobs) if lto else ''
linker_flags = ' --ld-path=/usr/bin/ld.lld-23' if llvm else ''
env.update(CC=cc, CXX=cxx, AR=ar, RANLIB=ranlib,
           CFLAGS='-O2 -g0 -fPIC -march=x86-64-v3 -mtune=generic' + lto_flags,
           CXXFLAGS='-O2 -g0 -fPIC -march=x86-64-v3 -mtune=generic' + lto_flags,
           CPPFLAGS='-I' + str(prefix / 'include'),
           LDFLAGS='-L' + str(prefix / 'lib') + ' -Wl,-z,relro,-z,now' + lto_flags + linker_flags,
           PKG_CONFIG_PATH='',
           PKG_CONFIG_LIBDIR=str(prefix / 'lib/pkgconfig') + ':' + str(prefix / 'share/pkgconfig'),
           PKG_CONFIG='pkg-config --static', LC_ALL='C.UTF-8', TZ='UTC')

def run(cmd, cwd, log, extra=None):
    print('  ' + ' '.join(map(str, cmd)), flush=True)
    actual = env.copy()
    if extra:
        actual.update(extra)
    with log.open('a') as out:
        result = subprocess.run(list(map(str, cmd)), cwd=cwd, env=actual, stdout=out, stderr=subprocess.STDOUT)
    if result.returncode:
        print('\n'.join(log.read_text(errors='replace').splitlines()[-65:]), file=sys.stderr)
        raise RuntimeError('Build failed; see ' + str(log))

def source(name):
    s = manifest[name]
    archive = ROOT / 'cache/sources' / (name + '-' + s['version'] + '.tar')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != s['sha256']:
        raise RuntimeError('Source checksum mismatch: ' + name)
    dst = work / 'src' / name
    if not dst.exists():
        dst.mkdir(parents=True)
        subprocess.run(['tar', '-xf', str(archive), '--strip-components=1', '-C', str(dst)], check=True)
    return dst

recipes = {
    'ncurses': ['--without-shared', '--without-debug', '--without-ada', '--without-cxx-binding',
                '--enable-widec', '--enable-pc-files', '--with-pkg-config-libdir=' + str(prefix / 'lib/pkgconfig'),
                '--with-terminfo-dirs=/etc/terminfo:/lib/terminfo:/usr/share/terminfo',
                '--with-default-terminfo-dir=/usr/share/terminfo'],
    'gmp': ['--disable-shared', '--enable-static', '--enable-fat', '--build=x86_64-pc-linux-gnu'],
    'nettle': ['--disable-shared', '--enable-static', '--disable-documentation', '--disable-openssl'],
    'libunistring': ['--disable-shared', '--enable-static'],
    'libidn2': ['--disable-shared', '--enable-static', '--disable-doc', '--disable-nls', '--with-libunistring-prefix=' + str(prefix)],
    'gnutls': ['--disable-shared', '--enable-static', '--disable-doc', '--disable-tests',
               '--disable-tools', '--disable-cxx', '--disable-nls',
               '--with-included-libtasn1', '--without-p11-kit', '--without-tpm', '--without-tpm2',
               '--without-brotli', '--without-zstd', '--with-default-trust-store-file=/etc/ssl/certs/ca-certificates.crt'],
    'libxml2': ['--disable-shared', '--enable-static', '--without-python', '--without-lzma', '--without-iconv'],
    'sqlite': ['--disable-shared', '--enable-static'],
}

for name in ['ncurses', 'zlib', 'gmp', 'nettle', 'libunistring', 'libidn2', 'gnutls', 'libxml2', 'sqlite', 'tree-sitter']:
    src = source(name)
    log = logs / (name + '.log')
    stamp = work / (name + '.done')
    if stamp.exists():
        print(name + ': cached', flush=True)
        continue
    print(name + ': building', flush=True)
    if name == 'tree-sitter':
        run(['make', '-j' + jobs, 'libtree-sitter.a', 'AR=' + ar, 'RANLIB=' + ranlib], src, log)
        (prefix / 'include/tree_sitter').mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / 'libtree-sitter.a', prefix / 'lib')
        shutil.copy2(src / 'lib/include/tree_sitter/api.h', prefix / 'include/tree_sitter')
        pc = f'prefix={prefix}\nlibdir=${{prefix}}/lib\nincludedir=${{prefix}}/include\nName: tree-sitter\nDescription: incremental parser\nVersion: {manifest[name]["version"]}\nLibs: -L${{libdir}} -ltree-sitter\nCflags: -I${{includedir}}\n'
        (prefix / 'lib/pkgconfig/tree-sitter.pc').write_text(pc)
    else:
        options = ['--static'] if name == 'zlib' else recipes[name]
        extra = None
        # GMP 6.3's configure probes predate GCC 15's default C23 semantics.
        if name == 'gmp':
            extra = {'CFLAGS': env['CFLAGS'] + ' -std=gnu17'}
        run(['./configure', '--prefix=' + str(prefix), '--libdir=' + str(prefix / 'lib'), *options], src, log, extra)
        run(['make', '-j' + jobs], src, log)
        targets = ['install.libs', 'install.includes'] if name == 'ncurses' else ['install']
        run(['make', *targets], src, log)
    stamp.touch()

# GnuTLS uses compiler atomic helpers. Ship their code, not a libatomic.so dependency.
atomic = pathlib.Path(subprocess.check_output(['gcc', '-print-file-name=libatomic.a'], text=True).strip())
if not atomic.is_file():
    raise RuntimeError('Compiler static atomic runtime missing')
shutil.copy2(atomic, prefix / 'lib/libatomic.a')

src = source('emacs')
variant = ('llvm-' + profile_mode) if llvm else 'gcc'
profile = pathlib.Path(os.environ.get('PROFILE_FILE', str(work / 'merged.profdata'))).resolve()
if profile_mode == 'use' and not profile.is_file():
    raise RuntimeError('Missing merged profile: ' + str(profile))
pgo_flags = (' -fprofile-generate=' + str(work / 'profiles') if profile_mode == 'generate' else
             ' -fprofile-use=' + str(profile) if profile_mode == 'use' else '')
if profile_mode == 'use':
    variant += '-' + hashlib.sha256(profile.read_bytes()).hexdigest()[:12]
obj = work / ('emacs-build-' + variant)
obj.mkdir(exist_ok=True)
log = logs / ('emacs-' + variant + '.log')
stage = work / ('stage-' + variant)
options = ['--prefix=/opt/emacs', '--without-all', '--without-x', '--without-native-compilation',
           '--with-modules', '--with-threads', '--with-file-notification=inotify',
           '--with-gnutls', '--with-libgmp', '--with-xml2', '--with-sqlite3',
           '--with-tree-sitter', '--with-zlib', '--with-compress-install',
           '--disable-build-details', '--disable-gc-mark-trace', '--without-small-ja-dic']
if not (work / ('emacs-' + variant + '.done')).exists():
    if not (src / 'configure').exists():
        run(['sh', 'autogen.sh', 'autoconf'], src, log)
    run([str(src / 'configure'), *options], obj, log,
        {'LDFLAGS': env['LDFLAGS'] + ' -Wl,--exclude-libs,ALL' + (' -Wl,--save-temps' if llvm and lto else ' -flto-report' if lto else '') + pgo_flags, 'LIBS': '-lm',
         'emacs_cv_tputs_lib': '-lncursesw',
         'CFLAGS': env['CFLAGS'].replace('-fPIC', '-fPIE') + pgo_flags})
    run(['make', '-j' + jobs], obj, log)
    run(['make', 'install', 'DESTDIR=' + str(stage)], obj, log)
    (work / ('emacs-' + variant + '.done')).touch()
# Slim GCC LTO objects require the linker plugin; retain evidence from the build.
if lto and llvm:
    if not list((obj / 'src').glob('*.index.bc')) or not list((obj / 'src').glob('*.3.import.bc')):
        raise RuntimeError('Missing lld ThinLTO link output')
    print('PASS: lld ThinLTO link output', flush=True)
elif lto:
    sections = subprocess.check_output(['readelf', '-SW', str(obj / 'src/emacs.o')], text=True)
    if '.gnu.lto_' not in sections or '[WPA] # of input files:' not in log.read_text(errors='replace'):
        raise RuntimeError('Missing GCC LTO object or whole-program analysis evidence')
    print('PASS: GCC LTO object sections and linker WPA report', flush=True)
if llvm and profile_mode == 'use' and lto:
    ir = subprocess.check_output(['llvm-dis-23', str(obj / 'src/bytecode.o.0.preopt.bc'), '-o', '-'], text=True)
    if 'function_entry_count' not in ir or 'ProfileSummary' not in ir:
        raise RuntimeError('Missing LLVM profile metadata in bytecode interpreter')
    print('PASS: LLVM profile counts and summary in bytecode interpreter', flush=True)
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
        'compiler': compiler,
        'glibc': subprocess.check_output(['getconf', 'GNU_LIBC_VERSION'], text=True).strip(),
        'configure': options, 'lto': lto, 'pgo': profile_mode,
        'profile_sha256': hashlib.sha256(profile.read_bytes()).hexdigest() if profile_mode == 'use' else None, 'build_id': identity,
        'cpu_baseline': 'x86-64-v3', 'cflags': env['CFLAGS'], 'ldflags': env['LDFLAGS'],
        'packages': subprocess.check_output(['dpkg-query', '-W'], text=True)}
(bundle / 'BUILD-INFO.json').write_text(json.dumps(info, indent=2) + '\n')
(ROOT / 'build/current-bundle').write_text(str(bundle.relative_to(ROOT)) + '\n')
print('Bundle staged at ' + str(bundle), flush=True)
