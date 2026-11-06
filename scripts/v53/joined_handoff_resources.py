"""Bind the original learner-to-voter handoff to one continuous resource pool.

Physical projection is derived from the native required-four history, never from
resource totals or the producer's retirement receipt. This covers the custody,
deletion and native-owner handoff, not whole-runtime maximum pressure or death.
"""
from collections import Counter
from pathlib import Path

from . import resource_transitions as t
from . import required_four_physical as physical

need = t.need
CUSTODY = tuple('LEARNER_CUSTODY_'+v for v in (
    'DIRECTORY_FORCED','CREATED','PREFIX_WRITTEN','WRITTEN','FORCED',
    'PARENT_FORCED','BEFORE_TRANSFER','TRANSFERRED'))
POINTS = (
    ('custody', 'LEARNER_CUSTODY_BEFORE_TRANSFER'),
    ('custody', 'LEARNER_CUSTODY_TRANSFERRED'),
    ('joined-admission', 'LEARNER_JOINED_ADMISSION_FORCED'),
    ('retirement', 'JOINED_RETIREMENT_DECISION_FORCED'),
    ('retirement', 'JOINED_RETIREMENT_COMPLETE'),
    ('initial-owner', 'JOINED_NATIVE_RECORD_FORCED'),
    ('initial-owner', 'JOINED_NATIVE_DECISION_FORCED'),
    ('initial-owner', 'JOINED_NATIVE_TRANSFERRED'),
    ('initial-owner', 'CURRENT_VALIDATED'),
    ('initial-owner', 'ACCEPT_ACTIVE_PARENT_FORCED'),
)


def project(handoff):
    """Input is an independently checked physical Retirement projection."""
    r = physical.init.retirement
    return dict(node=handoff.owner.replay.joining,
                predecessor=r.reservations(handoff.owner),
                native=r.native_storage(handoff.owner.installed, handoff.expected),
                deletions=len(handoff.removed))


def derive(root):
    """Replay original prefix, placement and retirement before deriving charges.

    Complete continuation/network/ledger admission remains a mandatory caller
    precondition. The special required-four topology must not use a 3-ADD seed.
    """
    p = physical; root = Path(root)
    events = p.s.collection.read_json(root, 'events.json', p.s.collection.EVENT_BYTES)
    captures = p.p.Captures(root, events, voters=p.semantic.OLD_LIVE)
    retirements = p.Retirements(root, events, voters=(*p.semantic.OLD, 'node-6'))
    model = p.s.Replay(root, size=5, kind='REPLACE', required_four=True)
    for index in range(1, 12): model.step(index)
    model.publication_receipts = p.c.t.publication.CheckpointReceipts(root, model)
    history = p.covering.History(root, model, captures, retirements); history.run()
    owner = p.init.placement.Placement(root, history); owner.run()
    handoff = p.init.retirement.Retirement(root, owner); handoff.run()
    return project(handoff)


def positions(events, node):
    points = []
    for scope, name in POINTS:
        found = [i for i, v in enumerate(events) if v.get('event') == name and v.get('scope') == scope]
        need(len(found) == 1 and events[found[0]].get('node') == node,
             'joined resources unique original lifecycle point')
        points.append(found[0])
    need(points == sorted(set(points)), 'joined resources force and handoff order')
    return points


def amounts(rows):
    return Counter((v['unit'], v['bytes']) for v in rows)


def retirement_order(count):
    def writes(file):
        return ['JOINED_RETIREMENT_'+v+':'+file for v in (
            'CREATED','PREFIX_WRITTEN','WRITTEN','FORCED','PARENT_FORCED')]
    deleted = ['JOINED_RETIREMENT_'+v+':'+str(i) for i in range(count)
               for v in ('BEFORE_DELETE','DELETED','DELETE_FORCED')]
    return (['JOINED_RETIREMENT_DIRECTORY_FORCED'] + writes('retirement.json') +
            ['JOINED_RETIREMENT_DECISION_FORCED'] + deleted + writes('retired.json') +
            ['JOINED_RETIREMENT_COMPLETE'])


def replay(plan, events, traces, boundaries):
    """Conditional accounting binding, following full original admission."""
    node = plan['node']; points = positions(events, node)
    need(node in traces and len(events) == len(boundaries), 'joined resources complete observations')
    trace = traces[node]; t.replay(trace); rows = trace['changes']
    need(tuple(trace[k] for k in ('metadataLimit', 'stagingLimit', 'queueLimit')) ==
         (384*t.MIB, 512*t.MIB, 64*t.MIB), 'joined resources original limits')
    previous = -1
    for at, (event, point) in enumerate(zip(events, boundaries)):
        if event.get('node') != node: continue
        sequence = point['sequence']
        need(point['node'] == node and type(point['eventIndex']) is int and point['eventIndex'] == at and
             type(sequence) is int and previous <= sequence < len(rows) and sequence >= 0,
             'joined resources exact original checkpoint')
        t.same_usage(point['usage'], rows[sequence]['usage']); previous = sequence
    seq = [boundaries[i]['sequence'] for i in points]
    need(seq == sorted(seq), 'joined resources monotonic lifecycle')
    custody_points = [(i,v) for i,v in enumerate(events) if v.get('scope')=='custody']
    need(all(v.get('node')==node for _,v in custody_points) and
         tuple(v['event'] for _,v in custody_points)==CUSTODY,
         'joined resources original custody force order')
    need(all(boundaries[i]['sequence']==seq[0] for i,_ in custody_points[:-1]),
         'joined resources custody ownership through force')
    # Derive every deletion callback from the checked physical deletion list.
    retirement = [(i,v) for i,v in enumerate(events) if v.get('scope')=='retirement']
    need(all(v.get('node')==node for _,v in retirement) and
         [v['event'] for _,v in retirement]==retirement_order(plan['deletions']),
         'joined resources exact original deletion window')
    deletion_events = [(i, v['event']) for i,v in retirement if v['event'].startswith((
        'JOINED_RETIREMENT_BEFORE_DELETE:', 'JOINED_RETIREMENT_DELETED:', 'JOINED_RETIREMENT_DELETE_FORCED:'))]
    expected = [prefix+str(i) for i in range(plan['deletions']) for prefix in (
        'JOINED_RETIREMENT_BEFORE_DELETE:', 'JOINED_RETIREMENT_DELETED:', 'JOINED_RETIREMENT_DELETE_FORCED:')]
    need(expected and [v for _, v in deletion_events] == expected and
         all(points[3] < i < points[4] for i, _ in deletion_events),
         'joined resources exact original deletion window')
    state = {}; states = {}
    for row in rows[:seq[-1]+1]:
        for v in row['removed']: state.pop(t.key(v))
        for v in row['added']: state[t.key(v)] = v
        if row['sequence'] in seq: states[row['sequence']] = dict(state)
    old = states[seq[0]]; custody = states[seq[1]]; native = states[seq[7]]
    need(amounts(old.values()) == amounts(plan['predecessor']) and
         all(not v['claimSource'] for v in old.values()), 'joined resources exact predecessor extents')
    need(amounts(custody.values()) == amounts(plan['predecessor']) and
         {v['owner'] for v in custody.values()} == {'learner-custody-'+str(i) for i in range(len(custody))} and
         all(not v['claimSource'] for v in custody.values()), 'joined resources exact custody extents')
    target = sorted((dict(v, claimSource='') for v in plan['native']), key=t.order_key)
    need(sorted(native.values(), key=t.order_key) == target, 'joined resources exact native extents')
    # A release/reacquire with the same byte totals is still a broken lifetime.
    # Exactly one mutation performs each handoff, after its forced decision.
    def atomic(first, last, event, before, after):
        changes = rows[first+1:last+1]
        need(len(changes) == 1 and changes[0]['event'] == event and
             changes[0]['removed'] == sorted(before.values(), key=t.order_key) and
             changes[0]['added'] == sorted(after.values(), key=t.order_key),
             'joined resources atomic '+event.lower()+' after force')
    atomic(seq[0], seq[1], 'TRANSFER', old, custody)
    need(seq[1] == seq[6], 'joined resources continuous predecessor ownership')
    atomic(seq[6], seq[7], 'REPLACE', custody, native)
    need(seq[7] == seq[9], 'joined resources native ownership through open')
    # All deletion and force callbacks use the same original custody charges.
    need(all(boundaries[i]['sequence'] == seq[1] for i in range(points[1], points[6]+1)
             if events[i].get('node') == node), 'joined resources continuous deletion checkpoints')
    need(sum(row['event'] == 'TRANSFER' for row in rows) == 1 and
         sum(row['event'] == 'REPLACE' for row in rows) == 1,
         'joined resources unbound storage handoff')
    return dict(status='PASS', scope='required-four-original-learner-native-handoff', node=node,
                predecessorLeases=len(old), nativeLeases=len(native), deletedMembers=plan['deletions'],
                custodySequence=seq[1], nativeSequence=seq[7],
                predecessorUsage=rows[seq[1]]['usage'], nativeUsage=rows[seq[7]]['usage'],
                lifecyclePoints=len(points), deletionCallbacks=len(deletion_events),
                continuousHandoffQualified=True, observedAccountingClosed=True,
                explicitJoiningCloseIntervalsQualified=False, physicalPeakQualified=False,
                wholeRuntimeResourcesQualified=False, processDeathQualified=False,
                finalSourceCohortQualified=False, phase3Complete=False)
