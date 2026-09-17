"""Deterministic local JSON stream; no network or user data."""
import json
import os
import sys
count,chunk=map(int,sys.argv[1:])
data=''.join(json.dumps({'value':i,'message':'异步输出-'+str(i)},ensure_ascii=False)+'\n' for i in range(count)).encode()
for start in range(0,len(data),chunk):
    part=data[start:start+chunk]
    while part:
        written=os.write(1,part)
        part=part[written:]
