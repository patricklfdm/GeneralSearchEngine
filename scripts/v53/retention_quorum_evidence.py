"""Original-first native retention quorum/ACK replay.

Derives bootstrap, installed election and first publication before interpreting
any new ACK. Quorum permits here queue a test callback, not a production peer
installation. No future publication, joint transition or autonomous runtime claim.
"""
from __future__ import annotations
import argparse
import base64
import copy
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from . import selected_retention_evidence as s

r, b, f = s.r, s.b, s.f
need, sha = r.need, r.sha
FILE, NEXT = s.FILE, s.NEXT
POINTS = ('RETENTION_PREFIX_WRITTEN', 'RETENTION_FORCED', 'RETENTION_RENAMED',
          'RETENTION_PARENT_FORCED', 'RETENTION_ACK_BEFORE_RETURN')


def read(path):
    return json.loads(Path(path).read_text())


def prelude(root, size):
    group = s.initialize(b.original(root, size, False))
    prepared, selected, installed = s.campaign(root, group, 2, 'round-1-prepared')
    for stage, state in [('prepared', prepared), ('selected', selected), ('installed', installed)]:
        b.match(root, 'round-1-'+stage, state)
    group = b.settled(installed); b.match(root, 'round-1-settled', group)
    group, _ = b.publication(root, group, 1, None, [])
    b.match(root, 'before-quorum', group)
    names = sorted(group); rows = read(root/'calls.json')
    expected = [(n, 'initialize') for n in names]+[('node-1', 'allocate-1')]
    expected += [(n, phase+'-1') for phase in ('prepare', 'select', 'install') for n in names]
    expected += [(n, 'round-1-settled-'+phase) for phase in ('copy', 'maintain') for n in names]
    expected += [('node-1', 'entry-1')]+[(n, phase+'-1') for phase in ('accept', 'proof', 'certificate', 'apply', 'publish') for n in names]
    expected += [(n, 'slot-1-settled-'+phase) for phase in ('copy', 'maintain') for n in names]+[(n, 'inspect-1') for n in names]
    need([(v['node'], v['operation']) for v in rows[:len(expected)]] == expected, 'retention original calls')
    forces = {'initialize': ['RETENTION_FORCED', 'RETENTION_RENAMED', 'RETENTION_PARENT_FORCED'],
              'prepare': ['PROMISE_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_FORCED', 'GRANT_BEFORE_RETURN'],
              'install': ['INSTALL_GENERATION_FORCED', 'INSTALL_SELECTOR_FORCED', 'INSTALL_PARENT_FORCED', 'INSTALL_BEFORE_RETURN'],
              'accept': ['ACCEPT_ACTIVE_FORCED', 'ACCEPT_BEFORE_RETURN'],
              'proof': ['PROOF_CANDIDATE_FORCED', 'PROOF_PARENT_FORCED', 'PROOF_BEFORE_RETURN'],
              'publish': ['PUBLICATION_SELECTOR_FORCED', 'PUBLICATION_BEFORE_RETURN']}
    for row in rows[:len(expected)]:
        s.ordered(row['events'], forces.get(row['operation'].split('-')[0], []), row['operation'])
    return group


def updated(files, target):
    state = r.decode(files[FILE]); plan = copy.deepcopy(state['plan'])
    row = next(v for v in plan['peers'] if v['identity']['node'] == target)
    row['possible'].append(b.c.anchor(b.c.current(files)[2]['capsule']))
    return r.frame(dict(state, revision=1, previous=sha(files[FILE]), plan=plan))


def request(raw, group):
    value = f.decode(raw, 'wire', 'RETENTION_INTENT')
    _, members, packet = b.c.current(group['node-1']); cap = packet['capsule']
    selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
    identities = {n: f.decode(files['node.gsr'], 'records', 'NODE')['identity'] for n, files in group.items()}
    recipient = value['recipient']['node']; target = sorted(group)[-1]
    need(recipient in identities and str(uuid.UUID(value['trace'])) == value['trace'], 'retention wire recipient/trace')
    plan = r.decode(group['node-1'][FILE])['plan']
    lower = next(v['possible'][0] for v in plan['peers'] if v['identity']['node'] == target)
    payload = dict(selection=sha(members['selected.gsr']), peer=identities[target], lower=lower, upper=b.c.anchor(cap))
    expected = dict(root=cap['root'], view=selected['view'], ballot=selected['ballot'], sender=identities['node-1'],
                    recipient=identities[recipient], trace=value['trace'], sequence=int(recipient[5:]), payload=payload)
    # The fresh-process receiver test uses sequence 1 for its sole node-2 call.
    if value['sequence'] == 1 and recipient == 'node-2': expected['sequence'] = 1
    need(value == expected, 'retention exact native request')
    return value, sha(f.canonical(payload))


def response(raw, sent, intent, ledger):
    expected = dict(sent, sender=sent['recipient'], recipient=sent['sender'],
                    payload=dict(intent=intent, revision=1, ledger=sha(ledger)))
    need(f.decode(raw, 'wire', 'RETENTION_ACK') == expected, 'retention exact durable acknowledgement')


def network(root):
    result = read(root/'network.json'); size = result['size']; lost = result['lostAck']
    need(type(size) is int and size in (3, 4, 5) and type(lost) is bool and (not lost or size == 3), 'retention network profile')
    group = prelude(root, size); names = sorted(group); target = names[-1]
    ledgers = {n: updated(files, target) for n, files in group.items()}
    events = read(root/'events.json'); need(len(events) == size, 'retention owner event count')
    final = {}
    for node, steps in zip(names, events):
        forced = 'RETENTION_BEFORE_WRITE' in steps
        if forced:
            need(steps.count('RETENTION_BEFORE_WRITE') == 1, 'retention duplicate rewrote ledger')
            s.ordered(steps, ['RETENTION_BEFORE_WRITE', 'RETENTION_FORCED', 'RETENTION_RENAMED', 'RETENTION_PARENT_FORCED'], node)
        if 'RETENTION_ACK_BEFORE_RETURN' in steps:
            need(forced, 'retention acknowledgement without force')
            s.ordered(steps, ['RETENTION_PARENT_FORCED', 'RETENTION_ACK_BEFORE_RETURN'], node)
        final[node] = dict(group[node], **({FILE: ledgers[node]} if forced else {}))
    b.match(root, 'after-quorum', final)
    wire = read(root/'wire.json'); need(wire, 'retention missing wire evidence')
    requests, replies, traces = {}, {}, set()
    for exchange in wire:
        raw = base64.b64decode(exchange['request'], validate=True); sent, intent = request(raw, group)
        node = sent['recipient']['node']; reply = base64.b64decode(exchange['response'], validate=True)
        response(reply, sent, intent, ledgers[node]); need(final[node][FILE] == ledgers[node], 'retention reply before durable state')
        requests.setdefault(node, []).append(sha(raw)); replies[sha(reply)] = node; traces.add(sent['trace'])
        need(intent == result['intent'], 'retention changed quorum intent')
    need(len(traces) == 1, 'retention mixed wire rounds')
    attempts = read(root/'requests.json')
    need([v['node'] for v in attempts] == names[1:], 'retention exact peer attempts')
    for row in attempts:
        hashes = row['digests']; need(1 <= len(hashes) <= 3 and len(set(hashes)) == 1, 'retention bounded identical retry')
        need(all(h == hashes[0] for h in requests.get(row['node'], [])), 'retention replay changed request')
    if lost:
        need(len(requests.get('node-2', [])) == 2 and 'node-3' not in requests, 'retention lost ACK history')
    voters = result['voters']; need(voters == sorted(set(voters)) and 'node-1' in voters
                                   and set(voters) <= set(names) and len(voters) == size//2+1, 'retention governing majority')
    timeline = read(root/'timeline.json'); dispatch = [i for i, row in enumerate(timeline) if row['event'] == 'DISPATCH']
    need(len(dispatch) == 1, 'retention exact dispatch callback'); before = timeline[:dispatch[0]]
    for node in voters:
        steps = [v['event'] for v in before if v['node'] == node]
        s.ordered(steps, ['RETENTION_PARENT_FORCED', 'RETENTION_ACK_BEFORE_RETURN']+([] if node == 'node-1' else ['ACK_RECEIVED']), node+' before dispatch')
        if node != 'node-1':
            rows = [v for v in before if v['node'] == node and v['event'] == 'ACK_RECEIVED']
            need(all(replies.get(v['digest']) == node for v in rows), 'retention received ACK identity')
    return dict(size=size, lostAck=lost, status='PASS', voters=voters, exchanges=len(wire))


def crashes(root):
    group = prelude(root, 3); b.match(root, 'crash-ready', group)
    sent, intent = request((root/'request.gsrp').read_bytes(), group)
    need(sent['recipient']['node'] == 'node-2', 'retention crash original receiver')
    ledger = updated(group['node-2'], 'node-3'); completed = dict(group['node-2'], **{FILE: ledger})
    paths = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith(('halt-', 'kill-')))
    need({p.name for p in paths} == {mode+'-'+point for mode in ('halt', 'kill') for point in POINTS}, 'retention complete crash matrix')
    rows = []
    for path in paths:
        record = read(path/'result.json'); mode, point = record['mode'], record['cut']
        need(record == dict(mode=mode, cut=point, exit=23 if mode == 'halt' else 137)
             and path.name == mode+'-'+point, 'retention actual crash identity')
        log = (path/'worker.log').read_text(); need(log.count('CUT '+point+'\n') == 1 and 'RESPONSE' not in log, 'retention interrupted response')
        events = [v[6:] for v in log.splitlines() if v.startswith('EVENT ')]
        need(events[-1] == point, 'retention exact process cut')
        s.ordered(events, ['RETENTION_BEFORE_WRITE', point], point)
        expected = dict(group['node-2'])
        if point in POINTS[2:]: expected[FILE] = ledger
        else: expected[NEXT] = ledger[:len(ledger)//2] if point == POINTS[0] else ledger
        need(b.c.inventory(path/'interrupted') == expected, 'retention interrupted exact files')
        need(b.c.inventory(path/'recovered') == completed, 'retention resumed exact files')
        resume = (path/'resume.log').read_text().splitlines(); answers = [v[9:] for v in resume if v.startswith('RESPONSE ')]
        need(len(answers) == 1, 'retention resumed response count'); response(base64.b64decode(answers[0], validate=True), sent, intent, ledger)
        steps = [v[6:] for v in resume[:next(i for i, v in enumerate(resume) if v.startswith('RESPONSE '))] if v.startswith('EVENT ')]
        if point in POINTS[:2]: s.ordered(steps, ['RETENTION_FORCED', 'RETENTION_PARENT_FORCED', 'RETENTION_ACK_BEFORE_RETURN'], 'resume')
        else:
            s.ordered(steps, ['RETENTION_RECOVERY_ACTIVE_FORCED', 'RETENTION_RECOVERY_PARENT_FORCED', 'RETENTION_ACK_BEFORE_RETURN'], 'resume')
            need('RETENTION_BEFORE_WRITE' not in steps, 'retention resumed duplicate rewrite')
        need(steps.count('RETENTION_ACK_BEFORE_RETURN') == 2, 'retention exact duplicate ACK boundary')
        rows.append(dict(mode=mode, cut=point, status='PASS'))
    return rows


def validate(root):
    root = Path(root); networks = [network(p.parent) for p in sorted(root.rglob('network.json'))]
    need(len(networks) == 4 and {(v['size'], v['lostAck']) for v in networks} == {(3, False), (3, True), (4, False), (5, False)}, 'retention complete network matrix')
    crash_roots = [p.parent for p in root.rglob('request.gsrp')]; need(len(crash_roots) == 1, 'retention crash root count')
    rows = crashes(crash_roots[0])
    return dict(status='PASS', network=networks, crashes=rows, originalBootstrap=True, originalPublication=True,
                scope='same-view-current-target-quorum', actualPeerDispatch=False, autonomousRuntime=False, phase3Complete=False)


def qualify(root):
    original = validate(root)
    variants = [('majority', 'retention governing majority'), ('intent', 'retention changed quorum intent'),
                ('retry', 'retention bounded identical retry'), ('dispatch', 'selected retention force order: node-1 before dispatch'),
                ('initial', 'admitted original public bootstrap'), ('interrupted', 'retention interrupted exact files'),
                ('resumed', 'retention resumed exact files'), ('response', 'retention interrupted response'),
                ('missing', 'retention complete network matrix')]
    negatives = []
    for mutation, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-retention-quorum-negative-') as temp:
            raw = Path(temp)/'raw'; shutil.copytree(root, raw)
            network_root = next(p.parent for p in sorted(raw.rglob('network.json')) if read(p)['size'] == 3 and not read(p)['lostAck'])
            crash_root = next(raw.rglob('request.gsrp')).parent/'kill-RETENTION_FORCED'
            if mutation in ('majority', 'intent'):
                path = network_root/'network.json'; value = read(path)
                if mutation == 'majority': value['voters'] = ['node-1']
                else: value['intent'] = 'f'*64
                path.write_text(json.dumps(value))
            elif mutation == 'retry':
                path = network_root/'requests.json'; value = read(path); value[0]['digests'] *= 4; path.write_text(json.dumps(value))
            elif mutation == 'dispatch':
                path = network_root/'timeline.json'; value = read(path); row = next(v for v in value if v['event'] == 'DISPATCH'); value.remove(row); value.insert(0, row); path.write_text(json.dumps(value))
            elif mutation == 'initial': (network_root/'initial/target-0/allocator.gsr').write_bytes(b'bad')
            elif mutation == 'interrupted': (crash_root/'interrupted'/NEXT).unlink()
            elif mutation == 'resumed': (crash_root/'recovered'/FILE).write_bytes((crash_root.parent/'crash-ready/node-2'/FILE).read_bytes())
            elif mutation == 'response':
                with (crash_root/'worker.log').open('a') as stream: stream.write('RESPONSE false\n')
            else: (network_root/'network.json').unlink()
            try: validate(raw)
            except ValueError as error: need(str(error) == reason, 'negative reached wrong rejection: '+str(error))
            else: raise ValueError('negative unexpectedly accepted: '+mutation)
            negatives.append(dict(case=mutation, status='REJECTED', reason=reason))
    return dict(original=original, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root), sort_keys=True))
