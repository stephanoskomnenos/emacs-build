#!/usr/bin/env python3
"""Download pinned inputs; --lock explicitly records hashes for a source update."""
import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--lock', action='store_true')
group = p.add_mutually_exclusive_group()
group.add_argument('--tests', action='store_true')
group.add_argument('--benchmarks', action='store_true')
group.add_argument('--toolchain', action='store_true', help='source archive only; never builds GCC')
args = p.parse_args()
manifest_path = ROOT / ('benchmarks/sources.json' if args.benchmarks else 'test-sources.json' if args.tests else 'toolchain-sources.json' if args.toolchain else 'sources.json')
manifest = json.loads(manifest_path.read_text())
cache = ROOT / 'cache' / 'sources'
cache.mkdir(parents=True, exist_ok=True)

def fetch(item):
    name, spec = item
    target = cache / (name + '-' + spec['version'] + '.tar')
    if not args.lock and 'sha256' not in spec:
        raise RuntimeError(name + ': missing source lock')
    if not target.exists():
        part = target.with_suffix('.part')
        subprocess.run(['curl', '--fail', '--location', '--retry', '3',
                        '--connect-timeout', '30', '--max-time', '600',
                        '--silent', '--show-error', spec['url'], '-o', str(part)], check=True)
        part.replace(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if 'sha256' in spec and digest != spec['sha256']:
        raise RuntimeError(name + ': checksum mismatch; cached file left for inspection')
    print(name + ': ' + digest, flush=True)
    return name, digest

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    hashes = dict(pool.map(fetch, manifest.items()))
if args.lock:
    for name, digest in hashes.items():
        manifest[name]['sha256'] = digest
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
