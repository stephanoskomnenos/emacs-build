#!/usr/bin/env python3
"""Held-out diagnostics replay through the user's configured lsp-mode."""
import argparse
import json
import os
from pathlib import Path
import statistics
import time
from pty_driver import Session

class ConfiguredSession(Session):
    def receive(self, kind, timeout=120):
        data = super().receive(kind, timeout)
        if kind == 'ready':
            self.configuration = data
        return data

p = argparse.ArgumentParser()
p.add_argument('--label', required=True)
p.add_argument('--mode', choices=['paced', 'saturated'], required=True)
p.add_argument('--runs', type=int, default=3)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
base = root / 'build/lsp-load'
info = json.loads(Path('/bundle/BUILD-INFO.json').read_text())
if info.get('pgo') == 'generate':
    raise SystemExit('User configuration must not train PGO')
os.sched_setaffinity(0, {0})
env = dict(os.environ, HOME=str(base/'home'), LSP_LOAD_PROJECT=str(base/'project'),
           LSP_LOAD_SERVER=str(root/'benchmarks/lsp/server.py'), LSP_LOAD_MODE=a.mode)
for key in ['LLVM_PROFILE_FILE', 'EMACSLOADPATH', 'EMACSDATA', 'EMACSDOC', 'EMACSPATH', 'LD_LIBRARY_PATH']:
    env.pop(key, None)
runs = []
for index in range(a.runs + 1):
    session = ConfiguredSession(base/'emacs', base/f'{a.label}-{index}', root/'benchmarks/lsp/observer.el', env)
    try:
        assert session.configuration['threshold']==16000000
        assert session.configuration['percentage']==0.1
        assert session.configuration['retained']=={'files':64,'diagnostics':16384}
        before = session.action(b'')['state']['size']
        start = session.action(b'\x1b[17~')
        latencies = []
        schedule_latencies = []
        missed = 0
        deadline = time.monotonic()
        result = start['state']['done']
        while not result:
            delay = deadline - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            measurement = session.action(b'z')
            now = time.monotonic()
            latencies.append(measurement['seconds'])
            schedule_latencies.append(now-deadline)
            assert measurement['state']['size'] == before+len(latencies), 'Input lost or edited by a different command'
            result = measurement['state']['done']
            deadline += 0.01
            if deadline < now:
                skipped = int((now-deadline)/0.01)+1
                missed += skipped
                deadline += skipped*0.01
            if len(latencies)>20000:
                raise RuntimeError('Replay did not finish')
        assert result['messages']==1000, result
        assert result['retained']=={'files':64,'diagnostics':16384}, result
        assert result['collections']>0, result
        assert len(result['gc_pauses'])==result['collections'], result
        status = Path(f'/proc/{session.pid}/status').read_text().splitlines()
        memory = {line.split(':')[0]:int(line.split()[1]) for line in status
                  if line.startswith(('VmRSS:', 'VmHWM:'))}
        result.update(input_seconds=latencies, scheduled_input_seconds=schedule_latencies,
                      missed_input_slots=missed, memory_kib=memory,
                      configuration=session.configuration)
        print(a.label,index,{k:v for k,v in result.items() if not isinstance(v,(list,dict))},flush=True)
        if index:
            runs.append(result)
    finally:
        session.close()
(base/f'{a.label}.json').write_text(json.dumps(dict(label=a.label,mode=a.mode,
    build={k:v for k,v in info.items() if k!='packages'},warmups=1,runs=runs),indent=2)+'\n')
