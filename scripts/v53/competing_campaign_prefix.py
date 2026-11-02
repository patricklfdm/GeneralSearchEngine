"""Derive competing bootstrap grants and every retained selection from originals.

No winning-node shortcut: abandoned selections and equal-counter/different-
proposer ballots are consumed too. This is a pre-install physical prefix, not
the subsequent retirement, installation, publication or full network gate.
"""
import argparse
import base64
from collections import defaultdict, deque
import copy
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from . import competing_grant_captures as collection
from . import competing_node_network as network
from . import grant_evidence as journal
from . import joining_same_view_ballot as ballot
from . import selection_journal_evidence as selection_writes

p, g, f, need = collection.p, collection.g, collection.f, collection.need
sha, disk = g.sha, g.disk


def transport(root, events, initial):
    identities = {node:p.n.future.identity(files) for node,files in initial.items()}
    cap = disk.current(initial['node-1'])[2]['capsule']
    header = dict(root=cap['root'], view=p.e.authority(cap['root'], cap['cut']['view']))
    entries = p.exchange.exchanges(root, events, -1, len(events), identities)
    network.raw_sends(events, entries, identities, header)
    by_offer = {v['offered']:v for v in entries}
    need(len(by_offer) == len(entries), 'competing prefix unique response event')
    pending, received, offered = defaultdict(deque), defaultdict(deque), defaultdict(deque)
    attempts = []
    for at,row in enumerate(events):
        kind = row['event']
        if kind == 'NETWORK_SEND':
            _, request = p.n.transfer.t.wire(row['bytes'])
            attempt = dict(sent=at, received=None, request=request, requestHash=row['request'], kind=row['kind'])
            attempts.append(attempt); pending[row['request']].append(attempt)
        elif kind == 'NETWORK_REQUEST':
            need(pending[row['request']], 'competing prefix request without send')
            attempt = pending[row['request']].popleft(); attempt['received'] = at
            received[row['request']].append(attempt)
        elif kind == 'WIRE_RESPONSE':
            value = by_offer[at]; digest = sha(base64.b64decode(value['row']['request'], validate=True))
            need(received[digest], 'competing prefix response without request')
            attempt = received[digest].popleft()
            value.update(sent=attempt['sent'], received=attempt['received'], requestHash=digest,
                         responseHash=row['response'], delivered=None)
            offered[value['request']['sender']['node'], value['answer'], row['response']].append(value)
        elif kind == 'NETWORK_RECEIVED':
            key = row['node'], row['kind'], row['response']
            need(offered[key], 'competing prefix delivery without response')
            offered[key].popleft()['delivered'] = at
    return entries, attempts


def prepare(files, incoming, original_basis, identifiers):
    """Observe only a fresh UUID and an externally bound ballot, derive all bytes."""
    _, members, packet = disk.current(files); cap = packet['capsule']
    owner = f.decode(files['node.gsr'], 'records', 'NODE')['identity']; node = owner['node']
    prior = disk.journal(files['grants.gsr'], cap['root'], node)
    promises = [v for kind,_,v in prior if kind == 'PROMISE']
    need(promises and journal.order(incoming) > journal.order(promises[-1]['ballot']),
         'competing prefix grant advances full ballot')
    need(files['pending.accept'] == disk.EMPTY, 'competing prefix pending tail requires later-state replay')
    observed = f.decode(original_basis, 'records', 'BASIS', cap['root']); identifier = observed['basisId']
    need(str(uuid.UUID(identifier)) == identifier and identifier not in identifiers
         and 'sources/'+identifier not in files, 'competing prefix fresh source identity')
    identifiers.add(identifier)
    value = dict(root=cap['root'], view=p.e.authority(cap['root'], cap['cut']['view']), ballot=incoming, basisId=identifier)
    promise = f.encode('records', 'PROMISE', value)
    wrapped = p.n.s.s.wrap(promise, files[p.n.s.FILE])
    packet_raw = disk.packet_bytes(cap, dict(packet['objects'], **{sha(wrapped):wrapped}), packet['images'])
    frozen = disk.p.decode(packet_raw)
    basis = f.encode('records', 'BASIS', dict(value, voter=node, cut=cap['cut'],
                     capsule=sha(frozen['capsuleBytes']), inventory=sha(frozen['indexBytes']), accepted=None))
    need(basis == original_basis, 'competing prefix exact derived basis')
    source = 'sources/'+identifier
    changed = dict(files, **{'grants.gsr':files['grants.gsr']+promise+basis, source:None, source+'/source.gscp':packet_raw})
    changed.update({source+'/'+h+'.image':members[h+'.image'] for h in packet['images']})
    return changed


class Replay:
    def __init__(self, root):
        self.root = Path(root); self.precondition = collection.validate(root)
        self.events = collection.timelines(root); self.initial = collection.originals(self.root)
        self.captures = g.collect(root, self.events, learner_retention=False)
        self.identities = {node:p.n.future.identity(files) for node,files in self.initial.items()}
        self.rows, self.attempts = transport(self.root, self.events, self.initial)
        self.by_basis = {}; self.original = {}; self.starts = {}
        for cap in self.captures:
            files,_,_ = g.inventory(self.root/cap['capture']/'replica')
            records = disk.journal(files['grants.gsr'], cap['root'], cap['node'])
            need(cap['basisSha256'] not in self.by_basis, 'competing prefix duplicate captured basis')
            cap = dict(cap, basis=records[-1][1], promise=records[-2][1])
            self.by_basis[cap['basisSha256']] = cap; self.original[cap['basisSha256']] = files
            starts = [i for i,v in enumerate(self.events[:cap['returnEvent']]) if v == dict(node=cap['node'], event='CURRENT_BEFORE_CAPTURE')]
            need(starts, 'competing prefix capture start'); self.starts[cap['basisSha256']] = starts[-1]
        self.selections = self.selected_records()

    def selected_records(self):
        result = {}; per_node = defaultdict(dict)
        snapshots = [(cap['node'], self.original[key]) for key,cap in self.by_basis.items()]
        snapshots += [(node, disk.inventory(self.root/'after-close'/node)) for node in self.initial]
        for node, files in snapshots:
            need(files['root.gsr'] == self.initial[node]['root.gsr'] and files['node.gsr'] == self.initial[node]['node.gsr'],
                 'competing prefix original journal owner')
            for kind, raw, value in disk.journal(files['grants.gsr'], self.by_basis[next(iter(self.by_basis))]['root'], node):
                if kind != 'SELECTED':continue
                digest = sha(raw); key = f.canonical(value['ballot'])
                need(key not in per_node[node] or per_node[node][key] == digest, 'competing prefix immutable selected pair')
                per_node[node][key] = digest; result[digest] = dict(raw=raw, value=value)
        bindings = []
        for node in self.initial:
            original = sorted(per_node[node].values(), key=lambda h:journal.order(result[h]['value']['ballot']))
            forces = [i for i,v in enumerate(self.events) if v == dict(node=node,event='SELECTED_FORCED')]
            need(len(original) == len(forces), 'competing prefix complete original selections')
            for digest,at in zip(original,forces):bindings.append(dict(node=node,selection=digest,forced=at))
        need(result, 'competing prefix original selection absent')
        self.bindings = bindings
        return result

    def grant_requests(self):
        # Failed/undelivered proposals still need an original local decision.
        # A request may not disappear from this audit merely because it lost.
        for attempt in self.attempts:
            q=attempt['request']; sender=q['sender']['node']
            if attempt['kind']=='PREPARE':
                local=[v for v in self.by_basis.values() if v['node']==sender and v['ballot']==q['ballot']]
                need(len(local)==1 and q['ballot']['proposer']==sender and
                     local[0]['capturedEvent']<attempt['sent'] and q['payload']==dict(promise=sha(local[0]['promise'])) and
                     q['view']==f.decode(local[0]['basis'],'records','BASIS')['view'],
                     'competing prefix PREPARE send lacks original grant')
            elif attempt['kind']=='SELECTED':
                selected=self.selections.get(q['payload']['selection'])
                need(selected is not None and selected['value']['ballot']==q['ballot'] and
                     selected['value']['view']==q['view'] and selected['value']['ballot']['proposer']==sender and
                     any(v['node']==sender and v['selection']==q['payload']['selection'] and v['forced']<attempt['sent']
                         for v in self.bindings), 'competing prefix SELECTED send lacks original decision')
        for cap in self.by_basis.values():
            who = cap['ballot']['proposer']
            need(who in self.identities and cap['ballot']['incarnation'] == self.identities[who]['storage'],
                 'competing prefix proposer incarnation')
            if who == cap['node']:continue
            local = [v for v in self.by_basis.values() if v['node'] == who and v['ballot'] == cap['ballot']]
            need(len(local) == 1, 'competing prefix original proposing grant')
            local = local[0]
            candidates = [v for v in self.attempts if v['kind'] == 'PREPARE' and v['request']['ballot'] == cap['ballot']
                          and v['request']['sender']['node'] == who and v['request']['recipient']['node'] == cap['node']]
            need(any(local['capturedEvent'] < v['sent'] < v['received'] < self.starts[cap['basisSha256']]
                     and v['request']['payload'] == dict(promise=sha(local['promise']))
                     for v in candidates if v['received'] is not None), 'competing prefix grant after original PREPARE')

    def choices(self):
        for bound in self.bindings:
            selected = self.selections[bound['selection']]['value']; sources = selected['sources']; node = bound['node']
            caps = []
            for ref in sources:
                cap = self.by_basis.get(ref['basisDigest'])
                need(cap is not None and cap['node'] == ref['voter'] and cap['basisId'] == ref['basisId']
                     and cap['ballot'] == selected['ballot'] and cap['capturedEvent'] < bound['forced'],
                     'competing prefix original selected grant')
                caps.append(cap)
            own = next((v for v in caps if v['node'] == node), None)
            need(own is not None, 'competing prefix selected local source')
            basis = f.decode(own['basis'], 'records', 'BASIS')
            journal.selected_binding(selected, f.decode(own['promise'],'records','PROMISE'), basis, own['basis'], node)
            need(all(f.decode(v['basis'],'records','BASIS')['cut'] == basis['cut'] and
                     f.decode(v['basis'],'records','BASIS')['accepted'] is None for v in caps),
                 'competing prefix selection requires later-state replay')
            expected = dict(root=basis['root'],view=basis['view'],ballot=basis['ballot'],cut=basis['cut'],nextEntry=None,sources=sources)
            need(selected == expected, 'competing prefix exact derived selection')
            lower = max(v['capturedEvent'] for v in caps)
            if node == selected['ballot']['proposer']:
                for cap in caps:
                    if cap['node'] == node:continue
                    replies = [v for v in self.rows if v['kind'] == 'PREPARE' and v['answer'] == 'PROMISE'
                               and v['request']['ballot'] == selected['ballot'] and v['request']['sender']['node'] == node
                               and v['request']['recipient']['node'] == cap['node'] and v['response']['payload'] == dict(basis=cap['basisSha256'])
                               and v['delivered'] is not None and cap['capturedEvent'] < v['offered'] < v['delivered'] < bound['forced']]
                    need(replies, 'competing prefix selection before delivered promise')
                    lower = max(lower, min(v['delivered'] for v in replies))
            else:
                proposer = selected['ballot']['proposer']
                earlier = [v for v in self.bindings if v['node'] == proposer and v['selection'] == bound['selection'] and v['forced'] < bound['forced']]
                requests = [v for v in self.attempts if v['kind'] == 'SELECTED' and v['request']['ballot'] == selected['ballot']
                            and v['request']['sender']['node'] == proposer and v['request']['recipient']['node'] == node
                            and v['request']['payload'] == dict(selection=bound['selection']) and v['received'] is not None
                            and any(b['forced'] < v['sent'] < v['received'] < bound['forced'] for b in earlier)]
                need(requests, 'competing prefix remote selection before proposer')
                lower = max(lower, min(v['received'] for v in requests))
            bound.update(scope=None,lower=lower,upper=len(self.events))
        return selection_writes.validate(self.events, self.bindings)

    def physical_prefix(self):
        stops = [i for i,v in enumerate(self.events) if v['event'] in ('INSTALL_RESERVED','FLOOR_RESERVED','SOURCE_RETIREMENT_CREATED')]
        need(stops, 'competing prefix continuation boundary absent'); stop = min(stops)
        need(all(v['capturedEvent'] < stop for v in self.by_basis.values()), 'competing prefix later grant needs continuation replay')
        opened=[(i,v) for i,v in enumerate(self.events[:stop]) if v['event']=='NODE_OPEN']
        need([v for _,v in opened]==[dict(node=node,event='NODE_OPEN') for node in sorted(self.initial)],
             'competing prefix exact opened owners')
        end=opened[-1][0]
        p.wait.lifecycle(p.n.read(self.root/'calls.json'),[v for v in self.events[:end+1] if v['event']!='NODE_OPEN'],self.initial)
        allowed=set(ballot.WRITES)|set(ballot.PROMISE)|set(selection_writes.WRITES)|{
            'CURRENT_BEFORE_CAPTURE','GRANT_BEFORE_RETURN',g.EVENT,'FLOOR_COPY_BEFORE_RETURN',
            'NETWORK_SEND','NETWORK_REQUEST','NETWORK_RECEIVED','WIRE_RESPONSE'}
        need(all(v['event'] in allowed or collection.network.capture_callback(v['event']) for v in self.events[end+1:stop]),
             'competing prefix unmodeled owner work')
        promise_points={i for cap in self.by_basis.values() for i in range(self.starts[cap['basisSha256']]+1,cap['returnEvent'])
                        if self.events[i]['node']==cap['node'] and self.events[i]['event'] in ballot.PROMISE}
        need(promise_points=={i for i,v in enumerate(self.events[:stop]) if v['event'] in ballot.PROMISE},
             'competing prefix unbound promise writes')
        group = copy.deepcopy(self.initial); actions = []; identifiers = set(); comparisons = 0
        self.allocations = []
        tx = ballot.allocations(self.events[:stop], tuple(group), None)
        need(all(any(cap['node']==row['node'] and row['end']<cap['capturedEvent'] for cap in self.by_basis.values()) for row in tx),
             'competing prefix unobserved allocation')
        actions.extend((v['end'],'allocate',v) for v in tx)
        actions.extend((v['returnEvent'],'grant',v) for v in self.by_basis.values())
        actions.extend((v['capturedEvent'],'compare',v) for v in self.by_basis.values())
        actions.extend((v['forced'],'select',v) for v in self.bindings if v['forced'] < stop)
        for _,kind,row in sorted(actions,key=lambda v:v[0]):
            node = row['node']; files = group[node]
            if kind == 'allocate':
                value = f.decode(files['allocator.gsr'],'records','ALLOCATOR')
                records = disk.journal(files['grants.gsr'],value['root'],node)
                counter = max(value['counter'], *[v['ballot']['counter'] for _,_,v in records])+1
                need(counter <= 2**63-2, 'competing prefix counter capacity')
                group[node] = dict(files, **{'allocator.gsr':f.encode('records','ALLOCATOR',dict(value,counter=counter))})
                self.allocations.append(dict(row,ballot=dict(counter=counter,proposer=node,
                    incarnation=self.identities[node]['storage'])))
            elif kind == 'grant':
                if row['ballot']['proposer'] == node:
                    need(f.decode(files['allocator.gsr'],'records','ALLOCATOR')['counter'] == row['ballot']['counter'],
                         'competing prefix local grant reservation')
                group[node] = prepare(files,row['ballot'],row['basis'],identifiers)
            elif kind == 'select':
                selected = self.selections[row['selection']]['raw']
                group[node] = dict(files, **{'grants.gsr':files['grants.gsr']+selected})
                disk.journal(group[node]['grants.gsr'],files['root.gsr'][16:48].hex(),node)
            else:
                need(files == self.original[row['basisSha256']], 'competing prefix exact captured files: '+node)
                comparisons += 1
        # Continuations consume the derived state, never a copied/final snapshot.
        self.group = group
        self.stop = stop
        return dict(capturedComparisons=comparisons,reservations=len(tx),throughEvent=stop-1,
                    nextBoundary=self.events[stop]['event'],stateSha256=sha(f.canonical({n:{k:None if v is None else sha(v) for k,v in files.items()} for n,files in group.items()})))

    def run(self):
        selections = self.choices(); self.grant_requests(); prefix = self.physical_prefix()
        return dict(status='PARTIAL',scope='competing-bootstrap-campaign-prefix',precondition=self.precondition,
                    capturedGrants=len(self.by_basis),competingBallots=len({f.canonical(v['ballot']) for v in self.by_basis.values()}),
                    distinctSelections=len(self.selections),selectionWrites=selections,physicalPrefix=prefix,
                    allCampaignsQualified=False,retirementQualified=False,installationQualified=False,
                    fullNetworkQualified=False,publicationQualified=False,phase3Complete=False)


def validate(root):return Replay(root).run()


NEGATIVES = {
    'missing-selected-write':'selection journal complete write order',
    'selected-write-after-force':'selection journal complete write order',
    'undelivered-promise':'competing prefix selection before delivered promise',
    'substituted-prepare-promise':'competing prefix PREPARE send lacks original grant',
    'substituted-remote-selection':'competing prefix SELECTED send lacks original decision',
    'superseded-selection-carried-entry':'competing prefix exact derived selection',
    'captured-extra-file':'competing prefix exact captured files: {node}',
    'captured-allocator':'competing prefix exact captured files: {node}',
    'missing-allocator-force':'joining ballot exact allocator force order',
    'missing-local-reservation':'competing prefix local grant reservation',
    'unmodeled-publication':'competing prefix unmodeled owner work',
    'unbound-promise':'competing prefix unbound promise writes',
    'unobserved-allocation':'competing prefix unobserved allocation',
}


def mutate(root, name):
    root=Path(root); events=collection.h.read_json(root,'events.json',16*g.MIB)
    links=g.json_file(root/collection.FILE)[1]
    def point(value):return next(i for i,v in enumerate(events) if v['event']==value)
    def omitted(at):
        events.pop(at)
        for row in links:
            for key in ('returnEvent','capturedAfterEvent'):
                need(row[key]!=at or key=='capturedAfterEvent','competing prefix mutation cannot remove grant return')
                if row[key]>=at:row[key]-=1
    if name=='missing-selected-write':omitted(point('SELECTED_WRITTEN'))
    elif name=='selected-write-after-force':
        a,b=point('SELECTED_WRITTEN'),point('SELECTED_FORCED')
        events[a]['event'],events[b]['event']=events[b]['event'],events[a]['event']
    elif name=='undelivered-promise':
        omitted(next(i for i,v in enumerate(events) if v['event']=='NETWORK_RECEIVED' and v['kind']=='PROMISE'))
    elif name in ('substituted-prepare-promise','substituted-remote-selection'):
        kind='PREPARE' if name=='substituted-prepare-promise' else 'SELECTED'
        at=next(i for i,v in enumerate(events) if v['event']=='NETWORK_SEND' and v['kind']==kind)
        old=events[at]['request']; _,request=p.n.transfer.t.wire(events[at]['bytes'])
        request['payload']['promise' if kind=='PREPARE' else 'selection']='0'*64
        raw=f.encode('wire',kind,request);encoded=base64.b64encode(raw).decode();new=sha(raw)
        for row in events:
            if row.get('request')==old:
                row['request']=new
                if row['event']=='NETWORK_SEND':row['bytes']=encoded
        wires=collection.h.read_json(root,'wire.json',32*g.MIB)
        for row in wires:
            if sha(base64.b64decode(row['request'],validate=True))==old:row['request']=encoded
        (root/'wire.json').write_bytes(f.canonical(wires))
    elif name in ('captured-extra-file','captured-allocator','superseded-selection-carried-entry'):
        link=links[0]
        if name=='superseded-selection-carried-entry':
            link=next(v for v in links if any(kind=='SELECTED' for kind,_,_ in disk.journal(
                g.snapshot.s.regular(root/v['capture']/'replica/grants.gsr',32*g.MIB),
                (root/v['capture']/'replica/root.gsr').read_bytes()[16:48].hex(),v['node'])))
        directory=root/link['capture']; replica=directory/'replica';_,metadata=g.json_file(directory/'capture.json')
        if name=='captured-extra-file':(replica/'unexpected-original').write_bytes(b'unowned')
        elif name=='captured-allocator':
            path=replica/'allocator.gsr';value=f.decode(path.read_bytes(),'records','ALLOCATOR')
            path.write_bytes(f.encode('records','ALLOCATOR',dict(value,counter=value['counter']+1)))
        else:
            path=replica/'grants.gsr';rows=disk.journal(path.read_bytes(),(replica/'root.gsr').read_bytes()[16:48].hex(),link['node'])
            at=next(i for i,v in enumerate(rows) if v[0]=='SELECTED');kind,_,value=rows[at]
            value=dict(value,nextEntry='0'*64);rows[at]=(kind,f.encode('records',kind,value),value)
            path.write_bytes(b''.join(v[1] for v in rows))
        _,inventory,_=g.inventory(replica)
        metadata['files']=[dict(name=k,identity=inventory[k]) for k in sorted(inventory)]
        encoded=f.canonical(metadata);(directory/'capture.json').write_bytes(encoded);link['sha256']=sha(encoded)
    elif name=='missing-allocator-force':omitted(point('ALLOCATOR_FORCED'))
    elif name=='missing-local-reservation':
        node=events[point('ALLOCATOR_BEFORE_WRITE')]['node']
        upper=next(i for i,v in enumerate(events) if v['node']==node and v['event']=='ALLOCATOR_BEFORE_RETURN')
        for i in range(upper,-1,-1):
            v=events[i]
            if v['node']==node and v['event'].startswith('ALLOCATOR_'):omitted(i)
    elif name=='unmodeled-publication':events[point('FLOOR_COPY_BEFORE_RETURN')]['event']='PUBLICATION_SELECTOR_FORCED'
    elif name in ('unbound-promise','unobserved-allocation'):
        at=point('FLOOR_RESERVED');node=events[at]['node'];time=events[at]['nanoTime']
        names=ballot.PROMISE if name=='unbound-promise' else ballot.WRITES
        extra=[dict(node=node,event=event,nanoTime=time) for event in names]
        events[at:at]=extra
        for row in links:
            for key in ('returnEvent','capturedAfterEvent'):
                if row[key]>=at:row[key]+=len(extra)
    else:raise ValueError('unknown competing prefix mutation')
    (root/'events.json').write_bytes(f.canonical(events));(root/collection.FILE).write_bytes(f.canonical(links))


def qualify(root):
    root=Path(root); original=validate(root); before=collection.h.inventory(root)
    need(original['competingBallots']>=2 and original['distinctSelections']>=2,'competing prefix original competing choices required')
    first=g.json_file(root/collection.FILE)[1][0]['node']; results=[]
    for name,expected in NEGATIVES.items():
        reason=expected.format(node=first)
        with tempfile.TemporaryDirectory(prefix='v53-competing-prefix-negative-') as temp:
            copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,name)
            try:validate(copied)
            except ValueError as error:
                need(str(error)==reason,'competing prefix unrelated negative: '+name+': '+str(error))
            else:raise ValueError('competing prefix mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(collection.h.inventory(root)==before,'competing prefix original changed')
    return dict(original=original,negatives=results)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('raw');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.raw),sort_keys=True))
