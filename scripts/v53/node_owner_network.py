"""Original network replay for a native cold reopen, including silent attempts.

Object incarnations are checked by the physical reader before projecting events
for the shared wire validator. Every request write retains its original bytes;
an unmatched request is diagnostic only and can never satisfy a source or vote.
"""
import argparse
import base64
from collections import defaultdict, deque
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import node_owner_evidence as p
from . import automatic_restart_network as a

n, c, e, f, need = a.n, a.c, a.e, a.f, a.need


def source(files, ballot, *, application=False):
    promise, basis, raw, packet = a.frozen(files, ballot)
    result = [(e.digest(basis),basis,'RECORD'),(e.digest(promise),promise,'RECORD'),(e.digest(packet['capsuleBytes']),raw,'CAPSULE')]
    if application:
        identifier = f.decode(basis,'records','BASIS')['basisId']
        result += [(h,files['sources/'+identifier+'/'+h+'.image'],'APPLICATION') for h in sorted(packet['images'])]
    return result


def unused_source(phase, value, expected, ballot, lower):
    """Validate a cancelled nonselected pull's actual prefix, never complete it."""
    phase.sources.remove(value); rows = value['ordered']; cursor = 0; identifiers = set()
    need(value['ballot']==ballot and lower < value['offered'],'node network unused source authority')
    first = rows[0]['request']
    def exchange(kind, answer, request, response):
        nonlocal cursor
        if cursor == len(rows): return False
        row = rows[cursor]; cursor += 1
        envelope = dict(first,sequence=cursor,payload=request)
        need(row['kind']==kind and row['answer']==answer and row['request']==envelope and row['response']==
             dict(envelope,sender=envelope['recipient'],recipient=envelope['sender'],payload=response),
             'node network exact unused source prefix')
        return True
    for reference,raw,kind in expected:
        if cursor == len(rows): break
        identifier = rows[cursor]['request']['payload']['id']
        need(str(uuid.UUID(identifier))==identifier and uuid.UUID(identifier).int!=0 and identifier not in identifiers,
             'node network unused source fresh object')
        identifiers.add(identifier); digest = e.digest(raw)
        exchange('CHUNK','SOURCE_OFFER',dict(id=identifier,action='REQUEST',offset=0,digest=reference,bytes=''),
            dict(id=identifier,kind=kind,digest=digest,bytes=len(raw)))
        for offset in range(0,len(raw),4*e.MIB):
            part = raw[offset:offset+4*e.MIB]
            if not exchange('CHUNK','CHUNK',dict(id=identifier,action='REQUEST',offset=offset,digest=digest,bytes=''),
                dict(id=identifier,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode())): break
        if not exchange('TRANSFER_COMMIT','TRANSFER_COMMIT',dict(id=identifier,digest=digest),dict(id=identifier,digest=digest)): break
    need(cursor==len(rows),'node network unused source extra message')
    size = sum(2+(len(raw)+4*e.MIB-1)//(4*e.MIB) for _,raw,_ in expected)
    if cursor < size or not all(value['arrivals']): phase.unfinished += 1


def activate(root, events, entries, start, stop, identities, number):
    before = a.group(root,'before-network' if number == 1 else 'before-reopen')
    installed = a.group(root,f'installed-{number}')
    chosen = (root/f'selected-{number}.gsr').read_bytes(); selected = f.decode(chosen,'records','SELECTED')
    ballot = selected['ballot']; voters = tuple(v['voter'] for v in selected['sources']); peer = voters[1]
    old = f.decode(c.current(before['node-1'])[1]['promise.gsr'],'records','PROMISE')['ballot']
    phase = a.Phase(events,entries,start,stop,identities)
    allocation = phase.at('node-1','ALLOCATOR_BEFORE_WRITE')
    discovery_end = allocation if number == 1 else phase.at('node-1','FLOOR_PARENT_FORCED')
    previous = start
    for voter in ('node-2','node-3'):
        previous = phase.probe('node-1',voter,old,c.current(before[voter])[2]['capsule']['cut'],previous,discovery_end)
    previous_voters = (tuple(v['voter'] for v in f.decode(c.current(before['node-1'])[1]['selected.gsr'],
        'records','SELECTED')['sources']) if number == 2 else voters)
    if number == 2: a.maintenance(phase,before,'node-1',old,previous,allocation,voters=previous_voters)
    local_promise = a.frozen(installed['node-1'],ballot)[0]
    phase.ordered('node-1',['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN','PROMISE_FORCED'])
    for voter in voters:
        phase.ordered(voter,['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN',
            'SELECTED_FORCED','SELECTED_BEFORE_RETURN','INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN'])
    if number == 2:
        old_peer = previous_voters[1]
        a.maintenance(phase,before,old_peer,ballot,allocation,phase.at(old_peer,'PROMISE_FORCED'),voters=previous_voters)
    local_selected = phase.at('node-1','SELECTED_FORCED')
    prepared = [v for v in ('node-2','node-3') if ('PREPARE','node-1',v) in phase.controls]
    need(prepared in (['node-2'],['node-2','node-3']) and peer in prepared,'node network bounded candidates')
    campaign_trace = None
    for ordinal,voter in enumerate(prepared,1):
        promise,basis,raw,packet = a.frozen(installed[voter],ballot)
        phase.ordered(voter,['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'])
        phase.transfer(voter,'node-1',a.record(local_promise),ballot,phase.at('node-1','BASIS_FORCED'),phase.at(voter,'PROMISE_FORCED'))
        delivery,trace,_ = phase.control('PREPARE','node-1',voter,dict(promise=e.digest(local_promise)),
            'PROMISE',dict(basis=e.digest(basis)),ballot,phase.at(voter,'GRANT_BEFORE_RETURN'),stop,sequence=ordinal,trace=campaign_trace)
        if campaign_trace is None: campaign_trace = trace
        if voter == peer:
            phase.transfer('node-1',voter,[source(installed[voter],ballot)],ballot,delivery,local_selected)
        else:
            # A delayed unused reply may never be pulled, or may finish only
            # its basis/promise and capsule offer. Neither supplies SELECTED.
            pulls = [v for v in phase.sources if v['sender']=='node-1' and v['peer']==voter and v['first']==e.digest(basis)]
            need(len(pulls)<=1,'node network one unused source')
            if pulls: unused_source(phase,pulls[0],source(installed[voter],ballot),ballot,delivery)
            need(not any(v['node']==voter and v['event'] in ('SELECTED_FORCED','INSTALL_SELECTOR_FORCED') for v in events[start+1:stop]),
                 'node network unused grant cannot install')
    phase.transfer(peer,'node-1',a.record(chosen),ballot,local_selected,phase.at(peer,'SELECTED_FORCED'))
    source_packet = a.frozen(installed['node-1'],ballot)[3]
    prior_images = c.current(before[peer])[2]['images']
    needs_image = any(h not in prior_images for h in source_packet['images'])
    phase.transfer(peer,'node-1',[source(installed['node-1'],ballot,application=needs_image)],ballot,
        phase.at('node-1','BASIS_FORCED'),phase.at(peer,'SELECTED_FORCED'))
    delivered,_,_ = phase.control('SELECTED','node-1',peer,dict(selection=e.digest(chosen)),
        'INSTALL_ACK',dict(selection=e.digest(chosen),cut=selected['cut']),ballot,phase.at(peer,'INSTALL_BEFORE_RETURN'),stop,
        sequence=len(prepared)+1,trace=campaign_trace)
    need(delivered < phase.at('node-1','INSTALL_SELECTOR_FORCED'),'node network installed peer before local')
    result = phase.finish(); result['voters'] = list(voters); return result


def request_attempts(events, entries, identities, root, view):
    """Correlate write/read/response boundaries without inventing delivery."""
    sent = defaultdict(list); reads = defaultdict(deque); available = defaultdict(deque)
    responses = {v['offered']:v for v in entries}
    for at, row in enumerate(events):
        if row['event'] == 'NETWORK_SEND':
            need(set(row)=={'node','event','request','kind','bytes'},'node network original send shape')
            raw = base64.b64decode(row['bytes'],validate=True); kind, request = n.transfer.t.wire(row['bytes'])
            need(row['request']==e.digest(raw) and row['kind']==kind and row['node']==request['sender']['node']
                 and request['sender']==identities.get(request['sender']['node'])
                 and request['recipient']==identities.get(request['recipient']['node'])
                 and request['sender']!=request['recipient'] and request['root']==root and request['view']==view,
                 'node network original send bytes/identity')
            value = dict(at=at,kind=kind,request=request,raw=raw,received=None,response=None)
            sent[row['request']].append(value); available[row['request']].append(value)
            need(len(sent[row['request']])<=3,'node network bounded identical writes')
        elif row['event'] == 'NETWORK_REQUEST':
            need(set(row)=={'node','event','request','kind'},'node network original receive shape')
            need(available[row['request']],'node network received request without write')
            value = available[row['request']].popleft()
            need(value['at']<at and value['kind']==row['kind'] and value['request']['recipient']['node']==row['node'],
                 'node network original request receipt')
            value['received']=at; reads[row['request']].append(value)
        elif at in responses:
            entry = responses[at]; digest = e.digest(base64.b64decode(entry['row']['request'],validate=True))
            need(reads[digest],'node network response without original receipt')
            value = reads[digest].popleft(); need(value['received']<at,'node network response before receipt')
            value['response']=at
    return sent


def silent_attempts(root, events, unanswered, phases, identities, traces):
    results = []; classified = set()
    for start,stop,index,rejected,voters in phases:
        rows = unanswered.get(rejected)
        need(rows and all(start < v['at'] < stop and v['kind']=='FUTURE_RETENTION_INTENT' for v in rows),
             'node network exact unused retention attempt')
        classified.add(rejected); results.append(dict(index=index,kind='FUTURE_RETENTION_INTENT',attempts=len(rows)))
        if voters[1] == 'node-2': continue
        # The publication collector tries node 2 before node 3. Its initial
        # CHECKPOINT_ACK requests are expected bytes derived from each original
        # local statement, but no response from that unselected owner counts.
        applied = c.inventory(root/f'applied-{index}/node-1')
        ballot = f.decode(c.current(applied)[1]['selected.gsr'],'records','SELECTED')['ballot']
        lower = next(i for i in range(start+1,stop) if events[i]==dict(node='node-1',event='APPLY_ACK_DIRECTORY_FORCED'))
        upper = next(i for i in range(start+1,stop) if events[i]==dict(node='node-1',event='PUBLICATION_SELECTOR_FORCED'))
        for name,raw in applied.items():
            if not name.startswith('applied-end/') or not name.endswith('statement.gsr'): continue
            statement = f.decode(raw,'records','CHECKPOINT')
            ack = f.encode('records','CHECKPOINT_ACK',dict(root=statement['root'],voter='node-2',incarnation=identities['node-2']['storage'],
                cut=statement['end'],statement=e.digest(raw)))
            found = [(digest,values) for digest,values in unanswered.items() if values[0]['kind']=='CHUNK'
                and lower < values[0]['at'] < upper and values[0]['request']['payload']['digest']==e.digest(ack)]
            need(len(found)==1,'node network original unused checkpoint lookup')
            digest,values = found[0]; request = values[0]['request']; trace = request['trace']; identifier = request['payload']['id']
            need(trace not in traces and str(uuid.UUID(trace))==trace and uuid.UUID(trace).int!=0
                 and str(uuid.UUID(identifier))==identifier and uuid.UUID(identifier).int!=0,'node network fresh unused checkpoint trace')
            traces.add(trace)
            need(request==dict(root=statement['root'],view=e.authority(statement['root'],statement['end']['view']),ballot=ballot,
                 sender=identities['node-1'],recipient=identities['node-2'],trace=trace,sequence=1,
                 payload=dict(id=identifier,action='REQUEST',offset=0,digest=e.digest(ack),bytes=''))
                 and all(lower < v['at'] < upper and v['raw']==values[0]['raw'] for v in values),
                 'node network exact unused checkpoint request')
            classified.add(digest); results.append(dict(index=index,kind='CHECKPOINT_ACK_LOOKUP',attempts=len(values)))
    need(classified==set(unanswered),'node network unclassified silent request')
    return results


def request_phases(sent, boundaries, originals):
    for rows in sent.values():
        for row in rows:
            matches = [(ordinal,start,stop) for ordinal,(start,stop) in enumerate(boundaries) if start < row['at'] < stop]
            need(len(matches)==1,'node network request outside history')
            ordinal,start,stop = matches[0]
            need(all(start < row[k] < stop for k in ('received','response') if row[k] is not None),
                 'node network request crosses completed phase')
            if row['request']['sender']['node']=='node-1':
                need(originals[row['at']]['incarnation']==(1 if ordinal<3 else 2),'node network request wrong node lifetime')


def validate(root):
    root = Path(root); physical = p.validate(root)
    # No original file is rewritten; only this validated extra event field is
    # omitted when invoking the existing strict exchange/arrival reader.
    originals = n.read(root/'events.json')
    events = [{k:v for k,v in row.items() if k!='incarnation'} for row in originals]
    identities = {node:n.future.identity(files) for node,files in a.group(root,'before-network').items()}
    entries = a.x.exchanges(root,events,-1,len(events),identities); a.deliveries(events,entries)
    selected = f.decode((root/'selected-1.gsr').read_bytes(),'records','SELECTED')
    need(all(v['request']['root']==selected['root'] and v['request']['view']==selected['view'] for v in entries),'node network original authority')
    sent = request_attempts(events,entries,identities,selected['root'],selected['view'])
    held = [(i,row) for i,row in enumerate(events) if row['event'].startswith('ROUND_')]
    boundaries = [(-1,held[0][0]),(held[0][0],held[2][0]),(held[2][0],held[5][0]),
        (held[5][0],held[6][0]),(held[6][0],held[8][0]),(held[8][0],held[11][0])]
    request_phases(sent,boundaries,originals)
    results = []; traces = set(); silent = []
    for ordinal,(start,stop) in enumerate(boundaries):
        if ordinal in (0,3):
            result = activate(root,events,entries,start,stop,identities,1 if ordinal==0 else 2)
        else:
            index = {1:1,2:2,4:3,5:4}[ordinal]
            stage = {1:'installed-1',2:'published-1',3:'installed-2',4:'published-3'}[index]
            voters = tuple(v['voter'] for v in f.decode(c.current(a.group(root,stage)['node-1'])[1]['selected.gsr'],'records','SELECTED')['sources'])
            result = a.slot(root,events,entries,start,stop,identities,index,before_stage=stage,voters=voters,received_requests=True)
            silent.append((start,stop,index,result.pop('_rejected'),voters))
        own = result.pop('_traces')
        need(not traces.intersection(own) and all(str(uuid.UUID(v))==v and uuid.UUID(v).int!=0 for v in own),'node network distinct phase traces')
        traces.update(own); results.append(result)
    need(sum(v['exchanges'] for v in results)==len(entries),'node network complete response coverage')
    # Silent writes are classified from exact raw requests below; they are
    # deliberately excluded from all dependent source/quorum checks above.
    unanswered = {digest:rows for digest,rows in sent.items() if not any(v['response'] is not None for v in rows)}
    silent = silent_attempts(root,events,unanswered,silent,identities,traces)
    transfers=sum(v['transfers'] for v in results); incomplete=sum(v['unusedIncompleteTransfers'] for v in results)
    return dict(status='PASS',scope='one-native-node-cold-reopen-history',originalFirst=True,physical=physical,
        phases=results,exchanges=len(entries),transfers=transfers,completeTransfers=transfers-incomplete,unusedIncompleteTransfers=incomplete,
        requests=sum(len(v) for v in sent.values()),silentRequests=sum(v['attempts'] for v in silent),silent=silent,
        fullWireReplay=True,processRestart=False,publicRuntime=False,phase3Complete=False)


SHARED_NEGATIVES = {name:a.NEGATIVES[name] for name in (
    'missing-discovery','discovery-cut','missing-response-row','invented-delivery','early-delivery',
    'source-bytes','source-offer','basis-reply','reply-identity','vote-receipt','apply-statement',
    'future-revision','future-digest','early-quorum','wrong-quorum','early-publication','missing-retirement',
    'missing-parent-ack','bootstrap-force')}
NEGATIVES = dict(SHARED_NEGATIVES, **{
    'missing-send-bytes':'node network original send shape',
    'missing-send':'node network received request without write',
    'missing-receipt':'node network response without original receipt',
    'early-request-receipt':'node network received request without write',
    'four-write-attempts':'node network bounded identical writes',
    'cross-phase-request':'node network request crosses completed phase',
    'old-lifetime-request':'node network request wrong node lifetime',
    'missing-silent-retention':'node network exact unused retention attempt',
    'silent-checkpoint-reference':'node network original unused checkpoint lookup',
    'unused-prefix-data':'node network exact unused source prefix',
    'selected-image-data':'restart network source exact data',
})


def mutate(root, name):
    if name in SHARED_NEGATIVES:
        a.mutate(root,name)
        if name == 'invented-delivery':
            events = n.read(root/'events.json'); events[-1]['incarnation']=2
            (root/'events.json').write_bytes(f.canonical(events))
        return
    events = n.read(root/'events.json'); rows = n.read(root/'wire.json')
    sent = [v for v in events if v['event']=='NETWORK_SEND']; read = [v for v in events if v['event']=='NETWORK_REQUEST']
    answered = {e.digest(base64.b64decode(v['request'],validate=True)) for v in rows}
    if name == 'missing-send-bytes': sent[0].pop('bytes')
    elif name == 'missing-send': events.remove(sent[0])
    elif name == 'missing-receipt': events.remove(read[0])
    elif name == 'early-request-receipt':
        row=read[0]; events.remove(row); events.insert(events.index(sent[0]),row)
    elif name == 'four-write-attempts':
        at=events.index(sent[0])
        for _ in range(3): events.insert(at,dict(sent[0]))
    elif name == 'cross-phase-request':
        row=next(v for v in sent if v['kind']=='ACCEPT'); events.remove(row)
        at=next(i for i,v in enumerate(events) if v['event']=='ROUND_INSTALLED'); events.insert(at,row)
    elif name == 'old-lifetime-request':
        row=next(v for v in sent if v['node']=='node-1' and v['incarnation']==2); events.remove(row); row['incarnation']=1
        at=next(i for i,v in enumerate(events) if v['event']=='NODE_CLOSED'); events.insert(at,row)
    elif name == 'missing-silent-retention':
        row=next(v for v in sent if v['kind']=='FUTURE_RETENTION_INTENT' and v['request'] not in answered)
        events=[v for v in events if not (v['event'] in ('NETWORK_SEND','NETWORK_REQUEST') and v['request']==row['request'])]
    elif name == 'silent-checkpoint-reference':
        row=next(v for v in sent if v['kind']=='CHUNK' and v['request'] not in answered); old=row['request']
        request=f.decode(base64.b64decode(row['bytes'],validate=True),'wire','CHUNK');request['payload']['digest']='0'*64
        raw=f.encode('wire','CHUNK',request)
        for v in events:
            if v['event'] in ('NETWORK_SEND','NETWORK_REQUEST') and v['request']==old:
                v['request']=e.digest(raw)
                if v['event']=='NETWORK_SEND':v['bytes']=base64.b64encode(raw).decode()
    elif name in ('unused-prefix-data','selected-image-data'):
        if name=='unused-prefix-data':
            selected=f.decode((root/'selected-2.gsr').read_bytes(),'records','SELECTED')
            basis=a.frozen(c.inventory(root/'installed-2/node-2'),selected['ballot'])[1]
            row=next(v for v in rows if n.transfer.t.wire(v['request'])[0]=='CHUNK'
                and n.transfer.t.wire(v['request'])[1]['payload']['digest']==e.digest(basis)
                and n.transfer.t.wire(v['response'])[0]=='CHUNK')
        else:
            offer=next(v for v in rows if n.transfer.t.wire(v['response'])[0]=='SOURCE_OFFER'
                and n.transfer.t.wire(v['response'])[1]['payload']['kind']=='APPLICATION')
            identifier=n.transfer.t.wire(offer['request'])[1]['payload']['id']
            row=next(v for v in rows if n.transfer.t.wire(v['request'])[0]=='CHUNK'
                and n.transfer.t.wire(v['request'])[1]['payload']['id']==identifier and n.transfer.t.wire(v['response'])[0]=='CHUNK')
        old=row['response']; old_digest=e.digest(base64.b64decode(old,validate=True))
        kind,value=n.transfer.t.wire(old);value['payload'].update(bytes=base64.b64encode(b'changed').decode(),digest=e.digest(b'changed'))
        raw=f.encode('wire',kind,value)
        for v in rows:
            if v['response']==old:v['response']=base64.b64encode(raw).decode()
        for v in events:
            if v['event'] in ('WIRE_RESPONSE','NETWORK_RECEIVED') and v['response']==old_digest:v['response']=e.digest(raw)
    else: raise ValueError('unknown node network mutation')
    (root/'events.json').write_bytes(f.canonical(events));(root/'wire.json').write_bytes(f.canonical(rows))


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    cases={**{name:pair[1] for name,pair in p.NEGATIVES.items()},**NEGATIVES}
    for name,reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-node-network-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path);(mutate if name in NEGATIVES else p.mutate)(path,name)
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'node network unrelated negative '+name+': '+str(error))
            else:raise ValueError('node network accepted negative '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
