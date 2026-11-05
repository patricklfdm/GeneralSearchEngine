"""Original incoming voting requests, writer charges and handler waiter lifetimes.

The caller must first qualify the native physical history. Exact request digests
correlate local allocations; original connected request bytes supply extents.
Lost ACK delivery may overlap a cached duplicate. It is not a new durable vote.
Interrupted handlers and failed voting work remain outside this success scope.
"""
from collections import defaultdict
import base64
import json
import re
from uuid import UUID

from . import native_source_resources as source

need = source.need
ROLES = {'voting-control': 'CONTROL', 'voting-waiter': 'WAITER'}
OWNER = re.compile(r'(voting-control|voting-waiter)-([0-9a-f]{64})-([0-9a-f-]{36})\Z')
LEGACY = re.compile(r'(voting-control|voting-waiter)-([0-9a-f-]{36})\Z')
FORCE = {'ACCEPT': 'ACCEPT_PARENT_FORCED', 'PROOF': 'PROOF_PARENT_FORCED', 'APPLY': 'APPLY_END_FORCED'}
RETURN = {kind: kind+'_BEFORE_RETURN' for kind in FORCE}


def scan(traces):
    leases = {}; legacy = 0
    for node, trace in traces.items():
        source.a.transitions.replay(trace)
        for row in trace['changes']:
            charges = [v for v in row['removed']+row['added'] if any(v['owner'].startswith(role+'-') for role in ROLES)]
            if not charges: continue
            need(len(charges) == 1 and row['event'] in ('RESERVE', 'RELEASE'), 'voting resources immutable allocation')
            charge = charges[0]; match = OWNER.fullmatch(charge['owner']); old = LEGACY.fullmatch(charge['owner'])
            need(match is not None or old is not None, 'voting resources owner binding')
            role = (match or old)[1]; nonce = match[3] if match else old[2]
            need(charge['unit'] == ROLES[role], 'voting resources role/unit')
            try: value = UUID(nonce)
            except ValueError: raise ValueError('voting resources allocation UUID') from None
            need(value.int != 0 and str(value) == nonce, 'voting resources allocation UUID')
            key = node, charge['owner']
            if row['event'] == 'RESERVE':
                need(key not in leases, 'voting resources reused allocation')
                legacy += match is None
                leases[key] = dict(node=node, owner=charge['owner'], role=role, binding=match[2] if match else None,
                                   start=row['sequence'], end=None, bytes=charge['bytes'])
            else:
                need(key in leases and leases[key]['end'] is None and leases[key]['bytes'] == charge['bytes'],
                     'voting resources original lifetime')
                leases[key]['end'] = row['sequence']
    need(all(v['end'] is not None for v in leases.values()), 'voting resources incomplete drain')
    return leases, legacy


def match_waiters(waiters, attempts):
    """Injective interval matching; a retry cannot invent additional handlers.

    Process the latest waiter ends first. Among eligible server intervals take
    the latest read, preserving earlier reads for more restrictive later matches.
    This proves coverage, not which identical socket scheduled a particular call.
    """
    remaining = list(attempts)
    for life in sorted(waiters, key=lambda v: (-v['end'], v['start'])):
        choices = [v for v in remaining if v['receivedSequence'] < life['start'] < life['end'] <= v['offeredSequence']]
        need(choices, 'voting resources waiter request interval')
        chosen = max(choices, key=lambda v: (v['receivedSequence'], -v['offeredSequence']))
        remaining.remove(chosen)


def replay(events, wires, traces, boundaries, identities, root, *, require_complete=True):
    need(type(require_complete) is bool, 'voting resources completeness policy')
    leases, legacy = scan(traces)
    if legacy or not leases:
        need(not require_complete, 'voting resources original bindings required')
        return dict(status='NOT_OBSERVED', legacyReservations=legacy, boundReservations=0,
                    incomingVotingResourcesQualified=False, wholeRuntimeResourcesQualified=False, phase3Complete=False)
    network = source.network.replay(events, wires, identities, root)
    need(all(v['kind'] not in FORCE or v['received'] is None or any(
        row['sent'] == v['sent'] and row['answer'] == v['kind']+'_ACK' for row in network['rows'])
        for v in network['failed']), 'voting resources failed handler outside qualification')
    need(len(boundaries) == len(events), 'voting resources complete boundaries')
    def point(at, node):
        value = boundaries[at]
        need(type(value) is dict and set(value) == {'eventIndex', 'node', 'sequence', 'usage'} and
             type(value['eventIndex']) is int and value['eventIndex'] == at and value['node'] == node == events[at]['node'] and
             type(value['sequence']) is int and 0 <= value['sequence'] < len(traces[node]['changes']),
             'voting resources original checkpoint')
        source.a.transitions.same_usage(value['usage'], traces[node]['changes'][value['sequence']]['usage'])
        return value['sequence']
    wire_by_id = {v['connection']['id']: v for v in wires}
    attempts = defaultdict(list); semantics = {}; force_candidates = defaultdict(set)
    groups = defaultdict(lambda: defaultdict(list))
    for key, life in leases.items(): groups[life['node'], life['binding']][life['role']].append((key, life))
    for row in network['rows']:
        kind = row['kind']
        if kind not in FORCE: continue
        need(row['answer'] == kind+'_ACK', 'voting resources successful original reply')
        node = row['request']['recipient']['node']; binding = row['requestHash']; key = node, binding
        before, after = point(row['received'], node), point(row['offered'], node)
        original = wire_by_id[row['serverConnection']]
        size = len(base64.b64decode(original['request'], validate=True))
        # The connection reader checks the exact request bytes/hash/route and ACK.
        q = row['request']; semantic = (node, kind, q['root'], q['view'], json.dumps(q['ballot'],sort_keys=True),
                                      json.dumps(q['payload'],sort_keys=True))
        need(key not in semantics or semantics[key] == semantic, 'voting resources changed logical request')
        semantics[key] = semantic
        attempts[key].append(dict(row=row, receivedSequence=before, offeredSequence=after, size=size))
        for at in range(row['received']+1, row['offered']):
            if events[at]['node'] == node and events[at]['event'] == FORCE[kind]: force_candidates[node, at].add(key)
    need(attempts, 'voting resources original requests absent')
    need(set(groups) <= set(attempts), 'voting resources unobserved allocation')
    control_forces = defaultdict(list); forces = {}; checkpoints = 0
    for (node, at), keys in force_candidates.items():
        seq = point(at, node); choices = []
        for key in keys:
            for owner, life in groups.get(key, {}).get('voting-control', []):
                if life['start'] <= seq < life['end']: choices.append((owner, life, key))
        need(len(choices) == 1, 'voting resources forced work lacks unique control')
        owner, life, key = choices[0]; control_forces[owner].append(at); forces[owner] = (key, at)
    used = set(); kinds = defaultdict(int); fast_acks = 0; repeats = 0
    for key, pairs in list(groups.items()):
        controls, waiters = pairs['voting-control'], pairs['voting-waiter']; rows = attempts[key]
        need(len(controls) == 1 and waiters, 'voting resources one writer and admitted waiters')
        owner, control = controls[0]; kind = rows[0]['row']['kind']
        need(all(control['bytes'] == v['size'] for v in rows), 'voting resources original control extent')
        need(all(v['bytes'] == 0 for _, v in waiters), 'voting resources waiter extent')
        need(any(v['receivedSequence'] < control['start'] < control['end'] <= v['offeredSequence'] for v in rows),
             'voting resources control request interval')
        need(len(control_forces[owner]) == 1, 'voting resources exact original force')
        at = control_forces[owner][0]
        returns = [i for i in range(at+1, max(v['row']['offered'] for v in rows))
                   if events[i]['node'] == key[0] and events[i]['event'] == RETURN[kind]]
        need(len(returns) == 1, 'voting resources original durable return')
        need(control['start'] <= point(returns[0], key[0]) < control['end'], 'voting resources control released before durable return')
        need(any(w['start'] < control['start'] < control['end'] < w['end'] for _, w in waiters),
             'voting resources writer not held by original waiter')
        match_waiters([v for _, v in waiters], rows)
        used.update([owner, *(k for k, _ in waiters)]); kinds[kind] += 1; repeats += len(rows)-1; checkpoints += 2
    # Fast durable ACKs have no writer/waiter. They require an already observed
    # original force for the exact statement, not merely another equal-size call.
    for key, rows in attempts.items():
        if key in groups: continue
        for row in rows:
            need(any(semantics[other] == semantics[key] and at < row['row']['offered'] for other, at in forces.values()),
                 'voting resources cached reply without original force')
            fast_acks += 1
    need(used == set(leases), 'voting resources incomplete allocation coverage')
    return dict(status='PASS', boundReservations=len(used), writerControls=sum(kinds.values()),
                waiterReservations=sum(v['role'] == 'voting-waiter' for v in leases.values()),
                kinds=dict(sorted(kinds.items())), connectedAttempts=sum(map(len, attempts.values())),
                repeatedIdenticalAttempts=repeats, separatelyTracedFastAcks=fast_acks, durableBoundaryChecks=checkpoints,
                incomingVotingResourcesQualified=True, interruptedHandlersQualified=False,
                wholeRuntimeResourcesQualified=False, phase3Complete=False)
