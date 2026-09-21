"""Paired compile/link flags for macOS Clang ordinary and context-sensitive PGO."""
import os
import shlex
import subprocess
from pathlib import Path


def compiler_tools():
    prefix = os.environ.get('EMACS_LLVM_ROOT')
    if not prefix:
        raise RuntimeError('Set EMACS_LLVM_ROOT to the prebuilt LLVM installation')
    bin_dir = Path(prefix) / 'bin'
    # Name the linker kind explicitly so the driver forwards Mach-O LLD options.
    return str(bin_dir / 'clang'), str(bin_dir / 'llvm-profdata'), [
        '-fuse-ld=lld', '--ld-path=' + str(bin_dir / 'ld64.lld')]


def build_environment(lto=True):
    clang, _, linker = compiler_tools()
    tools = Path(clang).parent
    sdk = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()
    flags = '-O2 -g0 -isysroot ' + shlex.quote(sdk)
    if lto:
        flags += ' -flto=thin'
    return dict(CC=clang, CXX=str(tools / 'clang++'), OBJC=clang,
                AR=str(tools / 'llvm-ar'), RANLIB=str(tools / 'llvm-ranlib'),
                NM=str(tools / 'llvm-nm'), CFLAGS=flags, CXXFLAGS=flags,
                OBJCFLAGS=flags, LDFLAGS=flags + ' ' + shlex.join(linker))


def profile_flags(mode, build, raw):
    build, raw = Path(build), Path(raw)
    normal = '-fprofile-use=' + str(build / 'merged.profdata')
    strict = '-Werror=profile-instr-out-of-date'
    if mode == 'off':
        return [], []
    if mode == 'generate':
        flags = ['-fprofile-generate=' + str(raw)]
        return flags, flags
    if mode == 'use':
        return [normal, strict], [normal, strict]
    # Keep prelink bitcode identical between CS collection and final use.
    compile_flags = [normal, '-Xclang', '-fprofile-instrument=csllvm',
                     # Mach-O needs this variable before LTO symbol resolution.
                     # Keep the bootstrap path identical in both CS stages;
                     # training overrides it with LLVM_PROFILE_FILE.
                     '-Xclang', '-fprofile-instrument-path=' + str(build / 'cs-bootstrap/default_%m.profraw'),
                     strict]
    if mode == 'cs-generate':
        # Load the static profile runtime before ThinLTO resolves live globals.
        # Otherwise its late reference to the filename can follow its removal.
        return compile_flags, [normal, '-fcs-profile-generate=' + str(raw),
                               '-Wl,-u,___llvm_profile_runtime']
    if mode == 'cs-use':
        combined = str(build / 'combined.profdata')
        return compile_flags, ['-fprofile-use=' + combined, strict]
    raise ValueError('Unknown PGO mode: ' + mode)


if __name__ == '__main__':
    import sys
    for name, value in build_environment(lto='--no-lto' not in sys.argv).items():
        print('export ' + name + '=' + shlex.quote(value))
