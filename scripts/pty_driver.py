"""Real terminal input with an independent Emacs acknowledgement socket."""
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import signal
import socket
import struct
import termios
import time

class Session:
    def __init__(self, binary, directory, observer, env):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.socket_path = self.directory / 'control.sock'
        self.socket_path.unlink(missing_ok=True)
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(self.socket_path))
        self.listener.listen(1)
        self.listener.setblocking(False)
        self.output = bytearray()
        self.pending = b''
        self.messages = b''
        self.connection = None
        self.sequence = 0
        self.env = dict(env, WORKLOAD_SOCKET=str(self.socket_path), TERM='xterm-256color', LC_ALL='C.UTF-8')
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 100, 0, 0))
            os.chdir(self.directory)
            os.execve(str(binary), [str(binary), '-Q', '-nw', '-l', str(observer)], self.env)
        self.receive('ready')

    def receive(self, kind, timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if b'\n' in self.messages:
                line, self.messages = self.messages.split(b'\n', 1)
                result = json.loads(line)
                if result.get('kind') != kind:
                    raise RuntimeError(f'Expected {kind}, received {result}')
                if result.get('error'):
                    raise RuntimeError(result['error'])
                return result
            handles = [self.fd, self.connection or self.listener]
            for handle in select.select(handles, [], [], min(0.1, max(0, deadline-time.monotonic())))[0]:
                if handle is self.listener:
                    self.connection, _ = self.listener.accept()
                elif handle is self.connection:
                    data = self.connection.recv(65536)
                    if not data: raise RuntimeError('Emacs closed acknowledgement socket')
                    self.messages += data
                else:
                    try: data = os.read(self.fd, 65536)
                    except OSError: raise RuntimeError('Emacs terminal closed unexpectedly')
                    self.output.extend(data)
                    self.output = self.output[-2000000:]
                    self.pending += data
                    consumed = 0
                    for match in re.finditer(rb'\x1b\[[0-?]*[ -/]*[@-~]', self.pending):
                        response = {b'\x1b[c':b'\x1b[?62;4;6;22c', b'\x1b[>0c':b'\x1b[>1;4000;0c', b'\x1b[?u':b'\x1b[?0u'}.get(match[0])
                        if response: os.write(self.fd, response)
                        consumed = match.end()
                    self.pending = self.pending[consumed:][-64:]
        raise TimeoutError(f'Emacs did not acknowledge {kind}')

    def action(self, keys):
        self.sequence += 1
        start = time.perf_counter_ns()
        data = keys + b'\x1b[24~'  # F12: acknowledge after preceding commands.
        while data:
            sent = os.write(self.fd, data)
            data = data[sent:]
        result = self.receive('checkpoint')
        elapsed = (time.perf_counter_ns()-start)/1e9
        if result['sequence'] != self.sequence: raise RuntimeError('Out-of-order acknowledgement')
        return {'seconds':elapsed, 'state':result}

    def close(self):
        try:
            os.write(self.fd, b'\x1bOS')  # F4, explicit clean exit flushes training profiles.
            self.receive('exit', 10)
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                pid,status=os.waitpid(self.pid,os.WNOHANG)
                if pid:
                    self.pid=None
                    if os.waitstatus_to_exitcode(status)!=0: raise RuntimeError('Emacs failed')
                    break
                time.sleep(0.01)
        finally:
            if self.pid:
                os.kill(self.pid,signal.SIGKILL);os.waitpid(self.pid,0)
            (self.directory/'terminal.log').write_bytes(self.output)
            os.close(self.fd)
            if self.connection:self.connection.close()
            self.listener.close()
            self.socket_path.unlink(missing_ok=True)
