"""Continuous allocator forces and promise bindings in one original REPLACE.

The entire original storage/network/retention chain runs first. This focused
gate does not turn callback-name coverage into complete physical qualification.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_same_view_learner as prior

a, f, disk, need, sha = prior.a, prior.f, prior.disk, prior.need, prior.sha
WRITES = ['ALLOCATOR_' + p for p in ('BEFORE_WRITE', 'CREATED', 'WRITTEN', 'FORCED',
                                     'RENAMED', 'DIRECTORY_FORCED', 'BEFORE_RETURN')]
PROMISE = ['PROMISE_BEFORE_WRITE', 'PROMISE_WRITTEN', 'PROMISE_FORCED']


def allocations(events, owners, joining):
    pending, result = {}, []
    for at, row in enumerate(events):
        if not row['event'].startswith('ALLOCATOR_'): continue
        need(row['event'] in WRITES, 'joining ballot unsupported allocator event')
        node = row.get('node')
        need(node in owners and set(row) == ({'node', 'scope', 'event'} if node == joining else {'node', 'event'}),
             'joining ballot allocator event shape')
        need(row.get('scope') in (('retaining-owner', 'repeated-basis-owner', 'continuation-owner') if node == joining else (None,)),
             'joining ballot allocator owner scope')
        held = pending.setdefault(node, [])
        need(row['event'] == WRITES[len(held)] and (not held or row.get('scope') == held[0][1].get('scope')),
             'joining ballot exact allocator force order')
        held.append((at, row))
        if len(held) == len(WRITES):
            result.append(dict(node=node, scope=row.get('scope'), start=held[0][0], end=at))
            del pending[node]
    need(not pending, 'joining ballot incomplete allocation')
    return result


class State:
    def __init__(self, root):
        self.root = root; self.counters = {}; self.observed = {}; self.steps = []; self.comparisons = 0

    def seed(self, node, counter, observed):
        need(node not in self.counters and type(counter) is int and type(observed) is int and
             0 <= counter <= 2**63-2 and 0 <= observed <= 2**63-2, 'joining ballot original seed')
        self.counters[node] = counter; self.observed[node] = observed

    def promise(self, node, counter):
        need(node in self.counters and type(counter) is int and self.observed[node] <= counter <= 2**63-2,
             'joining ballot nonmonotonic promise')
        self.observed[node] = counter

    def reserve(self, tx):
        node = tx['node']; need(node in self.counters, 'joining ballot allocation before ownership')
        before = self.counters[node]; observed = self.observed[node]; counter = max(before, observed) + 1
        need(counter <= 2**63-2, 'joining ballot allocation exhausted')
        self.counters[node] = counter
        self.steps.append(dict(tx, before=before, observed=observed, counter=counter))

    def compare(self, node, raw, label):
        expected = f.encode('records', 'ALLOCATOR', dict(root=self.root, node=node, counter=self.counters[node]))
        need(raw == expected, 'joining ballot exact continuous allocator: ' + label + ': ' + node)
        self.comparisons += 1


class Replay:
    def __init__(self, root):
        self.root = Path(root); self.base = a.Replay(root); self.model = self.base.model; self.events = self.base.events
        self.owners = (*self.model.old, self.model.joining)
        self.tx = allocations(self.events, self.owners, self.model.joining)
        self.captures = a.physical.p.captures.collect(root, self.events)
        self.state = State(self.model.root); self.used = set(); self.promise_points = set(); self.self_grants = 0

    def one(self, node, name, scope):
        points = [i for i, v in enumerate(self.events) if v.get('node') == node and v['event'] == name and v.get('scope') == scope]
        need(len(points) == 1, 'joining ballot exact lifecycle boundary: ' + name)
        return points[0]

    def promise(self, node, scope, lower, upper, ballot, actions):
        rows = [(i, v) for i, v in enumerate(self.events) if lower < i < upper and v.get('node') == node and v['event'] in PROMISE]
        need([v['event'] for _, v in rows] == PROMISE and
             all(v == dict(node=node, event=v['event'], **({'scope': scope} if scope else {})) for _, v in rows),
             'joining ballot exact promise force order')
        need(not self.promise_points.intersection(i for i, _ in rows), 'joining ballot reused promise forces')
        self.promise_points.update(i for i, _ in rows)
        actions.append((rows[-1][0], 'promise', (node, ballot['counter'])))

    def original(self, node, path, label):
        self.state.compare(node, disk.inventory(self.root/path)['allocator.gsr'], label)

    def bind_grant(self, cap, actions):
        node = cap['node']; scope = None if cap['scope'] == 'network-owner' else cap['scope']
        starts = [i for i, v in enumerate(self.events[:cap['returnEvent']]) if v.get('node') == node and
                  v.get('scope') == scope and v['event'] == 'CURRENT_BEFORE_CAPTURE']
        need(starts, 'joining ballot capture start'); start = starts[-1]
        self.promise(node, scope, start, cap['returnEvent'], cap['ballot'], actions)
        if node == cap['ballot']['proposer']:
            boundaries = [i for i, v in enumerate(self.events[:start]) if v.get('node') == node and
                          v.get('scope') == scope and v['event'] == 'CURRENT_DIRECTORY_FORCED']
            boundaries += [v['capturedEvent'] for v in self.captures if v['node'] == node and v['capturedEvent'] < start]
            need(boundaries, 'joining ballot original allocation lower bound')
            candidates = [v for v in self.tx if v['node'] == node and v['scope'] == scope and max(boundaries) < v['start'] < v['end'] < start]
            need(len(candidates) == 1 and candidates[0]['start'] not in self.used,
                 'joining ballot exact allocation before local grant')
            self.used.add(candidates[0]['start']); self.self_grants += 1
            actions.append((start, 'grant', (node, cap['ballot'])))
        actions.append((cap['capturedEvent'], 'original', (node, cap['capture']+'/replica', 'grant')))

    def grant(self, node, ballot):
        identity = a.n.s.catalog.identities(self.model.states[-1]['identities'])[node]
        need(ballot == dict(counter=self.state.counters[node], proposer=node, incarnation=identity['storage']),
             'joining ballot local grant uses reserved counter')

    def run(self):
        initial = a.physical.t.selected.initialize(self.model.original)
        for node, files in initial.items():
            value = f.decode(files['allocator.gsr'], 'records', 'ALLOCATOR')
            journal = disk.journal(files['grants.gsr'], self.model.root, node)
            observed = max([0, *[v['ballot']['counter'] for _, _, v in journal]])
            self.state.seed(node, value['counter'], observed); self.original(node, 'before-network/'+node, 'bootstrap')
        joining = self.model.joining; actions = []
        # Placement derives this adopted allocator from the original JOINT
        # certificate; it is not another reservation and does not grant a vote.
        joined = self.one(joining, 'JOINED_NATIVE_TRANSFERRED', 'initial-owner')
        certificate = f.decode(self.model.phases[8]['CERTIFICATE'], 'records', 'CERTIFICATE')
        counter = certificate['ballot']['counter']
        actions.append((joined, 'seed', (joining, counter, counter)))
        actions.append((joined, 'original', (joining, 'joining-originals-placed/replica', 'placed')))
        for cap in self.captures: self.bind_grant(cap, actions)
        spare = [v for v in self.tx if v['node'] == joining and v['scope'] == 'repeated-basis-owner']
        need(len(spare) == 1, 'joining ballot one retained unused reservation')
        lower = self.one(joining, 'CURRENT_BEFORE_CAPTURE', 'repeated-basis-owner')
        upper = min(i for i, v in enumerate(self.events) if v.get('node') == joining and v.get('scope') == 'continuation-owner')
        need(lower < spare[0]['start'] < spare[0]['end'] < upper, 'joining ballot retained unused reservation lifetime')
        self.used.add(spare[0]['start'])
        actions.append((spare[0]['end']+0.5, 'original', (joining, 'joining-originals-native/replica', 'unused-reservation')))
        need(self.used == {v['start'] for v in self.tx}, 'joining ballot unbound allocations')
        for tx in self.tx:
            if tx['node'] == joining:
                a.c.owner_lifetime(self.events, joining, tx['scope'], tx['start'], tx['end'])
        actions.extend((v['end'], 'reserve', (v,)) for v in self.tx)
        # The verified newer-authority adoption appends an observation fence.
        # Its promise advances the next allocation even without a local grant.
        start = self.one(joining, 'ADOPTION_INSTALL_VALIDATED', 'continuation-owner')
        end = self.one(joining, 'ADOPTION_INSTALL_FENCED', 'continuation-owner')
        adopted = f.decode(self.model.phases[9]['CERTIFICATE'], 'records', 'CERTIFICATE')
        self.promise(joining, 'continuation-owner', start, end, adopted['ballot'], actions)
        need(self.promise_points == {i for i, v in enumerate(self.events) if v['event'] in PROMISE},
             'joining ballot unbound promise forces')
        for (index, node), points in self.base.phases.items():
            for label, point in [('applied', 'APPLY_BEFORE_RETURN'), ('published', 'PUBLICATION_BEFORE_RETURN')]:
                actions.append((points[point], 'compare', (node, self.model.owner(label, index, node)['allocator.gsr'], label)))
        for own in self.base.windows:
            # The first joining window reuses the later native snapshot. Its
            # ledgers are stable, but its allocator already includes the spare
            # reservation. Compare that snapshot only at the actual burn above.
            if own['start'] >= 0 and self.events[own['start']]['event'] in ('INSTALL_BEFORE_RETURN', 'ADOPTION_INSTALL_BEFORE_RETURN'):
                actions.append((own['start'], 'original', (own['node'], own['path'], 'generation')))
        for _, kind, args in sorted(actions, key=lambda v: v[0]):
            getattr(self.state if kind in ('seed', 'promise', 'reserve', 'compare') else self, kind)(*args)
        for node in self.owners:
            self.original(node, 'joining-originals-stable-cold/replica' if node == joining else 'after-close/'+node, 'cold')
        return dict(status='PASS', scope='one-native-REPLACE-continuous-ballot', reservations=len(self.tx),
                    selfGrants=self.self_grants, unusedReservations=1, forcedPromises=len(self.promise_points)//3,
                    allocatorComparisons=self.state.comparisons, finalCounters=self.state.counters,
                    chainSha256=sha(f.canonical(self.state.steps)), ballotForceQualified=True,
                    sameViewPhysicalQualified=False, completePhysicalQualified=False, phase3Complete=False)


def replay(root): return Replay(root).run()


def validate(root):
    root = Path(root); before = a.n.s.collection.inventory(root); original = prior.validate(root); result = replay(root)
    need(a.n.s.collection.inventory(root) == before, 'joining ballot original changed')
    return dict(status='PARTIAL', precondition=original, ballot=result, ballotForceQualified=True,
                sameViewPhysicalQualified=False, completePhysicalQualified=False, forceAndNetworkQualified=False,
                processDeathQualified=False, phase3Complete=False)


NEGATIVES = {
    'force-missing': 'joining ballot exact allocator force order',
    'rename-before-force': 'joining ballot exact allocator force order',
    'directory-force-missing': 'joining ballot exact allocator force order',
    'duplicate-return': 'joining ballot exact allocator force order',
    'incomplete-write': 'joining ballot incomplete allocation',
    'unknown-allocator-event': 'joining ballot unsupported allocator event',
    'foreign-owner': 'joining ballot allocator event shape',
    'forged-field': 'joining ballot allocator event shape',
    'wrong-joining-scope': 'joining ballot allocator owner scope',
    'reservation-after-grant': 'joining ballot exact allocation before local grant',
    'reservation-before-open': 'joining ballot exact allocation before local grant',
    'extra-local-reservation': 'joining ballot exact allocation before local grant',
    'unbound-reservation': 'joining ballot unbound allocations',
    'unused-before-repeated-read': 'joining ballot retained unused reservation lifetime',
    'unused-after-owner': 'joining ballot retained unused reservation lifetime',
    'promise-write-missing': 'joining ballot exact promise force order',
    'promise-force-before-write': 'joining ballot exact promise force order',
    'promise-wrong-scope': 'joining ballot exact promise force order',
    'unbound-promise': 'joining ballot unbound promise forces',
}


def relevant(row): return row['event'].startswith('ALLOCATOR_') or row['event'] in PROMISE


def mutate(root, name):
    need(name in NEGATIVES, 'joining ballot unknown negative'); root = Path(root)
    events = a.n.s.collection.read_json(root, 'events.json', a.n.s.collection.EVENT_BYTES)
    tx = allocations(events, ('node-1', 'node-2', 'node-3', 'node-4'), 'node-4')
    def values(t): return [v for v in events[t['start']:t['end']+1] if v.get('node') == t['node'] and v['event'] in WRITES]
    def move(rows, target, after=False):
        ids = {id(v) for v in rows}; events[:] = [v for v in events if id(v) not in ids]
        at = next(i for i, v in enumerate(events) if v is target)+int(after); events[at:at] = rows
    def remove(row): events[:] = [v for v in events if v is not row]
    first = values(tx[0]); spare = values(next(v for v in tx if v['scope'] == 'repeated-basis-owner'))
    if name == 'force-missing': remove(first[3])
    elif name == 'rename-before-force': move([first[4]], first[3])
    elif name == 'directory-force-missing': remove(first[5])
    elif name == 'duplicate-return': move([dict(first[-1])], first[-1])
    elif name == 'incomplete-write': remove(events[tx[-1]['end']])
    elif name == 'unknown-allocator-event': events.append(dict(node='node-1', event='ALLOCATOR_IGNORED'))
    elif name == 'foreign-owner': first[0]['node'] = 'node-9'
    elif name == 'forged-field': first[0]['counter'] = 2
    elif name == 'wrong-joining-scope':
        for v in spare: v['scope'] = 'initial-owner'
    elif name == 'reservation-after-grant': move(first, next(v for v in events if v['event'] == 'GRANT_BEFORE_RETURN'), True)
    elif name == 'reservation-before-open': move(first, events[0])
    elif name == 'extra-local-reservation': move([dict(v) for v in first], first[0])
    elif name == 'unbound-reservation': events.extend(dict(node='node-2', event=p) for p in WRITES)
    elif name.startswith('unused-'):
        scope = 'repeated-basis-owner' if name == 'unused-before-repeated-read' else 'continuation-owner'
        target = next(v for v in events if v.get('scope') == scope and v['event'] == 'CURRENT_BEFORE_CAPTURE')
        move(spare, target, name == 'unused-after-owner')
    elif name == 'unbound-promise': events.extend(dict(node='node-2', event=p) for p in PROMISE)
    else:
        rows = [next(v for v in events if v.get('node') == 'node-1' and v['event'] == p) for p in PROMISE]
        if name == 'promise-write-missing': remove(rows[1])
        elif name == 'promise-force-before-write': move([rows[2]], rows[1])
        else: rows[0]['scope'] = 'foreign-owner'
    (root/'events.json').write_bytes(f.canonical(events))


def negative(root, before, name):
    with tempfile.TemporaryDirectory(prefix='v53-same-view-ballot-') as temp:
        copied = Path(temp)/'raw'; shutil.copytree(root, copied); mutate(copied, name)
        after = a.n.s.collection.inventory(copied); protected = lambda v: {k: x for k, x in v['files'].items() if k != 'events.json'}
        need(protected(before) == protected(after) and before['directories'] == after['directories'], 'joining ballot negative changed original files')
        other = lambda p: [v for v in a.n.s.collection.read_json(p, 'events.json', a.n.s.collection.EVENT_BYTES) if not relevant(v)]
        need(other(Path(root)) == other(copied), 'joining ballot negative changed other observations')
        try: replay(copied)
        except ValueError as error: need(str(error) == NEGATIVES[name], 'joining ballot unrelated negative: '+name+': '+str(error))
        else: raise ValueError('joining ballot accepted mutation: '+name)
    return dict(case=name, status='REJECTED', reason=NEGATIVES[name], mutationScope='allocator-and-promise-callbacks-only', originalFilesAndOtherObservationsUnchanged=True)


def qualify(root, *, workers=1, progress=None):
    need(type(workers) is int and 1 <= workers <= 4, 'joining ballot replay workers')
    root = Path(root); original = validate(root); before = a.n.s.collection.inventory(root); results = []
    if progress: progress(dict(stage='original', status='PASS', negativeCases=len(NEGATIVES)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(negative, root, before, name): name for name in NEGATIVES}
        for task in as_completed(tasks):
            try: result = task.result()
            except Exception as error: result = dict(case=tasks[task], status='FAIL', failure=str(error), type=type(error).__name__)
            results.append(result)
            if progress: progress(dict(result, completed=len(results), total=len(NEGATIVES)))
    need(a.n.s.collection.inventory(root) == before, 'joining ballot qualification changed original')
    need(all(v['status'] == 'REJECTED' for v in results), 'joining ballot negative matrix failed')
    return dict(original=original, negatives=sorted(results, key=lambda v: v['case']), mutatedPrerequisiteReplayed=False,
                negativePrecondition='full original learner/authority chain; unchanged original files, wire and other observations')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true')
    parser.add_argument('--workers', type=int, default=1); args = parser.parse_args()
    result = qualify(args.root, workers=args.workers, progress=lambda v: print(json.dumps(v), file=sys.stderr, flush=True)) if args.qualify else validate(args.root)
    print(json.dumps(result, sort_keys=True))
