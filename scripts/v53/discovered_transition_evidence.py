"""Bounded original-first prelude/adoption inspection of a native 5 -> 4 run.

This is deliberately PARTIAL: it does not accept a service round or convert a
failed producer into a passed history. Bootstrap, seven actual slots, original
retention and both adopted generations are derived before inspecting discovery.
"""
import argparse
import base64
from collections import defaultdict
import json
from pathlib import Path
import shutil
import tempfile
from . import inherited_adoption_evidence as a
from .selected_prefix_evidence import prefix
from . import prefix_discovery_evidence as discovery
from . import promised_source_evidence as transfer

c, f, e, need = a.c, a.f, a.e, a.need


def prelude(root):
    walk = a.Walk(root, selected_prefix=prefix, size=5, initial_label=None)
    walk.campaign(2, walk.names, 'node-1', 'round-1')
    walk.settle('round-1-settled', walk.names)
    online = ['node-1', 'node-2', 'node-3', 'node-5']
    voters = walk.names[:3]
    walk.publication('BARRIER', None, online, 'slot-1')
    walk.settle('slot-1-settled', online)
    cap = a.state(walk.group['node-1'])[1]['capsule']
    request = dict(root=cap['root'], expected=e.authority(cap['root'], cap['cut']['view']),
                   number=1, kind='REMOVE', target=[a.u.identity(walk.group[n]) for n in walk.names[:4]])
    for slot, kind, command in [(2, 'RESERVE', dict(request=request)), (3, 'PREPARE', dict(number=1, revision=1)),
                                (4, 'READY', dict(number=1, receipt=None)), (5, 'SEAL', dict(number=1))]:
        walk.publication(kind, command, online, f'slot-{slot}')
        walk.settle(f'slot-{slot}-settled', online)
    operation = a.state(walk.group['node-1'])[2]['results'][-1]
    walk.publication('INTENT', dict(sealed={k: operation[k] for k in ('request', 'prepared', 'receipt')}), online, 'slot-6')
    walk.reconcile(online); walk.settle('slot-6-settled', online)
    walk.campaign(3, voters, 'node-1', 'campaign-3'); walk.settle('campaign-3-settled', voters)
    walk.publication('FINAL', dict(binding=operation['binding']), voters, 'slot-7')
    walk.reconcile(voters); walk.settle('slot-7-settled', voters)
    walk.match('heterogeneous-originals'); walk.match('before-network')
    observations = json.loads(a.p.t.plans.read(Path(root)/'observations.json', e.MIB))
    need(len(observations) == len(walk.observed) and {f.canonical(v) for v in observations} == walk.observed,
         'discovered transition original observations')
    return walk


def adopted(files, remote, node):
    folder, _, _ = c.current(files); members, packet, _ = a.state(remote); cap = packet['capsule']
    cert = packet['objects'][cap['items'][-1]['certificate']]
    certificate = f.decode(cert, 'records', 'CERTIFICATE')
    promise = f.encode('records', 'PROMISE', dict(root=cap['root'], view=certificate['authority'],
                       ballot=certificate['ballot'], basisId=None))
    values = dict(zip(('promise.gsr', 'source.gscp', 'adopted-certificate.gsr'), (promise, members['source.gscp'], cert)))
    values.update({h+'.image': members[h+'.image'] for h in packet['images']})
    if 'ancestry.gsr' in members: values['ancestry.gsr'] = members['ancestry.gsr']
    slot = 'b' if folder == 'generations/a/' else 'a'
    manifest = f.encode('records', 'GENERATION', dict(root=cap['root'], node=node, generation=slot, cut=cap['cut'],
        catalog=cap['catalog'], application=cap['application'], capsule=e.digest(packet['capsuleBytes']),
        promise=e.digest(promise), basis=None, selection=None, ownedTail=None,
        files=[dict(path=k, size=len(v), sha256=e.digest(v)) for k, v in sorted(values.items())]))
    values['generation.gsr'] = manifest
    selector = f.encode('records', 'SELECTOR', dict(root=cap['root'], node=node, generation=slot, digest=e.digest(manifest)))
    return dict(files, **{'selector.gsr': selector, 'grants.gsr': files['grants.gsr']+promise, 'generations/'+slot: None},
                **{'generations/'+slot+'/'+k: v for k, v in values.items()})


def recovery_transcript(root, node, before, remote, after):
    rows = json.loads(a.p.t.plans.read(Path(root)/'wire.json', 16*e.MIB))
    events = json.loads(a.p.t.plans.read(Path(root)/'events.json', 8*e.MIB))
    local = a.state(before)[0]; members, packet, _ = a.state(remote); cap = packet['capsule']
    ballot = f.decode(local['selected.gsr'], 'records', 'SELECTED')['ballot']
    view = e.authority(cap['root'], a.state(before)[1]['capsule']['cut']['view'])
    adoption = [(i, row) for i, row in enumerate(events) if row['node'] == node and row['event'] == 'ROUND_ADOPTED']
    need(len(adoption) == 1, 'discovered transition exact adoption event')
    boundary, event = adoption[0]; manifest = after[c.current(after)[0]+'generation.gsr']
    need(set(event) == {'node', 'event', 'record', 'bytes'} and event['record'] == e.digest(manifest)
         and base64.b64decode(event['bytes'], validate=True) == manifest, 'discovered transition original adoption event')
    probes = []; traces = defaultdict(list)
    for row in rows:
        kind, request = transfer.t.wire(row['request'])
        if request['sender']['node'] != node or request['ballot'] != ballot or request['view'] != view: continue
        need(set(row) == {'request', 'response', 'withheld'} and row['withheld'] is False,
             'discovered transition delivered recovery row')
        answer, response = transfer.t.wire(row['response'])
        need(request['recipient'] == a.u.identity(remote), 'discovered transition original recovery peer')
        qhash = e.digest(base64.b64decode(row['request'], validate=True))
        rhash = e.digest(base64.b64decode(row['response'], validate=True))
        offered = [i for i, v in enumerate(events[:boundary]) if v == dict(node=request['recipient']['node'],
                   event='WIRE_RESPONSE', request=qhash, response=rhash)]
        delivered = [i for i, v in enumerate(events[:boundary]) if v == dict(node=node, event='NETWORK_RECEIVED', kind=answer, response=rhash)]
        need(offered and delivered and min(offered) < min(delivered), 'discovered transition delivered before adoption')
        item = {k: row[k] for k in ('request', 'response')}
        if kind == 'STATUS_PROBE': probes.append(item)
        else:
            need(kind in ('CHUNK', 'TRANSFER_COMMIT'), 'discovered transition discovery cannot vote')
            traces[request['trace']].append(item)
    need(len(probes) == 1 and len(traces) == 2, 'discovered transition complete discovery traces')
    ordered = []
    for trace, items in traces.items():
        attempts = defaultdict(list)
        for item in items: attempts[transfer.t.wire(item['request'])[1]['sequence']].append(item)
        need(sorted(attempts) == list(range(1, len(attempts)+1)) and all(len(v) <= 3 and all(row == v[0] for row in v) for v in attempts.values()),
             'discovered transition identical recovery retries')
        ordered.append([attempts[i][0] for i in sorted(attempts)])
    status_trace = transfer.t.wire(probes[0]['request'])[1]['trace']
    need(status_trace not in traces, 'discovered transition separate discovery trace')
    prefix_rows = next((v for v in ordered if transfer.t.wire(v[0]['response'])[1]['payload'].get('kind') == 'CAPSULE'), None)
    need(prefix_rows is not None, 'discovered transition complete prefix')
    discovery.transcript(probes+prefix_rows, {'node-1': before, 'node-2': remote})
    ancestry_rows = next(v for v in ordered if v is not prefix_rows)
    reference = e.digest(f.canonical(dict(root=cap['root'], cut=cap['cut'], scope='retained-current-ancestry')))
    original = [(reference, remote[c.current(remote)[0]+'generation.gsr'], 'RECORD')]
    if 'ancestry.gsr' in members: original.append((e.digest(members['ancestry.gsr']), members['ancestry.gsr'], 'RECORD'))
    transfer.transcript(ancestry_rows, original, cap['root'], view, ballot, a.u.identity(before), a.u.identity(remote),
                        'discovered transition ancestry', chunk_bytes=4*e.MIB)
    return dict(node=node, traces=3, exchanges=len(probes)+sum(map(len, ordered)))


def inspect(root):
    walk = prelude(root); transcripts = []
    for node in ('node-5', 'node-4'):
        before = walk.group[node]
        walk.group[node] = adopted(before, walk.group['node-1'], node)
        walk.match(node+'-adopted')
        transcripts.append(recovery_transcript(root, node, before, walk.group['node-1'], walk.group[node]))
    need(c.inventory(Path(root)/'after-close/node-5') == walk.group['node-5'], 'discovered transition removed owner remains fenced')
    return dict(status='PARTIAL', scope='original-prelude-and-adoption-only', originalFirst=True,
                originalSlots=7, adoptions=2, snapshots=len(walk.snapshots), discovery=transcripts,
                fullHistoryQualified=False, autonomousElection=False, phase3Complete=False)


NEGATIVES = {
    'original-application': ('slot-4-applied/node-3/applied-end/application.image', 'admitted exact slot-4-applied: node-3'),
    'offline-owner-repaired': ('slot-7-settled/node-4/grants.gsr', 'admitted exact slot-7-settled: node-4'),
    'original-observation': ('observations.json', 'discovered transition original observations'),
    'removed-adoption-fence': ('node-5-adopted/node-5/grants.gsr', 'admitted exact node-5-adopted: node-5'),
    'survivor-selector': ('node-4-adopted/node-4/selector.gsr', 'admitted exact node-4-adopted: node-4'),
    'unrelated-owner': ('node-4-adopted/node-3/grants.gsr', 'admitted exact node-4-adopted: node-3'),
    'removed-owner-vote': ('after-close/node-5/grants.gsr', 'discovered transition removed owner remains fenced'),
    'missing-delivery': ('events.json', 'discovered transition delivered before adoption'),
    'early-adoption': ('events.json', 'discovered transition delivered before adoption'),
    'unverified-hint': ('wire.json', 'prefix discovery original cut'),
    'changed-source-bytes': ('wire.json', 'prefix exact data'),
}


def qualify(root):
    original = inspect(root); negatives = []
    for name, (filename, reason) in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-discovered-prelude-negative-') as temp:
            path = Path(temp)/'raw'; shutil.copytree(root, path)
            target = path/filename
            if filename == 'events.json':
                events = json.loads(target.read_text())
                if name == 'missing-delivery': events = [v for v in events if not (v['node'] == 'node-5' and v['event'] == 'NETWORK_RECEIVED')]
                else:
                    event = next(v for v in events if v['node'] == 'node-5' and v['event'] == 'ROUND_ADOPTED')
                    events.remove(event); events.insert(0, event)
                target.write_bytes(f.canonical(events))
            elif filename == 'wire.json':
                rows = json.loads(target.read_text()); events_path = path/'events.json'; events = json.loads(events_path.read_text())
                row = next(v for v in rows if transfer.t.wire(v['request'])[1]['sender']['node'] == 'node-5'
                           and transfer.t.wire(v['response'])[0] == ('STATUS' if name == 'unverified-hint' else 'CHUNK'))
                kind, response = transfer.t.wire(row['response']); old = e.digest(base64.b64decode(row['response']))
                if name == 'unverified-hint': response['payload']['cut']['index'] += 1
                else: response['payload'].update(bytes=base64.b64encode(b'changed').decode(), digest=e.digest(b'changed'))
                new = f.encode('wire', kind, response); row['response'] = base64.b64encode(new).decode()
                for event in events:
                    if event.get('response') == old: event['response'] = e.digest(new)
                target.write_bytes(f.canonical(rows)); events_path.write_bytes(f.canonical(events))
            else: target.write_bytes(b'[]' if name == 'original-observation' else b'changed')
            try: inspect(path)
            except ValueError as error: need(str(error) == reason, 'discovered transition unrelated negative: '+name+': '+str(error))
            else: raise ValueError('discovered transition accepted negative: '+name)
            negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('directory'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else inspect)(Path(args.directory)), sort_keys=True))
