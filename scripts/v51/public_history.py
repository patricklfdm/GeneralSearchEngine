"""Bounded exhaustive client-history search; no Java decoder, status or chosen oracle.

The fixture uses uniquely tagged atomic addAll calls and ordered match-all reads.
Pending/indeterminate writes may be omitted or completed once at any point after
invocation, including after an uncertainty response. This is not an unbounded proof.
"""
from .storage_harness import need


def check(history, max_operations=24, max_states=100000):
    need(0 < len(history) <= max_operations, 'history operation bound')
    ids = set()
    active = []
    for op in history:
        need(op['opId'] not in ids, 'duplicate operation identity'); ids.add(op['opId'])
        need(isinstance(op['startNanos'], int) and op['startNanos'] >= 0, 'invocation time')
        end = op.get('endNanos')
        need(end is None or isinstance(end, int) and end >= op['startNanos'], 'response interval')
        outcome = op['outcome']
        need(outcome in ('SUCCESS', 'NOT_SUBMITTED', 'INDETERMINATE', 'PENDING', 'NOT_APPLICABLE', 'VALIDATION_FAILURE'), 'unknown outcome')
        need(outcome == 'PENDING' or end is not None, 'missing response time')
        need(op['kind'] in ('addAll', 'read'), 'unsupported history operation')
        if op['kind'] == 'addAll':
            docs = op['documents']
            need(docs and len({d['id'] for d in docs}) == len(docs), 'atomic bulk keys')
            need(outcome != 'NOT_APPLICABLE', 'mutation without outcome')
        else:
            need(outcome not in ('NOT_SUBMITTED', 'INDETERMINATE'), 'read has mutation outcome')
            if outcome == 'SUCCESS': need(isinstance(op.get('documents'), list), 'missing read result')
        if outcome == 'SUCCESS' or op['kind'] == 'addAll' and outcome in ('PENDING', 'INDETERMINATE'):
            active.append(op)
    # Only successful responses constrain a required completion's real-time edge.
    # Uncertain writes have no abstract completion until a chosen completion extension.
    predecessors = [sum(1 << j for j, other in enumerate(active) if j != i and
                        other['outcome'] == 'SUCCESS' and other['endNanos'] < op['startNanos'])
                    for i, op in enumerate(active)]
    done = (1 << len(active)) - 1
    visited = set()

    def search(mask, state, path):
        if mask == done: return path
        key = mask, state
        if key in visited: return None
        need(len(visited) < max_states, 'history search bound exceeded (inconclusive)')
        visited.add(key)
        for i, op in enumerate(active):
            bit = 1 << i
            if mask & bit or predecessors[i] & ~mask: continue
            if op['outcome'] != 'SUCCESS':
                result = search(mask | bit, state, path + [dict(opId=op['opId'], included=False)])
                if result is not None: return result
            docs = tuple((d['id'], d['value']) for d in op['documents'])
            if op['kind'] == 'read':
                if docs != state: continue
                next_state = state
            else:
                if {k for k, _ in state} & {k for k, _ in docs}: continue
                next_state = state + docs
            result = search(mask | bit, next_state, path + [dict(opId=op['opId'], included=True)])
            if result is not None: return result
        return None

    witness = search(0, (), [])
    need(witness is not None, 'history is not linearizable within declared model')
    return dict(status='PASS', checker='bounded-exhaustive-client-history', operations=len(history),
                activeOperations=len(active), exploredStates=len(visited), maxOperations=max_operations,
                maxStates=max_states, witness=witness)
