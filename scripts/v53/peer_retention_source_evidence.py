"""Original-first native retention capture replay; no quorum propagation claim."""
from __future__ import annotations
import argparse
import json
import shutil
import struct
import tempfile
from pathlib import Path
from . import peer_retention_evidence as r
from . import source_packet as p

need, sha = r.need, r.sha
b = r.bootstrap
f = b.e.f
POINTS = ('CAPTURE_INTENT_PREFIX_WRITTEN', 'CAPTURE_INTENT_FORCED',
          'SOURCE_PACKET_PREFIX_WRITTEN', 'SOURCE_PACKET_FORCED',
          'BASIS_WRITTEN', 'BASIS_FORCED', 'GRANT_BEFORE_RETURN')


def wrap(promise, state):
    body = struct.pack('>I', len(promise))+promise+struct.pack('>I', len(state))+state
    prefix = struct.pack('>IHHII', 0x47535250, 1, 3, 0, len(body))
    return prefix+bytes.fromhex(sha(prefix+body))+body


def unwrap(raw):
    need(56 < len(raw) <= 48+8+8192+65536, 'retention source extent')
    need(struct.unpack('>IHHII', raw[:16]) == (0x47535250, 1, 3, 0, len(raw)-48), 'retention source framing')
    need(bytes.fromhex(sha(raw[:16]+raw[48:])) == raw[16:48], 'retention source checksum')
    size = struct.unpack('>I', raw[48:52])[0]
    need(48 <= size <= 8192 and 52+size+4 < len(raw), 'retention source promise extent')
    promise = raw[52:52+size];value = f.decode(promise, 'records', 'PROMISE')
    need(value['basisId'] is not None, 'retention source capture promise')
    extent = struct.unpack('>I', raw[52+size:56+size])[0];state = raw[56+size:]
    need(44 < extent <= 65536 and extent == len(state), 'retention source state extent')
    r.decode(state)
    return promise, state


def case(path):
    result = json.loads((path/'result.json').read_text());mode, cut = result['mode'], result['cut']
    need(mode in ('halt', 'kill') and cut in POINTS and result['status'] == 'PASS', 'capture case identity')
    need(result['exit'] == (23 if mode == 'halt' else 137), 'actual process exit')
    log = (path/'worker.log').read_text()
    need(log.count('CUT '+cut+'\n') == 1 and 'RESPONSE' not in log, 'capture response boundary')
    events = [line[6:] for line in log.splitlines() if line.startswith('EVENT ')]
    need(events[-1] == cut and events.index('PROMISE_FORCED') < len(events)-1, 'capture original promise force')
    group = b.original(path, 3, False);original = group['node-1'];_, members, seed = b.c.current(original)
    identities = [f.decode(group[n]['node.gsr'], 'records', 'NODE')['identity'] for n in sorted(group)]
    capsule = seed['capsule'];frozen = (path/'frozen.gspr').read_bytes();state = r.decode(frozen)
    anchor = {k: capsule[k] for k in ('cut', 'catalog', 'application')}
    plan = dict(root=capsule['root'], view=capsule['cut']['view'],
                peers=[dict(identity=i, possible=[anchor]) for i in identities])
    need(state == dict(root=capsule['root'], owner=identities[0], revision=0, previous=None, plan=plan), 'bootstrap frozen retention')
    promise, basis, raw = ((path/name).read_bytes() for name in ('promise.gsr', 'basis.gsr', 'source.gscp'))
    promise_value = f.decode(promise, 'records', 'PROMISE');basis_value = f.decode(basis, 'records', 'BASIS')
    packet = p.decode(raw);p.bind(packet, basis)
    expected_promise = dict(root=capsule['root'], view=b.e.authority(capsule['root'], capsule['cut']['view']),
                            ballot=dict(counter=2, proposer='node-1', incarnation=identities[0]['storage']), basisId=promise_value['basisId'])
    need(promise_value == expected_promise and all(basis_value[k] == v for k, v in expected_promise.items()), 'capture promise/basis binding')
    need(basis_value['voter'] == 'node-1' and basis_value['accepted'] is None, 'capture original voter/tail')
    wrapped = wrap(promise, frozen);need(unwrap(wrapped) == (promise, frozen), 'capture envelope round trip')
    need(packet['objects'] == dict(seed['objects'], **{sha(wrapped): wrapped}) and packet['images'] == seed['images'], 'exact frozen source objects')
    need({k: v for k, v in packet['capsule'].items() if k != 'inventory'} ==
         {k: v for k, v in capsule.items() if k != 'inventory'}, 'capture changed application prefix')
    source = 'sources/'+promise_value['basisId'];intent = original['selector.gsr']+promise+basis
    base = dict(original, **{'peer-retention.gspr': frozen, 'allocator.gsr': f.encode('records', 'ALLOCATOR',
                dict(root=capsule['root'], node='node-1', counter=2)), 'grants.gsr': original['grants.gsr']+promise})
    interrupted = dict(base)
    if cut != 'GRANT_BEFORE_RETURN':interrupted['source.capture.gsr'] = intent[:len(intent)//2] if cut == POINTS[0] else intent
    if cut not in POINTS[:2]:
        interrupted[source] = None
        interrupted[source+'/source.gscp'] = raw[:len(raw)//2] if cut == POINTS[2] else raw
    if cut in POINTS[4:]:
        interrupted['grants.gsr'] += basis
        for h in packet['images']:interrupted[source+'/'+h+'.image'] = members[h+'.image']
    need(b.c.inventory(path/'interrupted') == interrupted, 'exact interrupted capture bytes')
    recovered = dict(base);recovered['grants.gsr'] += basis;recovered[source] = None;recovered[source+'/source.gscp'] = raw
    for h in packet['images']:recovered[source+'/'+h+'.image'] = members[h+'.image']
    need(b.c.inventory(path/'recovered') == recovered, 'exact recovered capture bytes')
    updated = dict(recovered);next_state = dict(state, revision=1, previous=sha(frozen));updated['peer-retention.gspr'] = r.frame(next_state)
    need(b.c.inventory(path/'updated') == updated, 'update rewrote original capture')
    recovery = [v for v in result['events'] if v['operation'] == 'recover']
    need(len(recovery) == 1, 'capture recovery trace');steps = recovery[0]['events']
    need(steps.index('RETENTION_RECOVERY_ACTIVE_FORCED') < steps.index('RETENTION_RECOVERY_PARENT_FORCED'), 'capture retention reseal')
    if cut not in POINTS[4:]:
        need(steps.index('SOURCE_DIRECTORY_FORCED') < steps.index('BASIS_FORCED') < steps.index('CAPTURE_INTENT_CLEARED'), 'capture recovery force order')
    return dict(mode=mode, cut=cut, status='PASS')


def validate(root):
    rows = [case(path.parent) for path in sorted(Path(root).rglob('result.json'))]
    expected = {(mode, cut) for mode in ('halt', 'kill') for cut in POINTS}
    need(len(rows) == len(expected) and {(v['mode'], v['cut']) for v in rows} == expected, 'complete frozen capture matrix')
    return dict(status='PASS', scope='native-frozen-retention-capture', cases=rows,
                quorumPropagation=False, autonomousRuntime=False, phase3Complete=False)


def qualify(root):
    original = validate(root)
    variants = [('frozen', 'retention checksum'), ('packet', 'packet checksum'), ('promise', 'capture promise/basis binding'),
                ('original', 'admitted original public bootstrap'), ('interrupted', 'exact interrupted capture bytes'),
                ('updated', 'update rewrote original capture'), ('response', 'capture response boundary'),
                ('force', 'capture recovery force order'), ('missing', 'complete frozen capture matrix')]
    rows = []
    for mutation, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-retention-source-negative-') as temp:
            copied = Path(temp)/'raw';shutil.copytree(root, copied)
            path = next(p.parent for p in copied.rglob('result.json') if json.loads(p.read_text())['mode'] == 'kill'
                        and json.loads(p.read_text())['cut'] == 'SOURCE_PACKET_FORCED')
            if mutation in ('frozen', 'packet'):
                file = path/('frozen.gspr' if mutation == 'frozen' else 'source.gscp');raw = bytearray(file.read_bytes());raw[-1] ^= 1;file.write_bytes(raw)
            elif mutation == 'promise':
                file = path/'promise.gsr';v = f.decode(file.read_bytes(), 'records', 'PROMISE');v['ballot']['counter'] += 1;file.write_bytes(f.encode('records', 'PROMISE', v))
            elif mutation == 'original':(path/'initial/target-0/allocator.gsr').write_bytes(b'bad')
            elif mutation == 'interrupted':(path/'interrupted/peer-retention.gspr').unlink()
            elif mutation == 'updated':(path/'updated/peer-retention.gspr').write_bytes((path/'frozen.gspr').read_bytes())
            elif mutation == 'response':
                with (path/'worker.log').open('a') as stream:stream.write('RESPONSE false\n')
            elif mutation == 'force':
                file = path/'result.json';v = json.loads(file.read_text());steps = next(c['events'] for c in v['events'] if c['operation'] == 'recover')
                at, other = steps.index('BASIS_FORCED'), steps.index('SOURCE_DIRECTORY_FORCED');steps[at], steps[other] = steps[other], steps[at];file.write_text(json.dumps(v))
            else:(path/'result.json').unlink()
            try:validate(copied)
            except ValueError as error:need(str(error) == reason, 'negative reached wrong rejection: '+str(error))
            else:raise ValueError('negative unexpectedly accepted: '+mutation)
            rows.append(dict(case=mutation, status='REJECTED', reason=reason))
    return dict(original=original, negatives=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify', action='store_true');args = parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root), sort_keys=True))
