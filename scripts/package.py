#!/usr/bin/env python3
"""Collect the installed tree and produce a relocatable release archive."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--force', action='store_true', help='replace previously generated release trees')
args = p.parse_args()
bundle = ROOT / (ROOT / 'build/current-bundle').read_text().strip()
info = json.loads((bundle / 'BUILD-INFO.json').read_text())
expected = json.loads((ROOT / 'build/acceptance/bundle-hashes.json').read_text())
actual = {str(f.relative_to(bundle)): hashlib.sha256(f.read_bytes()).hexdigest()
          for f in sorted(bundle.rglob('*')) if f.is_file() and not f.is_symlink()}
if actual != expected:
    raise SystemExit('Bundle changed since acceptance; rerun container.sh test')
for name in ('builder', 'debian13'):
    report = ROOT / 'build/acceptance' / (name + '.log')
    if not report.exists() or 'ALL ACCEPTANCE TESTS PASSED' not in report.read_text():
        raise SystemExit('Run bash scripts/container.sh test before packaging')
dist = ROOT / 'dist'
dist.mkdir(exist_ok=True)
name = 'emacs-' + info['emacs'] + '-linux-' + info['cpu_baseline']
release = dist / name
if release.exists():
    if not args.force:
        raise SystemExit(str(release) + ' already exists; use --force to regenerate it')
    shutil.rmtree(release)
shutil.copytree(bundle, release, symlinks=True)
licenses = release / 'licenses'
licenses.mkdir(exist_ok=True)
work = bundle.parents[2]
for dep in info['sources']:
    source = work / 'src' / dep
    dest = licenses / dep
    dest.mkdir(exist_ok=True)
    for f in source.iterdir():
        if f.is_file() and f.name.upper().startswith(('COPYING', 'LICENSE', 'COPYRIGHT', 'NOTICE')):
            shutil.copy2(f, dest / f.name)
shutil.copy2(ROOT / 'README.md', release / 'README.md')
gcc = json.loads((ROOT / 'toolchain-sources.json').read_text())['gcc']
gcc_archive = ROOT / 'cache/sources' / ('gcc-' + gcc['version'] + '.tar')
if hashlib.sha256(gcc_archive.read_bytes()).hexdigest() != gcc['sha256']:
    raise SystemExit('GCC source checksum mismatch')
(licenses / 'gcc-runtime').mkdir()
with tarfile.open(gcc_archive) as source:
    for item in ('COPYING3', 'COPYING.RUNTIME'):
        member = source.extractfile('gcc-' + gcc['version'] + '/' + item)
        (licenses / 'gcc-runtime' / item).write_bytes(member.read())
shutil.copytree(ROOT / 'build/acceptance', release / 'acceptance',
                ignore=shutil.ignore_patterns('rpm.log'))
audit = subprocess.check_output(['python3', str(ROOT / 'scripts/audit.py'), str(release)], text=True)
(release / 'ELF-AUDIT.json').write_text(audit)
archive = dist / (name + '.tar.zst')
with tarfile.open(ROOT / 'cache/sources' / ('emacs-' + info['emacs'] + '.tar')) as t:
    epoch = str(t.getmembers()[0].mtime)
subprocess.run(['tar', '--sort=name', '--mtime=@' + epoch, '--owner=0', '--group=0',
                '--numeric-owner', '--zstd', '-cf', str(archive), '-C', str(dist), name], check=True)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(dist / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n')
print(archive)

# Ship the exact source inputs and build/install recipes beside the binary.
source_name = name + '-sources'
source_release = dist / source_name
if source_release.exists() and args.force:
    shutil.rmtree(source_release)
source_release.mkdir()
for item in ('scripts', 'containers', 'tests', '.github', 'packaging', 'benchmarks'):
    if (ROOT / item).exists():
        shutil.copytree(ROOT / item, source_release / item,
                        ignore=shutil.ignore_patterns('__pycache__'))
for item in ('sources.json', 'test-sources.json', 'toolchain-sources.json', 'README.md', '.containerignore'):
    shutil.copy2(ROOT / item, source_release / item)
inputs = source_release / 'cache/sources'
inputs.mkdir(parents=True)
for lock in ('sources.json', 'test-sources.json', 'toolchain-sources.json', 'benchmarks/sources.json'):
    for dep, spec in json.loads((ROOT / lock).read_text()).items():
        source = ROOT / 'cache/sources' / (dep + '-' + spec['version'] + '.tar')
        if hashlib.sha256(source.read_bytes()).hexdigest() != spec['sha256']:
            raise SystemExit('Source checksum mismatch: ' + str(source))
        shutil.copy2(source, inputs / source.name)
if info.get('pgo') == 'use':
    profile = ROOT / 'build/merged.profdata'
    provenance = ROOT / 'build/pgo-training/provenance.json'
    digest = hashlib.sha256(profile.read_bytes()).hexdigest()
    if digest != info['profile_sha256'] or json.loads(provenance.read_text())['profile_sha256'] != digest:
        raise SystemExit('Profile does not match the accepted binary')
    destination = source_release / 'build'
    (destination / 'pgo-training').mkdir(parents=True)
    shutil.copy2(profile, destination / 'merged.profdata')
    shutil.copy2(provenance, destination / 'pgo-training/provenance.json')
    shutil.copy2(ROOT / 'build/pgo-training/profile-summary.txt', destination / 'pgo-training/profile-summary.txt')
source_archive = dist / (source_name + '.tar.zst')
subprocess.run(['tar', '--sort=name', '--mtime=@' + epoch, '--owner=0', '--group=0',
                '--numeric-owner', '--zstd', '-cf', str(source_archive), '-C', str(dist), source_name], check=True)
digest = hashlib.sha256(source_archive.read_bytes()).hexdigest()
(dist / (source_archive.name + '.sha256')).write_text(digest + '  ' + source_archive.name + '\n')
print(source_archive)
