#!/usr/bin/env python3
"""Check paired compiler tools before compiling dependencies."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from pgo import compiler_tools, profile_flags, build_environment

p = argparse.ArgumentParser()
p.add_argument('--cspgo', action='store_true', help='also verify CS generation and final-link profile use')
a = p.parse_args()
ROOT = Path(__file__).resolve().parents[2]
base = Path(os.environ.get('EMACS_BUILD_ROOT', ROOT / 'build/macos')).resolve() / 'toolchain'
# This directory contains only the disposable compiler probe and its report.
if base.exists():
    shutil.rmtree(base)
base.mkdir(parents=True, exist_ok=False)
def xcrun(*args):
    return subprocess.check_output(['xcrun', *args], text=True).strip()
clang, profdata, linker_flags = compiler_tools()
environment = build_environment()
archive_source = base / 'library.c'
archive_source.write_text('int library_value(void) { return 42; }\n')
archive_obj = base / 'library.o'
archive = base / 'libprobe.a'
subprocess.run([clang, *shlex.split(environment['CFLAGS']), '-c', str(archive_source), '-o', str(archive_obj)], check=True)
subprocess.run([environment['AR'], 'rcs', str(archive), str(archive_obj)], check=True)
subprocess.run([environment['RANLIB'], str(archive)], check=True)
subprocess.run([environment['NM'], str(archive)], check=True)
main = base / 'main.c'
main.write_text('int library_value(void); int main(void) { return library_value() != 42; }\n')
subprocess.run([clang, *shlex.split(environment['CFLAGS']), str(main), str(archive),
                *linker_flags, '-o', str(base / 'archive-probe')], check=True)
subprocess.run([str(base / 'archive-probe')], check=True)
source = base / 'probe.m'
source.write_text('#import <Foundation/Foundation.h>\nint main(int argc, char **argv) {\n'
                  '  @autoreleasepool { NSLog(@"PGO probe: %d", argc); }\n  return 0;\n}\n')
environment = build_environment()
flags = [clang, *shlex.split(environment['CFLAGS'])]
subprocess.run([*flags, *linker_flags, '-fprofile-generate', str(source), '-framework', 'Foundation', '-o', str(base / 'generate')], check=True)
subprocess.run([str(base / 'generate')], env=dict(os.environ, LLVM_PROFILE_FILE=str(base / 'probe-%m-%p.profraw')), check=True)
profile = base / 'merged.profdata'
subprocess.run([profdata, 'merge', '-o', str(profile), *map(str, base.glob('*.profraw'))], check=True)
summary = subprocess.check_output([profdata, 'show', '--detailed-summary', str(profile)], text=True)
match = re.search(r'^Total count: (\d+)', summary, re.M)
if not match or int(match[1]) == 0:
    raise SystemExit('Profile execution counts are unavailable')
subprocess.run([*flags, '-fprofile-use=' + str(profile), '-Werror=profile-instr-out-of-date',
                '-S', '-emit-llvm', str(source), '-o', str(base / 'probe.ll')], check=True)
ir = (base / 'probe.ll').read_text()
if 'function_entry_count' not in ir or 'ProfileSummary' not in ir:
    raise SystemExit('Clang did not consume the generated profile')
report = dict(compiler=subprocess.check_output([clang, '--version'], text=True),
              profdata=subprocess.check_output([profdata, '--version'], text=True), linker_flags=linker_flags, sdk=xcrun('--show-sdk-version'),
              objective_c_thinlto_pgo=True, profile_summary=summary)
(base / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
if a.cspgo:
    try:
        raw = base / 'cs-raw'
        raw.mkdir()
        obj = base / 'probe.o'
        compile_cs, link_cs = profile_flags('cs-generate', base, raw)
        subprocess.run([*flags, *compile_cs, '-c', str(source), '-o', str(obj)], check=True)
        bitcode_hash = hashlib.sha256(obj.read_bytes()).hexdigest()
        subprocess.run([*flags, *linker_flags, str(obj), *link_cs, '-framework', 'Foundation',
                        '-o', str(base / 'cs-generate')], check=True)
        subprocess.run([str(base / 'cs-generate')],
                       env=dict(os.environ, LLVM_PROFILE_FILE=str(raw / '%m-%p.profraw')), check=True)
        profiles = list(raw.glob('*.profraw'))
        if not profiles:
            raise RuntimeError('No CS raw profiles generated')
        for path in profiles:
            with path.open('rb') as stream:
                header = stream.read(16)
            if int.from_bytes(header[8:16], 'little') & (3 << 56) != (3 << 56):
                raise RuntimeError('Profile does not carry IR+CS flags')
        cs_profile = base / 'cs.profdata'
        subprocess.run([profdata, 'merge', '-o', str(cs_profile), *map(str, profiles)], check=True)
        cs_summary = subprocess.check_output([profdata, 'show', '--showcs', '--detailed-summary',
                                              str(cs_profile)], text=True)
        count = re.search(r'^Total count: (\d+)', cs_summary, re.M)
        if not count or int(count[1]) == 0:
            raise RuntimeError('No positive context-sensitive execution counts')
        subprocess.run([profdata, 'merge', str(profile), str(cs_profile),
                        '-o', str(base / 'combined.profdata')], check=True)
        compile_use, link_use = profile_flags('cs-use', base, raw)
        subprocess.run([*flags, *compile_use, '-c', str(source), '-o', str(obj)], check=True)
        if hashlib.sha256(obj.read_bytes()).hexdigest() != bitcode_hash:
            raise RuntimeError('CS generation/use prelink bitcode differs')
        # Print the tiny probe's IR after profile use inside the actual linker.
        # This catches toolchains that accept the flags but do not apply CS PGO.
        result = subprocess.run([*flags, *linker_flags, str(obj), *link_use, '-framework', 'Foundation',
                                 '-Wl,-mllvm,-print-after=pgo-instr-use',
                                 '-o', str(base / 'cs-use')], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (base / 'cs-link.log').write_text(result.stdout + result.stderr)
        result.check_returncode()
        if 'CSProfileSummary' not in result.stderr or 'function_entry_count' not in result.stderr:
            raise RuntimeError('Final link did not demonstrate CS profile application; see cs-link.log')
        subprocess.run([str(base / 'cs-use')], check=True)
        report.update(context_sensitive_pgo=True, cs_profile_summary=cs_summary)
    except (subprocess.CalledProcessError, RuntimeError) as error:
        report.update(context_sensitive_pgo=False, error=str(error))
        (base / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        raise SystemExit(f'Toolchain CSPGO probe failed: {error}. Disable cspgo to use ordinary PGO.')
(base / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if os.environ.get('GITHUB_OUTPUT'):
    spec = json.loads((ROOT / 'scripts/macos/llvm.json').read_text())
    normalized = {k: v.replace(os.environ['EMACS_LLVM_ROOT'], '/llvm').replace(
        xcrun('--sdk', 'macosx', '--show-sdk-path'), '/sdk') for k, v in environment.items()}
    identity = dict(llvm=spec['sha256'], sdk=report['sdk'], architecture=os.uname().machine,
                    deployment_target=os.environ.get('MACOSX_DEPLOYMENT_TARGET', ''), flags=normalized)
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write('identity=' + digest + '\n')
# Retain only the small diagnostic report.
for path in base.iterdir():
    if path.name not in ('result.json', 'cs-link.log'):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
