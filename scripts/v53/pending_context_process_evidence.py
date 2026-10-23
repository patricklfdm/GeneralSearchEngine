"""Independent physical/event replay of the private pending-context file component.

The context inputs are syntax/identity-checked conditional fixtures. This gate
does not authenticate their backing objects, create protocol force observations,
authorize owner integration or establish power-loss durability.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile

from . import format_fixture as f
from . import pending_context_evidence as codec
from . import source_packet as packet
from .applied_end_evidence import digest
from .context_evidence import parse, exact, identities
from .membership_model import need

ACTIVE = 'pending.context'
NEXT = 'pending.context.next'
WRITE = ('CONTEXT_CANDIDATE_CREATED', 'CONTEXT_PREFIX_WRITTEN', 'CONTEXT_CANDIDATE_WRITTEN',
         'CONTEXT_CANDIDATE_FORCED', 'CONTEXT_CANDIDATE_PARENT_FORCED', 'CONTEXT_RENAMED', 'CONTEXT_PARENT_FORCED')
REPLAY = ('CONTEXT_ACTIVE_FORCED', 'CONTEXT_ACTIVE_PARENT_FORCED')
READ_LIMIT = codec.MAXIMUM


def read(path, maximum=READ_LIMIT):
    need(path.is_file() and not path.is_symlink() and 0 <= path.stat().st_size <= maximum, 'context process bounded regular file: '+path.name)
    return path.read_bytes()


def directory(path, expected):
    need(path.is_dir() and not path.is_symlink() and {v.name for v in path.iterdir()} == set(expected), 'context process exact directory: '+path.name)


def contents(path, expected):
    directory(path, expected)
    for name, raw in expected.items(): need(read(path/name) == raw, 'context process exact bytes: '+str(path/name))
    need(sum(len(value) for name, value in expected.items() if name in (ACTIVE, NEXT)) <= 2*codec.MAXIMUM,
         'context process shared metadata bound')


def input_context(raw, root_raw):
    """Validate all metadata available here, without inventing missing source object bodies."""
    segments, metadata, binding = codec.decode(raw)
    need(codec.encode(segments, metadata) == raw, 'context process canonical input')
    root = f.decode(root_raw, 'records', 'ROOT'); registry = identities(root['initial']); owner = root['initial'][0]
    need(root['limits'] == digest(f.canonical(f.catalog()['resources'])) and binding['root'] == root_raw[16:48].hex()
         and binding['node'] == owner['node'] and binding['storage'] == registry[binding['node']]['storage'], 'context process input root/owner')
    selector = f.decode(segments[1], 'records', 'SELECTOR'); promise = f.decode(segments[2], 'records', 'PROMISE')
    basis = f.decode(segments[3], 'records', 'BASIS')
    need(all(promise[key] == basis[key] for key in ('root', 'view', 'ballot', 'basisId')) and basis['root'] == binding['root']
         and basis['voter'] == binding['node'], 'context process backing grant syntax/binding')
    need({'generation.gsr', 'promise.gsr', 'basis.gsr', 'selected.gsr'} <= set(metadata), 'context process required original metadata')
    manifest_raw = metadata['generation.gsr']; manifest = f.decode(manifest_raw, 'records', 'GENERATION')
    need(selector == dict(root=binding['root'], node=binding['node'], generation=manifest['generation'], digest=digest(manifest_raw))
         and manifest['root'] == binding['root'] and manifest['node'] == binding['node'], 'context process original selector/manifest')
    cap_raw, at = codec.part(segments[4], 0, codec.MIB-56)
    index_raw, at = codec.part(segments[4], at, codec.MIB-56-len(cap_raw))
    need(at == len(segments[4]), 'context process input envelope trailing bytes')
    cap = f.decode(cap_raw, 'records', 'CAPSULE'); index = parse(index_raw); exact(index, 'schema objects images')
    need(index['schema'] == 'gse-membership-source-index/1.3' and cap['inventory'] == digest(index_raw), 'context process envelope capsule/index')
    objects = packet.rows(index['objects'], 65536, 8*codec.MIB, 0); images = packet.rows(index['images'], 7, 64*codec.MIB, 1)
    packet_size = 48+len(segments[4])+sum(objects.values())
    need(packet_size <= 32*codec.MIB and cap['initial'] in objects and cap['catalog'] in objects and cap['application'] in images,
         'context process original envelope capacity/inventory')
    need(manifest['capsule'] == digest(cap_raw) and all(manifest[key] == cap[key] for key in ('root', 'cut', 'catalog', 'application')),
         'context process envelope/generation binding')
    rows = manifest['files']; need([row['path'] for row in rows] == sorted({row['path'] for row in rows}), 'context process original inventory order')
    expected_names = set(metadata)-{'generation.gsr'} | {'source.gscp'} | {key+'.image' for key in images}
    need({row['path'] for row in rows} == expected_names, 'context process original metadata inventory')
    for row in rows:
        name = row['path']
        if name == 'source.gscp': need(row['size'] == packet_size, 'context process reconstructed packet declared size')
        elif name.endswith('.image'):
            key = name[:-6]; need(row == dict(path=name, size=images[key], sha256=key), 'context process original image declaration')
        else: need(row == dict(path=name, size=len(metadata[name]), sha256=digest(metadata[name])), 'context process original metadata bytes')
    for name, field, kind in (('promise.gsr', 'promise', 'PROMISE'), ('basis.gsr', 'basis', 'BASIS'), ('selected.gsr', 'selection', 'SELECTED')):
        decoded = f.decode(metadata[name], 'records', kind)
        need(decoded['root'] == binding['root'] and digest(metadata[name]) == manifest[field], 'context process original grant digest')
    return segments, metadata, binding


def cases():
    for transition in ('create', 'replace', 'replay'):
        for mode in ('halt', 'kill'):
            for point in REPLAY if transition == 'replay' else WRITE:
                yield dict(case=transition+'-'+mode+'-'+point, transition=transition, mode=mode, cut=point)


def trace(path, events, success=None, kill=None):
    raw = read(path.with_suffix('.stdout'), 65536)
    need(raw.endswith(b'\n'), 'context process incomplete stdout line')
    lines = [parse(line) for line in raw.splitlines()]
    expected = [dict(event=event) for event in events]
    if kill: expected.append(dict(event='AWAITING_KILL', cut=kill))
    if success is not None: expected.append(dict(status='PASS', context=digest(success), bytes=len(success)))
    need(lines == expected and all(type(row.get('bytes')) is int for row in lines if 'bytes' in row), 'context process exact event/return sequence')
    need(read(path.with_suffix('.stderr'), 65536) == b'', 'context process nonempty stderr')


def fault_state(initial, expected, point):
    result = dict(initial)
    if point in REPLAY: return result
    at = WRITE.index(point)
    if at >= WRITE.index('CONTEXT_RENAMED'): return {ACTIVE: expected}
    result[NEXT] = b'' if at == 0 else expected[:len(expected)//2] if at == 1 else expected
    return result


def validate_case(root, case, first, replacement, root_raw):
    path = root/case['case']; expected = first if case['transition'] == 'create' else replacement
    initial = {} if case['transition'] == 'create' else {ACTIVE: first if case['transition'] == 'replace' else replacement}
    labels = ('fault', 'recovery-fault', 'resume')
    directory(path, {'store', 'inputs', 'crash', 'recovery-crash', 'final'} | {name+suffix for name in labels for suffix in ('.stdout', '.stderr')})
    inputs = {'root.gsr': root_raw, 'expected.gspc': expected}
    if case['transition'] != 'create': inputs['prior.gspc'] = first
    contents(path/'inputs', inputs)
    order = REPLAY if case['transition'] == 'replay' else WRITE
    trace(path/'fault', order[:order.index(case['cut'])+1], kill=case['cut'] if case['mode'] == 'kill' else None)
    crash = fault_state(initial, expected, case['cut']); contents(path/'crash', crash)
    if crash.get(ACTIVE) == expected:
        recovery_cut = 'CONTEXT_ACTIVE_FORCED'; recovery = dict(crash); recovery_order = REPLAY
    else:
        recovery_cut = 'CONTEXT_PREFIX_WRITTEN'; prefix = len(crash[NEXT]); recovery = dict(crash)
        recovery[NEXT] = expected[:prefix+(len(expected)-prefix)//2]; recovery_order = WRITE[1:]
    trace(path/'recovery-fault', recovery_order[:recovery_order.index(recovery_cut)+1])
    contents(path/'recovery-crash', recovery)
    final_order = REPLAY if recovery.get(ACTIVE) == expected else WRITE[1:]
    trace(path/'resume', final_order, success=expected)
    final = {ACTIVE: expected}; contents(path/'final', final); contents(path/'store', dict(final, **{'owner.lock': b''}))
    return dict(case, recoveryCut=recovery_cut, status='PASS',
                exitCodes={'fault': 73 if case['mode'] == 'halt' else 137, 'recoveryFault': 73, 'resume': 0})


def validate(root):
    root = Path(root); expected_cases = list(cases())
    directory(root, {'root.gsr', 'first.gspc', 'replacement.gspc', 'receipt.json'} | {case['case'] for case in expected_cases})
    root_raw = read(root/'root.gsr', 65536); first = read(root/'first.gspc'); replacement = read(root/'replacement.gspc')
    first_segments, first_meta, first_binding = input_context(first, root_raw)
    replacement_segments, replacement_meta, replacement_binding = input_context(replacement, root_raw)
    need(first != replacement and first_segments[1:] == replacement_segments[1:] and first_meta == replacement_meta,
         'context process actual distinct same-original inputs')
    retained = set(first_binding)-{'vote', 'proof', 'certificate'}
    need({key: first_binding[key] for key in retained} == {key: replacement_binding[key] for key in retained}
         and first_binding['proof'] is None and first_binding['certificate'] is None and replacement_binding['proof'] is not None
         and replacement_binding['certificate'] is not None, 'context process same-original ACCEPT/CERT component fixture')
    results = [validate_case(root, case, first, replacement, root_raw) for case in expected_cases]
    receipt = parse(read(root/'receipt.json', 65536))
    expected = dict(schema='gse-v53-pending-context-process-v1', status='PASS', cases=results, expectedCases=32, freshProcesses=96,
                    protocolAuthority='conditional-fixture', ownerIntegration=False, powerLoss=False)
    need(receipt == expected and all(type(receipt[key]) is type(value) for key, value in expected.items())
         and all(type(code) is int for row in receipt['cases'] for code in row['exitCodes'].values()), 'context process exact receipt/scope')
    return dict(status='PASS', cases=32, freshProcesses=96, transitions=['create', 'replace', 'replay'], repeatedCrashes=32,
                originalFirst=True, physicalBytes=True, processEventOrder=True, crashReturnedSuccess=False, portableInputs=True,
                protocolAuthority='conditional-fixture', backingAuthorityVerified=False, osExitCodesVerified=True,
                ownerIntegration=False, runtimeEnabled=False, powerLoss=False, inputContextBytes=[len(first), len(replacement)])


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    variants = ('bad-first-container', 'changed-owner', 'missing-case', 'unexpected-case', 'changed-input-prior', 'lost-old-active',
                'nonprefix-candidate', 'premature-active', 'lost-recovery-candidate', 'bad-final-context', 'retained-final-candidate',
                'changed-store', 'missing-force-event', 'false-crash-success', 'missing-kill-handshake', 'false-return-hash',
                'nonempty-stderr', 'false-process-count', 'false-owner-authority', 'linked-snapshot', 'false-child-exit', 'boolean-child-exit')
    for variant in variants:
        with tempfile.TemporaryDirectory(prefix='v53-context-process-negative-') as temporary:
            case = Path(temporary)/'evidence'; shutil.copytree(root, case)
            replace = case/'replace-halt-CONTEXT_PREFIX_WRITTEN'; create = case/'create-kill-CONTEXT_CANDIDATE_WRITTEN'
            if variant == 'bad-first-container':
                path = case/'first.gspc'; raw = path.read_bytes(); path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif variant == 'changed-owner':
                path = case/'first.gspc'; segments, metadata, binding = codec.decode(path.read_bytes()); binding['storage'] = '11111111-2222-3333-4444-555555555555'
                segments[0] = f.canonical(binding); path.write_bytes(codec.encode(segments, metadata))
            elif variant == 'missing-case': shutil.rmtree(create)
            elif variant == 'unexpected-case': (case/'extra-case').mkdir()
            elif variant == 'changed-input-prior': (replace/'inputs/prior.gspc').write_bytes((case/'replacement.gspc').read_bytes())
            elif variant == 'lost-old-active': (replace/'crash'/ACTIVE).unlink()
            elif variant == 'nonprefix-candidate':
                path = replace/'crash'/NEXT; raw = path.read_bytes(); path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif variant == 'premature-active': (replace/'crash'/ACTIVE).write_bytes((case/'replacement.gspc').read_bytes())
            elif variant == 'lost-recovery-candidate': (replace/'recovery-crash'/NEXT).unlink()
            elif variant == 'bad-final-context': (replace/'final'/ACTIVE).write_bytes((case/'first.gspc').read_bytes())
            elif variant == 'retained-final-candidate': (replace/'final'/NEXT).write_bytes(b'')
            elif variant == 'changed-store': (replace/'store'/ACTIVE).write_bytes((case/'first.gspc').read_bytes())
            elif variant == 'missing-force-event':
                path = replace/'resume.stdout'; path.write_bytes(b'\n'.join(line for line in path.read_bytes().splitlines() if b'"event":"CONTEXT_CANDIDATE_FORCED"' not in line)+b'\n')
            elif variant == 'false-crash-success':
                path = replace/'fault.stdout'; path.write_bytes(path.read_bytes()+f.canonical(dict(status='PASS'))+b'\n')
            elif variant == 'missing-kill-handshake':
                path = create/'fault.stdout'; path.write_bytes(b'\n'.join(path.read_bytes().splitlines()[:-1])+b'\n')
            elif variant == 'false-return-hash':
                path = replace/'resume.stdout'; rows = [parse(line) for line in path.read_bytes().splitlines()]; rows[-1]['context'] = '0'*64
                path.write_bytes(b''.join(f.canonical(row)+b'\n' for row in rows))
            elif variant == 'nonempty-stderr': (replace/'recovery-fault.stderr').write_bytes(b'error\n')
            elif variant in ('false-process-count', 'false-owner-authority'):
                path = case/'receipt.json'; value = parse(path.read_bytes())
                value['freshProcesses' if variant == 'false-process-count' else 'ownerIntegration'] = 95 if variant == 'false-process-count' else True
                path.write_bytes(f.canonical(value))
            elif variant in ('false-child-exit', 'boolean-child-exit'):
                path = case/'receipt.json'; value = parse(path.read_bytes()); value['cases'][0]['exitCodes']['fault' if variant == 'false-child-exit' else 'resume'] = 0 if variant == 'false-child-exit' else False
                path.write_bytes(f.canonical(value))
            else:
                path = replace/'final'/ACTIVE; path.unlink(); path.symlink_to((root/replace.name/'final'/ACTIVE).resolve())
            try: validate(case)
            except (ValueError, OSError, KeyError, TypeError): negatives.append(variant)
            else: raise ValueError('accepted context process mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-context-process-portable-') as temporary:
        case = Path(temporary)/'evidence'; shutil.copytree(root, case); need(validate(case) == result, 'context process portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
