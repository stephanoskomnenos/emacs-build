"""Training-only RPC with variable messages and writes; no LSP implementation."""
import json
import os
import sys
import time


def write_all(data):
    while data:
        data = data[os.write(1, data):]


if sys.argv[1] == 'rpc':
    messages = []
    for i in range(180):
        diagnostics = [dict(message='训练消息 ' + 'detail ' * (32 if i % 11 == 0 else 1),
                            severity=1 + j % 3,
                            range={'start': {'line': i % 70, 'character': j},
                                   'end': {'line': i % 70, 'character': j + 2}},
                            relatedInformation=[{'message': 'context', 'code': i}])
                       for j in range((0, 1, 3, 12)[i % 4])]
        messages.append((json.dumps({'jsonrpc': '2.0', 'method': 'textDocument/publishDiagnostics',
                                    'params': {'ordinal': i, 'uri': f'file:///training/unit-{i % 9}.c',
                                               'diagnostics': diagnostics}}, ensure_ascii=False) + '\n').encode())
    if sys.argv[2] == 'batched':
        for start in range(0, len(messages), 15):
            write_all(b''.join(messages[start:start + 15]))
            time.sleep(0.002)
    else:
        data=b''.join(messages)
        sizes=(1, 61, 4093, 127, 8192)
        position=index=0
        while position < len(data):
            size=sizes[index % len(sizes)]
            write_all(data[position:position + size])
            position += size;index += 1
            if index % 20 == 0:time.sleep(0.001)
else:
    write_all(''.join(f'unit-{i % 9}.c:{i + 1}:3: warning: training diagnostic {i}\n' for i in range(120)).encode())
