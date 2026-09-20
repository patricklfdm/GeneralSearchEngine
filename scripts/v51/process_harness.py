"""Separate-PID fixture crash qualification, pre-reopen bytes and force/ACK evidence."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
from . import fixtures, format_inspector

CUTS=('before-write','after-write','after-force','before-ack','after-ack')


def validate(events,cut,returncode,method,raw,expected,pids):
    format_inspector.need(len(set(pids))==3 and all(p>0 for p in pids),'three concurrent PIDs')
    format_inspector.need(returncode==(-signal.SIGKILL if method=='kill' else 97),'actual process exit')
    kinds=[e['event'] for e in events]
    format_inspector.need(kinds[-1]=='barrier' and events[-1]['cut']==cut,'requested crash barrier')
    times=[e['monotonicNanos'] for e in events]
    format_inspector.need(times==sorted(times),'worker monotonic event order')
    format_inspector.need(all(e['pid']==pids[0] for e in events),'worker identity')
    if cut=='before-write':format_inspector.need(raw is None,'write occurred before cut')
    else:format_inspector.need(raw==expected,'pre-reopen bytes differ')
    if 'ack' in kinds:
        format_inspector.need(kinds.index('after-force')<kinds.index('ack'),'ACK without preceding force')
        format_inspector.need(next(e for e in events if e['event']=='ack')['sha256']==hashlib.sha256(expected).hexdigest(),'ACK byte identity')
    format_inspector.need(('ack' in kinds)==(cut=='after-ack'),'ACK cut mismatch')
    format_inspector.need(('after-force' in kinds)==(CUTS.index(cut)>=2),'force cut mismatch')


def line(process,timeout=10):
    ready,_,_=select.select([process.stdout],[],[],timeout)
    if not ready:raise TimeoutError('fixture worker output deadline')
    value=process.stdout.readline()
    if not value:raise ValueError('worker exited before barrier')
    return json.loads(value)


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    fixture=json.loads((fixtures.ROOT/'format-fixtures.json').read_text());cases=[]
    for name in ('PROMISE','ACCEPT','PROOF'):
        expected=base64.b64decode(fixture['storage'][name])
        for cut in CUTS:
            for method in ('kill','halt'):
                root=output/f'{name.lower()}-{cut}-{method}';root.mkdir();workers=[];events=[];logs=[]
                try:
                    for n in range(3):
                        log=(root/f'worker-{n}.stderr').open('wb');logs.append(log)
                        workers.append(subprocess.Popen([sys.executable,'-u','-m','scripts.v51.process_worker',str(root/f'node-{n}')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,bufsize=0))
                    ready=[line(p) for p in workers];pids=[e['pid'] for e in ready];events.append(ready[0])
                    if any(p.poll() is not None for p in workers):raise ValueError('workers not concurrent')
                    worker=workers[0]
                    worker.stdin.write((json.dumps(dict(cut=cut,frame=fixture['storage'][name]))+'\n').encode());worker.stdin.flush()
                    while events[-1]['event']!='barrier':events.append(line(worker))
                    if method=='kill':worker.kill()
                    else:worker.stdin.write(b'halt\n');worker.stdin.flush()
                    code=worker.wait(timeout=10)
                    path=root/'node-0/authority.gsr';raw=path.read_bytes() if path.exists() else None
                    # Archive before any reopen/recovery; no implementation rewrites the evidence.
                    if raw is not None:(root/'pre-reopen.gsr').write_bytes(raw);format_inspector.inspect(raw,name)
                    (root/'events.json').write_text(json.dumps(events,indent=2)+'\n')
                    record=dict(kind=name,cut=cut,method=method,exitCode=code,pids=pids,status='PASS',
                                preReopenSha256=hashlib.sha256(raw).hexdigest() if raw else None)
                    validate(events,cut,code,method,raw,expected,pids);cases.append(record)
                    (root/'result.json').write_text(json.dumps(record,indent=2)+'\n')
                finally:
                    if events and not (root/'events.json').exists():(root/'events.json').write_text(json.dumps(events,indent=2)+'\n')
                    for p in workers:
                        if p.poll() is None:p.kill()
                        p.wait(timeout=10)
                        if p.stdin:p.stdin.close()
                        if p.stdout:p.stdout.close()
                    for log in logs:log.close()
    result=dict(status='PASS',execution='fixture-process-only',cases=cases)
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();r=run(a.output)
    print(json.dumps(dict(status=r['status'],execution=r['execution'],cases=len(r['cases']))))
