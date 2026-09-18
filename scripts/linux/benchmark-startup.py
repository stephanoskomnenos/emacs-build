#!/usr/bin/env python3
"""Time real -nw startup in a private, reusable copy of the user's configuration."""
import argparse
import fcntl
import hashlib
import json
import os
import pathlib
import pty
import re
import select
import shutil
import signal
import statistics
import struct
import termios
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument('bundle', type=pathlib.Path)
p.add_argument('--config', type=pathlib.Path)
p.add_argument('--workspace', type=pathlib.Path, default=ROOT / 'build/startup-benchmark')
p.add_argument('--label', required=True)
p.add_argument('--runs', type=int, default=7)
p.add_argument('--cpu', type=int, default=0)
p.add_argument('--files', nargs='*', type=pathlib.Path)
p.add_argument('--prepare-only', action='store_true')
a = p.parse_args()
if a.runs < 1:
    p.error('--runs must be positive')
os.sched_setaffinity(0, {a.cpu})
a.workspace = a.workspace.resolve()
config = a.workspace / 'home/.emacs.d'
if a.config:
    if config.exists():
        raise SystemExit('Benchmark copy already exists; omit --config to reuse it')
    shutil.copytree(a.config.expanduser().resolve(), config, symlinks=True,
                    ignore=shutil.ignore_patterns('.git', 'eln-cache'))
    source_root = a.config.expanduser().resolve()
    for link in config.rglob('*'):
        if link.is_symlink():
            target = link.readlink()
            if target.is_absolute() and target.is_relative_to(source_root):
                relocated = config / target.relative_to(source_root)
                link.unlink()
                link.symlink_to(os.path.relpath(relocated, link.parent))
    original = (config / 'early-init.el').read_text()
    (config / 'early-init.el').write_text(original + '\n(load ' + json.dumps(str(ROOT / 'benchmarks/startup.el')) + ' nil t)\n')
    (a.workspace / 'config-sha256.json').write_text(json.dumps({
        name: hashlib.sha256((a.config.expanduser() / name).read_bytes()).hexdigest()
        for name in ('init.el', 'early-init.el', 'elpaca-lock.el')}, indent=2))
if a.prepare_only:
    print(config)
    raise SystemExit(0)
if not config.is_dir():
    raise SystemExit('Prepare a configuration copy first')
# The copy may have been prepared on the host at a different workspace path.
early = config / 'early-init.el'
s = early.read_text(); start = s.rfind('\n(load ')
if start == -1: raise SystemExit('Missing benchmark observer')
early.write_text(s[:start] + '\n(load ' + json.dumps(str(ROOT / 'benchmarks/startup.el')) + ' nil t)\n')
results = []
for iteration in range(a.runs + 1):
    result = a.workspace / f'{a.label}-{iteration}.json'
    result.unlink(missing_ok=True)
    log = a.workspace / f'{a.label}-{iteration}.log'
    env = dict(os.environ, HOME=str(config.parent), TERM='xterm-256color', LC_ALL='C.UTF-8',
               BENCHMARK_RESULT=str(result), BENCHMARK_START=str(time.time()))
    if a.files:
        env['BENCHMARK_FILES'] = json.dumps([str(f.resolve()) for f in a.files])
    # Test executions must never contribute to an instrumentation profile.
    env.pop('LLVM_PROFILE_FILE', None)
    info_file = a.bundle / 'BUILD-INFO.json'
    if info_file.exists() and json.loads(info_file.read_text()).get('pgo') in ('generate', 'cs-generate'):
        raise SystemExit('Do not benchmark the user config with an instrumented binary')
    for key in ('EMACSLOADPATH','EMACSDATA','EMACSDOC','EMACSPATH','LD_LIBRARY_PATH'):
        env.pop(key, None)
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(config.parent)
        os.execve(str(a.bundle.resolve() / 'bin/emacs'),
                  [str(a.bundle.resolve() / 'bin/emacs'), '-nw', '--init-directory=' + str(config)], env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 100, 0, 0))
    output = bytearray()
    pending = b""
    keyboard_flags = b"0"
    deadline = time.monotonic() + 120
    status = None
    try:
        while time.monotonic() < deadline:
            if select.select([fd], [], [], 0.1)[0]:
                try:
                    chunk = os.read(fd, 65536)
                    output.extend(chunk)
                    pending += chunk
                    consumed = 0
                    for match in re.finditer(rb'\x1b\[[0-?]*[ -/]*[@-~]', pending):
                        query = match[0]
                        response = {b'\x1b[c': b'\x1b[?62;4;6;22c',
                                    b'\x1b[>0c': b'\x1b[>1;4000;0c',
                                    b'\x1b[?u': b'\x1b[?' + keyboard_flags + b'u'}.get(query)
                        if query.startswith(b'\x1b[>') and query.endswith(b'u'):
                            keyboard_flags = query[3:-1]
                        if response: os.write(fd, response)
                        consumed = match.end()
                    pending = pending[consumed:][-64:]
                except OSError: pass
            done, code = os.waitpid(pid, os.WNOHANG)
            if done:
                status = os.waitstatus_to_exitcode(code)
                break
        if status is None:
            os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
        log.write_bytes(output)
        if status != 0 or not result.exists():
            raise SystemExit(f'Startup failed or timed out; see {log}')
    finally:
        os.close(fd)
    measurement = json.loads(result.read_text())
    print(a.label, iteration, measurement, flush=True)
    if iteration: results.append(measurement)
report = {'label': a.label, 'runs': results, 'warmup_runs': 1, 'cpu': a.cpu, 'terminal': 'PTY with device-attributes and Kitty keyboard query replies',
          'build': json.loads((a.bundle / 'BUILD-INFO.json').read_text()),
          'config_sha256': json.loads((a.workspace / 'config-sha256.json').read_text()),
          'median_window_seconds': statistics.median(r['window_seconds'] for r in results),
          'median_ready_seconds': statistics.median(r['ready_seconds'] for r in results)}
(a.workspace / (a.label + '-summary.json')).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
