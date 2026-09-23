"""Complete only an exited observer's exact, pre-published telemetry append.

Replica authority is never touched. Final evidence readers remain strict JSONL
readers; live readers expose only newline-terminated observations.
"""
import hashlib
import json
from pathlib import Path
import struct
from .storage_harness import need, save


def live_rows(root, node):
    raw = (Path(root) / (node + '-trace.jsonl')).read_text()
    return [json.loads(line) for line in raw.split('\n')[:-1]]


def finish(root, node, process, generation=1):
    # Never race a live writer, even when there is currently no pending record.
    need(process.poll() is not None, 'observer still running')
    path = Path(root) / (node + '-trace.jsonl')
    pending = path.with_name(path.name + '.pending')
    original = path.read_bytes() if path.exists() else b''
    if not pending.exists():
        need(not original or original.endswith(b'\n'), 'observer tail lacks published record')
        return
    data = pending.read_bytes()
    need(len(data) > 48 and data[:8] == b'GSETRC1\n', 'observer pending header')
    offset = struct.unpack('>Q', data[8:16])[0]; line = data[48:]
    need(hashlib.sha256(line).digest() == data[16:48], 'observer pending digest')
    need(line.endswith(b'\n') and len(line.splitlines()) == 1, 'observer pending line')
    row = json.loads(line)
    need(row['node'] == node and row['pid'] == process.pid and row['generation'] == generation,
         'observer pending process identity')
    need(type(row['order']) is int and row['order'] > 0, 'observer pending order')
    need(offset <= len(original) <= offset + len(line) and (offset == 0 or original[offset-1:offset] == b'\n'),
         'observer pending offset')
    tail = original[offset:]
    need(line.startswith(tail), 'observer append differs from published record')
    previous = json.loads(original[:offset].splitlines()[-1]) if offset else None
    order = previous['order'] + 1 if previous and previous['pid'] == process.pid else 1
    need(row['order'] == order, 'observer append order discontinuity')
    # Keep the exact published record and interrupted bytes for offline inspection.
    archive = path.with_name(path.name + f'.recovery-{process.pid}-{row["order"]}')
    archive.mkdir(exist_ok=True)
    (archive / 'pending.bin').write_bytes(data)
    (archive / 'partial.bin').write_bytes(tail)
    save(archive / 'receipt.json', dict(node=node, pid=process.pid, generation=generation,
         order=row['order'], offset=offset, appendedBytes=len(line)-len(tail), exitCode=process.returncode))
    with path.open('ab') as stream: stream.write(line[len(tail):])
    pending.unlink()


def verify_writer(root, cp):
    """Exercise the Java publication format and real SIGKILL before any candidates."""
    import select
    import subprocess
    from . import public_qualification_harness as q
    root = Path(root)
    q.command(['javac', '--release', '21', '-proc:none', '-cp', cp, '-d', root/'observer',
               q.ROOT/'scripts/v51/java/V51PublicTraceProbe.java'], root, 'compile-trace-probe')
    checks = []
    for boundary in ('before', 'partial', 'complete'):
        output = root / ('trace-probe-'+boundary); output.mkdir()
        with (output/'stderr.log').open('wb') as stderr:
            process = subprocess.Popen(['java','-cp',cp,q.PACKAGE+'replication.V51PublicTraceProbe',
                                        str(output),boundary,'1'], stdout=subprocess.PIPE, stderr=stderr)
            try:
                need(select.select([process.stdout],[],[],10)[0] and process.stdout.readline()==b'READY\n',
                     'trace probe did not reach append boundary')
                process.kill(); need(process.wait(timeout=10)==-9,'trace probe SIGKILL')
                finish(output,'node-1',process)
            finally:
                if process.poll() is None: process.kill(); process.wait(timeout=10)
                process.stdout.close()
        before = (output/'node-1-trace.jsonl').read_bytes()
        q.command(['java','-cp',cp,q.PACKAGE+'replication.V51PublicTraceProbe',str(output),'normal','2'],
                  output,'restart')
        path = output/'node-1-trace.jsonl'; rows=[json.loads(line) for line in path.read_bytes().splitlines()]
        need(path.read_bytes().startswith(before) and len(rows)==4,'trace probe lost or duplicated events')
        need([(r['generation'],r['order']) for r in rows]==[(1,1),(1,2),(2,1),(2,2)]
             and rows[1]['payload']==rows[3]['payload']=='x'*32768,'trace probe restart content')
        need(not path.with_name(path.name+'.pending').exists(),'trace probe pending after normal write')
        checks.append(dict(boundary=boundary,status='PASS'))
    return dict(status='PASS',checks=checks)
