"""Original process-bound export, control and retention authority replay."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_process_composition as physical
from . import joining_profile_export_evidence as exports
from . import joining_profile_control_evidence as control
from . import joining_profile_maintenance_evidence as maintenance
from . import joining_profile_peer_evidence as peer
from . import joining_same_view_future as future
from . import joining_same_view_learner as learner
from . import joining_same_view_ballot as ballot

need, f, run = physical.need, physical.f, physical.run
c, e = control.c, exports.e
CONTROL = 'JOINING_PROCESS_CONTROL'


def observations(raw, case):
    """Include original child control messages as diagnostic anchors only.

    They are not storage/transport callbacks and confer no protocol authority.
    Keeping them in the same projection lets later mutations/replay preserve
    their actual order without reusing stale numeric event offsets.
    """
    observed = physical.observations(raw, case); events = []; positions = []
    for at, row in enumerate(run.lines(Path(raw)/'process-trace.jsonl')):
        if row['origin'] == 'parent': value = row['value']
        elif row['value']['kind'] == 'WIRE': continue
        elif row['value']['kind'] == 'EVENT': value = row['value']['value']
        else: value = dict(event=CONTROL, origin=row['origin'], **row['value'])
        events.append(value); positions.append(dict(trace=at, origin=row['origin']))
    need([v for v in events if v['event'] != CONTROL] == observed['events'], 'joining process authority exact event projection')
    need(len(events) <= physical.s.collection.HISTORY_ROWS, 'joining process authority observation capacity')
    return dict(observed, events=events, positions=positions)


def controls(events, observed):
    expected = [v for v in observed['events'] if v['event'] == CONTROL]
    need(len(expected) == 5 and [v['kind'] for v in expected] == ['STARTED', 'CUT', 'STARTED', 'READY', 'CLOSED'] and
         expected[0]['origin'] == expected[1]['origin'] in ('halt', 'kill') and
         all(v['origin'] == 'resume' for v in expected[2:]), 'joining process original control catalogue')
    actual = [(i, v) for i, v in enumerate(events) if v['event'] == CONTROL]
    need(f.canonical([v for _, v in actual]) == f.canonical(expected), 'joining process original control anchors')
    result = {}
    for at, row in actual: result.setdefault(row['origin'], {})[row['kind']] = at
    return result


def transport_lifetimes(events, anchors, case):
    """A constructed endpoint cannot precede its original owner-open return."""
    joining = physical.topology(run.selected(case)['profile'])[3][-1]
    for mode in (run.selected(case)['mode'], 'resume'):
        scope = 'initialization-'+mode; start = anchors[mode]['STARTED']
        end = anchors[mode]['CLOSED' if mode == 'resume' else 'CUT']
        opened = [i for i, row in enumerate(events) if row.get('scope') == scope and row.get('node') == joining and
                  row['event'] == 'FIXTURE_OPEN_RETURNED']
        need(len(opened) == 1 and start < opened[0] < end, 'joining process original transport owner open')
        for at, row in enumerate(events):
            if row.get('scope') == scope and row['event'] in physical.TRANSPORT:
                need(row.get('node') == joining and opened[0] < at < end, 'joining process original endpoint lifetime')


def initialization_point(events, case):
    """The original resumed transaction's last durable completion boundary."""
    point = run.selected(case)['point']
    completed = run.POINTS.index(point) >= run.POINTS.index('JOINING_RETENTION_DONE_RENAMED')
    wanted = 'JOINING_RETENTION_DONE_RECOVERY_PARENT_FORCED' if completed else 'JOINING_RETENTION_BEFORE_RETURN'
    joining = physical.topology(run.selected(case)['profile'])[3][-1]
    points = [i for i, row in enumerate(events) if row.get('node') == joining and
              row.get('scope') == 'initialization-resume' and row['event'] == wanted]
    need(len(points) == 1, 'joining process original resumed initialization boundary')
    return points[0]


def lifetime(reader, scope, lower, upper, *, ready=False):
    """Actual child controls bound endpoint authority, including its close."""
    aliases = {'initial-endpoint': 'initial-owner', 'continuation-endpoint': 'continuation-owner'}
    mode = run.selected(reader.case)['mode']; child = {'initialization-'+v: v for v in (mode, 'resume')}
    if scope in aliases:
        need(not ready or scope == 'continuation-endpoint', 'joining process completion before child recovery')
        c.owner_lifetime(reader.events, reader.model.joining, aliases[scope], lower, upper)
        return
    need(scope in child, 'joining process export original endpoint')
    origin = child[scope]; anchors = reader.controls[origin]
    need(0 <= lower <= upper < len(reader.events), 'joining process export original positions')
    begin = anchors['STARTED']; end = anchors['CLOSED' if origin == 'resume' else 'CUT']
    if ready:
        need(origin == 'resume', 'joining process completion before child recovery'); begin = anchors['READY']
    need(reader.events[lower].get('scope') == reader.events[upper].get('scope') == scope and begin < lower <= upper < end,
         'joining process original endpoint lifetime')
    c.owner_lifetime(reader.events, reader.model.joining, scope, lower, upper)


class Control(control.Replay):
    def __init__(self, root, case, observed):
        self.case, self.observed = case, observed
        super().__init__(root, run.selected(case)['profile'])
        self.controls = controls(self.events, observed)
        transport_lifetimes(self.events, self.controls, case)
        self.initialized = initialization_point(self.events, case)
        interrupted = run.POINTS.index(run.selected(case)['point']) < run.POINTS.index('JOINING_RETENTION_SEED_WRITTEN')
        pulls = 2 if interrupted else 1
        self.expected_controls = dict(self.expected_controls, preparation=pulls, retention=len(self.expected_confirmations)*pulls)

    def completion(self, values, own):
        q = c.initial(values, own); cap = own['packet']['capsule']; c.joint(own, q['recipient'], exporter=True)
        first = values[0]['offer']; last = values[-1]['commit']['offered']
        need(q['sender']['node'] in cap['cut']['view']['old'], 'joining control completion original old reader')
        need(self.initialized < first['received'] <= last < e.next_promise(self.events, own['node'], first['received'], own['end']),
             'joining control completion initialization/fence')
        scope = self.events[first['received']].get('scope')
        lifetime(self, scope, first['received'], last, ready=True)
        if scope == 'initialization-resume':
            points = ['LEARNER_RETENTION_RECOVERY_PARENT_FORCED', 'RETENTION_RECOVERY_PARENT_FORCED', 'FUTURE_RETENTION_RECOVERY_PARENT_FORCED']
            c.n.interval(self.events, own['node'], self.initialized, first['received'], points,
                         'joining process completion original ledger recovery', scope)
        else:
            recovered = [i for i, v in enumerate(self.events) if v.get('node') == own['node'] and
                         v.get('scope') == 'continuation-owner' and v['event'] == 'ACCEPT_ACTIVE_PARENT_FORCED']
            need(len(recovered) == 1 and recovered[0] < first['received'], 'joining control completion ledger recovery')
        c.exact(values, c.alias('joining-completion', cap, q['recipient']),
                f.canonical(dict(schema='gse-v53-joining-completion/1.3', root=self.model.root, cut=cap['cut'], joining=q['recipient'])))


def content(reader):
    result = e.authorize_contents(reader.model, reader.events, reader.contents, reader.windows, reader.sources, reader.records)
    if reader.abandoned_offers: result['abandonedGenerationOffers'] = reader.abandoned_offers
    bound = 0
    for values in reader.groups:
        first, last = values[0]['offer'], values[-1]['commit']
        if first['request']['recipient']['node'] != reader.model.joining or values[0]['raw'] == e.pending_ack(reader.model): continue
        lifetime(reader, reader.events[first['received']].get('scope'), first['received'], last['offered']); bound += 1
    result['joiningExportLifetimes'] = bound
    return result


class ProcessLedgers:
    def lifetimes(self):
        # The initial parent and interrupted child never opened active native
        # ledgers. Every remaining open must reseal all original ledger bytes.
        scopes = ('initialization-resume', 'process-retention-observe', 'retaining-owner',
                  'repeated-basis-owner', 'continuation-owner', 'stable-cold-owner')
        return [(node, None) for node in self.model.old]+[(self.model.joining, scope) for scope in scopes]

    def initialization_point(self):
        return initialization_point(self.events, self.case)


class Peers(ProcessLedgers, peer.Replay):
    def __init__(self, root, case):
        self.case = case; super().__init__(root, run.selected(case)['profile'])


class Future(ProcessLedgers, future.Replay):
    def __init__(self, root, case):
        self.case = case
        super().__init__(root, base=maintenance.Replay(root, run.selected(case)['profile']))

    def reopen_boundary(self, node, scope, at, order, rows):
        incomplete = run.POINTS.index(run.selected(self.case)['point']) < run.POINTS.index('JOINING_RETENTION_SEED_WRITTEN')
        if scope != 'initialization-resume' or not incomplete:
            return super().reopen_boundary(node, scope, at, order, rows)
        required = ['ACCEPT_ACTIVE_FORCED', 'ACCEPT_ACTIVE_PARENT_FORCED', 'FIXTURE_OPEN_RETURNED',
                    'INCOMPLETE_NATIVE_USES_REFUSED']
        positions = [[i for i, point in rows if point == name] for name in required]
        need(node == self.model.joining and all(len(v) == 1 for v in positions),
             'joining process incomplete owner native refusal')
        points = [v[0] for v in positions]+[self.initialization_point(), order[1], at]
        need(all(a < b for a, b in zip(points, points[1:])), 'joining process incomplete owner recovery order')


class Learner(ProcessLedgers, learner.Replay):
    def __init__(self, root, case):
        self.case = case
        super().__init__(root, base=maintenance.Replay(root, run.selected(case)['profile']))


def coverage(controlled, counts, exported):
    need(controlled['observedCommittedContents'] == counts['committedTransfers'] and
         controlled['observedContentSessions'] == exports.abandoned.content_sessions(counts, exported),
         'joining process complete export coverage')


def replay(root, case, observed, prior):
    reader = Control(root, case, observed); exported = content(reader); controlled = reader.run(exported)
    coverage(controlled, prior['transfers'], exported)
    maintained = maintenance.Replay(root, run.selected(case)['profile']).run()
    peers = Peers(root, case).run(); futures = Future(root, case).run(); learned = Learner(root, case); learners = learned.run()
    ballots = ballot.Replay(root, base=maintenance.Replay(root, run.selected(case)['profile'])).run()
    return dict(exports=exported, controls=controlled, maintenance=maintained,
                peers=peers, future=futures, learner=learners, ballots=ballots,
                joiningLearnerWrites=sum(v['node'] == reader.model.joining for v in learned.steps))


def validate(raw, case):
    raw = Path(raw); before = run.h.inventory(raw); prior = physical.validate(raw, case)
    observed = observations(raw, case)
    with physical.view(raw, observed) as copied: result = replay(copied, case, observed, prior)
    need(run.h.inventory(raw) == before, 'joining process authority changed original')
    return dict(status='PARTIAL', scope='original-joining-process-export-control-and-maintenance', case=case,
                precondition=prior, **result, exportControlAuthorityVerified=True, maintenanceAuthorityVerified=True,
                continuousLedgersQualified=True, ballotCompositionVerified=True, processDeathQualified=False, phase3Complete=False)


MODULES = dict(exports=e, controls=c, maintenance=maintenance, peers=peer.peer, future=future, learner=learner, ballots=ballot)
NEGATIVES = {stage+'/'+name: reason for stage, module in MODULES.items() for name, reason in module.NEGATIVES.items()}
PROCESS_NEGATIVES = {
    'process/missing-control-anchor': 'joining process original control anchors',
    'process/completion-before-ready': 'joining process original endpoint lifetime',
    'process/completion-after-close': 'joining process original endpoint lifetime',
    'process/partial-native-refusal-missing': 'joining process incomplete owner native refusal',
    'process/reseal-old-owner': 'joining peer exact open reseal count',
}
NEGATIVES.update(PROCESS_NEGATIVES)


def negative_plan(original):
    absent = {}
    if original['exports']['boundSessions'].get('pending-joining-checkpoint', 0) == 0:
        absent['exports/pending-after-retain'] = exports.PENDING_ABSENT
    if original['joiningLearnerWrites'] == 0:
        absent['learner/wrong-write-scope'] = 'original continuous learner chain contains no joining-owner write'
    point = run.selected(original['case'])['point']
    if run.POINTS.index(point) >= run.POINTS.index('JOINING_RETENTION_SEED_WRITTEN'):
        absent['process/partial-native-refusal-missing'] = 'original complete seed recovers before native owner open'
    return absent


def context_reader(root, case, anchors, stage):
    if stage in ('exports', 'controls', 'process'): return Control(root, case, anchors)
    if stage == 'maintenance': return maintenance.Replay(root, run.selected(case)['profile'])
    if stage == 'peers': return Peers(root, case)
    if stage == 'future': return Future(root, case)
    if stage == 'learner': return Learner(root, case)
    return ballot.Replay(root, base=maintenance.Replay(root, run.selected(case)['profile']))


def mutate(root, case, anchors, name):
    stage, selector = name.split('/'); reader = context_reader(root, case, anchors, stage)
    if stage != 'process' and name != 'controls/completion-before-initialization':
        MODULES[stage].mutate(root, selector, reader=reader); return
    events = reader.events
    if name == 'controls/completion-before-initialization':
        # Retained DONE may recover without another BEFORE_RETURN callback.
        target = events[reader.initialized]
        values = next(v for v in reader.groups if v[0]['raw'].startswith(b'{') and
                      json.loads(v[0]['raw']).get('schema') == 'gse-v53-joining-completion/1.3')
        # Keep the entire original exchange and owner-open ordering intact;
        # place only its durable initialization boundary after the export.
        offered = events[values[-1]['commit']['offered']]
        events.remove(target); events.insert(events.index(offered)+1, target)
    elif selector == 'missing-control-anchor':
        events.remove(next(v for v in events if v['event'] == CONTROL and v['origin'] == 'resume' and v['kind'] == 'READY'))
    elif selector in ('completion-before-ready', 'completion-after-close'):
        anchor = next(v for v in events if v['event'] == CONTROL and v['origin'] == 'resume' and
                      v['kind'] == ('READY' if selector == 'completion-before-ready' else 'CLOSED'))
        row = next(v for v in reader.rows if reader.events[v['received']].get('scope') == 'initialization-resume')
        target = events[row['offered'] if selector == 'completion-before-ready' else row['received']]
        events.remove(anchor); at = events.index(target)+int(selector == 'completion-before-ready'); events.insert(at, anchor)
    elif selector == 'partial-native-refusal-missing':
        events.remove(next(v for v in events if v.get('scope') == 'initialization-resume' and v['event'] == 'INCOMPLETE_NATIVE_USES_REFUSED'))
    elif selector == 'reseal-old-owner':
        for v in events:
            if v.get('scope') == 'process-retention-observe' and v['event'] in peer.peer.RESEAL: v['scope'] = 'initial-owner'
    (Path(root)/'events.json').write_bytes(f.canonical(events))


def staged(root, case, anchors, target):
    # These callback-only negatives use the same isolation as the existing
    # profile ledger/ballot gates. The complete original has passed first;
    # all other observations and physical bytes are protected below. Replaying
    # an earlier ACK gate after deleting its later-required callback would test
    # that earlier gate instead of the declared continuous-ledger rejection.
    if target in ('future', 'learner', 'ballots'):
        return context_reader(root, case, anchors, target).run()
    reader = Control(root, case, anchors)
    # Valid transport/ACK order is a prerequisite even for mutated exports.
    physical.durable_network(root, case, dict(events=reader.events), reader.model, reader.rows)
    exported = content(reader)
    if target == 'exports' or target == 'controls/completion-closed-owner': return exported
    controlled = reader.run(exported)
    if target == 'controls': return controlled
    maintained = maintenance.Replay(root, run.selected(case)['profile']).run()
    if target == 'maintenance': return maintained
    peers = Peers(root, case).run()
    if target == 'peers' or target == 'process/reseal-old-owner': return peers
    futures = Future(root, case).run()
    if target == 'future' or target == 'process/partial-native-refusal-missing': return futures
    learned = Learner(root, case).run()
    if target == 'learner': return learned
    return ballot.Replay(root, base=maintenance.Replay(root, run.selected(case)['profile'])).run()


def negative(projected, case, anchors, name):
    """Mutation is confined to one disposable same-history observation view."""
    with tempfile.TemporaryDirectory(prefix='v53-process-authority-negative-') as directory:
        copied = Path(directory)/'raw'; shutil.copytree(projected, copied); before = run.h.inventory(copied)
        mutate(copied, case, anchors, name); after = run.h.inventory(copied)
        stage = name.split('/')[0]
        allowed = {'events.json', 'wire.json'} if stage in ('exports', 'controls', 'maintenance') else {'events.json'}
        protected = lambda v: {k: data for k, data in v['files'].items() if k not in allowed}
        need(protected(before) == protected(after) and before['directories'] == after['directories'],
             'joining process authority mutation changed physical inputs')
        if stage in ('future', 'learner', 'ballots'):
            relevant = (lambda v: v['event'].startswith('FUTURE_RETENTION_')) if stage == 'future' else \
                       (lambda v: learner.relevant(v['event'])) if stage == 'learner' else ballot.relevant
            untouched = lambda path: [v for v in physical.s.collection.read_json(Path(path), 'events.json', physical.s.collection.EVENT_BYTES)
                                      if not relevant(v)]
            need(untouched(projected) == untouched(copied), 'joining process authority mutation changed other callbacks')
        target = name if name in PROCESS_NEGATIVES or name == 'controls/completion-closed-owner' else name.split('/')[0]
        try: staged(copied, case, anchors, target)
        except ValueError as error:
            need(str(error) == NEGATIVES[name], 'joining process unrelated authority negative: '+name+': '+str(error))
        else: raise ValueError('joining process accepted authority negative: '+name)
    return dict(case=name, status='REJECTED', reason=NEGATIVES[name])


def qualify(raw, case, *, selected=None, workers=1, progress=None):
    need(type(workers) is int and 1 <= workers <= 3, 'joining process authority replay workers')
    chosen = list(NEGATIVES) if selected is None else selected
    need(type(chosen) is list and chosen and all(type(v) is str and v in NEGATIVES for v in chosen) and len(set(chosen)) == len(chosen),
         'joining process authority negative selection')
    raw = Path(raw); before = run.h.inventory(raw); original = validate(raw, case); absent = negative_plan(original)
    observed = observations(raw, case); results = {}
    anchors = dict(events=[v for v in observed['events'] if v['event'] == CONTROL])
    for name in chosen:
        if name in absent: results[name] = dict(case=name, status='NOT_APPLICABLE', reason=absent[name])
    with physical.view(raw, observed) as projected:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            pending = {pool.submit(negative, projected, case, anchors, name): name for name in chosen if name not in absent}
            for task in as_completed(pending):
                name = pending[task]
                try: result = task.result()
                except Exception as error: result = dict(case=name, status='FAIL', failure=dict(type=type(error).__name__, message=str(error)))
                results[name] = result
                if progress: progress(dict(result, completed=len(results), total=len(chosen)))
    need(run.h.inventory(raw) == before, 'joining process authority qualification changed original')
    success = all(v['status'] != 'FAIL' for v in results.values()); complete = set(chosen) == set(NEGATIVES)
    return dict(status=('PASS' if complete else 'PARTIAL') if success else 'FAIL', original=original,
                negatives=[results[name] for name in chosen], completeNegativeCatalogue=complete and success,
                originalPreserved=True, phase3Complete=False, processDeathQualified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('raw')
    parser.add_argument('--case', required=True, choices=run.CASES); parser.add_argument('--qualify', action='store_true')
    parser.add_argument('--negative', action='append', choices=NEGATIVES); parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args(); need(args.qualify or args.negative is None, 'joining process negative requires qualification')
    result = qualify(args.raw, args.case, selected=args.negative, workers=args.workers,
                     progress=lambda v: print(json.dumps(v), file=sys.stderr, flush=True)) if args.qualify else validate(args.raw, args.case)
    print(json.dumps(result, sort_keys=True)); sys.exit(2 if result['status'] == 'FAIL' else 0)
