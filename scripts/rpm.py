#!/usr/bin/env python3
"""Wrap the verified portable archive in an RPM without modifying its payload."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
dist = ROOT / 'dist'
bundle = ROOT / (ROOT / 'build/current-bundle').read_text().strip()
info = json.loads((bundle / 'BUILD-INFO.json').read_text())
if info['cpu_baseline'] != 'x86-64-v3':
    raise SystemExit('RPM spec requires an x86-64-v3 build')
archive = dist / ('emacs-' + info['emacs'] + '-linux-x86-64-v3.tar.zst')
expected = archive.with_name(archive.name + '.sha256').read_text().split()[0]
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise SystemExit('Portable archive checksum mismatch')

with tempfile.TemporaryDirectory(prefix='rpm-', dir=ROOT / 'build') as tmp:
    top = pathlib.Path(tmp)
    (top / 'SOURCES').mkdir()
    shutil.copy2(archive, top / 'SOURCES' / archive.name)
    subprocess.run(['rpmbuild', '-bb', '--define', '_topdir ' + str(top),
                    '--define', 'emacs_version ' + info['emacs'],
                    str(ROOT / 'packaging/emacs-nox.spec')], check=True)
    products = list((top / 'RPMS/x86_64').glob('*.rpm'))
    if len(products) != 1:
        raise SystemExit('Expected exactly one binary RPM')
    rpm = dist / products[0].name
    shutil.copy2(products[0], rpm)
    digest = hashlib.sha256(rpm.read_bytes()).hexdigest()
    rpm.with_name(rpm.name + '.sha256').write_text(digest + '  ' + rpm.name + '\n')
    requires = subprocess.check_output(['rpm', '-qp', '--requires', str(rpm)], text=True)
    rpm.with_name(rpm.name + '.requires.txt').write_text(requires)
    (ROOT / 'build/current-rpm').write_text(str(rpm.relative_to(ROOT)) + '\n')
    print(rpm)
