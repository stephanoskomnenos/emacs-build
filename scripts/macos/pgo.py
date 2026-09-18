"""Paired compile/link flags for macOS Clang ordinary and context-sensitive PGO."""
import os
from pathlib import Path
import subprocess


def compiler_tools():
    prefix = os.environ.get('EMACS_LLVM_ROOT')
    if prefix:
        bin_dir = Path(prefix) / 'bin'
        # The linker kind must be 'lld': an absolute -fuse-ld value makes the
        # Darwin driver forward Apple's libLTO options instead of LLD options.
        return str(bin_dir / 'clang'), str(bin_dir / 'llvm-profdata'), [
            '-fuse-ld=lld', '--ld-path=' + str(bin_dir / 'ld64.lld')]
    def xcrun(tool):
        return subprocess.check_output(['xcrun', '--find', tool], text=True).strip()
    return xcrun('clang'), xcrun('llvm-profdata'), []


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
