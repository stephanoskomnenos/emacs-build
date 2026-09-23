"""Pexpect terminal sessions with small Emacs completion messages."""
import json
import os
from pathlib import Path
import time

import pexpect

# OSC messages leave the terminal cursor and displayed buffer untouched.
MESSAGE = rb'\x1b\]777;emacs-workload;(.*?)\x07'
QUERIES = [rb'\x1b\[c', rb'\x1b\[>0c', rb'\x1b\[\?u']
RESPONSES = [b'\x1b[?62;4;6;22c', b'\x1b[>1;4000;0c', b'\x1b[?0u']


class Session:
    def __init__(self, binary, directory, observer, env):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log = (self.directory / 'terminal.log').open('wb')
        self.sequence = 0
        self.child = None
        try:
            self.child = pexpect.spawn(str(binary), ['-Q', '-nw', '-l', str(observer)],
                cwd=str(self.directory), env=dict(env, TERM='xterm-256color',
                LC_ALL='en_US.UTF-8' if os.uname().sysname == 'Darwin' else 'C.UTF-8'),
                dimensions=(30, 100), timeout=120)
            self.child.delaybeforesend = None
            self.child.logfile_read = self.log
            self.pid = self.child.pid
            self.receive('ready')
        except BaseException:
            if self.child is not None:
                self.child.close(force=True)
            self.log.close()
            raise

    def send(self, keys):
        self.child.send(keys)

    def receive(self, kind, timeout=120):
        deadline = time.monotonic() + timeout
        while True:
            which = self.child.expect([MESSAGE, *QUERIES], timeout=max(0, deadline-time.monotonic()))
            if which:
                self.child.send(RESPONSES[which-1])
                continue
            result = json.loads(self.child.match[1])
            if result.get('kind') != kind:
                raise RuntimeError(f'Expected {kind}, received {result}')
            if result.get('error'):
                raise RuntimeError(result['error'])
            return result

    def action(self, keys):
        self.sequence += 1
        start = time.perf_counter_ns()
        # A trailing ESC starts a Meta-key sequence in the terminal.  Give
        # Emacs enough time to dispatch it as Evil's state transition before
        # sending the F12 acknowledgement.
        if keys.endswith(b'\x1b'):
            self.send(keys)
            time.sleep(0.6)
            self.send(b'\x1b[24~')
        else:
            self.send(keys + b'\x1b[24~')  # F12 acknowledges preceding commands.
        result = self.receive('checkpoint')
        elapsed = (time.perf_counter_ns()-start)/1e9
        if result['sequence'] != self.sequence:
            raise RuntimeError('Out-of-order acknowledgement')
        return {'seconds': elapsed, 'state': result}

    def close(self):
        try:
            self.send(b'\x1bOS')  # F4 exits cleanly and flushes the PGO profile.
            self.receive('exit', 10)
            self.child.expect(pexpect.EOF, timeout=10)
            self.child.close()
            if self.child.exitstatus != 0:
                raise RuntimeError('Emacs failed')
        finally:
            self.child.close(force=True)
            self.log.close()
