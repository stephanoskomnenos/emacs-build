#!/usr/bin/env python3
"""Local Mach-O archive/LTO reproducer; run in the existing Clang 23 container.

The tiny archive models profile runtime symbol dependencies, not its behavior.
Successful linking is evidence about symbol resolution, not a macOS runtime test.
"""
import pathlib
import subprocess
import tempfile

with tempfile.TemporaryDirectory() as temporary:
    root = pathlib.Path(temporary)
    source = root / 'probe.c'
    source.write_text('int main(void) { return 0; }\n')
    runtime = root / 'runtime.c'
    runtime.write_text('int __llvm_profile_runtime;\n'
                       'extern const char __llvm_profile_filename[];\n'
                       'const char *runtime_profile_name = __llvm_profile_filename;\n')
    subprocess.run(['clang-23', '--target=arm64-apple-macos26', '-c', str(runtime),
                    '-o', str(root / 'runtime.o')], check=True)
    subprocess.run(['llvm-ar-23', 'rc', str(root / 'runtime.a'), str(root / 'runtime.o')], check=True)
    for standard in (False, True):
        compile_flags = (['-fcs-profile-generate=' + str(root / 'bootstrap')] if standard else
                         ['-Xclang', '-fprofile-instrument=csllvm', '-Xclang',
                          '-fprofile-instrument-path=' + str(root / 'bootstrap/default_%m.profraw')])
        subprocess.run(['clang-23', '--target=arm64-apple-macos26', '-O2', '-flto=thin',
                        *compile_flags, '-c', str(source), '-o', str(root / 'probe.o')], check=True)
        for early_runtime in (False, True):
            link_flags = ['-u', '___llvm_profile_runtime'] if early_runtime else []
            result = subprocess.run(['ld64.lld-23', '-arch', 'arm64', '-platform_version',
                                     'macos', '26.0', '26.0', '-e', '_main',
                                     '--cs-profile-generate',
                                     '--cs-profile-path=' + str(root / 'raw.profraw'),
                                     *link_flags, str(root / 'probe.o'), str(root / 'runtime.a'),
                                     '-o', str(root / 'macho')], text=True, capture_output=True)
            if early_runtime:
                assert result.returncode == 0, result.stderr
            else:
                assert result.returncode != 0 and '__llvm_profile_filename' in result.stderr, result.stderr
            print(f'standard={standard}, early_runtime={early_runtime}, exit={result.returncode}')
