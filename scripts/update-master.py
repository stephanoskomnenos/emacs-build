#!/usr/bin/env python3
"""Resolve upstream master once, then lock its archive for this build."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import tarfile
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--ref', default='master', help='upstream branch, tag or full commit (default: master)')
a = p.parse_args()
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', a.ref):
    p.error('Invalid upstream ref')

def download(url, target):
    subprocess.run(['curl', '--fail', '--location', '--retry', '3', '--silent',
                    '--show-error', '--connect-timeout', '30', '--max-time', '600',
                    url, '-o', str(target)], check=True)

cache = ROOT / 'cache/sources'
cache.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=cache) as tmp:
    repo = pathlib.Path(tmp) / 'repository'
    subprocess.run(['git', 'init', '--quiet', str(repo)], check=True)
    git = ['git', '-C', str(repo)]
    fetch = [*git, '-c', 'http.lowSpeedLimit=1024', '-c', 'http.lowSpeedTime=30',
             'fetch', '--quiet', '--depth=1', '--filter=blob:none', '--no-tags',
             'https://github.com/emacs-mirror/emacs.git', a.ref]
    for attempt in range(3):
        try:
            subprocess.run(fetch, env=dict(os.environ, GIT_TERMINAL_PROMPT='0'),
                           check=True, timeout=180)
            break
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    sha = subprocess.check_output([*git, 'rev-parse', 'FETCH_HEAD'], text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise SystemExit('Invalid upstream commit')
    timestamp = int(subprocess.check_output([*git, 'show', '-s', '--format=%ct', sha], text=True))
    committed = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    date = committed.strftime('%Y-%m-%dT%H:%M:%SZ')
    stamp = committed.strftime('%Y%m%d%H%M%S')
    url = f'https://codeload.github.com/emacs-mirror/emacs/tar.gz/{sha}'
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
    spec = {'version': snapshot, 'emacs_version': version, 'ref': a.ref,
            'commit': sha, 'commit_date': date, 'url': url,
            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
    archive.replace(cache / f'emacs-{snapshot}.tar')
manifest_path = ROOT / 'sources.json'
manifest = json.loads(manifest_path.read_text())
manifest['emacs'] = spec
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Locked Emacs {a.ref}: {snapshot} ({sha})')
