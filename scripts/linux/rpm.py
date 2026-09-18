#!/usr/bin/env python3
"""Wrap the verified portable archive in an RPM without modifying its payload."""
import argparse
import os
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = pathlib.Path(os.environ.get('EMACS_BUILD_ROOT', ROOT / 'build')).resolve()
dist = pathlib.Path(os.environ.get('EMACS_DIST_ROOT', ROOT / 'dist')).resolve()
p = argparse.ArgumentParser()
p.add_argument('bundle', type=pathlib.Path)
a = p.parse_args()
bundle = a.bundle.resolve()
info = json.loads((bundle / 'BUILD-INFO.json').read_text())
if info['cpu_baseline'] != 'x86-64-v3':
    raise SystemExit('RPM spec requires an x86-64-v3 build')
archive = dist / ('emacs-' + info['emacs'] + '-linux-x86-64-v3.tar.zst')
expected = archive.with_name(archive.name + '.sha256').read_text().split()[0]
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise SystemExit('Portable archive checksum mismatch')

packed_info = json.loads(subprocess.check_output(['tar', '--zstd', '-xOf', str(archive),
                        archive.name.removesuffix('.tar.zst') + '/BUILD-INFO.json'], text=True))
if packed_info != info:
    raise SystemExit('Archive belongs to a different build; package the selected bundle first')

with tempfile.TemporaryDirectory(prefix='rpm-', dir=BUILD) as tmp:
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
    (BUILD / 'current-rpm').write_text(str(rpm.relative_to(ROOT)) + '\n')
    print(rpm)
