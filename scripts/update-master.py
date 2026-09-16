#!/usr/bin/env python3
"""Resolve upstream master once, then lock its archive for this build."""
import datetime
import hashlib
import json
import pathlib
import re
import subprocess
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

def download(url, target=None):
    cmd = ['curl', '--fail', '--location', '--retry', '3', '--silent',
           '--show-error', '--connect-timeout', '30', '--max-time', '600', url]
    if target is not None:
        subprocess.run([*cmd, '-o', str(target)], check=True)
    else:
        return subprocess.check_output(cmd)

commit = json.loads(download('https://api.github.com/repos/emacs-mirror/emacs/commits/master'))
sha = commit['sha']
if not re.fullmatch(r'[0-9a-f]{40}', sha):
    raise SystemExit('Invalid upstream commit')
date = commit['commit']['committer']['date']
stamp = datetime.datetime.fromisoformat(date.replace('Z', '+00:00')).strftime('%Y%m%d%H%M%S')
url = f'https://codeload.github.com/emacs-mirror/emacs/tar.gz/{sha}'
cache = ROOT / 'cache/sources'
cache.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=cache) as tmp:
    archive = pathlib.Path(tmp) / 'emacs.tar'
    download(url, archive)
    with tarfile.open(archive) as source:
        member = next(m for m in source.getmembers() if m.name.endswith('/configure.ac') and m.name.count('/') == 1)
        configure = source.extractfile(member).read().decode()
    match = re.search(r'AC_INIT\(\[GNU Emacs\],\s*\[([0-9.]+)\]', configure)
    if not match:
        raise SystemExit('Cannot determine upstream Emacs version')
    version = match[1]
    snapshot = f'{version}.{stamp}.git{sha[:12]}'
    spec = {'version': snapshot, 'emacs_version': version, 'branch': 'master',
            'commit': sha, 'commit_date': date, 'url': url,
            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
    archive.replace(cache / f'emacs-{snapshot}.tar')
manifest_path = ROOT / 'sources.json'
manifest = json.loads(manifest_path.read_text())
manifest['emacs'] = spec
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Locked Emacs master: {snapshot} ({sha})')
