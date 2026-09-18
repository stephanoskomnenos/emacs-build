"""Paired compile/link flags for Apple Clang ordinary and context-sensitive PGO."""
from pathlib import Path


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
    compile_flags = [normal, '-Xclang', '-fprofile-instrument=csllvm', strict]
    if mode == 'cs-generate':
        return compile_flags, [normal, '-fcs-profile-generate=' + str(raw)]
    if mode == 'cs-use':
        combined = str(build / 'combined.profdata')
        return compile_flags, ['-fprofile-use=' + combined, strict]
    raise ValueError('Unknown PGO mode: ' + mode)
