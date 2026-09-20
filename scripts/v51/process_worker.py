"""Fixture-only durable-cut worker. Never used by the shipped automatic runtime."""
import base64
import fcntl
import json
import os
from pathlib import Path
import sys
import time


def main():
    root=Path(sys.argv[1]);root.mkdir(exist_ok=False)
    with (root/'worker.lock').open('wb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        def emit(event,**extra):
            print(json.dumps(dict(event=event,pid=os.getpid(),monotonicNanos=time.monotonic_ns(),**extra)),flush=True)
        emit('ready',generation=1,execution='fixture-process-only')
        request=json.loads(sys.stdin.readline())
        def cut(stage):
            emit(stage)
            if stage==request['cut']:
                emit('barrier',cut=stage)
                command=sys.stdin.readline().strip()
                if command=='halt':os._exit(97)
                if command!='continue':raise ValueError('missing barrier release')
        cut('before-write')
        payload=base64.b64decode(request['frame'],validate=True)
        with (root/'authority.gsr').open('xb') as output:
            output.write(payload);output.flush();cut('after-write')
            os.fsync(output.fileno())
            parent=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(parent)
            finally:os.close(parent)
            cut('after-force');cut('before-ack')
            emit('ack',sha256=__import__('hashlib').sha256(payload).hexdigest())
            cut('after-ack')
        emit('complete')

if __name__=='__main__':main()
