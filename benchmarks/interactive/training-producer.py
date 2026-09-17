"""Local training-only RPC and compiler-like output, distinct from validation."""
import json
import os
import sys
if sys.argv[1]=='rpc':
    data=''.join(json.dumps({'jsonrpc':'2.0','method':'textDocument/publishDiagnostics','params':{'ordinal':i,'uri':f'file:///training/unit-{i%9}.c','diagnostics':[{'message':'训练消息','severity':1,'range':{'start':{'line':i%70,'character':2}}}]}},ensure_ascii=False)+'\n' for i in range(360)).encode()
else:
    data=''.join(f'unit-{i%9}.c:{i+1}:3: warning: training diagnostic {i}\n' for i in range(120)).encode()
for start in range(0,len(data),61):
    chunk=data[start:start+61]
    while chunk:
        written=os.write(1,chunk);chunk=chunk[written:]
