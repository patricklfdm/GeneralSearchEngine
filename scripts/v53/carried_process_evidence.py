"""Original-first replay of carried-vote installation and repeated maintenance crashes.

The prior publication and all carried votes come from actual retained local
owners. The historical bootstrap remains conditional; process termination does
not establish power-loss durability or enable the public runtime.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import carried_publication_evidence as carried
from . import current_generation_evidence as current
from . import generation_install_evidence as install
from . import floor_evidence as floor
from . import retirement_evidence as retirement
from . import source_release_evidence as source_release
from . import floor_release_evidence as floor_release
from . import maintenance_lifetime_evidence as maintenance
from . import format_fixture as f
from . import source_packet as p
from .applied_end_evidence import read, digest
from .grant_evidence import journal
from .journal_application_evidence import inventory
from .membership_model import need

CUTS = (
    ('INSTALL_MANIFEST_FORCED', 'INSTALL_GENERATION_FORCED'),
    ('INSTALL_SELECTOR_RENAMED', 'ACCEPT_ACTIVE_FORCED'),
    ('ACCEPT_PREFIX_WRITTEN', 'ACCEPT_CANDIDATE_FORCED'),
    ('ACCEPT_RENAMED', 'FLOOR_COPIES_FORCED'),
    ('FLOOR_PROPOSAL_FORCED', 'FLOOR_AUTHORITY_FORCED'),
    ('FLOOR_AUTHORITY_FORCED', 'RETIREMENT_AUTHORITY_FORCED'),
    ('RETIREMENT_FILE_DELETED', 'RETIREMENT_AUTHORITY_RESEALED'),
    ('SOURCE_RETIREMENT_FORCED', 'JOURNAL_ROTATION_FORCED'),
    ('SOURCE_RETIREMENT_FILE_DELETED', 'SOURCE_RETIREMENT_FORCED'),
    ('FLOOR_RELEASE_RELINQUISHED', 'FLOOR_RELEASE_AUTHORITY_FORCED'),
    ('FLOOR_RELEASE_AUTHORITY_CLEARED', 'FLOOR_RELEASE_CLEARED'))


def observations(seed):
    """Derive authenticated inputs only from original owner phase/end bytes."""
    result = set()
    for slot in (1, 2, 3):
        for node in carried.NODES:
            physical = inventory(seed/'originals'/('slot-'+str(slot))/node)
            _, _, packet = carried.current(physical)
            frames, _ = carried.pending(physical['pending.accept'], ('PROOF', 'CERTIFICATE'))
            identity = f.decode(physical['node.gsr'], 'records', 'NODE')['identity']
            for kind in ('ACCEPT', 'PROOF'):
                result.add(f.canonical(dict(voter=node, storage=identity['storage'], record=digest(frames[kind]),
                    parent=digest(f.canonical(packet['capsule']['cut'])))))
            for name, value in physical.items():
                if name.startswith('applied-end/') and name.endswith('ack.gsr'):
                    ack = f.decode(value, 'records', 'CHECKPOINT_ACK')
                    result.add(f.canonical(dict(voter=node, storage=identity['storage'], record=digest(value), parent=digest(f.canonical(ack['cut'])))))
    for node in carried.NODES:
        physical = inventory(seed/'carried-snapshots/old-accepted'/node)
        frames, _ = carried.pending(physical['pending.accept']); _, _, packet = carried.current(physical)
        identity = f.decode(physical['node.gsr'], 'records', 'NODE')['identity']
        result.add(f.canonical(dict(voter=node, storage=identity['storage'], record=digest(frames['ACCEPT']), parent=digest(f.canonical(packet['capsule']['cut'])))))
    return result


def plan(seed):
    # Validate the complete originals before trusting any retained intermediate.
    carried.validate_case(seed, 3)
    supplied = json.loads(read(seed/'inputs.json')); actual = [f.canonical(v) for v in supplied['observations']]
    expected = observations(seed)
    need(set(supplied) == {'observations', 'obsolete'} and len(actual) == len(expected) == 39 and set(actual) == expected,
         'carried process physical observation provenance')
    prepared = {n: inventory(seed/'carried-snapshots/prepared'/n) for n in carried.NODES}
    accepted = {n: inventory(seed/'carried-snapshots/reaccepted'/n) for n in carried.NODES}
    raw = prepared['node-1']; prefix, old_generation, _ = carried.current(raw)
    target, files, packet = carried.current(accepted['node-1']); selector = accepted['node-1']['selector.gsr']; cap = packet['capsule']
    old_generation = dict(old_generation, **{'generation.gsr': raw[prefix+'generation.gsr']})
    files = dict(files, **{'generation.gsr': accepted['node-1'][target+'generation.gsr']})
    rows = journal(raw['grants.gsr'], cap['root'], 'node-1'); obsolete = rows[1][2]['basisId']
    need(supplied['obsolete'] == obsolete and prefix == 'generations/a/' and target == 'generations/b/'
         and [r[0] for r in rows] == ['PROMISE', 'BASIS', 'SELECTED']*2, 'carried process original generations and grants')
    pending = accepted['node-1']['pending.accept']; _, vote = carried.pending(pending)
    need(vote['ENTRY']['origin']['counter'] == 20 and vote['ACCEPT']['ballot']['counter'] == 21, 'carried original/new ballot identity')
    copies = {}; references = []
    for node in ('node-1', 'node-2'):
        peer_prefix, copy, peer = carried.current(accepted[node]); copy = dict(copy, **{'generation.gsr': accepted[node][peer_prefix+'generation.gsr']})
        generation = digest(copy['generation.gsr']); copies[generation] = copy
        need(peer['capsule']['cut'] == cap['cut'], 'carried governing copies common cut')
        references.append(dict(voter=node, generation=generation, catalog=cap['catalog'], snapshot=cap['application']))
    floor_record = f.encode('records', 'FLOOR', dict(root=cap['root'], node='node-1', cut=cap['cut'], sources=references))
    authority = dict(root=cap['root'], node='node-1', floor=digest(floor_record), selector=digest(selector))
    generation_retirement = f.encode('records', 'RETIREMENT', dict(authority, files=maintenance.entries(old_generation, prefix)))
    source_prefix = 'sources/'+obsolete+'/'
    old_source = {k.removeprefix(source_prefix): v for k, v in raw.items() if k.startswith(source_prefix)}
    source_retirement = f.encode('records', 'RETIREMENT', dict(authority, files=maintenance.entries(old_source, source_prefix)))
    source_retirement += rows[0][1]+rows[1][1]+p.decode(old_source['source.gscp'])['capsuleBytes']
    compact = b''.join(r[1] for r in rows[3:])
    floor_files = {'floor-copies/floor.gsr': floor_record, 'floor-copies/proposal.gsr': floor_record}
    for h, copy in copies.items(): floor_files.update({'floor-copies/'+h+'/'+k: v for k, v in copy.items()})
    release = f.encode('records', 'RETIREMENT', dict(authority, files=maintenance.entries(floor_files)))
    settled = maintenance.metadata(inventory(seed/'carried-snapshots/reclaimed/node-1'))
    return dict(initial=maintenance.metadata(raw), prepared=prepared, accepted=accepted, files=files, selector=selector, pending=pending,
                copies=copies, floor=floor_record, oldGeneration=old_generation, generationRetirement=generation_retirement,
                sourceRetirement=source_retirement, compact=compact, obsolete=obsolete, release=release, settled=settled)


def transaction(original, expected):
    state = dict(original); steps = []; desired = expected['pending']
    def event(name): steps.append((name, dict(state)))
    def append(rows):
        nonlocal state
        if rows: steps.extend(rows); state = dict(rows[-1][1])
    def release(): append(floor_release.transaction(state, expected['release']))
    def replace():
        if 'pending.accept.next' not in state:
            state['pending.accept.next'] = retirement.entry(b''); event('ACCEPT_CANDIDATE_CREATED')
        old = state['pending.accept.next']; length = old['bytes']
        need(old == retirement.entry(desired[:length]) and length <= len(desired), 'carried exact interrupted pending prefix')
        state['pending.accept.next'] = retirement.entry(desired[:length+(len(desired)-length)//2]); event('ACCEPT_PREFIX_WRITTEN')
        state['pending.accept.next'] = retirement.entry(desired)
        for name in ('ACCEPT_CANDIDATE_WRITTEN', 'ACCEPT_CANDIDATE_FORCED', 'ACCEPT_CANDIDATE_PARENT_FORCED'): event(name)
        state['pending.accept'] = state.pop('pending.accept.next'); event('ACCEPT_RENAMED'); event('ACCEPT_PARENT_FORCED')
    for name in current.OPEN: event(name)
    if state.get('pending.accept.next') == retirement.entry(desired):
        event('ACCEPT_RECOVERY_VALIDATED'); replace()
    event('ACCEPT_ACTIVE_FORCED'); event('ACCEPT_ACTIVE_PARENT_FORCED')
    if source_release.AUTHORITY in state:
        append(source_release.transaction(state, expected['sourceRetirement'], expected['compact'], expected['obsolete']))
    if floor_release.RELEASE in state or ('floor-copies' in state and not any(k.startswith('floor-copies/') for k in state)): release()
    if 'sources/'+expected['obsolete'] in state:
        if state['selector.gsr'] != retirement.entry(expected['selector']):
            events, writes = install.transaction(expected['files'])
            for i, name in enumerate(events):
                if name == 'INSTALL_DIRECTORY_CREATED': state['generations/b'] = dict(directory=True)
                for member, at in writes.items():
                    if i == at: state['generations/b/'+member] = retirement.entry(expected['files'][member])
                if name == 'INSTALL_SELECTOR_WRITTEN': state['selector.pending.gsr'] = retirement.entry(expected['selector'])
                if name == 'INSTALL_SELECTOR_RENAMED': state['selector.gsr'] = state.pop('selector.pending.gsr')
                event(name)
            for name in current.OPEN: event(name)
            event('INSTALL_BEFORE_RETURN')
        if state['pending.accept'] != retirement.entry(desired):
            event('ACCEPT_VALIDATED'); replace(); event('ACCEPT_BEFORE_RETURN')
        if 'floor-copies/floor.gsr' not in state:
            event('FLOOR_COPY_BEFORE_RETURN'); event('FLOOR_COPY_BEFORE_RETURN')
            events, files, writes, directories = floor.transaction(expected['copies'], expected['floor'])
            for i, row in enumerate(events):
                for name, at in directories.items():
                    if i == at: state[name] = dict(directory=True)
                for name, at in writes.items():
                    if i == at: state[name] = retirement.entry(files[name])
                event(row['event'])
        rows, _ = retirement.transaction(state, expected['oldGeneration'], expected['generationRetirement']); append(rows)
        append(source_release.transaction(state, expected['sourceRetirement'], expected['compact'], expected['obsolete']))
    release(); event('FLOOR_COPY_BEFORE_RETURN')
    return steps


def validate_case(root, row, expected):
    need(row == dict(mode=row['mode'], cut=row['cut'], recoveryCut=row['recoveryCut'], status='PASS')
         and (row['cut'], row['recoveryCut']) in CUTS and row['mode'] in ('halt', 'kill'), 'carried process case identity')
    retirement.snapshot(root/'original', expected['initial']); state = expected['initial']
    labels = ('fault', 'recovery-fault', 'resume', 'duplicate')
    requests = [v for v in root.iterdir() if v.name.startswith('requests-')]
    need(len(requests) == 4 and all(str(uuid.UUID(v.name.removeprefix('requests-'))) == v.name.removeprefix('requests-')
         and v.is_dir() and not v.is_symlink() for v in requests), 'carried four isolated request clones')
    need({v.name for v in root.iterdir()} == {'original', 'crash', 'recovery-crash', 'final', 'node-1'} |
         {label+suffix for label in labels for suffix in ('.stdout', '.stderr')} | {v.name for v in requests}, 'carried complete case inventory')
    for request in requests:
        need({v.name for v in request.iterdir()} == {'node-1', 'node-2', 'node-3', 'peer'}, 'carried request clone inventory')
        for n in carried.NODES: need(inventory(request/n) == expected['prepared'][n], 'carried immutable selected request original')
        need(inventory(request/'peer') == expected['accepted']['node-2'], 'carried immutable peer floor request')
    for label, cut, snapshot, mode in (('fault', row['cut'], 'crash', row['mode']), ('recovery-fault', row['recoveryCut'], 'recovery-crash', 'halt'),
                                       ('resume', None, 'final', None), ('duplicate', None, 'node-1', None)):
        need(read(root/(label+'.stderr')) == b'', 'carried process child stderr')
        actual = [json.loads(v) for v in read(root/(label+'.stdout'), 2*1024*1024).splitlines()]
        steps = transaction(state, expected); at = retirement.cut_position(steps, cut) if cut else len(steps)-1
        physical_peak = max(sum(name.endswith('.image') for name in snapshot) for _, snapshot in steps[:at+1])
        need(physical_peak <= 7, 'carried bounded images at every physical transaction step')
        emitted = [dict(event=name) for name, _ in steps[:at+1]]; state = steps[at][1]
        if mode == 'kill': emitted.append(dict(event='AWAITING_KILL', cut=cut))
        if mode is None:
            result = actual[-1]; peak = result.get('peakImages')
            # This is a producer-observed lease counter; physical occupancy above
            # is independently reconstructed, including intermediate deletion cuts.
            need(type(peak) is int and max(6, physical_peak) <= peak <= 7, 'carried bounded internal image leases')
            emitted.append(dict(status='PASS', manifest=digest(expected['files']['generation.gsr']), pending=digest(expected['pending']), runtimeEnabled=False, peakImages=peak))
        need(actual == emitted, 'carried exact force/deletion order: '+label+'; actual='+str(actual)+'; expected='+str(emitted))
        retirement.snapshot(root/snapshot, state)
    need(state == expected['settled'] and sum(n.endswith('.image') for n in state) == 2
         and not any(n.startswith(('retirement', 'floor-copies', 'sources.retirement', 'grants.rotation', 'generations/a')) for n in state), 'carried exact settled owner')


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json')); pairs = [(m, c, r) for m in ('halt', 'kill') for c, r in CUTS]
    need(receipt['execution'] == 'private-carried-maintenance-process' and receipt['expectedCases'] == 22 and receipt['freshJvms'] == 88
         and receipt['historicalBootstrap'] == 'conditional-fixture' and receipt['runtimeEnabled'] is False and receipt['powerLoss'] is False, 'carried process scope')
    need([(r['mode'], r['cut'], r['recoveryCut']) for r in receipt['cases']] == pairs
         and {v.name for v in root.iterdir()} == {'receipt.json', 'seed'} | {m+'-'+c for m, c, _ in pairs}, 'carried complete repeated crash matrix')
    expected = plan(root/'seed')
    for row in receipt['cases']: validate_case(root/(row['mode']+'-'+row['cut']), row, expected)
    return dict(status='PASS', cases=22, freshJvms=88, repeatedCrashes=22, physicalObservations=39, oldBallot=20, newBallot=21,
                originalFirst=True, exactPhasePrefixes=True, exactMaintenanceAuthority=True, physicalImageBound=7,
                leasePeak='producer-observed-bounded', settledImages=2, runtimeEnabled=False, powerLoss=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    for variant in ('missing-original-vote', 'changed-original-payload', 'false-observation', 'changed-selected-request', 'lost-old-generation',
                    'early-selector', 'changed-prefix', 'early-pending-clear', 'missing-floor-force', 'missing-retirement-force',
                    'early-source-delete', 'changed-journal', 'resurrected-floor', 'false-crash-cut'):
        with tempfile.TemporaryDirectory(prefix='v53-carried-process-negative-') as tmp:
            case = Path(tmp)/'evidence'; shutil.copytree(root, case); seed = case/'seed'; work = case/'halt-INSTALL_MANIFEST_FORCED'
            if variant == 'missing-original-vote': (seed/'carried-snapshots/old-accepted/node-3/pending.accept').write_bytes(b'')
            elif variant == 'changed-original-payload': (seed/'payload.bin').write_bytes(b'changed')
            elif variant == 'false-observation':
                path = seed/'inputs.json'; data = json.loads(read(path)); data['observations'].pop(); path.write_bytes(f.canonical(data))
            elif variant == 'changed-selected-request':
                request = next(work.glob('requests-*')); (request/'node-2/grants.gsr').write_bytes(b'changed')
            elif variant == 'lost-old-generation': shutil.rmtree(work/'crash/generations/a')
            elif variant == 'early-selector': (work/'crash/selector.gsr').write_bytes(read(work/'final/selector.gsr'))
            elif variant == 'changed-prefix': (case/'halt-ACCEPT_PREFIX_WRITTEN/crash/pending.accept.next').write_bytes(b'changed')
            elif variant == 'early-pending-clear': (work/'final/pending.accept').write_bytes(b'')
            elif variant in ('missing-floor-force', 'missing-retirement-force'):
                path = work/'resume.stdout'; rows = [json.loads(v) for v in read(path).splitlines()]
                target = 'FLOOR_AUTHORITY_FORCED' if variant == 'missing-floor-force' else 'SOURCE_RETIREMENT_FORCED'
                need(any(r.get('event') == target for r in rows), 'carried process negative force target')
                path.write_bytes(b''.join(f.canonical(r)+b'\n' for r in rows if r.get('event') != target))
            elif variant == 'early-source-delete':
                obsolete = json.loads(read(seed/'inputs.json'))['obsolete']; shutil.rmtree(work/'crash/sources'/obsolete)
            elif variant == 'changed-journal': (work/'final/grants.gsr').write_bytes(b'')
            elif variant == 'resurrected-floor': (work/'final/floor-copies').mkdir()
            else:
                path = work/'fault.stdout'; rows = [json.loads(v) for v in read(path).splitlines()]; rows[-1]['event'] = 'INSTALL_GENERATION_FORCED'
                path.write_bytes(b''.join(f.canonical(r)+b'\n' for r in rows))
            try: validate(case)
            except (ValueError, OSError, KeyError, TypeError): negatives.append(variant)
            else: raise ValueError('accepted carried process mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-carried-process-portable-') as tmp:
        case = Path(tmp)/'evidence'; shutil.copytree(root, case); need(validate(case) == result, 'carried process portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args(); print(json.dumps(qualify(args.root), sort_keys=True))
