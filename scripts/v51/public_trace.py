"""Complete only an exited observer's exact, pre-published telemetry append.

Replica authority is never touched. Final evidence readers remain strict JSONL
readers; live readers expose only newline-terminated observations.
"""
import hashlib
import json
from pathlib import Path
import struct
from .performance_model import need

FAULT_LINE_BYTES = 4 << 20
FAULT_SEGMENT_BYTES = 32 << 20
FAULT_TRACE_BYTES = 128 << 20


def fault_rows(root, node):
    """Read complete stopped fault segments, with one per-node decoded ceiling."""
    from .performance_model import strict_json
    root = Path(root); name = node+'-trace'
    paths = [root/(name+'.jsonl'), *sorted(root.glob(name+'-part*.jsonl'))]
    need(not list(root.glob(name+'*.jsonl.gz')), 'mixed fault trace encodings')
    rows = []; total = 0; orders = {}
    for i, path in enumerate(paths):
        expected = root/(name+('' if i == 0 else f'-part{i:04d}')+'.jsonl')
        # A legacy unsegmented live-source copy can be inspected before packing.
        bound = FAULT_TRACE_BYTES if len(paths) == 1 else FAULT_SEGMENT_BYTES
        need(path == expected and path.is_file() and not path.is_symlink() and
             0 < path.stat().st_size <= bound, 'fault trace member bound/type')
        total += path.stat().st_size
        need(total <= FAULT_TRACE_BYTES, 'fault trace per-node bound')
        with path.open('rb') as stream:
            while True:
                line = stream.readline(FAULT_LINE_BYTES+1)
                if not line: break
                need(len(line) <= FAULT_LINE_BYTES and line.endswith(b'\n'), 'fault trace response bound/completeness')
                row = strict_json(line)
                need(row['node'] == node and all(type(row[k]) is int and row[k] > 0
                     for k in ('pid', 'generation', 'order', 'localNanos')), 'fault trace process/counter types')
                identity = row['pid'], row['generation']
                need(row['order'] == orders.get(identity, 0)+1, 'fault trace order discontinuity')
                orders[identity] = row['order']
                rows.append(row)
    return rows


def copy_fault_trace(source, destination, node):
    """Losslessly segment a stopped trace; never trim rows or change live input.

    The caller has reaped all voter generations and completed any published tail.
    In-place use is only for the stopped local qualification before archive pack.
    """
    import tempfile
    source, destination = Path(source), Path(destination)
    name = node+'-trace'; path = source/(name+'.jsonl')
    need(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= FAULT_TRACE_BYTES,
         'fault trace per-node bound/type')
    need(not path.with_name(path.name+'.pending').exists(), 'fault trace unfinished append')
    need(not list(source.glob(name+'-part*')) and not list(source.glob(name+'*.gz')),
         'fault trace already segmented/mixed')
    same = source.resolve() == destination.resolve()
    need(same or not list(destination.glob(name+'*.jsonl*')), 'fault trace destination occupied')
    with tempfile.TemporaryDirectory(prefix='.fault-segments-', dir=destination) as temporary:
        stage = Path(temporary); segments = []; stream = None; size = total = 0
        try:
            with path.open('rb') as original:
                while True:
                    line = original.readline(FAULT_LINE_BYTES+1)
                    if not line: break
                    need(len(line) <= FAULT_LINE_BYTES and line.endswith(b'\n'), 'fault trace response bound/completeness')
                    total += len(line); need(total <= FAULT_TRACE_BYTES, 'fault trace per-node bound')
                    if stream is None or size+len(line) > FAULT_SEGMENT_BYTES:
                        if stream is not None: stream.close()
                        filename = name+('' if not segments else f'-part{len(segments):04d}')+'.jsonl'
                        segments.append(stage/filename); stream = segments[-1].open('xb'); size = 0
                    stream.write(line); size += len(line)
        finally:
            if stream is not None: stream.close()
        need(total == path.stat().st_size, 'fault trace changed during collection')
        for segment in segments: segment.replace(destination/segment.name)


def save(path, value): path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


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
    output=root/'trace-probe-fault-bound';output.mkdir()
    q.command(['java','-cp',cp,q.PACKAGE+'replication.V51PublicTraceProbe',str(output),'fault-bound','1'],
              output,'fault-bound')
    # The oversized sparse file only exercises rejection, and is not evidence.
    (output/'bounded.jsonl').unlink()
    segmented=output/'segments';segmented.mkdir()
    copy_fault_trace(output,segmented,'node-1')
    need(len(fault_rows(segmented,'node-1'))==34,'fault trace segment lost observations')
    checks.append(dict(boundary='fault-bound',status='PASS'))
    return dict(status='PASS',checks=checks)
