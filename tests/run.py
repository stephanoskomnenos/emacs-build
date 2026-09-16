#!/usr/bin/env python3
"""Artifact acceptance tests. Pass --prepare in the builder to compile fixtures."""
import argparse
import hashlib
import http.server
import json
import os
import pathlib
import pty
import select
import shutil
import signal
import ssl
import struct
import subprocess
import tempfile
import termios
import threading
import time
import uuid
import fcntl

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('bundle', type=pathlib.Path)
p.add_argument('--prepare', action='store_true')
p.add_argument('--fixtures', type=pathlib.Path, default=ROOT / 'build/test-fixtures')
a = p.parse_args()
fixtures = a.fixtures.resolve()
bundle = a.bundle.resolve()

def run(cmd, **kwargs):
    return subprocess.run(list(map(str, cmd)), check=True, timeout=90, **kwargs)

if a.prepare:
    fixtures.mkdir(parents=True, exist_ok=True)
    run(['gcc', '-O2', '-fPIC', '-shared', '-I' + str(bundle / 'include'),
         ROOT / 'tests/module.c', '-o', fixtures / 'test-module.so'])
    spec = json.loads((ROOT / 'test-sources.json').read_text())['tree-sitter-json']
    archive = ROOT / 'cache/sources' / ('tree-sitter-json-' + spec['version'] + '.tar')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == spec['sha256']
    grammar = fixtures / 'grammar-source'
    grammar.mkdir(exist_ok=True)
    run(['tar', '-xf', archive, '--strip-components=1', '-C', grammar])
    run(['gcc', '-O2', '-fPIC', '-shared', '-I' + str(grammar / 'src'),
         grammar / 'src/parser.c', '-o', fixtures / 'libtree-sitter-json.so'])
    specs = json.loads((ROOT / 'test-sources.json').read_text())
    for name in ('vterm', 'libvterm'):
        spec = specs[name]
        archive = ROOT / 'cache/sources' / (name + '-' + spec['version'] + '.tar')
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == spec['sha256']
        dest = fixtures / (name + '-source')
        dest.mkdir(exist_ok=True)
        run(['tar', '-xf', archive, '--strip-components=1', '-C', dest])
    vs = fixtures / 'vterm-source'
    ls = fixtures / 'libvterm-source'
    header = (ls / 'include/vterm.h').read_text()
    defs = []
    for symbol, macro in [('VTermStringFragment', 'VTermStringFragmentNotExists'),
                          ('VTermSelectionMask', 'VTermSelectionMaskNotExists'),
                          ('sb_clear', 'VTermSBClearNotExists'),
                          ('vterm_screen_enable_reflow', 'VTermScreenEnableReflowNotExists')]:
        if symbol not in header:
            defs.append('-D' + macro)
    run(['gcc', '-std=gnu99', '-O2', '-fPIC', '-fvisibility=hidden', '-shared',
         '-I' + str(ls / 'include'), '-I' + str(ls / 'src'), *defs,
         vs / 'vterm-module.c', vs / 'utf8.c', vs / 'elisp.c',
         *sorted((ls / 'src').glob('*.c')), '-o', vs / 'vterm-module.so'])
    run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2',
         '-subj', '/CN=Portable Test CA', '-addext', 'basicConstraints=critical,CA:TRUE',
         '-keyout', fixtures / 'ca-key.pem', '-out', fixtures / 'ca.pem'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run(['openssl', 'req', '-new', '-newkey', 'rsa:2048', '-nodes',
         '-subj', '/CN=localhost', '-keyout', fixtures / 'key.pem',
         '-out', fixtures / 'server.csr'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (fixtures / 'server.ext').write_text('subjectAltName=DNS:localhost\nbasicConstraints=critical,CA:FALSE\nextendedKeyUsage=serverAuth\n')
    run(['openssl', 'x509', '-req', '-in', fixtures / 'server.csr',
         '-CA', fixtures / 'ca.pem', '-CAkey', fixtures / 'ca-key.pem',
         '-CAcreateserial', '-days', '2', '-extfile', fixtures / 'server.ext',
         '-out', fixtures / 'cert.pem'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

required = ['test-module.so', 'libtree-sitter-json.so', 'vterm-source/vterm-module.so', 'cert.pem', 'key.pem', 'ca.pem']
for name in required:
    if not (fixtures / name).is_file():
        raise SystemExit('Missing fixture ' + name + '; run with --prepare in builder')

with tempfile.TemporaryDirectory(prefix='emacs acceptance ') as tmpstr:
    tmp = pathlib.Path(tmpstr)
    moved = tmp / 'moved installation'
    shutil.copytree(bundle, moved, symlinks=True)
    link = tmp / 'emacs-link'
    link.symlink_to(moved / 'bin/emacs')
    env = dict(os.environ, TEST_MODULE=str(fixtures / 'test-module.so'),
               TEST_GRAMMARS=str(fixtures), TEST_VTERM=str(fixtures / 'vterm-source'),
               LC_ALL='C.UTF-8', TERM='xterm-256color')
    for k in ('EMACSLOADPATH', 'EMACSDATA', 'EMACSDOC', 'EMACSPATH', 'LD_LIBRARY_PATH'):
        env.pop(k, None)
    # Keep HOME intact; -Q and an explicit init directory isolate Emacs state.
    base = [str(link), '--init-directory=' + str(tmp / 'config'), '-Q']
    run(base + ['--batch', '-l', ROOT / 'tests/smoke.el'], env=env, cwd=tmp)

    # A real controlling terminal, rather than a --batch-only smoke test.
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(tmp)
        argv = base + ['-nw', '--eval', '(progn (switch-to-buffer "*v3-test*") (insert "中文 portable-pty-ok") (redisplay t) (kill-emacs 0))']
        os.execve(argv[0], argv, env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 100, 0, 0))
    output = bytearray()
    deadline = time.monotonic() + 30
    status = None
    try:
        while time.monotonic() < deadline:
            if select.select([fd], [], [], 0.1)[0]:
                try:
                    output.extend(os.read(fd, 65536))
                except OSError:
                    pass
            done, code = os.waitpid(pid, os.WNOHANG)
            if done:
                status = code
                break
        if status is None:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            raise RuntimeError('PTY startup timed out')
        assert os.waitstatus_to_exitcode(status) == 0, output.decode(errors='replace')
        assert b'portable-pty-ok' in output, output.decode(errors='replace')
    finally:
        os.close(fd)
    print('PASS: relocated symlink, runtime data, external module/grammar and PTY', flush=True)

    name = 'portable-test-' + uuid.uuid4().hex
    daemon = subprocess.Popen(base + ['--fg-daemon=' + name], env=env, cwd=tmp,
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    client = moved / 'bin/emacsclient'
    try:
        for _ in range(100):
            if daemon.poll() is not None:
                raise RuntimeError(daemon.stderr.read().decode(errors='replace'))
            response = subprocess.run([str(client), '--socket-name=' + name, '-e', '(+ 20 22)'],
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=3)
            if response.returncode == 0:
                assert response.stdout.strip() == b'42'
                break
            time.sleep(0.1)
        else:
            raise RuntimeError('Daemon not ready')
        run([client, '--socket-name=' + name, '-e', '(kill-emacs 0)'], stdout=subprocess.DEVNULL)
        assert daemon.wait(timeout=10) == 0
    finally:
        if daemon.poll() is None:
            daemon.terminate()
            daemon.wait(timeout=10)
        daemon.stderr.close()
    print('PASS: relocated daemon/emacsclient', flush=True)

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def handle(self):
            try:
                super().handle()
            except ConnectionError:
                # Expected when the client rejects our untrusted certificate.
                pass
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(b'portable-tls-ok')))
            self.end_headers()
            self.wfile.write(b'portable-tls-ok')
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(fixtures / 'cert.pem', fixtures / 'key.pem')
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = 'https://localhost:' + str(server.server_port) + '/'
        for trusted in (True, False):
            trust = '(list ' + json.dumps(str(fixtures / 'ca.pem')) + ')' if trusted else 'nil'
            expression = f'''(progn (require 'url) (require 'gnutls) (require 'nsm)
              (let ((gnutls-trustfiles {trust}) (gnutls-verify-error t)
                    (network-security-level 'medium) (url-proxy-services '(("no_proxy" . ".*"))))
                (let ((ok (condition-case err
                    (let ((b (url-retrieve-synchronously {json.dumps(url)} t t 10)))
                      (when b (with-current-buffer b
                        (goto-char (point-min)) (search-forward "portable-tls-ok" nil t))))
                    (error (message "TLS request: %S" err) nil))))
                  (unless (eq (not (null ok)) {'t' if trusted else 'nil'})
                    (dolist (b (buffer-list))
                      (when (string-match-p "\\\\*\\\\(Messages\\\\|Warnings\\\\)\\\\*" (buffer-name b))
                        (princ (with-current-buffer b (buffer-string)))))
                    (error "TLS acceptance/rejection mismatch")))))'''
            run(base + ['--batch', '--eval', expression], env=env, cwd=tmp)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    print('PASS: TLS accepted with trusted CA and rejected without trust', flush=True)

print('ALL ACCEPTANCE TESTS PASSED', flush=True)
