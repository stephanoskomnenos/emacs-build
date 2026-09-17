#!/usr/bin/env python3
"""Check paired Apple tools before compiling dependencies."""
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
base = Path(os.environ.get('EMACS_BUILD_ROOT', ROOT / 'build/macos')).resolve() / 'toolchain'
base.mkdir(parents=True, exist_ok=False)
def xcrun(*args):
    return subprocess.check_output(['xcrun', *args], text=True).strip()
clang = xcrun('--find', 'clang')
profdata = xcrun('--find', 'llvm-profdata')
source = base / 'probe.m'
source.write_text('#import <Foundation/Foundation.h>\nint main(int argc, char **argv) {\n'
                  '  @autoreleasepool { NSLog(@"PGO probe: %d", argc); }\n  return 0;\n}\n')
flags = [clang, '-isysroot', xcrun('--sdk', 'macosx', '--show-sdk-path'), '-O2', '-g0', '-flto=thin']
subprocess.run([*flags, '-fprofile-generate', str(source), '-framework', 'Foundation', '-o', str(base / 'generate')], check=True)
subprocess.run([str(base / 'generate')], env=dict(os.environ, LLVM_PROFILE_FILE=str(base / 'probe-%m-%p.profraw')), check=True)
profile = base / 'probe.profdata'
subprocess.run([profdata, 'merge', '-o', str(profile), *map(str, base.glob('*.profraw'))], check=True)
summary = subprocess.check_output([profdata, 'show', '--detailed-summary', str(profile)], text=True)
match = re.search(r'^Total count: (\d+)', summary, re.M)
if not match or int(match[1]) == 0:
    raise SystemExit('Profile execution counts are unavailable')
subprocess.run([*flags, '-fprofile-use=' + str(profile), '-Werror=profile-instr-out-of-date',
                '-S', '-emit-llvm', str(source), '-o', str(base / 'probe.ll')], check=True)
ir = (base / 'probe.ll').read_text()
if 'function_entry_count' not in ir or 'ProfileSummary' not in ir:
    raise SystemExit('Apple Clang did not consume the generated profile')
report = dict(compiler=subprocess.check_output([clang, '--version'], text=True),
              profdata=xcrun('llvm-profdata', '--version'), sdk=xcrun('--show-sdk-version'),
              objective_c_thinlto_pgo=True, profile_summary=summary)
(base / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if os.environ.get('GITHUB_OUTPUT'):
    identity = dict(compiler=report['compiler'], sdk=report['sdk'], architecture=os.uname().machine,
                    system=subprocess.check_output(['sw_vers', '-buildVersion'], text=True).strip())
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write('identity=' + digest + '\n')
# Retain only the small diagnostic report.
for path in base.iterdir():
    if path.name != 'result.json':
        path.unlink()
