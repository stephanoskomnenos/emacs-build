#!/usr/bin/env python3
"""Cache only files installed by the ebuild-derived recipes, not the runner prefix."""
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
archive = ROOT / 'build/macos/dependencies.tar'
if sys.platform != 'darwin' or os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Only for disposable macOS CI runners')
if os.environ.get('CACHE_HIT') == 'true':
    with tarfile.open(archive) as cache:
        for member in cache:
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or not member.name.startswith('usr/local/'):
                raise SystemExit('Unexpected dependency cache path')
    subprocess.run(['sudo', 'tar', '-xpf', str(archive), '-C', '/'], check=True)
else:
    def snapshot():
        result = {}
        for directory, dirs, files in os.walk('/usr/local', followlinks=False):
            for name in files + [d for d in dirs if (Path(directory) / d).is_symlink()]:
                path = Path(directory) / name
                stat = path.lstat()
                result[path] = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_mode)
        return result
    before = snapshot()
    subprocess.run(['bash', str(ROOT / 'scripts/macos/dependencies.sh')], cwd=ROOT, check=True)
    after = snapshot()
    changed = [path for path in after if before.get(path) != after[path]]
    if not changed:
        raise SystemExit('Dependencies installed no files')
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'w', dereference=False) as cache:
        for path in sorted(changed):
            cache.add(path, arcname=str(path.relative_to('/')), recursive=False)
    print(f'Cached {len(changed)} installed files ({archive.stat().st_size // 1048576} MiB before cache compression)')
