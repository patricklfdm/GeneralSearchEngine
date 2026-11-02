"""One original joining process history: custody, native bytes and transport.

Only actual EVENT/WIRE observations from the shared interprocess trace are
projected into a disposable reader view. Original files are never rewritten;
no event or authority is synthesized to satisfy a single-process reader.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_initialization_process_evidence as transaction
from . import joining_profile_continuation_evidence as continuation
from . import joining_network_evidence as network
from .joining_profile_evidence import topology

run = transaction.run
p, init, s, f, disk, need = (continuation.p, continuation.init, continuation.s,
                            continuation.f, continuation.disk, continuation.need)
OPEN = list(network.current_lifecycle.OPEN)
ACCEPT = ['ACCEPT_ACTIVE_FORCED', 'ACCEPT_ACTIVE_PARENT_FORCED']
LEDGERS = init.recovery_order()[9:-2]
TRANSPORT = frozenset(('BEFORE_REQUEST_WRITE', 'AFTER_REQUEST_READ', 'BEFORE_RESPONSE_WRITE',
                       'AFTER_RESPONSE_READ', 'NETWORK_ATTEMPT_FAILED'))


def child_callbacks(final, case):
    """Expected owner callbacks; cold completion depends on the original cut."""
    selected = run.selected(case); at = run.POINTS.index(selected['point'])
    first = transaction.steps(final); recovery = transaction.steps(final, initial=first[at][1])
    interrupted = OPEN+ACCEPT+['FIXTURE_OPEN_RETURNED']+[v[0] for v in first[:at+1]]
    if at < run.POINTS.index('JOINING_RETENTION_SEED_WRITTEN'):
        # A missing/partial decision cannot authorize native ledgers. Only
        # explicit read-only acquisition after open can complete these bytes.
        resumed = OPEN+ACCEPT+['FIXTURE_OPEN_RETURNED', 'INCOMPLETE_NATIVE_USES_REFUSED']+[v[0] for v in recovery]+LEDGERS
    else:
        # The complete original decision finishes/reseals before open returns.
        resumed = OPEN+[v[0] for v in recovery]+LEDGERS+ACCEPT+['FIXTURE_OPEN_RETURNED']
    return {selected['mode']: interrupted, 'resume': resumed+['FIXTURE_CLOSE_RETURNED']}


def child_order(raw, case, observed):
    active = transaction.ledgers.snapshot.read(Path(raw)/'joining-process-resumed-active')
    files = transaction.files(active); final = {name: files[name] for name in transaction.ACTIVE}
    expected = child_callbacks(final, case); trace = run.lines(Path(raw)/'process-trace.jsonl')
    node = topology(run.selected(case)['profile'])[3][-1]
    for mode, points in expected.items():
        rows = [(i, row['value']['value']) for i, row in enumerate(trace)
                if row['origin'] == mode and row['value']['kind'] == 'EVENT' and
                row['value']['value']['event'] not in TRANSPORT]
        need([row for _, row in rows] == [dict(node=node, scope='initialization-'+mode, event=point) for point in points],
             'joining process exact child owner callbacks')
        if mode == 'resume':
            ready = observed['controls']['resume']['READY']
            need(rows[-2][0] < ready < rows[-1][0], 'joining process readiness before owner completion')
    return dict(interruptedCallbacks=len(expected[run.selected(case)['mode']]), recoveredCallbacks=len(expected['resume']))


def observations(raw, case):
    """Retain a mapping back to every original shared-trace position."""
    raw = Path(raw); run.collect(raw, case)
    mode = run.selected(case)['mode']; joining = topology(run.selected(case)['profile'])[3][-1]
    trace = run.lines(raw/'process-trace.jsonl'); events = []; wires = s.collection.read_json(raw, 'wire.json', s.collection.WIRE_BYTES)
    positions = []; controls = {}; counts = {}
    for origin in (mode, 'resume'):
        rows = [(i, v['value']) for i, v in enumerate(trace) if v['origin'] == origin]
        controls[origin] = {v['kind']: i for i, v in rows if v['kind'] not in ('EVENT', 'WIRE')}
        start, end = controls[origin]['STARTED'], controls[origin]['CUT' if origin == mode else 'CLOSED']
        need(all(start < i < end for i, v in rows if v['kind'] in ('EVENT', 'WIRE')),
             'joining process observation outside child lifetime')
        counts[origin] = len(rows)
    need(controls[mode]['CUT'] < controls['resume']['STARTED'], 'joining process overlapping child lifetimes')
    for at, row in enumerate(trace):
        if row['origin'] == 'parent': value = row['value']
        elif row['value']['kind'] == 'EVENT':
            value = row['value']['value']
            need(type(value) is dict and value.get('node') == joining and value.get('scope') == 'initialization-'+row['origin'],
                 'joining process foreign child observation')
        elif row['value']['kind'] == 'WIRE':
            wires.append(row['value']['value']); continue
        else: continue
        need(type(value) is dict and type(value.get('event')) is str, 'joining process event shape')
        events.append(value); positions.append(dict(trace=at, origin=row['origin']))
    # Parent lifetime boundaries remain original observations, not inferred
    # from producer PASS labels or copied filesystem timestamps.
    windows = {}
    for scope in ('initial-owner', 'process-retention-observe', 'retaining-owner', 'repeated-basis-owner'):
        rows = [i for i, row in enumerate(trace) if row['origin'] == 'parent' and row['value'].get('scope') == scope]
        need(rows and all(trace[i]['value'].get('node') == joining for i in rows), 'joining process parent owner scope')
        windows[scope] = min(rows), max(rows)
    need(windows['initial-owner'][1] < controls[mode]['STARTED'] and
         controls['resume']['CLOSED'] < windows['process-retention-observe'][0] <= windows['process-retention-observe'][1] <
         windows['retaining-owner'][0] <= windows['retaining-owner'][1] < windows['repeated-basis-owner'][0],
         'joining process cross-process owner order')
    need(len(events) <= s.collection.HISTORY_ROWS and len(wires) <= s.collection.HISTORY_ROWS,
         'joining process combined observation capacity')
    return dict(events=events, wires=wires, positions=positions, controls=controls, childMessages=counts)


@contextmanager
def view(raw, observed):
    """Same-history projection; retained original absolute paths stay data."""
    with tempfile.TemporaryDirectory(prefix='v53-joining-process-view-') as directory:
        copied = Path(directory)/'raw'; shutil.copytree(raw, copied)
        for name in ('events', 'wire'):
            data = f.canonical(observed['events' if name == 'events' else 'wires'])
            need(len(data) <= (s.collection.EVENT_BYTES if name == 'events' else s.collection.WIRE_BYTES),
                 'joining process projected observation byte capacity')
            (copied/(name+'.json')).write_bytes(data)
        yield copied


def snapshot_files(snap):
    return {family: {v['name']: None if 'directory' in v['identity'] else snap.member(family, v['name'])
                     for v in row['files']}
            for family, row in snap.identities.items() if row['present']}


class Initialization(p.Initialization):
    def __init__(self, root, handoff, captures, case):
        super().__init__(root, handoff, captures); self.case = case

    def initial_current(self, prefix, members):
        # This capture intentionally starts after old-majority preparation.
        # Compare the whole derived original custody, not nonexistent early
        # startup files and not a replacement seed imported from the snapshot.
        before = transaction.ledgers.snapshot.read(self.root/'joining-process-before-process')
        need(snapshot_files(before) == self.handoff.expected, 'joining process original pre-initialization custody')
        self.before = before
        spec = run.metadata.read(self.root/'joining-process/spec.json')
        request = self.owner.request
        manifest = f.decode(self.replay.root_bytes, 'records', 'ROOT')
        expected = dict(schema='gse-v53-joining-initialization-process-v1', plan=self.owner.plan,
                        root=dict(group=manifest['groupId'], history=manifest['historyId'], digest=self.replay.root),
                        learner=self.owner.joining, number=request['number'], kind=request['kind'],
                        expected=request['expected'], targets=request['target'],
                        paths={name: before.identities[family]['path']['path'] for name, family in
                               (('replica', 'replica'), ('operation', 'operation'), ('application', 'materialization'))},
                        proposer=s.catalog.identities(self.replay.states[-1]['identities'])['node-1'])
        need(f.canonical(spec) == f.canonical(expected), 'joining process specification original authority')
        for stage in ('before-process', 'interrupted', 'resumed-active', 'resumed-closed'):
            need({node: disk.inventory(self.root/('process-'+stage)/node) for node in self.group} == self.group,
                 'joining process changed old-majority preparation')

    def check_order(self, events):
        init.retained_order(events, joining=self.replay.joining)
        def own(scope):
            rows = [v for v in events if v.get('scope') == scope]
            need(all(v.get('node') == self.replay.joining for v in rows), 'joining process local order owner')
            return [v['event'] for v in rows]
        need(own('initial-owner') == ['JOINED_NATIVE_RECORD_FORCED', 'JOINED_NATIVE_DECISION_FORCED', 'JOINED_NATIVE_TRANSFERRED']+
             OPEN+ACCEPT+['FLOOR_COPY_BEFORE_RETURN']*3, 'joining process original uninitialized owner order')
        need(own('process-retention-observe') == init.recovery_order()+['FLOOR_COPY_BEFORE_RETURN'],
             'joining process completed observer order')


def physical(root, case):
    profile = run.selected(case)['profile']; size, kind, old, _ = topology(profile)
    events = s.collection.read_json(root, 'events.json', s.collection.EVENT_BYTES)
    captures = p.Captures(root, events, voters=old[:size//2+1])
    continuation.c.t.publication.validate(root, size=size, kind=kind)
    replay = s.Replay(root, size=size, kind=kind)
    for index in range(1, 12): replay.step(index)
    replay.publication_receipts = continuation.c.t.publication.CheckpointReceipts(root, replay)
    history = p.History(root, replay, captures); history.run()
    owner = init.placement.Placement(root, history); owner.run()
    handoff = init.retirement.Retirement(root, owner); handoff.run()
    initialized = Initialization(root, handoff, captures, case); initialized.run()
    result = continuation.Continuation(root, initialized, captures).run()
    return result, replay


def durable_network(root, case, observed, replay, rows):
    """Reuse the exact grant/selection/slot force gates with all child events."""
    events = observed['events']
    grants, bases = network.grants(root, events, rows)
    installs = network.installations(root, events, rows, replay, bases)
    slots = network.phase.phase_replay(events, rows, replay, network.phase.blocks(events, replay))
    network.initial_current.validate(events, replay.old)
    lifecycle = network.current_lifecycle
    current = lifecycle.Ownership(events)
    current.original_opens(replay.old, False); current.joining_opens(replay.joining)
    for scope in ('process-retention-observe', 'initialization-'+run.selected(case)['mode'], 'initialization-resume'):
        points = [i for i, v in enumerate(events) if v.get('node') == replay.joining and v.get('scope') == scope]
        need(points, 'joining process missing current lifecycle')
        current.take(replay.joining, scope, min(points)-1, max(points)+1, OPEN, 'process-open-'+scope)
    current.generations(lifecycle.changes(replay.phases, (*replay.old, replay.joining), joining=replay.joining), replay.joining)
    captures = Counter((v['node'], None if v['scope'] == 'network-owner' else v['scope']) for v in bases.values())
    captures[replay.joining, 'repeated-basis-owner'] += 1
    current.captures(captures)
    return dict(grants=grants, installations=installs, slots=slots, currentLifecycle=current.finish())


def validate(raw, case):
    raw = Path(raw); before = run.h.inventory(raw)
    original = transaction.validate(raw, case)
    observed = observations(raw, case)
    lifecycle = child_order(raw, case, observed)
    with view(raw, observed) as copied:
        derived, replay = physical(copied, case)
        failed = []; identities = s.catalog.identities(replay.states[-1]['identities'])
        rows = network.causal(observed['events'], observed['wires'], identities, replay.root, failed=failed)
        transfers = network.transfers(rows)
        durable = durable_network(copied, case, observed, replay, rows)
    need(run.h.inventory(raw) == before, 'joining process composition changed original')
    return dict(status='PARTIAL', scope='original-joining-process-physical-and-transport-composition', case=case,
                transaction=original, continuation=derived, transfers=transfers, childLifecycle=lifecycle, durableNetwork=durable,
                eventCount=len(observed['events']), wireCount=len(rows), failedAttempts=len(failed),
                projectionSha256=run.h.digest(f.canonical(observed['positions'])),
                originalPhysicalHistoryVerified=True, observedTransportVerified=True, durableACKsVerified=True,
                completeNetworkAuthorityQualified=False, continuousLedgersQualified=False,
                processDeathQualified=False, phase3Complete=False)


NEGATIVES = {
    'foreign-child-owner': 'joining process foreign child observation',
    'overlapping-children': 'joining process overlapping child lifetimes',
    'observer-before-close': 'joining process cross-process owner order',
    'missing-child-current-force': 'joining process exact child owner callbacks',
    'premature-ready': 'joining process readiness before owner completion',
    'unexplained-original-file': 'joining process original pre-initialization custody',
    'changed-old-preparation': 'joining process changed old-majority preparation',
    'changed-process-spec': 'joining process specification original authority',
    'missing-child-response': 'joining unmatched original response',
    'cold-extra-allocation': 'joining continuation exact family: joining-originals-stable-cold: replica',
    'missing-cold-force': 'joining continuation original cold reseal order',
}


def save_trace(raw, trace):
    """Keep original parent/child copies consistent in a disposable negative."""
    def lines(path, values): path.write_bytes(b''.join(f.canonical(v)+b'\n' for v in values))
    lines(raw/'process-trace.jsonl', trace)
    (raw/'events.json').write_bytes(f.canonical([v['value'] for v in trace if v['origin'] == 'parent']))
    for origin in {v['origin'] for v in trace}-{'parent'}:
        lines(raw/'joining-process'/origin/'stdout', [v['value'] for v in trace if v['origin'] == origin])


def mutate(raw, case, name):
    need(name in NEGATIVES, 'joining process composition negative selector'); raw = Path(raw)
    mode = run.selected(case)['mode']
    if name == 'unexplained-original-file':
        for stage in ('before-process', 'interrupted', 'resumed-active', 'resumed-closed'):
            path = raw/('joining-process-'+stage); data = b'not derived by the native history'
            rows = run.metadata.read(path/'inventory.json'); replica = next(v for v in rows if v['name'] == 'replica')
            replica['files'].append(dict(name='unexplained.gsr', identity=dict(key='original-extra-inode', size=len(data), sha256=run.h.digest(data))))
            replica['files'].sort(key=lambda v: v['name']); (path/'replica/unexplained.gsr').write_bytes(data)
            (path/'inventory.json').write_bytes(f.canonical(rows))
        return
    if name == 'changed-old-preparation':
        path = raw/'process-interrupted/node-1/allocator.gsr'; value = f.decode(path.read_bytes(), 'records', 'ALLOCATOR')
        value['counter'] += 1; path.write_bytes(f.encode('records', 'ALLOCATOR', value)); return
    if name == 'changed-process-spec':
        path = raw/'joining-process/spec.json'; value = run.metadata.read(path); value['root']['digest'] = '0'*64
        path.write_bytes(f.canonical(value)); return
    if name == 'cold-extra-allocation':
        continuation.c.mutate(raw, name); return
    trace = run.lines(raw/'process-trace.jsonl')
    def find(origin, kind, event=None):
        return next(i for i, v in enumerate(trace) if v['origin'] == origin and v['value']['kind'] == kind and
                    (event is None or v['value']['value'].get('event') == event))
    if name == 'foreign-child-owner':
        trace[find(mode, 'EVENT', 'CURRENT_FILES_FORCED')]['value']['value']['node'] = 'node-foreign'
    elif name == 'overlapping-children':
        row = trace.pop(find('resume', 'STARTED')); trace.insert(find(mode, 'CUT'), row)
    elif name == 'observer-before-close':
        i = next(i for i, v in enumerate(trace) if v['origin'] == 'parent' and v['value'].get('scope') == 'process-retention-observe')
        row = trace.pop(i); trace.insert(find('resume', 'CLOSED'), row)
    elif name == 'missing-child-current-force': del trace[find(mode, 'EVENT', 'CURRENT_FILES_FORCED')]
    elif name == 'premature-ready':
        row = trace.pop(find('resume', 'READY')); trace.insert(find('resume', 'EVENT', 'FIXTURE_OPEN_RETURNED'), row)
    elif name == 'missing-child-response': del trace[find('resume', 'WIRE')]
    elif name == 'missing-cold-force':
        i = next(i for i, v in enumerate(trace) if v['origin'] == 'parent' and v['value'].get('scope') == 'stable-cold-owner'
                 and v['value']['event'] == 'CURRENT_FILES_FORCED'); del trace[i]
    save_trace(raw, trace)


def qualify(raw, case, *, progress=None):
    raw = Path(raw); before = run.h.inventory(raw); original = validate(raw, case); results = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-process-negative-') as directory:
            copied = Path(directory)/'raw'; shutil.copytree(raw, copied); mutate(copied, case, name)
            try: validate(copied, case)
            except ValueError as error:
                need(str(error) == reason, 'joining process unrelated composition negative: '+name+': '+str(error))
            else: raise ValueError('joining process accepted composition negative: '+name)
        result = dict(case=name, status='REJECTED', reason=reason); results.append(result)
        if progress: progress(result)
    need(run.h.inventory(raw) == before, 'joining process composition negatives changed original')
    return dict(original=original, negatives=results, originalPreserved=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('raw')
    parser.add_argument('--case', required=True, choices=run.CASES); parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args()
    result = qualify(args.raw, args.case, progress=lambda v: print(json.dumps(v), file=sys.stderr, flush=True)) if args.qualify else validate(args.raw, args.case)
    print(json.dumps(result, sort_keys=True))
