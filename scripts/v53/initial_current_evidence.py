"""First successful opens of physically derived original network voters.

The caller validates before-network bytes and obtains the voter set from the
original model first. This is not a generic CURRENT callback scanner: later
installations, joined owners and interrupted process opens have separate owners.
"""
from .current_generation_evidence import OPEN
from .membership_model import need

RESEAL = {'LEARNER_RETENTION_RECOVERY_ACTIVE_FORCED', 'RETENTION_RECOVERY_ACTIVE_FORCED'}
ACTIVITY = {'ALLOCATOR_BEFORE_WRITE', 'CURRENT_BEFORE_CAPTURE',
            'BEFORE_REQUEST_WRITE', 'AFTER_REQUEST_READ', 'BEFORE_RESPONSE_WRITE', 'AFTER_RESPONSE_READ'}
ORDER_ERROR = 'initial current complete original open'
READY_ERROR = 'initial current all voters before activity'


def validate(events, nodes):
    nodes = tuple(nodes)
    need(nodes and all(type(n) is str and n for n in nodes) and len(set(nodes)) == len(nodes),
         'initial current original voters')
    ends = []
    for node in nodes:
        # Native opening constructs CURRENT before resealing either initialized
        # retention ledger. Use that independently owned boundary, not a force
        # marker whose omission could widen the interval into a later reload.
        boundary = next((i for i, v in enumerate(events)
                         if v.get('node') == node and v.get('event') in RESEAL), None)
        need(boundary is not None, ORDER_ERROR)
        prefix = [(i, v) for i, v in enumerate(events[:boundary]) if v.get('node') == node]
        need([v for _, v in prefix] == [dict(node=node, event=point) for point in OPEN], ORDER_ERROR)
        ends.append(prefix[-1][0])
    activity = [i for i, v in enumerate(events) if v.get('event') in ACTIVITY or
                type(v.get('event')) is str and v['event'].startswith('NETWORK_')]
    need(activity and max(ends) < min(activity), READY_ERROR)
    return dict(initialVoters=len(nodes), currentCallbacks=len(nodes)*len(OPEN))


SPECS = {**{'missing-'+point.lower().removeprefix('current_'): point for point in OPEN},
         'missing-block': None, 'duplicate-force': None, 'reordered-force': None,
         'foreign-scope': None, 'extra-field': None, 'unknown-current': None,
         'after-reseal': None}
NEGATIVES = {'initial-current-'+role+'-'+name: ORDER_ERROR for role in ('first', 'last') for name in SPECS}


def mutate(events, name):
    need(name in NEGATIVES, 'initial current unknown mutation')
    role, suffix = name.removeprefix('initial-current-').split('-', 1)
    # Before-network owners are the only unscoped initial opens preceding any
    # protocol activity. Choose first and last original voter, never a later
    # joined owner or a later open of the same voter.
    boundary = next(i for i, v in enumerate(events) if v.get('event') in ACTIVITY or
                    type(v.get('event')) is str and v['event'].startswith('NETWORK_'))
    nodes = sorted({v['node'] for v in events[:boundary] if v.get('event') == OPEN[0] and 'scope' not in v})
    node = nodes[0 if role == 'first' else -1]
    positions = [i for i, v in enumerate(events[:boundary]) if v.get('node') == node and v.get('event') in OPEN]
    need([events[i]['event'] for i in positions] == list(OPEN), 'initial current mutation original block')
    at = positions[1]
    if suffix.startswith('missing-'):
        if suffix == 'missing-block':
            for i in reversed(positions): events.pop(i)
        else: events.pop(next(i for i in positions if events[i]['event'] == SPECS[suffix]))
    elif suffix == 'duplicate-force': events.insert(at, dict(events[at]))
    elif suffix == 'reordered-force': events[at], events[positions[2]] = events[positions[2]], events[at]
    elif suffix == 'foreign-scope': events[at]['scope'] = 'foreign-owner'
    elif suffix == 'extra-field': events[at]['claimedForce'] = True
    elif suffix == 'unknown-current': events.insert(at, dict(node=node, event='CURRENT_UNKNOWN'))
    else:
        row = events.pop(at)
        after = next(i for i, v in enumerate(events) if v.get('node') == node and v.get('event') in RESEAL)
        events.insert(after+1, row)
