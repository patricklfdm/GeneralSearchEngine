"""Independent event oracle. No imports from the model, wire codecs or Java runtime."""
from collections import defaultdict


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(events):
    promises = defaultdict(lambda: 1)
    accepted = {}
    chosen = {}
    proofs = {}
    forces = {}
    published = defaultdict(tuple)
    acknowledged = set()
    reads = {}
    bases = {}
    selections = {}
    generations = defaultdict(lambda: 1)
    for position, e in enumerate(events):
        kind = e['event']; node = e.get('node'); ballot = e.get('ballot', 0)
        if node is not None:
            require(e['generation'] == generations[node], 'I07 process generation')
        if kind == 'restart':
            generations[node] += 1
        elif kind == 'promise-force':
            require(ballot > promises[node], 'I01 promise regression/reuse')
            require((ballot - 2) % 3 == e['proposer'], 'I01 ballot owner')
            promises[node] = ballot
        elif kind == 'basis':
            require(promises[node] == ballot, 'I05 basis without forced promise')
            expected = {str(i): [b, v] for (n, i), (b, v) in accepted.items()
                        if n == node and i > len(e['prefix'])}
            require(e['accepted'] == expected, 'I05 omitted accepted tail')
            require(tuple(e['prefix']) == published[node], 'I05 mixed prefix')
            require(e['id'] not in bases, 'I05 reused basis identity')
            bases[e['id']] = e
        elif kind == 'select':
            q = [bases.get(v) for v in e['bases']]
            require(len(q) == 2 and all(v is not None for v in q), 'I05 missing basis')
            require(len({v['node'] for v in q}) == 2 and e['proposer'] in {v['node'] for v in q}, 'I05 quorum')
            require(all(v['ballot'] == ballot for v in q), 'I05 mixed ballots')
            prefix = max((v['prefix'] for v in q), key=len)
            require(all(prefix[:len(v['prefix'])] == v['prefix'] for v in q), 'I02 conflicting prefixes')
            tails = [pair for v in q for i, pair in v['accepted'].items() if int(i) > len(prefix)]
            if tails:
                greatest = max(pair[0] for pair in tails)
                values = {pair[1] for pair in tails if pair[0] == greatest}
                require(len(values) == 1 and e['value'] in values, 'I05 highest acceptance ignored')
            require(e['prefix'] == prefix, 'I05 wrong recovered prefix')
            require(ballot not in selections, 'I05 same-ballot reselection')
            selections[ballot] = (len(prefix) + 1, e['value'])
        elif kind == 'install':
            prefix = tuple(e['prefix'])
            require(prefix[:len(published[node])] == published[node], 'I03 erased proven prefix')
            for i, value in enumerate(prefix, 1):
                require(chosen.get(i) == value, 'I07 unproven installed prefix')
            published[node] = prefix
        elif kind == 'accept-force':
            slot, value = e['slot'], e['value']
            require(promises[node] == ballot, 'I01 accept below promise')
            require(slot == len(published[node]) + 1, 'I04 unproven predecessor')
            require(ballot in selections, 'I05 acceptance without selection')
            first_slot, first_value = selections[ballot]
            if slot == first_slot:
                require(value == first_value, 'I05 accepted value differs from selection')
            previous = accepted.get((node, slot))
            require(previous is None or previous[0] < ballot or previous == (ballot, value), 'I02 same-ballot conflict')
            accepted[node, slot] = (ballot, value)
            forces[e['id']] = e
        elif kind == 'entry-quorum':
            q = [forces.get(v) for v in e['receipts']]
            require(len(q) == 2 and all(v is not None for v in q), 'I02 fabricated force')
            require(len({v['node'] for v in q}) == 2, 'I02 duplicate voter')
            require(all((v['ballot'], v['slot'], v['value']) == (ballot, e['slot'], e['value']) for v in q), 'I02 receipt identity')
            require(chosen.get(e['slot'], e['value']) == e['value'], 'I02 conflicting chosen values')
            chosen[e['slot']] = e['value']; proofs[e['id']] = e
        elif kind == 'proof-force':
            proof = proofs.get(e['proof'])
            require(proof is not None and accepted.get((node, e['slot'])) == (ballot, e['value']), 'I04 proof without acceptance')
            require(promises[node] == ballot, 'I01 stale proof write')
            require((proof['ballot'], proof['slot'], proof['value']) == (ballot, e['slot'], e['value']), 'I04 wrong proof')
            require(e['slot'] == len(published[node]) + 1, 'I04 proof gap')
            published[node] += (e['value'],)
            forces[e['id']] = e
        elif kind == 'success':
            q = [forces.get(v) for v in e['receipts']]
            require(len(q) == 2 and all(v is not None and v['event'] == 'proof-force' for v in q), 'I03 proof quorum absent')
            require(len({v['node'] for v in q}) == 2 and node in {v['node'] for v in q}, 'I03 proof voter quorum')
            require(all((v['ballot'], v['slot'], v['value']) == (ballot, e['slot'], e['value']) for v in q), 'I03 proof receipt mismatch')
            require(promises[node] == ballot and published[node][e['slot']-1] == e['value'], 'I04 success before publish/fencing')
            acknowledged.add((e['slot'], e['value']))
        elif kind == 'read-invoke':
            require(e['read'] not in reads, 'I06 reused invocation')
            reads[e['read']] = {'invoke': position, 'writes': set(acknowledged), 'node': node}
        elif kind == 'read-pin':
            read = reads[e['read']]
            proof = proofs.get(e['proof'])
            require(read['node'] == node and proof is not None, 'I06 foreign pin')
            require(proof['value'] == e['barrier'] and proof['position'] > read['invoke'], 'I06 reused barrier')
            require((e['slot'], e['barrier']) in acknowledged, 'I06 pin before proof quorum')
            require(tuple(e['prefix']) == published[node] and e['prefix'][-1] == e['barrier'], 'I06 substituted view')
            require(promises[node] == ballot, 'I06 pin after fencing')
            read['pin'] = tuple(e['prefix'])
            require(all(i <= len(read['pin']) and read['pin'][i-1] == v for i, v in read['writes']), 'I06 stale read')
        elif kind == 'read-result':
            require(tuple(e['prefix']) == reads[e['read']].get('pin'), 'I06 view changed after capture')
        elif kind == 'account':
            require(0 <= e['queued'] <= e['limit'] and 0 <= e['pins'] <= e['pinLimit'], 'I08 resource accounting')
        elif kind not in {'checkpoint', 'reject', 'drop', 'duplicate', 'lost-disk'}:
            raise ValueError('unknown event: ' + kind)
    return {'status': 'PASS', 'events': len(events), 'chosenSlots': len(chosen),
            'acknowledgedSlots': len(acknowledged), 'reads': len(reads)}
