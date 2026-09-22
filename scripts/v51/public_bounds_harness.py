"""Public capacity, admission and wire rejection on owned local JVMs."""
import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tarfile
import time
import uuid
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_protocol_harness as protocol
from . import public_recovery_harness as recovery
from . import public_history, public_bounds_evidence as evidence, storage_inspector as storage
from .storage_harness import ROOT, need, save
from scripts.v50.offline_harness import CORE, REPLICATION

PROCESS_CASES = ('pending-read', 'pending-write', 'payload-limit', 'bulk-limit', 'document-limit', 'no-quorum-start')
ADMISSION_CASES = tuple(evidence.ADMISSION_REASONS)
CASES = (*PROCESS_CASES, *ADMISSION_CASES, 'wire-rejection')


def bootstrap(root, cp, configured=False):
    return q.command(['java', '-cp', cp, q.PACKAGE+'admission.'+('PublicAdmissionConsumer' if configured else 'PublicRuntimeConsumer'),
                      root, 'setup-configured' if configured else 'setup'], root, 'public-bootstrap')


def process_case(root, cp, case):
    root.mkdir(); (root/'bounds-profile.txt').write_text('small\n')
    workers = {}; history = []; expected = []; targets = []; starts = []; receipt = dict(status='FAIL', case=case)
    def start(node, generation=1):
        began = time.monotonic_ns(); workers[node] = q.Worker(root, node, cp, history, generation=generation, consumer='lifecycle')
        starts.append(dict(node=node, pid=workers[node].proc.pid, startNanos=began, endNanos=time.monotonic_ns()))
        save(root/'worker-starts.json', starts)
    def docs(tag, count=1): return [dict(id=tag+i, value=f'tag-{tag+i}') for i in range(count)]
    def denied(active, kind, **values):
        pending = active.send(kind, **values); targets.append(history[-1]['opId'])
        result = pending.result(timeout=35)
        need(result is not None, 'rejected call disconnected'); return result
    def write(active, values): active.call('addAll', documents=values); expected.extend(values)
    try:
        bootstrap(root, cp); start('node-1')
        if case == 'no-quorum-start':
            fault.wait_for(lambda: any(r['event'] == 'FORCE' and r['kind'] == 'PROMISE' for r in fault.rows(root, 'node-1')), 'solo voter never campaigned')
            denied(workers['node-1'], 'addAll', documents=docs(90)); denied(workers['node-1'], 'read')
        start('node-2'); start('node-3'); node, active = fault.leader(workers)
        for tag in (10, 11): write(active, docs(tag))
        need(active.call('read')['documents'] == expected, 'seed read')
        if case.startswith('pending-'):
            cut = 'READ_CAPTURED' if case == 'pending-read' else 'ACCEPT_AFTER_FORCE'
            fault.replace(root/(node+'-arm.txt'), cut+'\npause\n')
            held = active.send('read') if case == 'pending-read' else active.send('addAll', documents=docs(20))
            receipt['held'] = history[-1]['opId']
            reached = fault.wait_for(lambda: next((r for r in fault.rows(root, node) if r['event'] == 'CUT_REACHED'), None), 'capacity pause not reached')
            need(reached['cut'] == cut and reached['pid'] == active.proc.pid, 'wrong capacity pause')
            denied(active, 'addAll', documents=docs(90)); denied(active, 'read')
            (root/(node+'-release')).touch()
            result = held.result(timeout=35); need(result is not None and result['outcome'] == 'SUCCESS', 'held call failed')
            if case == 'pending-write': expected.extend(docs(20))
            else: need(result['documents'] == expected, 'held read projection')
        elif case == 'payload-limit': denied(active, 'addAll', documents=[dict(id=90, value='x'*100000)])
        elif case == 'bulk-limit': denied(active, 'addAll', documents=docs(90, 5))
        elif case == 'document-limit': denied(active, 'addAll', documents=docs(90, 3))
        node, active = protocol.read_after_recovery(workers, expected)
        write(active, docs(30)); node, active = protocol.read_after_recovery(workers, expected)
        workers.pop(node).stop(); receipt['retained'] = recovery.archive(root, node)
        start(node, 2); node, active = protocol.read_after_recovery(workers, expected)
        receipt.update(expected=expected, targets=targets, finalLeader=node)
    except BaseException as error: receipt['failure'] = str(error); raise
    finally:
        for node in workers: (root/(node+'-release')).touch()
        errors = []
        for worker in workers.values():
            try: worker.stop()
            except Exception as error: errors.append(str(error))
        if errors: receipt['cleanupErrors'] = errors
        save(root/'history.json', history); save(root/'receipt.json', receipt)
        need(not errors, 'bounds worker cleanup: '+str(errors))
    try:
        traces = physical.traces_at(root)
        receipt['history'] = public_history.check(history)
        receipt['physical'] = physical.physical(root, history, traces)
        receipt['bounds'] = evidence.bounds(root, history, traces, case, targets)
        receipt['negatives'] = physical.negatives(root, history)
        args = [history, traces, case, targets]
        receipt['negatives'] += evidence.negatives(evidence.rejection_history, args, [
            ('changed-rejection', lambda a: next(v for v in a[0] if v['opId'] == a[3][0]).update(outcome='SUCCESS')),
            ('missing-worker-rejection', lambda a: [rows.__setitem__(slice(None), [r for r in rows if r['event'] != 'CLIENT_FAILURE']) for rows in a[1].values()]),
            ('missing-resumed-write', lambda a: a[0].__setitem__(slice(None), [v for v in a[0] if not (v['kind'] == 'addAll' and v['outcome'] == 'SUCCESS')]))])
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


def inventory(root): return {f'node-{i}': storage.inventory(root/f'node-{i}') for i in (1, 2, 3)}


def version(frame, minor):
    header = bytearray(frame[:16]); struct.pack_into('>H', header, 6, minor)
    return bytes(header)+hashlib.sha256(header+frame[48:]).digest()+frame[48:]


def admission_case(root, cp, case):
    root.mkdir(); receipt = dict(status='FAIL', case=case)
    try:
        bootstrap(root, cp, case == 'automatic-on-configured')
        original = inventory(root)
        if case.startswith('disk-'):
            path = root/'node-1/manifest.gsr'; path.write_bytes(version(path.read_bytes(), 0 if case == 'disk-v10' else 1))
        before = inventory(root); results = []; after = []
        save(root/'fault-inventory.json', dict(original=original, before=before))
        with tarfile.open(root/'rejected-authority.tar.gz', 'w:gz') as tar:
            for i in (1, 2, 3): tar.add(root/f'node-{i}', arcname=f'node-{i}')
        receipt['authority'] = evidence.admission_authority(root, case, original, before)
        for attempt in (1, 2):
            result = q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicAdmissionConsumer', root, case], root, f'probe-{attempt}')
            results.append(json.loads(result.stdout)); after.append(inventory(root))
            save(root/'probe-results.json', dict(attempts=results, afterEach=after))
        receipt.update(before=before, afterEach=after, attempts=results, validation=evidence.admission(case, before, after, results))
        receipt['negatives'] = evidence.negatives(evidence.admission, [case, before, after, results], [
            ('mutated-authority', lambda a: a[2][0].clear()),
            ('copied-process', lambda a: a[3][1].update(pid=a[3][0]['pid'])),
            ('accepted-wrong-authority', lambda a: a[3][0].update(outcome='SUCCESS'))])
        # Correct settings can still acquire ownership after rejected opens.
        if not case.startswith('disk-'):
            action = 'configured-control' if case == 'automatic-on-configured' else 'automatic-control'
            control = json.loads(q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicAdmissionConsumer', root, action], root, 'valid-control').stdout)
            need(control['outcome'] == 'SUCCESS', 'valid public control could not start after rejection'); receipt['control'] = control
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


def encode_wire(value, minor=2):
    body = storage.canonical(value); header = struct.pack('>4sHHHHi', b'GSRP', 1, minor, 1, 0, len(body))
    return header+hashlib.sha256(header+body).digest()+body


def exchange(port, frame):
    response = b''; deadline = time.monotonic()+3
    with socket.create_connection(('127.0.0.1', port), timeout=3) as connection:
        connection.settimeout(max(.001, deadline-time.monotonic()))
        connection.sendall(frame)
        try:
            while True:
                need(time.monotonic() < deadline, 'wire exchange deadline')
                connection.settimeout(max(.001, deadline-time.monotonic()))
                chunk = connection.recv(65536)
                if not chunk: break
                response += chunk; need(len(response) <= 1 << 20, 'wire response byte bound')
            terminal = 'EOF'
        except ConnectionResetError: terminal = 'RESET'
    return response, terminal


def wire_case(root, cp):
    root.mkdir(); (root/'bounds-profile.txt').write_text('wire\n')
    receipt = dict(status='FAIL', case='wire-rejection'); worker = None; probes = []
    try:
        bootstrap(root, cp); history = []; worker = q.Worker(root, 'node-1', cp, history, consumer='lifecycle')
        raw = (root/'node-1/manifest.gsr').read_bytes(); manifest = dict(storage.f.inspect(raw, 'MANIFEST'), digest=raw[16:48].hex())
        base = dict(protocol='gse-replication/1.2', groupId=manifest['groupId'], configurationId=manifest['configurationId'],
                    manifestDigest=manifest['digest'], epoch=1, proposer=None, incarnationId=storage.f.ZERO,
                    sender='node-2', recipient='node-1', type='HANDSHAKE', traceId=str(uuid.uuid4()), eventSequence=1, payload=dict(mode='AUTOMATIC'))
        port = int((root/'ports.txt').read_text().splitlines()[0])
        def b64(raw): return base64.b64encode(raw).decode()
        for case in ('wire-v10', 'wire-v11', 'wire-mode', 'wire-protocol', 'wire-group', 'wire-manifest', 'wire-oversize'):
            base['eventSequence'] += 1; value = copy.deepcopy(base); minor = 2
            if case in ('wire-v10', 'wire-v11'): minor = 0 if case == 'wire-v10' else 1
            elif case == 'wire-mode': value['payload']['mode'] = 'CONFIGURED'
            elif case == 'wire-protocol': value['protocol'] = 'gse-replication/1.1'
            elif case == 'wire-group': value['groupId'] = '22222222-2222-2222-2222-222222222222'
            elif case == 'wire-manifest': value['manifestDigest'] = '0'*64
            frame = encode_wire(value, minor)
            if case == 'wire-oversize':
                header = struct.pack('>4sHHHHi', b'GSRP', 1, 2, 1, 0, 1<<20); frame = header+hashlib.sha256(header).digest()
            good = encode_wire(base)
            # Prove the socket is live both before and after sending invalid bytes.
            initial, _ = exchange(port, good); storage.f.wire(initial, manifest)
            before = inventory(root); reply, terminal = exchange(port, frame); after = inventory(root)
            control, _ = exchange(port, good)
            probes.append(dict(case=case, request=b64(frame), response=b64(reply), terminal=terminal, before=before, after=after,
                               controlRequest=b64(good), initialResponse=b64(initial), controlResponse=b64(control), maxFrameBytes=1<<20))
            save(root/'wire-probes.json', probes)
        receipt['validation'] = evidence.wire(manifest, probes)
        receipt['negatives'] = evidence.negatives(evidence.wire, [manifest, probes], [
            ('timeout-is-not-rejection', lambda a: a[1][0].update(terminal='TIMEOUT')),
            ('successful-invalid-response', lambda a: a[1][0].update(response=a[1][0]['controlResponse'])),
            ('wire-mutated-authority', lambda a: a[1][0]['after'].clear()),
            ('missing-wire-probe', lambda a: a[1].pop()),
            ('wrong-valid-control', lambda a: a[1][0].update(controlResponse=a[1][0]['controlRequest']))])
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally:
        try:
            if worker: worker.stop()
        except BaseException as error:
            receipt.update(status='FAIL', cleanupFailure=str(error)); raise
        finally: save(root/'receipt.json', receipt)
    return receipt


def run(output, only=None):
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='FAIL', execution='public-admission-bounds', paidCloud=False, cases=[], scope='targeted-case' if only else 'complete-15-case-matrix')
    try:
        need(only is None or only in CASES, 'unknown public bounds case')
        receipt['head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
        source = {p: storage.sha((ROOT/p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT/p).is_file()}
        save(root/'source-inventory.json', source); receipt['sourceInventorySha256'] = storage.sha(storage.canonical(source))
        receipt['jars'] = {p.name: storage.sha(p.read_bytes()) for p in (CORE, REPLICATION)}
        module = ROOT/'general-search-engine-replication'; java = ROOT/'scripts/v51/java'
        need(all(p.stat().st_mtime_ns <= REPLICATION.stat().st_mtime_ns for p in (module/'src/main').rglob('*.java')), 'package current runtime first')
        classes = root/'consumer'; classes.mkdir(); observer = root/'observer'; observer.mkdir()
        jars = os.pathsep.join(map(str, (CORE, REPLICATION)))
        sources = [module/'src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java',
                   *[java/(n+'.java') for n in ('PublicRuntimeConsumer', 'PublicLifecycleConsumer', 'PublicAdmissionConsumer')]]
        q.command(['javac', '--release', '21', '-proc:none', '-cp', jars, '-d', classes, *sources], root, 'compile-consumer')
        q.command(['javac', '--release', '21', '-proc:none', '-cp', jars+os.pathsep+str(classes), '-d', observer, java/'V51PublicWorker.java'], root, 'compile-observer')
        cp = os.pathsep.join(map(str, (CORE, REPLICATION, classes, observer)))
        for case in CASES:
            if only and case != only: continue
            try:
                result = process_case(root/case, cp, case) if case in PROCESS_CASES else admission_case(root/case, cp, case) if case in ADMISSION_CASES else wire_case(root/case, cp)
                receipt['cases'].append(dict(case=case, status=result['status']))
            except Exception as error: receipt['cases'].append(dict(case=case, status='FAIL', failure=str(error)))
            print(json.dumps(receipt['cases'][-1]), flush=True)
        need(all(c['status'] == 'PASS' for c in receipt['cases']), 'public bounds cases failed: '+str(receipt['cases']))
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); parser.add_argument('--only')
    args = parser.parse_args(); run(args.output, args.only)
