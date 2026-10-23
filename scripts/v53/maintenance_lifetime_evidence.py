"""Compose original-first install/floor/retirement models across actual process crashes.

This is a fixed small-image, three-voter maintenance profile. Historical bootstrap
and supplied authenticated observations remain conditional inputs, not network evidence.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import publication_lifetime_evidence as lifetime
from . import generation_install_evidence as install
from . import floor_evidence as floor
from . import retirement_evidence as retirement
from . import source_release_evidence as source_release
from . import floor_release_evidence as floor_release
from . import current_generation_evidence as current
from . import format_fixture as f
from . import source_packet as p
from . import selected_sources_evidence as sources
from .journal_application_evidence import inventory
from .grant_evidence import journal
from .applied_end_evidence import read, digest
from .membership_model import need

CUTS = (
    ('INSTALL_MANIFEST_FORCED', 'INSTALL_GENERATION_FORCED'),
    ('INSTALL_SELECTOR_RENAMED', 'FLOOR_COPIES_FORCED'),
    ('FLOOR_AUTHORITY_FORCED', 'RETIREMENT_AUTHORITY_FORCED'),
    ('RETIREMENT_FILE_DELETED', 'RETIREMENT_AUTHORITY_RESEALED'),
    ('SOURCE_RETIREMENT_FORCED', 'JOURNAL_ROTATION_FORCED'),
    ('JOURNAL_ROTATION_RENAMED', 'SOURCE_RETIREMENT_FORCED'),
    ('SOURCE_RETIREMENT_FILE_DELETED', 'SOURCE_RETIREMENT_FORCED'),
    ('FLOOR_RELEASE_RELINQUISHED', 'FLOOR_RELEASE_AUTHORITY_FORCED'),
    ('FLOOR_RELEASE_AUTHORITY_CLEARED', 'FLOOR_RELEASE_CLEARED'))


def metadata(raw):
    return {k: dict(directory=True) if v is None else retirement.entry(v) for k, v in raw.items()}


def entries(files, prefix=''):
    return [dict(path=prefix+k, size=len(v), sha256=digest(v)) for k, v in sorted(files.items())]


def plan(root):
    root = Path(root); supplied = json.loads(read(root/'inputs.json')); previous = {}
    need([(r['cycle'], r['node']) for r in supplied['rounds']] == [(i, 'node-'+str(n)) for i in (0, 1) for n in (1, 2, 3)], 'maintenance original rounds')
    for row in supplied['rounds']:
        node = row['node']; previous[node] = lifetime.state(root/'snapshots'/('round-'+str(row['cycle']))/node, row, previous.get(node))
    initial = {}; grants = {}; new = {}; obsolete = None
    # Freeze the originals before deriving any candidate, deletion inventory or final state.
    for node in ('node-1', 'node-2', 'node-3'):
        raw = inventory(root/'inputs'/node); before = inventory(root/'snapshots/round-1'/node); root_hash = raw['root.gsr'][16:48].hex()
        rows = journal(raw['grants.gsr'], root_hash, node); old = journal(before['grants.gsr'], root_hash, node)
        need(rows[:3] == old and [k for k, _, _ in rows] == ['PROMISE', 'BASIS', 'SELECTED']*2, 'maintenance exact two original grants')
        promise, basis, selected = [r[2] for r in rows[3:]]; ident = basis['basisId']; prefix = 'sources/'+ident+'/'
        need(promise['ballot']['counter'] == basis['ballot']['counter'] == selected['ballot']['counter'] == 22
             and basis['cut'] == selected['cut'] == previous[node]['cut'] and basis['accepted'] is selected['nextEntry'] is None, 'maintenance original new decision')
        expected = dict(before, **{'grants.gsr': b''.join(r[1] for r in rows), prefix[:-1]: None, prefix+'source.gscp': previous[node]['packet']})
        packet = p.decode(previous[node]['packet']); p.bind(packet, rows[4][1])
        for h in packet['images']: expected[prefix+h+'.image'] = before['generations/a/'+h+'.image']
        need(raw == expected, 'maintenance exact prepared source and old publication')
        if node == 'node-1':
            obsolete = old[1][2]['basisId']; need(supplied['obsolete'] == obsolete, 'maintenance original obsolete identity')
        initial[node], grants[node] = raw, rows
    original_frames = b''.join(grants[n][4][1] for n in sorted(grants))
    for node, raw in initial.items():
        rows = grants[node]; cap = p.decode(previous[node]['packet']); selected = rows[-1][2]
        need(sources.cuts(original_frames, selected) == [cap['capsule']['cut']]*3, 'maintenance common fixed selection')
        files = dict(zip(('promise.gsr', 'basis.gsr', 'selected.gsr'), [r[1] for r in rows[3:]]))
        files.update({'source.gscp': previous[node]['packet'], sources.FILE: original_frames,
                      'ancestry.gsr': raw['generations/a/ancestry.gsr']})
        files.update({h+'.image': raw['generations/a/'+h+'.image'] for h in cap['images']})
        manifest = dict(root=cap['capsule']['root'], node=node, generation='b', **{k: cap['capsule'][k] for k in ('cut', 'catalog', 'application')},
                        capsule=digest(cap['capsuleBytes']), promise=digest(rows[3][1]), basis=digest(rows[4][1]), selection=digest(rows[5][1]), ownedTail=None, files=entries(files))
        files['generation.gsr'] = f.encode('records', 'GENERATION', manifest)
        selector = f.encode('records', 'SELECTOR', dict(root=root_hash, node=node, generation='b', digest=digest(files['generation.gsr'])))
        new[node] = (files, selector)
        if node != 'node-1':
            expected = dict(raw, **{'selector.gsr': selector, 'generations/b': None})
            expected.update({'generations/b/'+k: v for k, v in files.items()})
            need(inventory(root/node) == expected, 'maintenance original complete peer installation')
    parts = lifetime.frames(initial['node-1']['generations/a/ancestry.gsr'])
    need(parts[0] == read(root/'parent-statement.gsr') and parts[1:] == [read(root/('parent-'+str(n)+'.gsr')) for n in (1, 2, 3)], 'maintenance exact retained bridge')
    statement = f.decode(parts[0], 'records', 'CHECKPOINT', root_hash)
    expected_owned = []
    for n, ack in zip(sorted(initial), parts[1:]):
        identity = f.decode(initial[n]['node.gsr'], 'records', 'NODE', root_hash)['identity']
        expected_owned.append(dict(voter=n, storage=identity['storage'], record=digest(ack), parent=digest(f.canonical(statement['end']))))
    need(supplied['parents'] == expected_owned and all(v in supplied['observations'] for v in expected_owned), 'maintenance retained bridge observations')
    raw = initial['node-1']; need(inventory(root/'original') == raw, 'maintenance initial owner exact bytes')
    files, selector = new['node-1']; cap = p.decode(files['source.gscp'])['capsule']
    copies = {digest(new[n][0]['generation.gsr']): new[n][0] for n in ('node-1', 'node-2')}
    references = [dict(voter=n, generation=digest(new[n][0]['generation.gsr']), catalog=cap['catalog'], snapshot=cap['application']) for n in ('node-1', 'node-2')]
    floor_record = f.encode('records', 'FLOOR', dict(root=root_hash, node='node-1', cut=cap['cut'], sources=references))
    old_generation = {k.removeprefix('generations/a/'): v for k, v in raw.items() if k.startswith('generations/a/')}
    authority = dict(root=root_hash, node='node-1', floor=digest(floor_record), selector=digest(selector))
    generation_retirement = f.encode('records', 'RETIREMENT', dict(authority, files=entries(old_generation, 'generations/a/')))
    source_prefix = 'sources/'+obsolete+'/'
    old_source = {k.removeprefix(source_prefix): v for k, v in raw.items() if k.startswith(source_prefix)}
    source_retirement = f.encode('records', 'RETIREMENT', dict(authority, files=entries(old_source, source_prefix)))
    source_retirement += b''.join(r[1] for r in grants['node-1'][:2])+p.decode(old_source['source.gscp'])['capsuleBytes']
    compact = b''.join(r[1] for r in grants['node-1'][3:])
    floor_files = {'floor-copies/floor.gsr': floor_record, 'floor-copies/proposal.gsr': floor_record}
    for h, copy in copies.items(): floor_files.update({'floor-copies/'+h+'/'+k: v for k, v in copy.items()})
    release = f.encode('records', 'RETIREMENT', dict(authority, files=entries(floor_files)))
    return dict(initial=metadata(raw), files=files, selector=selector, copies=copies, floor=floor_record,
                oldGeneration=old_generation, generationRetirement=generation_retirement, sourceRetirement=source_retirement,
                compact=compact, obsolete=obsolete, release=release, cut=cap['cut'])


def transaction(original, plan):
    state = dict(original); steps = []
    def event(name): steps.append((name, dict(state)))
    def append(rows):
        nonlocal state
        if rows: steps.extend(rows); state = dict(rows[-1][1])
    def release(): append(floor_release.transaction(state, plan['release']))
    for name in current.OPEN: event(name)
    event('ACCEPT_ACTIVE_FORCED'); event('ACCEPT_ACTIVE_PARENT_FORCED')
    if source_release.AUTHORITY in state:
        append(source_release.transaction(state, plan['sourceRetirement'], plan['compact'], plan['obsolete']))
    if floor_release.RELEASE in state or ('floor-copies' in state and not any(k.startswith('floor-copies/') for k in state)):
        release()
    if 'sources/'+plan['obsolete'] in state:
        if state['selector.gsr'] != retirement.entry(plan['selector']):
            events, writes = install.transaction(plan['files'])
            for i, name in enumerate(events):
                if name == 'INSTALL_DIRECTORY_CREATED': state['generations/b'] = dict(directory=True)
                for member, at in writes.items():
                    if i == at: state['generations/b/'+member] = retirement.entry(plan['files'][member])
                if name == 'INSTALL_SELECTOR_WRITTEN': state['selector.pending.gsr'] = retirement.entry(plan['selector'])
                if name == 'INSTALL_SELECTOR_RENAMED': state['selector.gsr'] = state.pop('selector.pending.gsr')
                event(name)
            for name in current.OPEN: event(name)
            event('INSTALL_BEFORE_RETURN')
        if 'floor-copies/floor.gsr' not in state:
            event('FLOOR_COPY_BEFORE_RETURN'); event('FLOOR_COPY_BEFORE_RETURN')
            events, files, writes, directories = floor.transaction(plan['copies'], plan['floor'])
            for i, row in enumerate(events):
                for name, at in directories.items():
                    if i == at: state[name] = dict(directory=True)
                for name, at in writes.items():
                    if i == at: state[name] = retirement.entry(files[name])
                event(row['event'])
        rows, _ = retirement.transaction(state, plan['oldGeneration'], plan['generationRetirement']); append(rows)
        append(source_release.transaction(state, plan['sourceRetirement'], plan['compact'], plan['obsolete']))
    release(); event('FLOOR_COPY_BEFORE_RETURN')
    return steps


def validate_case(root, row):
    root = Path(root); need(row['status'] == 'PASS' and row['mode'] in ('halt', 'kill') and (row['cut'], row['recoveryCut']) in CUTS, 'maintenance case identity')
    expected = plan(root); state = expected['initial']
    for label, cut, snapshot, mode in (('fault', row['cut'], 'crash', row['mode']), ('recovery-fault', row['recoveryCut'], 'recovery-crash', 'halt'),
                                        ('resume', None, 'final', None), ('duplicate', None, 'node-1', None)):
        need(read(root/(label+'.stderr')) == b'', 'maintenance child stderr')
        rows = [json.loads(v) for v in read(root/(label+'.stdout'), 2*1024*1024).splitlines()]
        steps = transaction(state, expected); at = retirement.cut_position(steps, cut) if cut else len(steps)-1
        emitted = [dict(event=e) for e, _ in steps[:at+1]]; state = steps[at][1]
        if mode == 'kill': emitted.append(dict(event='AWAITING_KILL', cut=cut))
        if mode is None:
            emitted.append(dict(status='PASS', manifest=digest(expected['files']['generation.gsr']), cut=expected['cut'], journal=digest(expected['compact']), runtimeEnabled=False))
        need(rows == emitted, 'maintenance exact force/deletion order: '+label)
        retirement.snapshot(root/snapshot, state)
    need(not any(k.startswith(('floor-copies', 'retirement', 'sources.retirement', 'grants.rotation', 'generations/a')) for k in state), 'maintenance no obsolete authority')
    need(sum(k.endswith('.image') for k in state) == 2, 'maintenance settled two images')
    return state


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json')); pairs = [(mode, cut, again) for mode in ('halt', 'kill') for cut, again in CUTS]
    need(receipt['execution'] == 'private-coordinated-maintenance' and receipt['expectedCases'] == 18 and receipt['freshJvms'] == 72
         and receipt['historicalBootstrap'] == 'conditional-fixture' and receipt['runtimeEnabled'] is receipt['powerLoss'] is False, 'maintenance scope')
    need([(r['mode'], r['cut'], r['recoveryCut']) for r in receipt['cases']] == pairs
         and {p.name for p in root.iterdir()} == {'seed', 'receipt.json'} | {m+'-'+c for m, c, _ in pairs}, 'maintenance full case inventory')
    for row in receipt['cases']: validate_case(root/(row['mode']+'-'+row['cut']), row)
    return dict(status='PASS', cases=18, freshJvms=72, repeatedCrashes=18, settledImages=2, settledSources=1, powerLoss=False, runtimeEnabled=False)


def qualify(root):
    root = Path(root); result = validate(root); rows = json.loads(read(root/'receipt.json'))['cases']; rejected = []
    variants = ('missing-source', 'changed-peer', 'altered-old-ancestry', 'missing-parent-observation', 'early-selector',
                'early-generation-delete', 'early-source-delete', 'missing-floor-force', 'missing-retirement-force', 'changed-journal',
                'floor-recreated', 'missing-original-selected', 'false-crash-cut')
    for variant in variants:
        with tempfile.TemporaryDirectory(prefix='v53-maintenance-negative-') as temp:
            row = rows[0]; case = Path(temp)/'case'; shutil.copytree(root/(row['mode']+'-'+row['cut']), case)
            if variant == 'missing-source':
                source = next((case/'inputs/node-2/sources').glob('*/source.gscp')); source.unlink()
            elif variant == 'changed-peer': (case/'node-2/generations/b/ancestry.gsr').write_bytes(b'')
            elif variant == 'altered-old-ancestry': (case/'original/generations/a/ancestry.gsr').write_bytes(b'')
            elif variant == 'missing-parent-observation':
                path = case/'inputs.json'; data = json.loads(read(path)); data['parents'] = []; path.write_bytes(f.canonical(data))
            elif variant == 'early-selector': (case/'crash/selector.gsr').write_bytes(read(case/'final/selector.gsr'))
            elif variant == 'early-generation-delete': shutil.rmtree(case/'crash/generations/a')
            elif variant == 'early-source-delete':
                obsolete = json.loads(read(case/'inputs.json'))['obsolete']; shutil.rmtree(case/'crash/sources'/obsolete)
            elif variant in ('missing-floor-force', 'missing-retirement-force'):
                path = case/'resume.stdout'; event = 'FLOOR_AUTHORITY_FORCED' if variant == 'missing-floor-force' else 'SOURCE_RETIREMENT_FORCED'
                records = [json.loads(v) for v in read(path).splitlines()]; need(any(v.get('event') == event for v in records), 'maintenance negative target')
                path.write_bytes(b''.join(f.canonical(v)+b'\n' for v in records if v.get('event') != event))
            elif variant == 'changed-journal': (case/'final/grants.gsr').write_bytes(b'')
            elif variant == 'floor-recreated': (case/'final/floor-copies').mkdir()
            elif variant == 'missing-original-selected': (case/'final/generations/b'/sources.FILE).unlink()
            else: row = dict(row, recoveryCut='FLOOR_COPIES_FORCED')
            try: validate_case(case, row)
            except (ValueError, OSError, KeyError, TypeError): rejected.append(variant)
            else: raise ValueError('accepted maintenance mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-maintenance-portable-') as temp:
        dest = Path(temp)/'evidence'; shutil.copytree(root, dest); need(validate(dest) == result, 'maintenance portable replay')
    return dict(result, negatives=rejected, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args(); print(json.dumps(qualify(args.root), sort_keys=True))
