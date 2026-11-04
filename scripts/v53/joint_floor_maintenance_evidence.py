"""Original interrupted joint floor: continuation, export and reclamation replay.

The entire physical snapshot/grant chain precedes the focused recovered-floor
force check. This does not qualify every other floor or process death.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import joint_floor_recovery_evidence as prior
from . import joining_profile_continuation_evidence as continuation
from . import joining_export_evidence as exports
from . import joining_control_evidence as control
from . import joining_maintenance_evidence as maintenance
from . import retirement_images_evidence as retirement
from . import floor_release_evidence as release

f, disk, need, h, sha = prior.f, prior.c, prior.need, prior.h, prior.catalog.sha
NODE, SCOPE = 'node-2', 'joint-floor-reopened'


def boundary(events):
    starts = [i for i, row in enumerate(events) if row.get('node') == NODE and row.get('scope') == SCOPE]
    need(starts, 'joint maintenance missing cold owner')
    start = starts[0]
    points = ['CURRENT_VALIDATED', 'CURRENT_FILES_FORCED', 'CURRENT_GENERATION_FORCED',
              'CURRENT_SELECTOR_FORCED', 'CURRENT_DIRECTORY_FORCED']
    need(events[start:start+len(points)] == [dict(node=NODE, scope=SCOPE, event=p) for p in points],
         'joint maintenance original cold force order')
    end = next((i for i in range(start, len(events)) if events[i].get('node') == NODE and
                events[i]['event'] == 'FLOOR_RELEASE_BEFORE_RETURN'), None)
    need(end is not None, 'joint maintenance missing recovered floor release')
    return start, end


def physical(root, events):
    """Compose existing independent derivations, retaining all 25 captures."""
    v = continuation; start, _ = boundary(events); lifetimes = {NODE: (start, SCOPE)}
    observed = v.p.Captures(root, events, voters=prior.NODES[:-1], old_owner_lifetimes=lifetimes)
    model = v.s.Replay(root, size=5, kind='REPLACE')
    for index in range(1, 12): model.step(index)
    model.publication_receipts = v.c.t.publication.CheckpointReceipts(root, model, old_owner_lifetimes=lifetimes)
    history = v.p.History(root, model, observed); prefix = history.run()
    owner = v.init.placement.Placement(root, history); placement = owner.run()
    handoff = v.init.retirement.Retirement(root, owner); placed = handoff.run()
    initialized = v.p.Initialization(root, handoff, observed); initialization = initialized.run()
    end = v.Continuation(root, initialized, observed, old_owner_lifetimes=lifetimes).run()
    return model, dict(prefix=prefix, placement=placement, handoff=placed, initialization=initialization, continuation=end)


def recovered_exports(root, events, model):
    start, end = boundary(events)
    rows = exports.n.causal(events, prior.read(root/'wire.json'),
        prior.catalog.catalog.identities(model.states[-1]['identities']), model.root)
    contents = []; transport = exports.n.transfers(rows, contents=contents)
    windows = exports.generation_windows(root, events, model, nodes=(*model.old, model.joining), final_adoption=True)
    phases = exports.n.phase.blocks(events, model, old_owner_lifetimes={NODE: (start, SCOPE)})
    storage = exports.n.phase.slot_storage
    for node in ('node-1', 'node-3'):
        points = phases[9, node]; own = exports.current(windows, node, start, end)
        storage.exact(events, node, None, points['PUBLICATION_VALIDATED'], points['PUBLICATION_SELECTOR_FORCED'],
            storage.publication(own['members']), ('PUBLICATION_', 'INSTALL_', 'CURRENT_'),
            'joint maintenance original exporter force order')
    joined_open = [row for row in events if row.get('node') == model.joining and row.get('scope') == 'initial-owner' and
                   row['event'].startswith('CURRENT_')]
    need(joined_open == [dict(node=model.joining, scope='initial-owner', event=p) for p in storage.CURRENT],
         'joint maintenance original joining force order')
    groups = [group for group in exports.sessions(contents) if group[0]['offer']['request']['sender']['node'] == NODE and
              start < group[0]['offer']['sent'] < end]
    need(len(groups) == 6, 'joint maintenance complete original export sessions')
    for values in groups:
        first, last = values[0]['offer'], values[-1]['commit']; node = first['request']['recipient']['node']
        need(last['delivered'] is not None and last['delivered'] < end and
             exports.authorize_generation(values, windows) == 'current-generation', 'joint maintenance original export binding')
        own = exports.current(windows, node, first['received'], last['offered'])
        prefix, members, _ = disk.current(disk.inventory(root/'joint-floor-recovery/originals'/node))
        need(own['members'] == members, 'joint maintenance exported original generation')
        if node == model.joining:
            need(events[first['received']].get('scope') == 'joint-floor-export', 'joint maintenance temporary endpoint scope')
            control.owner_lifetime(events, node, 'initial-owner', first['received'], last['offered'])
    # The original precondition checks the exact packet/metadata routes and all
    # 66 delivered requests. Here the whole wire is causally paired, and each
    # recovered transfer must fit inside the forced original owner's lifetime.
    own_rows = [row for row in rows if row['request']['sender']['node'] == NODE and start < row['sent'] < end]
    need(len(own_rows) == 66 and all(row['delivered'] is not None and row['delivered'] < end for row in own_rows),
         'joint maintenance complete delivered recovery')
    return dict(wholeTranscript=transport, wholeExchanges=len(rows), recoveredSessions=len(groups), recoveredExchanges=len(own_rows))


def hashes(files):
    return {name: dict(directory=True) if raw is None else retirement.old.entry(raw) for name, raw in files.items()}


def reclaimed(root, events):
    """Derive retained state, borrowed-image retirement and exact release order."""
    side = root/'joint-floor-recovery'; start, end = boundary(events)
    group = {node: disk.inventory(side/'originals'/node) for node in prior.NODES}
    own = copy.deepcopy(group[NODE]); old = copy.deepcopy(own)
    peer_file = continuation.c.PEERS
    own[peer_file] = continuation.init.reconcile(own[peer_file], own, group['node-6'])
    peer_writes = int(own[peer_file] != old[peer_file]); ledger = own[peer_file]
    for node in (NODE, *[n for n in prior.NODES if n != NODE]):
        following = continuation.c.t.observation.observe_same_cut(ledger, own, group[node], defer_renewal=True)
        peer_writes += int(following != ledger); ledger = following
    group[NODE] = own
    expected = continuation.c.maintenance(group, NODE, voters=prior.NODES)
    need(disk.inventory(side/'after-maintenance') == expected, 'joint maintenance exact retained state')
    complete = disk.inventory(side/'resumed-floor'); prefix, members, packet = disk.current(old)
    # Only the inactive generation can disappear. Sources and journal remain
    # pinned in this recovered floor (other history floors are separate gates).
    inactive = [name for name, raw in old.items() if raw is None and name.startswith('generations/') and name != prefix[:-1]]
    need(len(inactive) == 1, 'joint maintenance one inactive generation')
    stale = inactive[0]; originals = {name[len(stale)+1:]: raw for name, raw in old.items() if name.startswith(stale+'/')}
    need({name for name in old if name not in expected} == {stale, *[stale+'/'+name for name in originals]} and
         all(expected[name] == raw for name, raw in old.items() if name in expected and name != continuation.c.PEERS),
         'joint maintenance protected original retention')
    complete[continuation.c.PEERS] = expected[continuation.c.PEERS]
    floor = complete['floor-copies/floor.gsr']; cap = packet['capsule']
    record_value = dict(root=cap['root'], node=NODE, floor=sha(floor), selector=sha(old['selector.gsr']),
        files=[dict(path=stale+'/'+name, size=len(raw), sha256=sha(raw)) for name, raw in sorted(originals.items())])
    record = f.encode('records', 'RETIREMENT', record_value)
    manifest = old[prefix+'generation.gsr']; owner = f.decode(old['node.gsr'], 'records', 'NODE')['identity']
    images = [dict(row, generation=sha(manifest)) for row in record_value['files'] if row['path'].endswith('.image')]
    need(images and all(members[row['path'].split('/')[-1]] == originals[row['path'].split('/')[-1]] for row in images),
         'joint maintenance exact borrowed floor images')
    binding = f.canonical(dict(schema='gse-v53-retirement-floor-images-v1', retirement=sha(record), floor=sha(floor),
        root=cap['root'], node=NODE, storage=owner['storage'], selector=sha(old['selector.gsr']), images=images))
    steps, _ = retirement.transaction(hashes(complete), originals, record, binding, True, slot=stale[-1])
    retired = steps[-1][1]
    release_record = f.encode('records', 'RETIREMENT', dict(root=cap['root'], node=NODE, floor=sha(floor),
        selector=sha(old['selector.gsr']), files=[dict(path=name, size=v['bytes'], sha256=v['sha256'])
        for name, v in sorted(retired.items()) if name.startswith('floor-copies/') and 'directory' not in v]))
    released = release.transaction(retired, release_record)
    need(released[-1][1] == hashes(expected), 'joint maintenance derived retirement and release')
    own_events = [row for row in events[start:end+1] if row.get('node') == NODE]
    peer_force = ['RETENTION_'+p for p in ('BEFORE_WRITE','PREFIX_WRITTEN','WRITTEN','FORCED',
                  'CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED')]
    need(ledger == expected[peer_file] and [row['event'] for row in own_events if row['event'] in peer_force] == peer_force*peer_writes,
         'joint maintenance exact peer ledger force order')
    floor_at = next(i for i in range(start,end+1) if events[i].get('node') == NODE and events[i]['event'] == 'FLOOR_BEFORE_RETURN')
    release_at = next(i for i in range(start,end+1) if events[i].get('node') == NODE and events[i]['event'] == 'FLOOR_RELEASE_AUTHORITY_CREATED')
    need(all(floor_at < i < release_at for i in range(start,end+1) if events[i].get('node') == NODE and events[i]['event'] in peer_force),
         'joint maintenance peer ledger outside floor')
    actual = [row['event'] for row in own_events if row['event'].startswith(('RETIREMENT_', 'SOURCE_RETIREMENT_', 'FLOOR_RELEASE_'))]
    need(actual == [point for point, _ in steps+released], 'joint maintenance exact retirement release force order')
    need(all(row.get('scope') == SCOPE for row in own_events), 'joint maintenance recovered owner scope')
    maintenance.retirement_order(events, NODE, start, end, SCOPE)
    return dict(retiredGenerations=1, retiredMembers=len(originals), borrowedImages=len(images), peerLedgerWrites=peer_writes,
                retirementAndReleaseEvents=len(actual), retainedSources=sum(name.startswith('sources/') and raw is None for name, raw in expected.items()),
                exactRetainedState=True, transientRetirementBytesCaptured=False)


def validated(directory):
    root = Path(directory); before = h.inventory(root)
    preceding = prior.validate(root); events = prior.read(root/'events.json')
    model, chain = physical(root, events)
    exported = recovered_exports(root, events, model); cleanup = reclaimed(root, events)
    need(h.inventory(root) == before, 'joint maintenance original changed')
    result = dict(status='PASS', scope='original-joint-floor-recovery-and-continuation', profile='5-REPLACE',
        precondition=preceding, physicalChain=chain, recoveredExports=exported, recoveredMaintenance=cleanup,
        recoveredRemoteExportForceQualified=True, recoveredMaintenanceReplayQualified=True,
        fullMaintenanceReplayQualified=False, processDeathQualified=False, phase3Complete=False)
    return result, model


def validate(directory):
    return validated(directory)[0]


NEGATIVES = {
    'cold-force-missing': ('exports', 'joint maintenance original cold force order'),
    'temporary-endpoint-substituted': ('exports', 'joint maintenance temporary endpoint scope'),
    'server-receive-missing': ('exports', 'joining network response without request'),
    'export-manifest-force-missing': ('exports', 'joint maintenance original exporter force order'),
    'joining-open-force-missing': ('exports', 'joint maintenance original joining force order'),
    'borrowed-force-missing': ('maintenance', 'joint maintenance exact retirement release force order'),
    'peer-force-missing': ('maintenance', 'joint maintenance exact peer ledger force order'),
    'peer-write-before-floor': ('maintenance', 'joint maintenance peer ledger outside floor'),
    'release-file-missing': ('maintenance', 'joint maintenance exact retirement release force order'),
    'release-before-retirement': ('maintenance', 'joint maintenance exact retirement release force order'),
    'foreign-retirement-owner': ('maintenance', 'joint maintenance recovered owner scope'),
    'extra-retained-allocation': ('maintenance', 'joint maintenance exact retained state'),
    'lost-pinned-source': ('maintenance', 'joint maintenance exact retained state'),
    'lost-journal': ('maintenance', 'joint maintenance exact retained state'),
}


def mutate(root, name):
    need(name in NEGATIVES, 'joint maintenance unknown mutation')
    root = Path(root); final = root/'joint-floor-recovery/after-maintenance'
    if name == 'extra-retained-allocation': (final/'unexpected').write_bytes(b'extra'); return
    if name == 'lost-pinned-source': next((final/'sources').glob('*/source.gscp')).unlink(); return
    if name == 'lost-journal': (final/'grants.gsr').write_bytes(b''); return
    events = prior.read(root/'events.json'); start, end = boundary(events)
    def point(event):
        return next(i for i in range(start, end+1) if events[i].get('node') == NODE and events[i]['event'] == event)
    if name == 'cold-force-missing': events.pop(point('CURRENT_FILES_FORCED'))
    elif name == 'joining-open-force-missing':
        events.pop(next(i for i,row in enumerate(events) if row.get('node') == 'node-6' and
                        row.get('scope') == 'initial-owner' and row['event'] == 'CURRENT_FILES_FORCED'))
    elif name == 'export-manifest-force-missing':
        lower = max(i for i,row in enumerate(events[:start]) if row.get('node') == 'node-1' and row['event'] == 'PUBLICATION_VALIDATED')
        events.pop(next(i for i in range(lower,start) if events[i].get('node') == 'node-1' and events[i]['event'] == 'INSTALL_MANIFEST_FORCED'))
    elif name == 'borrowed-force-missing': events.pop(point('RETIREMENT_BORROWED_IMAGES_FORCED'))
    elif name == 'peer-force-missing': events.pop(point('RETENTION_FORCED'))
    elif name == 'peer-write-before-floor':
        at = point('FLOOR_BEFORE_RETURN'); row = events.pop(point('RETENTION_BEFORE_WRITE')); events.insert(at, row)
    elif name == 'release-file-missing': events.pop(point('FLOOR_RELEASE_FILE_DELETED'))
    elif name == 'foreign-retirement-owner': events[point('RETIREMENT_AUTHORITY_FORCED')]['scope'] = 'foreign-owner'
    elif name == 'release-before-retirement':
        a, b = point('RETIREMENT_RESERVED'), point('FLOOR_RELEASE_AUTHORITY_CREATED')
        held = [v for v in events[b:end+1] if v.get('node') == NODE]
        events[b:end+1] = [v for v in events[b:end+1] if v.get('node') != NODE]
        events[a:a] = held
    elif name == 'temporary-endpoint-substituted':
        for row in events[start:end+1]:
            if row.get('scope') == 'joint-floor-export': row['scope'] = 'foreign-endpoint'
    elif name == 'server-receive-missing':
        at = next(i for i in range(start, end+1) if events[i].get('scope') == 'joint-floor-export' and
                  events[i]['event'] == 'AFTER_REQUEST_READ')
        events.pop(at)
    (root/'events.json').write_bytes(f.canonical(events))


def qualify(directory, progress=None):
    root = Path(directory); before = h.inventory(root); original, model = validated(root); results = []
    if progress: progress(dict(stage='original', status='PASS'))
    for name, (stage, reason) in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joint-maintenance-negative-') as tmp:
            changed = Path(tmp)/'raw'; shutil.copytree(root, changed); mutate(changed, name)
            allowed = ('joint-floor-recovery/after-maintenance/' if name in
                       ('extra-retained-allocation', 'lost-pinned-source', 'lost-journal') else 'events.json')
            def protected(inventory):
                return {n:v for n,v in inventory['files'].items() if not (n.startswith(allowed) if allowed.endswith('/') else n == allowed)}
            after = h.inventory(changed)
            need(protected(after) == protected(before) and after['directories'] == before['directories'],
                 'joint maintenance mutation changed protected inputs')
            # Original physical derivation is required once. Each mutant checks
            # its designated layer; never count an unrelated earlier rejection.
            try:
                events = prior.read(changed/'events.json')
                if stage == 'exports': recovered_exports(changed, events, model)
                else: reclaimed(changed, events)
            except ValueError as error:
                need(str(error) == reason, 'joint maintenance unrelated rejection: '+name+': '+str(error))
            else: raise ValueError('joint maintenance mutation accepted: '+name)
        results.append(dict(case=name, stage=stage, status='REJECTED', reason=reason))
        if progress: progress(results[-1])
    need(h.inventory(root) == before, 'joint maintenance original changed')
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args()
    result = qualify(args.root, lambda row: print(json.dumps(row, sort_keys=True), file=sys.stderr, flush=True)) if args.qualify else validate(args.root)
    print(json.dumps(result, sort_keys=True))
