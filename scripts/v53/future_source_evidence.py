"""Original-first replay of future obligations frozen by real native grants.

Derive the original bootstrap, certificate and actual applied end before building
any future/source frame. A copied proof is not a new voting or peer-progress ACK.
The current integration stops before selected installation of a future obligation.
"""
import argparse
import json
import shutil
import struct
import tempfile
import uuid
from pathlib import Path
from . import future_retention_evidence as u

n, s, p, c, f, e, need = u.n, u.s, u.p, u.c, u.f, u.e, u.need
POINTS = ('CAPTURE_INTENT_PREFIX_WRITTEN', 'CAPTURE_INTENT_FORCED',
          'SOURCE_PACKET_PREFIX_WRITTEN', 'SOURCE_PACKET_FORCED',
          'BASIS_WRITTEN', 'BASIS_FORCED', 'GRANT_BEFORE_RETURN')


def wrapper(promise, ledger, future):
    # Same old maximum; the full 3 MiB proof is separately indexed, not nested
    # in this small wrapper or a six-source selected ledger.
    body = s.part(promise)+s.part(ledger)+bytes.fromhex(e.digest(future))
    need(len(body)+48 <= 48+8+8192+65536, 'future source wrapper capacity')
    prefix = struct.pack('>IHHII', 0x47535250, 1, 3, 1, len(body))
    return prefix+bytes.fromhex(e.digest(prefix+body))+body


def crash(path, mode, point, retained, originals, identifiers):
    p.selection.layout(path, {'worker.log', 'resume.log', 'interrupted', 'recovered',
                             'result.json', 'promise.gsr', 'basis.gsr', 'source.gscp'}, 'future source case inventory')
    need(n.read_json(path/'result.json') == dict(status='PASS', mode=mode, cut=point, exit=23 if mode == 'halt' else 137), 'future source process exit')
    lines, events = u.worker(path/'worker.log')
    need(lines[-1] == 'CUT '+point and events[-1] == point and sum(v.startswith('CUT ') for v in lines) == 1
         and not any(v.startswith('RESPONSE ') for v in lines), 'future source interrupted response')
    required = ['PROMISE_FORCED', 'CAPTURE_INTENT_PREFIX_WRITTEN']
    if point != POINTS[0]: required += ['CAPTURE_INTENT_FORCED']
    if point in POINTS[2:]: required += ['SOURCE_PACKET_PREFIX_WRITTEN']
    if point in POINTS[3:]: required += ['SOURCE_PACKET_FORCED']
    if point in POINTS[4:]: required += ['SOURCE_DIRECTORY_FORCED', 'BASIS_WRITTEN']
    if point in POINTS[5:]: required += ['BASIS_FORCED']
    if point == POINTS[6]: required += ['CAPTURE_INTENT_CLEARED', 'GRANT_BEFORE_RETURN']
    s.ordered(events, required, 'future source capture')
    _, members, packet = c.current(retained); cap = packet['capsule']; identity = u.identity(retained)
    promise, basis, raw = ((path/name).read_bytes() for name in ('promise.gsr', 'basis.gsr', 'source.gscp'))
    value = f.decode(promise, 'records', 'PROMISE'); identifier = value['basisId']
    need(str(uuid.UUID(identifier)) == identifier and identifier not in identifiers, 'future source fresh basis identifier')
    old = c.journal(retained['grants.gsr'], cap['root'], 'node-1')
    need(all(row[2].get('basisId') != identifier for row in old), 'future source reused original identifier'); identifiers.add(identifier)
    expected = dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']),
                    ballot=dict(counter=3, proposer='node-1', incarnation=identity['storage']), basisId=identifier)
    need(value == expected, 'future source original promise')
    wrapped = wrapper(promise, retained[s.FILE], retained[u.FILE])
    objects = dict(packet['objects'])
    for name in ('entry.gsr', 'accept.gsr', 'proof.gsr', 'certificate.gsr'):
        objects[e.digest(originals[name])] = originals[name]
    objects[e.digest(b'')] = b''
    objects[e.digest(retained[u.FILE])] = retained[u.FILE]; objects[e.digest(wrapped)] = wrapped
    wanted = c.packet_bytes(cap, objects, packet['images'])
    need(raw == wanted, 'future source exact original packet')
    frozen = s.p.decode(raw)
    expected_basis = f.encode('records', 'BASIS', dict(expected, voter='node-1', cut=cap['cut'],
        capsule=e.digest(frozen['capsuleBytes']), inventory=e.digest(frozen['indexBytes']), accepted=e.digest(originals['accept.gsr'])))
    need(basis == expected_basis, 'future source exact original basis'); s.p.bind(frozen, basis)
    source = 'sources/'+identifier; intent = retained['selector.gsr']+promise+basis
    base = dict(retained, **{'allocator.gsr': f.encode('records', 'ALLOCATOR', dict(root=cap['root'], node='node-1', counter=3)),
                            'grants.gsr': retained['grants.gsr']+promise})
    interrupted = dict(base)
    if point != POINTS[6]: interrupted['source.capture.gsr'] = intent[:len(intent)//2] if point == POINTS[0] else intent
    if point in POINTS[2:]:
        interrupted[source] = None; interrupted[source+'/source.gscp'] = raw[:len(raw)//2] if point == POINTS[2] else raw
    if point in POINTS[4:]:
        interrupted['grants.gsr'] += basis
        for h in packet['images']: interrupted[source+'/'+h+'.image'] = members[h+'.image']
    recovered = dict(base); recovered['grants.gsr'] += basis; recovered[source] = None; recovered[source+'/source.gscp'] = raw
    for h in packet['images']: recovered[source+'/'+h+'.image'] = members[h+'.image']
    need(c.inventory(path/'interrupted') == interrupted, 'future source exact interrupted files')
    need(c.inventory(path/'recovered') == recovered, 'future source exact recovered files')
    lines, events = u.worker(path/'resume.log')
    need(lines[-1] == 'RESPONSE '+e.digest(basis)+' '+e.digest(retained[u.FILE])
         and sum(v.startswith('RESPONSE ') for v in lines) == 1 and not any(v.startswith('CUT ') for v in lines), 'future source exact recovered response')
    s.ordered(events, ['FUTURE_RETENTION_RECOVERY_FORCED', 'FUTURE_RETENTION_RECOVERY_PARENT_FORCED'], 'future source reseal')
    if point in POINTS[:4]:
        s.ordered(events, ['FUTURE_RETENTION_RECOVERY_PARENT_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_FORCED', 'CAPTURE_INTENT_CLEARED'], 'future source recovery')
    return dict(mode=mode, cut=point, status='PASS')


def validate(root):
    root = Path(root); cases = [(mode, point) for mode in ('halt', 'kill') for point in POINTS]
    required = {'original-plan.gsbp', 'original-application.image', 'initial', 'retaining-genesis',
                'calls.json', 'entry-1.gsr', 'payload-1.bin', 'certified', 'before-future', 'pending-future'}
    required |= {'round-1-'+name for name in ('prepared', 'selected', 'installed', 'settled')}
    required |= {'slot-1-'+name for name in ('accepted', 'proved', 'certified')}
    p.selection.layout(root, required | {'-'.join(case) for case in cases}, 'future source complete process matrix')
    _, before, ends = u.prelude(root); retained, _, originals = u.pending(before, ends)
    p.match(root, 'pending-future', dict(before, **{'node-1': retained}))
    identifiers = set(); results = [crash(root/'-'.join(case), *case, retained, originals, identifiers) for case in cases]
    return dict(status='PASS', cases=results, processCases=len(results), freshProcesses=2*len(results),
                originalSourcePropagation=True, selectedInstallation=False, governingQuorum=False,
                automaticDispatch=False, powerLoss=False, phase3Complete=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []; case = 'kill-SOURCE_PACKET_FORCED'
    variants = [('bootstrap', 'retaining-genesis/node-1/'+u.FILE, 'admitted exact retaining-genesis: node-1'),
        ('certificate', 'certified/node-1/pending.accept', 'admitted exact certified: node-1'),
        ('original-target', 'pending-future/node-1/'+u.FILE, 'admitted exact pending-future: node-1'),
        ('packet', case+'/source.gscp', 'future source exact original packet'),
        ('basis', case+'/basis.gsr', 'future source exact original basis'),
        ('interrupted-proof', case+'/interrupted/'+u.FILE, 'future source exact interrupted files'),
        ('recovered-proof', case+'/recovered/'+u.FILE, 'future source exact recovered files'),
        ('force-order', case+'/worker.log', 'selected retention force order: future source capture'),
        ('response', case+'/resume.log', 'future source exact recovered response'),
        ('missing', 'kill-GRANT_BEFORE_RETURN', 'context selection future source complete process matrix inventory')]
    for name, relative, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-future-source-negative-') as temp:
            copied = Path(temp)/'raw'; shutil.copytree(root, copied); path = copied/relative
            if name == 'missing': shutil.rmtree(path)
            else:
                original = path.read_bytes()
                if name == 'force-order': changed = original.replace(b'EVENT PROMISE_FORCED\n', b'', 1)
                elif name == 'response': changed = original.replace(b'RESPONSE ', b'RESPONSE bad-', 1)
                else: changed = original[:-1]+bytes([original[-1]^1])
                need(changed != original, 'future source ineffective mutation'); path.write_bytes(changed)
            try: validate(copied)
            except ValueError as error: need(str(error) == reason, f'future source wrong rejection: {name}: {error}')
            else: raise ValueError('future source accepted mutation: '+name)
            negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(result, negatives=negatives)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--negative', action='store_true')
    args = parser.parse_args(); print(json.dumps((qualify if args.negative else validate)(args.root), sort_keys=True))


if __name__ == '__main__': main()
