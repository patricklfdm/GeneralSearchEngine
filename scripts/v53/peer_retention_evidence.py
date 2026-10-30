"""Independent replay of local retention transaction bytes; no quorum/runtime claim."""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
import shutil
import tempfile
from pathlib import Path
from . import bootstrap_publication_evidence as bootstrap

POINTS = ('RETENTION_BEFORE_WRITE', 'RETENTION_PREFIX_WRITTEN', 'RETENTION_WRITTEN',
          'RETENTION_FORCED', 'RETENTION_CANDIDATE_PARENT_FORCED',
          'RETENTION_RENAMED', 'RETENTION_PARENT_FORCED')


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def decode(raw):
    need(44 < len(raw) <= 65536, 'retention frame extent')
    magic, major, minor, size = struct.unpack('>IHHI', raw[:12])
    need((magic, major, minor, size) == (0x47535052, 1, 3, len(raw)), 'retention frame header')
    body = raw[44:]
    need(hashlib.sha256(body).digest() == raw[12:44], 'retention checksum')
    value = json.loads(body, object_pairs_hook=unique)
    need(set(value) == {'root', 'owner', 'revision', 'previous', 'plan'}, 'retention fields')
    need(canonical(value) == body, 'retention canonical bytes')
    revision = value['revision']
    need(type(revision) is int and 0 <= revision <= 2**63-2, 'retention revision')
    need((revision == 0) == (value['previous'] is None), 'retention predecessor')
    need(value['plan']['root'] == value['root'], 'retention plan root')
    if any({'confirmation', 'renewals'} & set(row) for row in value['plan'].get('peers', [])):
        from .peer_confirmation_evidence import plan
        plan(value['plan'])  # Syntax/binding only; never a new forced-copy observation.
    return value


def case(path):
    result = json.loads((path/'result.json').read_text())
    mode, point = result['mode'], result['cut']
    need(mode in ('halt', 'kill') and point in POINTS and result['status'] == 'PASS', 'crash case identity')
    need(result['exit'] == (23 if mode == 'halt' else 137), 'actual process exit')
    log = (path/'worker.log').read_text()
    need(log.count('CUT '+point+'\n') == 1 and '"status":"PASS"' not in log, 'crash response boundary')
    raws = {name: (path/(name+'.gspr')).read_bytes() for name in ('before', 'interrupted.active', 'recovered', 'continued')}
    records = {name: decode(raw) for name, raw in raws.items()}
    before, interrupted, recovered, continued = (records[name] for name in raws)
    originals = bootstrap.original(path, 3, False)
    _, _, packet = bootstrap.c.current(originals['node-1'])
    capsule = packet['capsule'];cut = capsule['cut']
    members = [bootstrap.e.f.decode(originals[n]['node.gsr'], 'records', 'NODE')['identity'] for n in sorted(originals)]
    plan = dict(root=capsule['root'], view=cut['view'], peers=[dict(identity=identity,
        possible=[dict(cut=cut, catalog=capsule['catalog'], application=capsule['application'])]) for identity in members])
    need(before['owner'] == members[0] and before['root'] == capsule['root'] and before['plan'] == plan,
         'original bootstrap retention binding')
    expected = int(point in ('RETENTION_RENAMED', 'RETENTION_PARENT_FORCED'))
    need(before['revision'] == 0 and recovered['revision'] == expected and continued['revision'] == expected+1,
         'crash recovered revision')
    need(result['recoveredRevision'] == expected and result['continuedRevision'] == expected+1, 'reported revision')
    need(raws['interrupted.active'] == raws['recovered'], 'recovery changed selected active bytes')
    need(all(v['owner'] == before['owner'] and v['root'] == before['root'] and v['plan'] == before['plan']
             for v in records.values()), 'recovery changed original owner or endpoints')
    need(continued['previous'] == sha(raws['recovered']), 'continued predecessor')
    if expected:
        need(interrupted['previous'] == sha(raws['before']), 'selected predecessor')
    else:
        need(raws['before'] == raws['recovered'], 'unselected candidate promoted')
    candidate = path/'interrupted.next.gspr'
    has_candidate = point not in ('RETENTION_BEFORE_WRITE', 'RETENTION_RENAMED', 'RETENTION_PARENT_FORCED')
    need(candidate.exists() == has_candidate, 'interrupted candidate inventory')
    if has_candidate:
        raw = candidate.read_bytes()
        need(12 <= len(raw) <= 65536 and struct.unpack('>IHH', raw[:8]) == (0x47535052, 1, 3), 'candidate prefix')
        extent = struct.unpack('>I', raw[8:12])[0]
        if point == 'RETENTION_PREFIX_WRITTEN':
            need(len(raw) < extent <= 65536, 'candidate must be incomplete')
        else:
            next_value = decode(raw)
            need(next_value['previous'] == sha(raws['before']) and next_value['revision'] == 1,
                 'candidate original predecessor')
            need(next_value['owner'] == before['owner'] and next_value['plan'] == before['plan'], 'candidate changed owner/plan')
    calls = [v for v in result['events'] if v['operation'] == 'recover']
    need(len(calls) == 1, 'recovery trace')
    events = calls[0]['events']
    first, second = 'RETENTION_RECOVERY_ACTIVE_FORCED', 'RETENTION_RECOVERY_PARENT_FORCED'
    need(events.count(first) == events.count(second) == 1 and events.index(first) < events.index(second), 'recovery resealing order')
    if has_candidate:
        need(events.index('RETENTION_DISCARD_PARENT_FORCED') < events.index(first), 'discard before exposure')
    return {'mode': mode, 'cut': point, 'status': 'PASS'}


def validate(root):
    paths = sorted(Path(root).rglob('result.json'))
    rows = [case(p.parent) for p in paths]
    expected = {(mode, point) for mode in ('halt', 'kill') for point in POINTS}
    need(len(rows) == len(expected) and {(v['mode'], v['cut']) for v in rows} == expected, 'complete retention crash matrix')
    return {'status': 'PASS', 'scope': 'local-retention-transactions', 'cases': rows,
            'publicBootstrapOriginals': True,
            'quorumReplication': False, 'autonomousRuntime': False, 'phase3Complete': False}


def frame(value):
    body = canonical(value)
    return struct.pack('>IHHI', 0x47535052, 1, 3, 44+len(body))+hashlib.sha256(body).digest()+body


def qualify(root):
    original = validate(root)  # An invalid original can never count as a negative pass.
    variants = [('checksum', 'retention checksum'), ('owner', 'original bootstrap retention binding'),
                ('parent', 'continued predecessor'), ('missing-candidate', 'interrupted candidate inventory'),
                ('response', 'crash response boundary'), ('reseal', 'recovery resealing order'),
                ('exit', 'actual process exit'), ('missing-case', 'complete retention crash matrix')]
    rows = []
    for mutation, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-retention-negative-') as temp:
            copied = Path(temp)/'evidence';shutil.copytree(root, copied)
            case_root = next(p.parent for p in copied.rglob('result.json')
                             if json.loads(p.read_text())['mode'] == 'kill'
                             and json.loads(p.read_text())['cut'] == 'RETENTION_WRITTEN')
            if mutation == 'checksum':
                p = case_root/'recovered.gspr';raw = bytearray(p.read_bytes());raw[-1] ^= 1;p.write_bytes(raw)
            elif mutation == 'owner':
                p = case_root/'before.gspr';v = decode(p.read_bytes());v['owner']['node'] = 'node-2';p.write_bytes(frame(v))
            elif mutation == 'parent':
                p = case_root/'continued.gspr';v = decode(p.read_bytes());v['previous'] = 'f'*64;p.write_bytes(frame(v))
            elif mutation == 'missing-candidate':
                (case_root/'interrupted.next.gspr').unlink()
            elif mutation == 'response':
                with (case_root/'worker.log').open('a') as stream:stream.write('{"status":"PASS"}\n')
            elif mutation in ('reseal', 'exit'):
                p = case_root/'result.json';v = json.loads(p.read_text())
                if mutation == 'exit':v['exit'] = 0
                else:
                    call = next(r for r in v['events'] if r['operation'] == 'recover')
                    call['events'].remove('RETENTION_RECOVERY_PARENT_FORCED')
                p.write_text(json.dumps(v))
            else:
                (case_root/'result.json').unlink()
            try:
                validate(copied)
            except ValueError as error:
                need(str(error) == reason, 'negative reached wrong rejection: '+str(error))
            else:
                raise ValueError('negative unexpectedly accepted: '+mutation)
            rows.append(dict(case=mutation, status='REJECTED', reason=reason))
    return dict(original=original, negatives=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify', action='store_true');args = parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root), sort_keys=True))
