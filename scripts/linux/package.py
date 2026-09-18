#!/usr/bin/env python3
"""Collect the installed tree and produce a relocatable release archive."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = pathlib.Path(os.environ.get('EMACS_BUILD_ROOT', ROOT / 'build')).resolve()
p = argparse.ArgumentParser()
p.add_argument('bundle', type=pathlib.Path)
p.add_argument('--force', action='store_true', help='replace previously generated release trees')
p.add_argument('--skip-validation', action='store_true', help='package without acceptance reports or ELF audit')
args = p.parse_args()
bundle = args.bundle.resolve()
info = json.loads((bundle / 'BUILD-INFO.json').read_text())
if not args.skip_validation:
    expected = json.loads((BUILD / 'acceptance/bundle-hashes.json').read_text())
    actual = {str(f.relative_to(bundle)): hashlib.sha256(f.read_bytes()).hexdigest()
              for f in sorted(bundle.rglob('*')) if f.is_file() and not f.is_symlink()}
    if actual != expected:
        raise SystemExit('Bundle changed since acceptance; rerun container.sh test')
    for name in ('builder', 'debian13'):
        report = BUILD / 'acceptance' / (name + '.log')
        if not report.exists() or 'ALL ACCEPTANCE TESTS PASSED' not in report.read_text():
            raise SystemExit('Run bash scripts/linux/container.sh test before packaging')
dist = pathlib.Path(os.environ.get('EMACS_DIST_ROOT', ROOT / 'dist')).resolve()
dist.mkdir(parents=True, exist_ok=True)
name = 'emacs-' + info['emacs'] + '-linux-' + info['cpu_baseline']
release = dist / name
if release.exists():
    if not args.force:
        raise SystemExit(str(release) + ' already exists; use --force to regenerate it')
    shutil.rmtree(release)
shutil.copytree(bundle, release, symlinks=True)
licenses = release / 'licenses'
licenses.mkdir(exist_ok=True)
# Read licenses from the locked archives, independent of dependency cache layout.
for dep, spec in info['sources'].items():
    dest = licenses / dep
    dest.mkdir(exist_ok=True)
    archive_path = ROOT / 'cache/sources' / (dep + '-' + spec['version'] + '.tar')
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != spec['sha256']:
        raise SystemExit('Source checksum mismatch: ' + dep)
    with tarfile.open(archive_path) as archive_source:
        for member in archive_source:
            path = pathlib.PurePosixPath(member.name)
            if (member.isfile() and len(path.parts) == 2 and
                    path.name.upper().startswith(('COPYING', 'LICENSE', 'COPYRIGHT', 'NOTICE'))):
                (dest / path.name).write_bytes(archive_source.extractfile(member).read())
shutil.copy2(ROOT / 'README.md', release / 'README.md')
runtime_source = pathlib.Path('/opt/gcc-runtime-source')
(licenses / 'gcc-runtime').mkdir()
for item in ('copyright', 'GPL-3'):
    shutil.copy2(runtime_source / item, licenses / 'gcc-runtime' / item)
if not args.skip_validation:
    shutil.copytree(BUILD / 'acceptance', release / 'acceptance',
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
                        ignore=lambda directory, names: [name for name in names if name == '__pycache__'
                            or (pathlib.Path(directory) == ROOT / 'benchmarks' and name == 'results')])
for item in ('sources.json', 'sources-macos.json', 'test-sources.json', 'requirements.txt', 'README.md', '.containerignore'):
    shutil.copy2(ROOT / item, source_release / item)
(source_release / 'sources.json').write_text(json.dumps(info['sources'], indent=2) + '\n')
shutil.copytree(runtime_source, source_release / 'gcc-runtime-source')
inputs = source_release / 'cache/sources'
inputs.mkdir(parents=True)
for lock in ('sources.json', 'test-sources.json', 'benchmarks/sources.json'):
    for dep, spec in json.loads((source_release / lock).read_text()).items():
        source = ROOT / 'cache/sources' / (dep + '-' + spec['version'] + '.tar')
        if hashlib.sha256(source.read_bytes()).hexdigest() != spec['sha256']:
            raise SystemExit('Source checksum mismatch: ' + str(source))
        shutil.copy2(source, inputs / source.name)
if info.get('pgo') in ('use', 'cs-use'):
    cs = info['pgo'] == 'cs-use'
    def profile_digest(name):
        return hashlib.sha256((BUILD / name).read_bytes()).hexdigest()
    normal_digest = profile_digest('merged.profdata')
    normal_provenance = json.loads((BUILD / 'pgo-training/provenance.json').read_text())
    final_name = 'combined.profdata' if cs else 'merged.profdata'
    if profile_digest(final_name) != info['profile_sha256'] or normal_provenance['profile_sha256'] != normal_digest:
        raise SystemExit('Profile does not match the accepted binary')
    profiles = ['merged.profdata']
    training_dirs = ['pgo-training']
    if cs:
        cs_provenance = json.loads((BUILD / 'pgo-training-cs/provenance.json').read_text())
        if (info['compile_profile_sha256'] != normal_digest or
                cs_provenance['compile_profile_sha256'] != normal_digest or
                cs_provenance['profile_sha256'] != profile_digest('cs.profdata')):
            raise SystemExit('CS profile provenance does not match the accepted binary')
        profiles += ['cs.profdata', 'combined.profdata']
        training_dirs += ['pgo-training-cs']
    destination = source_release / 'build'
    destination.mkdir(parents=True, exist_ok=True)
    for name in profiles:
        shutil.copy2(BUILD / name, destination / name)
    for name in training_dirs:
        (destination / name).mkdir(exist_ok=True)
        for filename in ('provenance.json', 'profile-summary.txt'):
            shutil.copy2(BUILD / name / filename, destination / name / filename)
source_archive = dist / (source_name + '.tar.zst')
subprocess.run(['tar', '--sort=name', '--mtime=@' + epoch, '--owner=0', '--group=0',
                '--numeric-owner', '--zstd', '-cf', str(source_archive), '-C', str(dist), source_name], check=True)
digest = hashlib.sha256(source_archive.read_bytes()).hexdigest()
(dist / (source_archive.name + '.sha256')).write_text(digest + '  ' + source_archive.name + '\n')
print(source_archive)
