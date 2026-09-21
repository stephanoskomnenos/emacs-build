"""Linux static dependency recipes and toolchain flags; cache independently of Emacs."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def toolchain_env(prefix, lto):
    lto_flags = ' -flto=thin' if lto else ''
    return dict(CC='clang-23', CXX='clang++-23', AR='llvm-ar-23', RANLIB='llvm-ranlib-23',
                CFLAGS='-O2 -g0 -fPIC -march=x86-64-v3 -mtune=generic' + lto_flags,
                CXXFLAGS='-O2 -g0 -fPIC -march=x86-64-v3 -mtune=generic' + lto_flags,
                CPPFLAGS='-I' + str(prefix / 'include'),
                LDFLAGS='-L' + str(prefix / 'lib') + ' -Wl,-z,relro,-z,now' + lto_flags + ' --ld-path=/usr/bin/ld.lld-23',
                PKG_CONFIG_PATH='',
                PKG_CONFIG_LIBDIR=str(prefix / 'lib/pkgconfig') + ':' + str(prefix / 'share/pkgconfig'),
                PKG_CONFIG='pkg-config --static', LC_ALL='C.UTF-8', TZ='UTC')

def run_command(cmd, cwd, log, env, extra=None):
    print('  ' + ' '.join(map(str, cmd)), flush=True)
    actual = env.copy()
    if extra:
        actual.update(extra)
    with log.open('a') as out:
        result = subprocess.run(list(map(str, cmd)), cwd=cwd, env=actual, stdout=out, stderr=subprocess.STDOUT)
    if result.returncode:
        print('\n'.join(log.read_text(errors='replace').splitlines()[-65:]), file=sys.stderr)
        raise RuntimeError('Build failed; see ' + str(log))

def source(name, manifest, work):
    s = manifest[name]
    archive = ROOT / 'cache/sources' / (name + '-' + s['version'] + '.tar')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != s['sha256']:
        raise RuntimeError('Source checksum mismatch: ' + name)
    dst = work / 'src' / name
    stamp = dst / '.source-sha256'
    if not stamp.exists() or stamp.read_text() != s['sha256']:
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        subprocess.run(['tar', '-xf', str(archive), '--strip-components=1', '-C', str(dst)], check=True)
        stamp.write_text(s['sha256'])
    return dst


def build_dependencies(manifest, work, env, jobs):
    prefix = work / 'prefix'
    logs = work / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    prefix.mkdir(parents=True, exist_ok=True)
    cc, ar, ranlib = env['CC'], env['AR'], env['RANLIB']
    def run(cmd, cwd, log, extra=None):
        return run_command(cmd, cwd, log, env, extra)

    recipes = {
        'ncurses': ['--without-shared', '--without-debug', '--without-ada', '--without-cxx-binding',
                    '--disable-widec', '--enable-overwrite', '--enable-pc-files', '--with-pkg-config-libdir=' + str(prefix / 'lib/pkgconfig'),
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

    for name in ['ncurses', 'zlib', 'gmp', 'nettle', 'libunistring', 'libidn2', 'gnutls', 'libxml2', 'sqlite', 'tree-sitter', 'dbus']:
        log = logs / (name + '.log')
        stamp = work / (name + '.done')
        if stamp.exists():
            print(name + ': cached', flush=True)
            continue
        shutil.rmtree(work / 'src' / name, ignore_errors=True)
        src = source(name, manifest, work)
        print(name + ': building', flush=True)
        if name == 'dbus':
            obj = src / '_build'
            run(['meson', 'setup', str(obj), '--prefix=' + str(prefix), '--libdir=lib',
                 '--sysconfdir=/etc', '--localstatedir=/var', '--buildtype=plain',
                 '--default-library=static', '--auto-features=disabled', '--wrap-mode=nodownload',
                 '-Dmessage_bus=false', '-Dtools=false', '-Depoll=enabled',
                 '-Druntime_dir=/run', '-Dsystem_socket=/run/dbus/system_bus_socket'], src, log)
            run(['meson', 'compile', '-C', str(obj), '-j', jobs], src, log)
            run(['meson', 'install', '-C', str(obj)], src, log)
        elif name == 'tree-sitter':
            run(['make', '-j' + jobs, 'libtree-sitter.a', 'AR=' + ar, 'RANLIB=' + ranlib], src, log)
            (prefix / 'include/tree_sitter').mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / 'libtree-sitter.a', prefix / 'lib')
            shutil.copy2(src / 'lib/include/tree_sitter/api.h', prefix / 'include/tree_sitter')
            pc = f'prefix={prefix}\nlibdir=${{prefix}}/lib\nincludedir=${{prefix}}/include\nName: tree-sitter\nDescription: incremental parser\nVersion: {manifest[name]["version"]}\nLibs: -L${{libdir}} -ltree-sitter\nCflags: -I${{includedir}}\n'
            (prefix / 'lib/pkgconfig/tree-sitter.pc').write_text(pc)
        else:
            options = ['--static'] if name == 'zlib' else recipes[name]
            extra = None
            # GMP 6.3's configure probes require pre-C23 semantics.
            if name == 'gmp':
                extra = {'CFLAGS': env['CFLAGS'] + ' -std=gnu17'}
            run(['./configure', '--prefix=' + str(prefix), '--libdir=' + str(prefix / 'lib'), *options], src, log, extra)
            run(['make', '-j' + jobs], src, log)
            targets = ['install.libs', 'install.includes'] if name == 'ncurses' else ['install']
            run(['make', *targets], src, log)
        stamp.touch()
        shutil.rmtree(src)

    # GnuTLS uses compiler atomic helpers. Ship their code, not a libatomic.so dependency.
    atomic = pathlib.Path(subprocess.check_output([cc, '-print-file-name=libatomic.a'], text=True).strip())
    if not atomic.is_file():
        raise RuntimeError('Compiler static atomic runtime missing')
    if not (prefix / 'lib/libatomic.a').exists():
        shutil.copy2(atomic, prefix / 'lib/libatomic.a')


def dependency_identity(manifest, lto):
    packages = subprocess.check_output([
        'dpkg-query', '-W', '-f=${binary:Package}=${Version}\n',
        'clang-23', 'lld-23', 'llvm-23', 'libclang-rt-23-dev',
        'libgcc-14-dev', 'libstdc++-14-dev', 'libc6-dev', 'linux-libc-dev',
    ], text=True)
    inputs = {
        'sources': {name: spec['sha256'] for name, spec in manifest.items() if name != 'emacs'},
        'toolchain': sorted(packages.splitlines()),
        'flags': toolchain_env(pathlib.Path('/dependency-prefix'), lto),
        'recipe': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
    }
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:12]


if __name__ == '__main__':
    manifest = json.loads((ROOT / 'sources.json').read_text())
    print(dependency_identity(manifest, os.environ.get('LTO', '1') == '1'))
