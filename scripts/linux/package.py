#!/usr/bin/env python3
"""Collect the installed tree and produce a relocatable release archive."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
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
        raise SystemExit('Run bash scripts/linux/container.sh test before packaging')
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
runtime_source = pathlib.Path('/opt/gcc-runtime-source')
(licenses / 'gcc-runtime').mkdir()
for item in ('copyright', 'GPL-3'):
    shutil.copy2(runtime_source / item, licenses / 'gcc-runtime' / item)
shutil.copytree(ROOT / 'build/acceptance', release / 'acceptance',
                ignore=shutil.ignore_patterns('rpm.log'))
audit = subprocess.check_output(['python3', str(ROOT / 'scripts/linux/audit.py'), str(release)], text=True)
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
for item in ('sources.json', 'test-sources.json', 'requirements.txt', 'README.md', '.containerignore'):
    shutil.copy2(ROOT / item, source_release / item)
shutil.copytree(runtime_source, source_release / 'gcc-runtime-source')
inputs = source_release / 'cache/sources'
inputs.mkdir(parents=True)
for lock in ('sources.json', 'test-sources.json', 'benchmarks/sources.json'):
    for dep, spec in json.loads((ROOT / lock).read_text()).items():
        source = ROOT / 'cache/sources' / (dep + '-' + spec['version'] + '.tar')
        if hashlib.sha256(source.read_bytes()).hexdigest() != spec['sha256']:
            raise SystemExit('Source checksum mismatch: ' + str(source))
        shutil.copy2(source, inputs / source.name)
if info.get('pgo') in ('use', 'cs-use'):
    cs = info['pgo'] == 'cs-use'
    def profile_digest(name):
        return hashlib.sha256((ROOT / 'build' / name).read_bytes()).hexdigest()
    normal_digest = profile_digest('merged.profdata')
    normal_provenance = json.loads((ROOT / 'build/pgo-training/provenance.json').read_text())
    final_name = 'combined.profdata' if cs else 'merged.profdata'
    if profile_digest(final_name) != info['profile_sha256'] or normal_provenance['profile_sha256'] != normal_digest:
        raise SystemExit('Profile does not match the accepted binary')
    profiles = ['merged.profdata']
    training_dirs = ['pgo-training']
    if cs:
        cs_provenance = json.loads((ROOT / 'build/pgo-training-cs/provenance.json').read_text())
        if (info['compile_profile_sha256'] != normal_digest or
                cs_provenance['compile_profile_sha256'] != normal_digest or
                cs_provenance['profile_sha256'] != profile_digest('cs.profdata')):
            raise SystemExit('CS profile provenance does not match the accepted binary')
        profiles += ['cs.profdata', 'combined.profdata']
        training_dirs += ['pgo-training-cs']
    destination = source_release / 'build'
    destination.mkdir(parents=True, exist_ok=True)
    for name in profiles:
        shutil.copy2(ROOT / 'build' / name, destination / name)
    for name in training_dirs:
        (destination / name).mkdir(exist_ok=True)
        for filename in ('provenance.json', 'profile-summary.txt'):
            shutil.copy2(ROOT / 'build' / name / filename, destination / name / filename)
source_archive = dist / (source_name + '.tar.zst')
subprocess.run(['tar', '--sort=name', '--mtime=@' + epoch, '--owner=0', '--group=0',
                '--numeric-owner', '--zstd', '-cf', str(source_archive), '-C', str(dist), source_name], check=True)
digest = hashlib.sha256(source_archive.read_bytes()).hexdigest()
(dist / (source_archive.name + '.sha256')).write_text(digest + '  ' + source_archive.name + '\n')
print(source_archive)
