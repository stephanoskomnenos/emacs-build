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
