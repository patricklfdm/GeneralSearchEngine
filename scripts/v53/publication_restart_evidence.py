"""Original-first replay of completed publication across receiving process loss.

This checks actual original voting/application, checkpoint network receipts,
interrupted selector/retention bytes and a fresh receiver's exact ACK. The first
sender exhausts its bounded I/O attempts; explicit identical resubmission after
restart is not autonomous recovery or a new vote/application.
"""
import argparse
import base64
import copy
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from . import remote_publication_evidence as remote

q, p, c, f, e, need = remote.q, remote.p, remote.c, remote.f, remote.e, remote.need
POINTS = ('PUBLICATION_SELECTOR_FORCED', 'FUTURE_RETENTION_PROMOTED',
          'PUBLICATION_BEFORE_RETURN', 'PUBLICATION_ACK_BEFORE_RETURN')


def log(path):
    lines = p.t.plans.read(path, 8*e.MIB).decode().splitlines()
    need(all(line.startswith(('EVENT ', 'CUT ', 'REQUEST ', 'WIRE ', 'RECEIVED ', 'CHECKPOINT ', 'READY ', 'CLOSED '))
             for line in lines), 'publication restart log shape')
    return lines, [line[6:] for line in lines if line.startswith('EVENT ')]


def wire(raw):
    return remote.transfer.wire(raw)


def checkpoint(rows, raw, identities, cap, selected):
    """Complete real transport of the original checkpoint, not its expected hash."""
    traces = {wire(row['request'])[1]['trace'] for row in rows}
    need(len(traces) == 1 and len(rows) == 3, 'publication restart complete checkpoint exchange')
    digest = e.digest(raw); offset = 0; tid = None
    for index, row in enumerate(rows):
        need(set(row) == {'request', 'response', 'withheld'} and row['withheld'] is False,
             'publication restart checkpoint wire shape')
        kind, sent = wire(row['request']); reply_kind, reply = wire(row['response'])
        need(sent['root'] == cap['root'] and sent['view'] == selected['view'] and sent['ballot'] == selected['ballot']
             and sent['sender'] == identities['node-3'] and sent['recipient'] == identities['node-1']
             and sent['sequence'] == index+1 and
             {k: v for k, v in reply.items() if k != 'payload'} ==
             dict({k: v for k, v in sent.items() if k != 'payload'}, sender=sent['recipient'], recipient=sent['sender']),
             'publication restart checkpoint correlation')
        a, b = sent['payload'], reply['payload']
        if index == 0:
            tid = a['id']
            need((kind, reply_kind) == ('CHUNK', 'SOURCE_OFFER') and
                 a == dict(id=tid, action='REQUEST', offset=0, digest=digest, bytes='') and
                 b == dict(id=tid, digest=digest, bytes=len(raw), kind='RECORD'), 'publication restart checkpoint offer')
        elif index == 1:
            need((kind, reply_kind) == ('CHUNK', 'CHUNK') and
                 a == dict(id=tid, action='REQUEST', offset=0, digest=digest, bytes='') and
                 b == dict(id=tid, action='DATA', offset=0, digest=digest, bytes=base64.b64encode(raw).decode()),
                 'publication restart checkpoint original bytes')
            offset = len(raw)
        else:
            need((kind, reply_kind) == ('TRANSFER_COMMIT', 'TRANSFER_COMMIT') and
                 a == b == dict(id=tid, digest=digest) and offset == len(raw), 'publication restart checkpoint commit')
    return [base64.b64decode(row['response'], validate=True) for row in rows]


def validate(root):
    root = Path(root); result = q.read(root/'restart-result.json'); mode, point = result.get('mode'), result.get('cut')
    need(mode in ('halt', 'kill') and point in POINTS, 'publication restart case')
    need(result == dict(status='PASS', mode=mode, cut=point, exit=23 if mode == 'halt' else 137,
                        resumeExit=0, duplicateReceipts=2, originalDispatch='IO_FAILED'), 'publication restart exact exit')
    before, ends = q.prelude(root, 3, suffix=[('node-3', 'lock-probe')] if mode == 'kill' else [])
    p.match(root, 'crash-ready', before)
    identities = {node: q.future.identity(files) for node, files in before.items()}
    cap, selected, logical = q.payload(before, ends)
    retained = {node: q.pending(before[node], ends[node], identities['node-3']) for node in ('node-1', 'node-3')}
    lines, events = log(root/'worker.log'); resumed, recovery = log(root/'resume.log')
    need(events[-1] == point and lines.count('CUT '+point) == 1 and lines.count('READY '+mode) == 1,
         'publication restart exact interruption')
    # Another connection may be read while the writer is stopped at its cut.
    # It must not produce another storage event or any response after that cut.
    need(all(line.startswith('REQUEST ') for line in lines[lines.index('CUT '+point)+1:]),
         'publication restart work after interruption')
    q.n.native_order(events, 1)
    q.s.ordered(events, ['APPLY_BEFORE_RETURN', 'FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_PARENT_FORCED',
                        'FUTURE_RETENTION_ACK_BEFORE_RETURN', 'PUBLICATION_SELECTOR_FORCED'], 'restart original force')
    required = ['PUBLICATION_SELECTOR_FORCED']
    if point != POINTS[0]: required += ['RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_PROMOTED']
    if point in POINTS[2:]: required += ['FUTURE_RETENTION_CLEARED', 'PUBLICATION_BEFORE_RETURN']
    if point == POINTS[3]: required += ['PUBLICATION_ACK_BEFORE_RETURN']
    q.s.ordered(events, required, 'restart interrupted force')
    need(events.count('PUBLICATION_SELECTOR_FORCED') == 1, 'publication restart one original selector')
    sent_raw = p.t.plans.read(root/'publication-request.gsrp', 32768); sent = f.decode(sent_raw, 'wire', 'PUBLISH')
    expected_sent = dict(root=cap['root'], view=selected['view'], ballot=selected['ballot'], sender=identities['node-1'],
                         recipient=identities['node-3'], trace=sent['trace'], sequence=4, payload=dict(certificate=logical['certificate']))
    need(sent == expected_sent and str(uuid.UUID(sent['trace'])) == sent['trace'], 'publication restart original request')
    requests = [wire(line[8:]) for line in lines if line.startswith('REQUEST ')]
    publications = [v for v in requests if v[0] == 'PUBLISH']
    need(1 <= len(publications) <= 3 and all(v == ('PUBLISH', sent) for v in publications),
         'publication restart original received request')
    future = dict(sent, sequence=3, payload=logical)
    need(requests == [('FUTURE_RETENTION_INTENT', future)]+publications, 'publication restart exact incoming operations')
    original_wire = [json.loads(line[5:]) for line in lines if line.startswith('WIRE ')]
    need(len(original_wire) == 1 and wire(original_wire[0]['request']) == ('FUTURE_RETENTION_INTENT', future),
         'publication restart no premature ACK')
    future_ack = base64.b64decode(original_wire[0]['response'], validate=True)
    q.acknowledgement(future_ack, future, e.digest(f.canonical(logical)), retained['node-3'])
    transfers = q.read(root/'publication-wire.json')
    actual = checkpoint(transfers, ends['node-1']['ack.gsr'], identities, cap, selected)
    need([base64.b64decode(line[9:], validate=True) for line in lines if line.startswith('RECEIVED ')] == actual,
         'publication restart checkpoint delivery')
    checkpoint_line = 'CHECKPOINT '+base64.b64encode(ends['node-1']['ack.gsr']).decode()
    need(lines.count(checkpoint_line) == 1 and
         lines.index('REQUEST '+base64.b64encode(sent_raw).decode()) < lines.index(checkpoint_line) < lines.index('EVENT PUBLICATION_SELECTOR_FORCED') and
         max(i for i, line in enumerate(lines) if line.startswith('RECEIVED ')) < lines.index(checkpoint_line),
         'publication restart checkpoint before selector')
    timeline = q.read(root/'timeline.json')
    quorum = dict(node='node-1', event='FUTURE_QUORUM_COMPLETE', voters=['node-1', 'node-3'])
    need(timeline.count(quorum) == 1, 'publication restart original governing quorum')
    qi = timeline.index(quorum)
    need(dict(node='node-1', event='NETWORK_RECEIVED', kind='FUTURE_RETENTION_ACK', digest=e.digest(future_ack)) in timeline[:qi],
         'publication restart recording delivered before dispatch')
    q.s.ordered([v['event'] for v in timeline[:qi] if v['node'] == 'node-1'],
                ['FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_PARENT_FORCED'], 'restart local original recording')
    sends = [(i, row) for i, row in enumerate(timeline) if row['event'] == 'PUBLICATION_SEND_BOUNDARY']
    need(len(publications)+2 <= len(sends) <= 5 and all(i > qi and row == dict(node='node-1', event='PUBLICATION_SEND_BOUNDARY', digest=e.digest(sent_raw))
                                    for i, row in sends), 'publication restart unchanged resubmission')
    final = {node: dict(files, **({q.future.FILE: retained[node]} if node in retained else {})) for node, files in before.items()}
    target = remote.published(final['node-3'], ends['node-3'], [ends[node]['ack.gsr'] for node in ('node-1', 'node-3')], 'node-3')
    ledger = q.s.r.decode(before['node-3'][q.s.FILE]); plan = copy.deepcopy(ledger['plan'])
    next(v for v in plan['peers'] if v['identity'] == identities['node-3'])['possible'].append(logical['upper'])
    target[q.s.FILE] = q.s.r.frame(dict(ledger, revision=ledger['revision']+1, previous=e.digest(before['node-3'][q.s.FILE]), plan=plan))
    target[q.future.FILE] = q.future.frame(dict(q.future.initial(before['node-3']), revision=2, previous=e.digest(retained['node-3'])), {})
    final['node-3'] = target
    interrupted = dict(target)
    if point == POINTS[0]:
        interrupted.update({k: v for k, v in before['node-3'].items() if k == 'pending.accept' or k == 'applied-end' or k.startswith('applied-end/')})
        interrupted[q.s.FILE] = before['node-3'][q.s.FILE]
    if point in POINTS[:2]: interrupted[q.future.FILE] = retained['node-3']
    need(c.inventory(root/'interrupted') == interrupted, 'publication restart exact interrupted files')
    need(c.inventory(root/'recovered') == target, 'publication restart exact recovered files')
    p.match(root, 'after-endpoint', final)
    selector = f.decode(target['selector.gsr'], 'records', 'SELECTOR')
    expected_ack = dict(sent, sender=sent['recipient'], recipient=sent['sender'],
                        payload=dict(certificate=logical['certificate'], selection=logical['selection'], published=logical['upper'],
                                     generation=e.digest(target['generations/'+selector['generation']+'/generation.gsr'])))
    ack_raw = p.t.plans.read(root/'publication-ack.gsrp', 32768)
    need(f.decode(ack_raw, 'wire', 'PUBLISH_ACK') == expected_ack, 'publication restart durable acknowledgement')
    need(resumed.count('READY resume') == 1 and resumed[-1] == 'CLOSED resume' and not any(v.startswith(('CUT ', 'CHECKPOINT ', 'RECEIVED ')) for v in resumed),
         'publication restart completed receiver lifecycle')
    ready = resumed.index('READY resume'); after_ready = resumed[ready+1:-1]
    ack_wire = dict(request=base64.b64encode(sent_raw).decode(), response=base64.b64encode(ack_raw).decode())
    expected_lines = ['REQUEST '+base64.b64encode(sent_raw).decode(), 'EVENT PUBLICATION_ACK_BEFORE_RETURN', 'WIRE '+f.canonical(ack_wire).decode()]*2
    need(after_ready == expected_lines, 'publication restart no reapplication or new observations')
    forbidden = {'NATIVE_CERTIFICATE_RETAINED', 'ACCEPT_BEFORE_WRITE', 'PROOF_BEFORE_WRITE', 'PUBLICATION_SELECTOR_FORCED'}
    need(not forbidden.intersection(recovery) and not any(v.startswith(('APPLY_', 'CERTIFICATE_', 'PROMISE_', 'BASIS_', 'SELECTED_', 'GRANT_', 'INSTALL_')) for v in recovery)
         and recovery.count('PUBLICATION_ACK_BEFORE_RETURN') == 2, 'publication restart no new vote or selector')
    if point == POINTS[0]: q.s.ordered(recovery, ['PUBLICATION_COVERAGE_VALIDATED', 'PUBLICATION_RETIRED', 'FUTURE_RETENTION_PROMOTED', 'FUTURE_RETENTION_CLEARED'], 'restart recovered force')
    elif point == POINTS[1]: q.s.ordered(recovery, ['FUTURE_RETENTION_PROMOTED', 'FUTURE_RETENTION_CLEARED'], 'restart recovered force')
    delivered = [(i, v) for i, v in enumerate(timeline) if v.get('kind') == 'PUBLISH_ACK']
    need(len(delivered) == 2 and sends[-2][0] < delivered[0][0] < sends[-1][0] < delivered[1][0] and
         all(v == dict(node='node-1', event='NETWORK_RECEIVED', kind='PUBLISH_ACK', digest=e.digest(ack_raw))
             for _, v in delivered), 'publication restart actual ACK delivery')
    return dict(status='PASS', mode=mode, cut=point, processes=2, originalDispatch='IO_FAILED', resumedReceipts=2,
                reapplication=False, autonomous=False, phase3Complete=False)


def qualify(root):
    root = Path(root); original = validate(root); negatives = []
    variants = [('certificate', 'admitted exact certified: node-1'), ('checkpoint', 'publication restart checkpoint original bytes'),
                ('interrupted', 'publication restart exact interrupted files'), ('recovered', 'publication restart exact recovered files'),
                ('ack', 'publication restart durable acknowledgement'), ('request', 'publication restart original request'),
                ('quorum', 'publication restart recording delivered before dispatch'), ('reapply', 'publication restart no reapplication or new observations'),
                ('exit', 'publication restart exact exit'), ('future-force', 'selected retention force order: restart original force'),
                ('premature-ack', 'publication restart no premature ACK')]
    for name, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-publication-restart-negative-') as temp:
            dest = Path(temp)/'raw'; shutil.copytree(root, dest)
            if name in ('certificate', 'interrupted', 'recovered'):
                path = dest/('certified/node-1/pending.accept' if name == 'certificate' else name+'/selector.gsr')
                raw = path.read_bytes(); path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name in ('ack', 'request'):
                path = dest/('publication-'+name+'.gsrp'); kind = 'PUBLISH_ACK' if name == 'ack' else 'PUBLISH'
                value = f.decode(path.read_bytes(), 'wire', kind)
                value['payload']['generation' if name == 'ack' else 'certificate'] = 'f'*64
                path.write_bytes(f.encode('wire', kind, value))
            elif name == 'quorum':
                path = dest/'timeline.json'; path.write_text(json.dumps([v for v in q.read(path) if v.get('kind') != 'FUTURE_RETENTION_ACK']))
            elif name == 'exit':
                path = dest/'restart-result.json'; value = q.read(path); value['exit'] = 0; path.write_text(json.dumps(value))
            elif name == 'reapply':
                path = dest/'resume.log'; path.write_text(path.read_text().replace('READY resume\n', 'READY resume\nEVENT NATIVE_CERTIFICATE_RETAINED\n'))
            elif name == 'future-force':
                path = dest/'worker.log'; path.write_text(path.read_text().replace('EVENT FUTURE_RETENTION_PARENT_FORCED\n', ''))
            elif name == 'premature-ack':
                path = dest/'worker.log'
                row = dict(request=base64.b64encode((dest/'publication-request.gsrp').read_bytes()).decode(),
                           response=base64.b64encode((dest/'publication-ack.gsrp').read_bytes()).decode())
                path.write_text(path.read_text().replace('CUT ', 'WIRE '+f.canonical(row).decode()+'\nCUT '))
            else:
                path = dest/'publication-wire.json'; rows = q.read(path)
                row = next(v for v in rows if wire(v['response'])[0] == 'CHUNK'); kind, value = wire(row['response'])
                value['payload']['bytes'] = base64.b64encode(b'wrong').decode(); value['payload']['digest'] = e.digest(b'wrong')
                row['response'] = base64.b64encode(f.encode('wire', kind, value)).decode(); path.write_text(json.dumps(rows))
            try: validate(dest)
            except ValueError as error: need(str(error) == reason, 'publication restart wrong negative: '+name+': '+str(error))
            else: raise ValueError('publication restart mutation accepted: '+name)
        negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
