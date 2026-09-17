#!/usr/bin/env python3
"""Deterministic stdio LSP diagnostics replay; no language-analysis timing."""
import json
import os
from pathlib import Path
import sys
import threading
import time

os.sched_setaffinity(0, {1})  # Keep producer work off the measured Emacs CPU.
lock = threading.Lock()
root = Path(os.environ['LSP_LOAD_PROJECT'])
def packet(message):
    body = json.dumps(message, ensure_ascii=False, separators=(',', ':')).encode()
    return f'Content-Length: {len(body)}\r\n\r\n'.encode() + body
def write(data):
    with lock:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
def notify(method, params):
    write(packet(dict(jsonrpc='2.0', method=method, params=params)))

# Prepared before measurement, with a stable retained set of 64 document URIs.
packets = []
for file in range(64):
    diagnostics = [dict(range={'start': {'line': i, 'character': 0},
                               'end': {'line': i, 'character': 4}},
                        severity=i % 3 + 1, code=f'load-{i}', source='replay',
                        message=f'Diagnostic {file}/{i}: ' + 'Unicode 验证 λ; ' * 12,
                        relatedInformation=[dict(location=dict(uri=(root/f'file-{(file+1)%64}.txt').as_uri(),
                                                               range={'start': {'line': i, 'character': 0},
                                                                      'end': {'line': i, 'character': 4}}),
                                                 message='Related diagnostic context')])
                   for i in range(256)]
    packets.append(packet(dict(jsonrpc='2.0', method='textDocument/publishDiagnostics',
                               params=dict(uri=(root/f'file-{file}.txt').as_uri(), diagnostics=diagnostics))))

def replay(mode):
    started = time.monotonic()
    size = 0
    for i in range(1000):
        if mode == 'paced':
            time.sleep(max(0, started + i / 200 - time.monotonic()))
        data = packets[i % 64]
        write(data)
        size += len(data)
    notify('load/done', dict(messages=1000, wireBytes=size, producerSeconds=time.monotonic()-started))

seeded = False
while True:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            sys.exit(0)
        if line == b'\r\n':
            break
        name, value = line.decode().split(':', 1)
        headers[name.lower()] = value.strip()
    message = json.loads(sys.stdin.buffer.read(int(headers['content-length'])))
    method = message.get('method')
    if method == 'initialize':
        write(packet(dict(jsonrpc='2.0', id=message['id'], result=dict(
            capabilities=dict(textDocumentSync=2), serverInfo=dict(name='diagnostics-replay', version='1')))))
    elif method == 'textDocument/didOpen' and not seeded:
        seeded = True
        for data in packets:
            write(data)
        notify('load/ready', dict(files=64, diagnostics=16384))
    elif method == 'load/start':
        threading.Thread(target=replay, args=(message['params']['mode'],), daemon=True).start()
    elif method == 'shutdown':
        write(packet(dict(jsonrpc='2.0', id=message['id'], result=None)))
    elif method == 'exit':
        break
    elif 'id' in message:
        write(packet(dict(jsonrpc='2.0', id=message['id'], result=None)))
