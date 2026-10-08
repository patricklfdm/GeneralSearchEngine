"""Independent local-clock and actual wire/force checks for owned network faults."""
from . import performance_model as m, remote_command as c, format_inspector as f
from . import runtime_evidence as a
from .guest_fault_network import NODES

CASES = ('isolated-old-leader', 'asymmetric-requests', 'asymmetric-responses', 'slow-follower')


def check(record, history, traces, root, rows, observations, collections, seed_capture):
    case = record['case']; leader = record['seedLeader']
    def event(name):
        values = [v for v in record['events'] if v['event'] == name]
        m.need(len(values) == 1, 'owned network control event: '+name)
        return values[0]['controllerNanos']
    ready, heal = event('network-ready'), event('network-heal-request')
    m.need(record['faultStartNanos'] <= ready and 15*10**9 <= heal-ready <= 17*10**9, 'owned network controller hold')
    selected = None
    if case == 'slow-follower':
        selected = record['selected']; target = record['delayedNode']
        m.need(selected in traces[leader] and selected['event'] == 'PROMISE_QUORUM' and
               selected['pid'] == history[3]['pid'], 'owned slow selected trace')
        bases = f.inspect(a.raw(selected['selected']), 'SELECTED')['bases']
        m.need({v['node'] for v in bases} == {leader, target} and target != leader, 'owned slow selected follower')
        affected = {target}; expected_rules = None
        observed = [r['result']['selected'] for q,r in rows[leader]
                    if q['command'] == 'fault' and q['payload'] == {'action':'observe-network'}]
        m.need(selected in observed, 'owned slow original selected observation')
    else:
        affected = set(NODES)
        barrier = 'AFTER_RESPONSE_READ' if case == 'asymmetric-responses' else 'BEFORE_REQUEST_WRITE'
        expected_rules = [f'{x} {y} {barrier} *' for x in NODES for y in NODES if x != y and
                          (leader in (x,y) if case == 'isolated-old-leader' else x == leader)]
    actuals = {}
    def during(row):
        interval = actuals[row['node']]
        return interval['appliedNanos'] <= row['localNanos'] <= interval['healedNanos']
    for node, seq in rows.items():
        injections = [(q,r) for q,r in seq if q['command'] == 'fault' and q['payload'].get('action') == 'isolate']
        releases = [(q,r) for q,r in seq if q['command'] == 'fault' and q['payload'].get('action') == 'heal']
        if node not in affected:
            m.need(not injections and not releases, 'owned network wrong target'); continue
        m.need(len(injections) == len(releases) == 1, 'owned network injection/release coverage')
        iq, ir = injections[0]; hq, hr = releases[0]
        target = record['delayedNode'] if case == 'slow-follower' else leader
        m.need(iq['payload'] == dict(action='isolate',node=target) and hq['payload'] == dict(action='heal'), 'owned network payload')
        actual = c.read(collections[node]/'isolation.json'); actuals[node] = actual
        wanted = dict(node=target, delayMillis=1500) if case == 'slow-follower' else dict(node=target, rules=expected_rules)
        m.need(ir['result'] == dict(wanted, appliedNanos=actual['appliedNanos']) and hr['result'] == actual and
               actual == dict(wanted, appliedNanos=actual['appliedNanos'], healedNanos=actual['healedNanos'], watchdog=False) and
               15*10**9 <= actual['healedNanos']-actual['appliedNanos'] <= 17*10**9,
               f"owned network guest hold/watchdog: case={case} node={node} "
               f"holdSeconds={(actual['healedNanos']-actual['appliedNanos'])/1e9:.9f} watchdog={actual.get('watchdog')}")
        begin, end = observations[iq['commandId']], observations[hq['commandId']]
        m.need(record['faultStartNanos'] <= begin['startNanos'] <= begin['endNanos'] <= ready <= heal <= end['startNanos'] <= end['endNanos'],
               'owned network controller command barrier')
        m.need(c.read(collections[node]/'network-injection-claim.json') == iq['payload'], 'owned network original claim')
    flat = [v for seq in traces.values() for v in seq]
    successful = [v for v in record['progress'] if all(v[k]['outcome'] == 'SUCCESS' for k in ('write','read'))]
    if case == 'slow-follower':
        node = record['delayedNode']; own = traces[node]; actual = actuals[node]
        begins = [v for v in own if v['event'] == 'SLOW_FORCE_BEGIN']; ends = [v for v in own if v['event'] == 'SLOW_FORCE_END']
        m.need(begins and len(begins) == len(ends) and record['delayed'] == begins[0], 'owned slow actual force missing')
        # A hook that already read the fault file can log after its removal.
        # Require an in-hold witness, while validating every observed force.
        m.need(any(during(v) for v in begins), 'owned slow force outside hold')
        for first,last in zip(begins,ends):
            m.need(first['kind'] == last['kind'] and first['kind'] in ('ACCEPT','PROOF') and
                   first['delayMillis'] == last['delayMillis'] == 1500 and first['pid'] == last['pid'] and
                   last['localNanos']-first['localNanos'] >= 1500*10**6 and first['order'] < last['order'], 'owned slow force duration')
        observed = [r['result']['delayed'] for q,r in rows[node] if q['command'] == 'fault' and q['payload'] == {'action':'observe-network'}]
        m.need(record['delayed'] in observed, 'owned slow original delay observation')
        for label, owner in (('leader', successful[-1]['node']), ('follower', node)):
            m.need(any(q['command']=='fault' and q['payload']=={'action':'status'} and r['result']['response']==record['lag'][label]
                       for q,r in rows[owner]), 'owned slow original lag observation')
    else:
        encoded = (root/'node-1/manifest.gsr').read_bytes()
        manifest = dict(f.inspect(encoded,'MANIFEST'), digest=encoded[16:48].hex())
        wire = lambda row,key='frame': f.wire(a.raw(row[key]), manifest)
        drops = [v for v in flat if v['event']=='NETWORK_DROP']
        m.need(drops and any(during(v) for v in drops) and all(v['rule'] in expected_rules for v in drops), 'owned network actual drops')
        for drop in drops:
            request = wire(drop,'request')
            m.need(drop['barrier']==barrier and drop['node']==request['sender'] and
                   drop['rule']==f"{request['sender']} {request['recipient']} {barrier} *", 'owned network direction')
        if case.startswith('asymmetric-'):
            m.need(all(wire(v,'request')['sender']==leader and v['barrier']==barrier for v in drops), 'owned network direction')
            replies = [v for v in flat if v['event']=='REPLY']
            m.need(any(v['node']==leader and during(v) and wire(v)['type']!='REJECT' and wire(v,'request')['sender']!=leader for v in replies), 'owned network reverse traffic missing')
            if case=='asymmetric-responses':
                m.need(all(any(v['request']==drop['request'] for v in replies) for drop in drops), 'owned network response never executed')
                call = record['directionalCall']; op = next(h for h in history if h['opId']==call['opId'])
                m.need(op['node']==leader and op['kind']=='addAll' and op['response']==call and ready<=op['startNanos']<=op['endNanos']<=heal,
                       'owned directional original call')
        else:
            m.need(any(v['node']!=leader and v['endNanos']<=heal for v in successful), 'owned network no majority progress under isolation')
            refusals = record['refusals']; m.need([v['kind'] for v in refusals]==['addAll','read'], 'owned network refusal pair')
            for response in refusals:
                op = next(h for h in history if h['opId']==response['opId'])
                m.need(op['response']==response and op['node']==leader and op['outcome']!='SUCCESS' and
                       ready<=op['startNanos']<=op['endNanos']<=heal, 'owned network refusal outside isolation')
            m.need(any(v['event']=='FORCE' and v['kind']=='PROMISE' and
                       f.inspect(a.raw(v['record']),'PROMISE')['epoch']>seed_capture['epoch'] for v in traces[leader]), 'owned network old leader never fenced')
    healed = max(observations[q['commandId']]['endNanos'] for seq in rows.values() for q,r in seq
                 if q['command']=='fault' and q['payload']=={'action':'heal'})
    m.need(len(record['rejoins'])==3 and {v['node'] for v in record['rejoins']}==set(NODES) and
           all(v['startNanos']>=healed for v in record['rejoins']), 'owned network post-heal rejoin coverage')
