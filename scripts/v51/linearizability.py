"""Bounded independent atomic-map history search, including indeterminate mutations.

This is a small-history oracle, not a query-language or unbounded linearizability proof.
Unknown mutations may be omitted or completed after a timeout; no retry is invented.
"""


def check(history,maximum=10):
    if len(history)>maximum:raise ValueError('linearizability history bound')
    ids=[h['id'] for h in history]
    if len(set(ids))!=len(ids):raise ValueError('duplicate invocation')
    for h in history:
        if h['kind'] not in ('write','read') or h['outcome'] not in ('success','unknown','not-submitted'):raise ValueError('history operation')
        if type(h['start']) is not int or h['start']<0 or h.get('end') is not None and (type(h['end']) is not int or h['end']<h['start']):raise ValueError('operation interval')
        if h['outcome']=='success' and h.get('end') is None:raise ValueError('success without response')
    explored=0;memo=set()
    def visit(pending,state,order):
        nonlocal explored
        explored+=1
        if not pending:return order
        key=(tuple(pending),tuple(sorted(state.items())))
        if key in memo:return None
        memo.add(key)
        for i in pending:
            h=history[i]
            others=[j for j in pending if j!=i]
            if h['outcome']=='not-submitted' or h['kind']=='read' and h['outcome']=='unknown':
                return visit(others,state,order)
            if h['outcome']=='unknown':
                omitted=visit(others,state,order)
                if omitted is not None:return omitted
            # Only successful responses establish a completed-operation precedence edge.
            if any(history[j]['outcome']=='success' and history[j]['end']<=h['start'] for j in others):continue
            next_state=dict(state)
            if h['kind']=='read':
                if h['result']!=next_state:continue
            else:
                for k,v in h['changes']:
                    if v is None:next_state.pop(k,None)
                    else:next_state[k]=v
            result=visit(others,next_state,order+[h['id']])
            if result is not None:return result
        return None
    order=visit(list(range(len(history))),{},[])
    if order is None:raise ValueError('nonlinearizable bounded history')
    return dict(status='PASS',linearization=order,visitedStates=explored)
