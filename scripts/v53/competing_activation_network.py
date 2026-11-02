"""Original activation exchanges for successful and superseded bootstrap choices.

Publication/physical replay is mandatory. Incomplete SELECTED transfers remain
incomplete: their received bytes never become an installation acknowledgement.
This original-history gate does not qualify arbitrary fault/process schedules.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from . import competing_campaign_publication as publication

p=publication.p;net=publication.network;f=publication.f;disk=publication.disk
need=publication.need;sha=publication.sha


def point(replay,cap,name):
    found=[i for i,v in enumerate(replay.events[:cap['returnEvent']+1])
           if v==dict(node=cap['node'],event=name)]
    need(found,'competing activation original grant boundary: '+name)
    prior=max([-1]+[v['returnEvent'] for v in replay.by_basis.values()
                   if v['node']==cap['node'] and v['returnEvent']<cap['returnEvent']])
    need(prior<found[-1],'competing activation grant boundary belongs to another grant')
    return found[-1]


def end_of_source(replay,cap):
    # A newer promise alone does NOT end a frozen-source/record borrow.
    # Native exports retain exact old originals until retirement or close.
    ends=[]
    for value in replay.transactions:
        if value['node']!=cap['node']:continue
        starts=[i for i,v in enumerate(replay.events) if value['start']<=i<=value['end']
                and v==dict(node=cap['node'],event='SOURCE_RETIREMENT_CREATED')]
        need(len(starts)==len(value['decisions']),'competing activation exact retirement boundaries')
        ends.extend(at for at,decision in zip(starts,value['decisions']) if decision['identifier']==cap['basisId'])
    need(len(ends)<=1,'competing activation source retired twice')
    return ends[0] if ends else len(replay.events)


def original_source(replay,cap,reader):
    files=replay.original[cap['basisSha256']];source='sources/'+cap['basisId']+'/'
    raw=files[source+'source.gscp'];packet=disk.p.decode(raw)
    # The complete bootstrap physical gate proves these equal-cut local images.
    _,members,_=disk.current(replay.initial[reader])
    expected=[(sha(cap['basis']),cap['basis'],'RECORD'),(sha(cap['promise']),cap['promise'],'RECORD'),
              (sha(packet['capsuleBytes']),raw,'CAPSULE')]
    for digest in sorted(packet['images']):
        if members.get(digest+'.image')!=files[source+digest+'.image']:
            expected.append((digest,files[source+digest+'.image'],'APPLICATION'))
    return [expected]


def delivered_before(value,lower,upper,reason):
    # Phase.transfer checks response bytes and deliveries. Also require actual
    # original sends after the dependency, not merely late server responses.
    rows=value['ordered']
    need(all(lower<v['sent']<v['received']<v['offered']<v['delivered']<upper for v in rows
             if v['delivered'] is not None) and all(v['delivered'] is not None for v in rows),reason)
    need(all(rows[i]['delivered']<rows[i+1]['sent'] for i in range(len(rows)-1)),
         'competing activation transfer next before delivery')


def incomplete_selected(phase,attempts,rows,raw,ballot,reader,owner,lower,upper):
    """Two real replies and three unanswered COMMITs; synthesize no reply."""
    digest=sha(raw)
    found=[v for v in phase.sources if v['sender']==reader and v['peer']==owner and v['first']==digest]
    need(len(found)==1,'competing incomplete selection original transfer')
    value=found[0];observed=value['ordered']
    need(len(observed)==2 and len(raw)<=4*p.e.MIB and value['ballot']==ballot,
         'competing incomplete selection exact prefix')
    offer,chunk=observed;q=offer['request'];header={k:v for k,v in q.items() if k not in ('payload','sequence')}
    identifier=q['payload']['id']
    need(str(uuid.UUID(identifier))==identifier and uuid.UUID(identifier).int!=0,
         'competing incomplete selection original identity')
    def request(sequence,payload):return dict(header,sequence=sequence,payload=payload)
    def response(sequence,payload):return dict(request(sequence,payload),sender=q['recipient'],recipient=q['sender'])
    ask=dict(id=identifier,action='REQUEST',offset=0,digest=digest,bytes='')
    need(offer['kind']=='CHUNK' and offer['answer']=='SOURCE_OFFER' and q==request(1,ask) and
         offer['response']==response(1,dict(id=identifier,kind='RECORD',digest=digest,bytes=len(raw))) and
         chunk['kind']==chunk['answer']=='CHUNK' and chunk['request']==request(2,ask) and
         chunk['response']==response(2,dict(id=identifier,action='DATA',offset=0,digest=digest,
                                          bytes=base64.b64encode(raw).decode())),
         'competing incomplete selection exact original bytes')
    delivered_before(value,lower,upper,'competing incomplete selection causal prefix')
    need(offer['delivered']<chunk['sent'],'competing incomplete selection next before delivery')
    commits=[v for v in attempts if v['request']['trace']==q['trace'] and v['kind']=='TRANSFER_COMMIT']
    expected=request(3,dict(id=identifier,digest=digest))
    need(len(commits)==3 and all(v['request']==expected and v['received'] is not None and
             chunk['delivered']<v['sent']<v['received']<upper for v in commits) and
         not any(v['kind']=='TRANSFER_COMMIT' and v['request']['trace']==q['trace'] for v in rows),
         'competing incomplete selection commit must stay unanswered')
    need(all(commits[i]['received']<commits[i+1]['sent'] for i in range(2)),
         'competing incomplete selection ordered commit attempts')
    # No unaccounted sends can hide in the checked prefix either.
    all_attempts=[v for v in attempts if v['request']['trace']==q['trace']]
    need(len(all_attempts)==5 and [v['kind'] for v in all_attempts]==['CHUNK','CHUNK']+['TRANSFER_COMMIT']*3,
         'competing incomplete selection complete attempts')
    phase.sources.remove(value);phase.unfinished+=1
    return {v['sent'] for v in commits}


class Replay:
    def __init__(self,root):self.root=Path(root)

    def run(self):
        original=publication.Replay(self.root);precondition=original.run();r=original.preceding
        events=r.events;stop=original.activation_at
        # Maintenance already consumes the whole original copies/floor/release
        # interval. Keep its traces disjoint and account for them in the total.
        rows=[v for v in r.rows if v['request']['trace'] not in r.maintenance_traces]
        phase=net.net.Phase(events,rows,-1,stop,r.identities);self.phase=phase
        self.original=original;self.replay=r
        allowed=set();discoveries=0;campaigns=0;abandoned=0
        locals=sorted([v for v in r.by_basis.values() if v['ballot']['proposer']==v['node']],key=lambda v:v['capturedEvent'])
        for local in locals:
            node=local['node'];ballot=local['ballot'];campaigns+=1
            allocated=phase.at(node,'ALLOCATOR_BEFORE_WRITE')
            prior=f.decode(disk.current(r.initial[node])[1]['promise.gsr'],'records','PROMISE')['ballot']
            lower=-1
            for peer in sorted(set(r.identities)-{node}):
                cut=disk.current(r.initial[peer])[2]['capsule']['cut']
                previous=lower;lower=phase.probe(node,peer,prior,cut,lower,allocated);discoveries+=1
                probes=[v for v in r.rows if v['kind']=='STATUS_PROBE' and v['request']['sender']['node']==node
                        and v['request']['recipient']['node']==peer and v['request']['ballot']==prior]
                need(probes and all(previous<v['sent']<v['received']<v['offered']<v['delivered']<allocated for v in probes),
                     'competing activation discovery before allocation')
            grants=[v for v in r.by_basis.values() if v['ballot']==ballot and v['node']!=node]
            need(len(grants)==1,'competing activation bootstrap first remote majority')
            remote=grants[0];peer=remote['node']
            choice=[v for v in r.selections.values() if v['value']['ballot']==ballot]
            need(len(choice)==1,'competing activation one original local choice');choice=choice[0]
            bindings=[v for v in r.bindings if v['selection']==sha(choice['raw'])]
            own=next(v for v in bindings if v['node']==node)
            value=phase.transfer(peer,node,net.net.record(local['promise']),ballot,local['capturedEvent'],point(r,remote,'PROMISE_BEFORE_WRITE'))
            delivered_before(value,local['capturedEvent'],point(r,remote,'PROMISE_BEFORE_WRITE'),
                             'competing activation proposer promise before grant')
            delivered,trace,reply=phase.control('PREPARE',node,peer,dict(promise=sha(local['promise'])),
                'PROMISE',dict(basis=remote['basisSha256']),ballot,remote['returnEvent'],own['forced'])
            need(all(local['capturedEvent']<v['sent']<v['received']<point(r,remote,'PROMISE_BEFORE_WRITE') for v in reply),
                 'competing activation PREPARE before remote grant')
            value=phase.transfer(node,peer,original_source(r,remote,node),ballot,delivered,own['forced'])
            delivered_before(value,delivered,min(own['forced'],end_of_source(r,remote)),
                             'competing activation selected basis before choice')
            remote_choices=[v for v in bindings if v['node']==peer]
            if remote_choices:
                need(len(remote_choices)==1,'competing activation one remote choice')
                bound=remote_choices[0];selected_start=max(i for i,v in enumerate(events[:bound['forced']])
                    if v==dict(node=peer,event='SELECTED_BEFORE_WRITE'))
                requests=[v for v in r.attempts if v['kind']=='SELECTED' and v['request']['ballot']==ballot]
                need(requests and all(v['received'] is not None for v in requests),'competing activation original selected receive')
                received=min(v['received'] for v in requests)
                value=phase.transfer(peer,node,net.net.record(choice['raw']),ballot,own['forced'],selected_start)
                delivered_before(value,max(own['forced'],received),min(selected_start,end_of_source(r,local)),
                                 'competing activation original decision before remote selection')
                value=phase.transfer(peer,node,original_source(r,local,peer),ballot,local['capturedEvent'],selected_start)
                delivered_before(value,max(local['capturedEvent'],received),min(selected_start,end_of_source(r,local)),
                                 'competing activation original proposer basis before remote selection')
                installed=max(i for i,v in enumerate(events[:stop]) if v==dict(node=peer,event='INSTALL_BEFORE_RETURN'))
                local_start=min(i for i,v in enumerate(events) if i>own['forced'] and v==dict(node=node,event='INSTALL_RESERVED'))
                _,_,replies=phase.control('SELECTED',node,peer,dict(selection=sha(choice['raw'])),'INSTALL_ACK',
                    dict(selection=sha(choice['raw']),cut=choice['value']['cut']),ballot,installed,local_start,sequence=2,trace=trace)
                need(all(own['forced']<v['sent']<v['received']<selected_start for v in replies),
                     'competing activation original SELECTED before selection')
            else:
                requests=[v for v in r.attempts if v['kind']=='SELECTED' and v['request']['ballot']==ballot]
                need(len(requests)==1,'competing abandoned selection exact original attempt')
                attempt=requests[0];q=attempt['request']
                need(q['sender']==r.identities[node] and q['recipient']==r.identities[peer] and q['sequence']==2 and
                     q['trace']==trace and q['payload']==dict(selection=sha(choice['raw'])) and
                     attempt['received'] is not None and own['forced']<attempt['sent']<attempt['received']<stop and
                     not any(v['request']==q for v in r.rows),'competing abandoned selection cannot acknowledge')
                allowed.add(attempt['sent']);allowed|=incomplete_selected(phase,r.attempts,r.rows,choice['raw'],ballot,
                    peer,node,attempt['received'],min(stop,end_of_source(r,local)))
                abandoned+=1
        summary=phase.finish();traces=summary.pop('_traces')
        need(not traces&r.maintenance_traces,'competing activation distinct maintenance traces')
        after={v['request']['trace'] for v in r.attempts if v['sent']>stop}
        need(not (traces|r.maintenance_traces)&after,'competing activation trace reused after installation')
        pre=[v for v in r.attempts if v['sent']<stop]
        unanswered={v['sent'] for v in pre if not any(z['sent']==v['sent'] for z in r.rows)}
        need(unanswered==allowed,'competing activation complete unanswered attempts')
        covered=summary['exchanges']+sum(v['network']['exchanges'] for v in r.transactions)
        need(covered==len([v for v in r.rows if v['offered']<stop]),'competing activation complete exchange coverage')
        need(all(v['delivered'] is not None and v['sent']<v['received']<v['offered']<v['delivered']<stop
                 for v in r.rows if v['offered']<stop),'competing activation complete original delivery')
        published=precondition['publicationNetwork']
        need(covered+published['exchanges']+published['heartbeat']['responses']==len(r.rows),
             'competing whole history exact response coverage')
        return dict(status='PARTIAL',scope='competing-bootstrap-original-activation-network',precondition=precondition,
            campaigns=campaigns,discoveryProbes=discoveries,activation=summary,maintenanceExchanges=covered-summary['exchanges'],
            preinstallationExchanges=covered,abandonedSelections=abandoned,unansweredAttempts=len(allowed),
            wholeHistoryExchanges=len(r.rows),wholeHistoryAttempts=len(r.attempts),
            originalActivationNetworkQualified=True,fullNetworkQualified=True,
            completeExportLifetimesQualified=False,processDeathQualified=False,finalSourceCohortQualified=False,phase3Complete=False)


def validate(root):return Replay(root).run()


NEGATIVES={
    'missing-proposer-delivery':'restart network original source delivered',
    'basis-bytes':'restart network source exact data',
    'winning-decision-bytes':'restart network source exact data',
    'losing-decision-bytes':'competing incomplete selection exact original bytes',
    'missing-losing-commit':'competing incomplete selection commit must stay unanswered',
    'changed-losing-commit':'competing incomplete selection commit must stay unanswered',
    'invented-losing-commit':'competing incomplete selection exact prefix',
    'invented-losing-install':'competing abandoned selection cannot acknowledge',
    'early-winning-ack':'restart network exact delivered control',
    'missing-discovery-delivery':'discovered selection response delivered',
    'wrong-discovery-cut':'restart network exact delivered control',
    'wrong-prepare-sequence':'restart network exact delivered control',
    'wrong-selected-sequence':'restart network exact delivered control',
    'unaccounted-preinstall-send':'competing activation complete unanswered attempts',
}


def mutate(root,name):
    root=Path(root);need(name in NEGATIVES,'unknown competing activation mutation')
    events=p.n.read(root/'events.json');original=list(events);wire=p.n.read(root/'wire.json')
    links=p.n.read(root/publication.preceding.prefix.collection.FILE)
    def request(row):return net.n.transfer.t.wire(row['request'])
    def response(row):return net.n.transfer.t.wire(row['response'])
    def replace(row,field,kind,value):
        old=sha(base64.b64decode(row[field],validate=True));raw=f.encode('wire',kind,value);new=sha(raw)
        row[field]=base64.b64encode(raw).decode()
        for event in events:
            if event.get(field)==old:
                event[field]=new
                if field=='request' and event['event']=='NETWORK_SEND':event['bytes']=row[field]
    def boundary(point):return next(i for i,v in enumerate(events) if v['event']==point)
    winner=p.record(events[boundary('ROUND_INSTALLED')],'records','SELECTED')[1]['ballot']['proposer']
    # The original has one successful and one superseded local SELECTED.
    selected=[v for v in events if v['event']=='NETWORK_SEND' and v['kind']=='SELECTED']
    losing=next(v for v in selected if v['node']!=winner);_,lost=net.n.transfer.t.wire(losing['bytes'])
    transfer=next(v for v in wire if request(v)[0]=='CHUNK' and request(v)[1]['payload']['digest']==lost['payload']['selection'])
    lost_trace=request(transfer)[1]['trace']
    if name in ('missing-losing-commit','changed-losing-commit'):
        commits=[v for v in events if v['event']=='NETWORK_SEND' and v['kind']=='TRANSFER_COMMIT'
                 and net.n.transfer.t.wire(v['bytes'])[1]['trace']==lost_trace]
        h=commits[0]['request']
        if name=='missing-losing-commit':
            events.remove(commits[0]);events.remove(next(v for v in events if v['event']=='NETWORK_REQUEST' and v['request']==h))
        else:
            _,q=net.n.transfer.t.wire(commits[0]['bytes']);q['payload']['digest']='f'*64
            raw=f.encode('wire','TRANSFER_COMMIT',q)
            for v in events:
                if v.get('request')==h:
                    v['request']=sha(raw)
                    if v['event']=='NETWORK_SEND':v['bytes']=base64.b64encode(raw).decode()
    elif name.startswith('invented-losing-'):
        if name=='invented-losing-install':
            q=lost;kind='INSTALL_ACK';payload=dict(selection=q['payload']['selection'],cut=response(next(v for v in wire if request(v)[0]=='SELECTED'))[1]['payload']['cut'])
            request_bytes=losing['bytes']
        else:
            commit=next(v for v in events if v['event']=='NETWORK_SEND' and v['kind']=='TRANSFER_COMMIT'
                        and net.n.transfer.t.wire(v['bytes'])[1]['trace']==lost_trace)
            _,q=net.n.transfer.t.wire(commit['bytes']);kind='TRANSFER_COMMIT';payload=q['payload'];request_bytes=commit['bytes']
        raw=f.encode('wire',kind,dict(q,sender=q['recipient'],recipient=q['sender'],payload=payload))
        at=boundary('ROUND_INSTALLED');clock=events[at]['nanoTime']
        wire.append(dict(request=request_bytes,response=base64.b64encode(raw).decode(),withheld=False))
        events[at:at]=[dict(node=q['recipient']['node'],event='WIRE_RESPONSE',request=sha(base64.b64decode(request_bytes)),response=sha(raw),nanoTime=clock),
                      dict(node=q['sender']['node'],event='NETWORK_RECEIVED',kind=kind,response=sha(raw),nanoTime=clock)]
    elif name=='unaccounted-preinstall-send':
        row=next(v for v in events if v['event']=='NETWORK_SEND' and v['kind']=='STATUS_PROBE')
        at=boundary('ROUND_INSTALLED');events.insert(at,dict(row,nanoTime=events[at]['nanoTime']))
    elif name=='early-winning-ack':
        peer=next(v['node'] for v in events if v['event']=='INSTALL_BEFORE_RETURN' and v['node']!=winner)
        reply=next(v for v in wire if request(v)[0]=='SELECTED');h=sha(base64.b64decode(reply['response']))
        moved=[v for v in events if v.get('response')==h];need(len(moved)==2,'mutation winning reply event pair')
        for v in moved:events.remove(v)
        at=next(i for i,v in enumerate(events) if v['event']=='INSTALL_BEFORE_RETURN' and v['node']==peer)
        for v in moved:v['nanoTime']=events[at]['nanoTime']
        events[at:at]=moved
    elif name in ('wrong-prepare-sequence','wrong-selected-sequence'):
        kind='PREPARE' if name=='wrong-prepare-sequence' else 'SELECTED'
        row=next(v for v in wire if request(v)[0]==kind)
        for field in ('request','response'):
            frame,value=net.n.transfer.t.wire(row[field]);value['sequence']+=1;replace(row,field,frame,value)
    elif name=='wrong-discovery-cut':
        row=next(v for v in wire if request(v)[0]=='STATUS_PROBE');kind,value=response(row)
        value['payload']['cut']['entry']='e'*64;replace(row,'response',kind,value)
    elif name in ('missing-discovery-delivery','missing-proposer-delivery'):
        if name=='missing-discovery-delivery':row=next(v for v in wire if request(v)[0]=='STATUS_PROBE')
        else:row=next(v for v in wire if request(v)[0]=='TRANSFER_COMMIT')
        h=sha(base64.b64decode(row['response']));events.remove(next(v for v in events if v['event']=='NETWORK_RECEIVED' and v['response']==h))
    else:
        if name=='losing-decision-bytes':trace=lost_trace
        elif name=='winning-decision-bytes':
            q=net.n.transfer.t.wire(next(v['bytes'] for v in selected if v['node']==winner))[1]
            trace=request(next(v for v in wire if request(v)[0]=='CHUNK' and request(v)[1]['payload']['digest']==q['payload']['selection']))[1]['trace']
        else:
            # A BASIS reply follows the first successful remote PROMISE.
            basis=response(next(v for v in wire if request(v)[0]=='PREPARE'))[1]['payload']['basis']
            trace=request(next(v for v in wire if request(v)[0]=='CHUNK' and request(v)[1]['payload']['digest']==basis))[1]['trace']
        row=next(v for v in wire if request(v)[1]['trace']==trace and response(v)[0]=='CHUNK')
        kind,value=response(row);raw=bytearray(base64.b64decode(value['payload']['bytes']));raw[-1]^=1
        value['payload'].update(bytes=base64.b64encode(raw).decode(),digest=sha(raw));replace(row,'response',kind,value)
    # Preserve the original clocks and rebind capture indices to those same
    # events. Never renumber clocks or manufacture grant/capture observations.
    positions={id(v):i for i,v in enumerate(events)}
    for link in links:
        link['returnEvent']=positions[id(original[link['returnEvent']])]
        original_upper=link['capturedAfterEvent']
        link['capturedAfterEvent']=max(positions[id(v)] for v in original[:original_upper+1] if id(v) in positions)
    (root/'events.json').write_bytes(f.canonical(events));(root/'wire.json').write_bytes(f.canonical(wire))
    (root/publication.preceding.prefix.collection.FILE).write_bytes(f.canonical(links))


def qualify(root):
    root=Path(root);original=validate(root);inventory=publication.preceding.prefix.collection.h.inventory
    before=inventory(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-competing-activation-negative-') as temp:
            copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,name)
            try:validate(copied)
            except ValueError as error:need(str(error)==reason,'unrelated competing activation negative: '+name+': '+str(error))
            else:raise ValueError('competing activation mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(inventory(root)==before,'competing activation original changed')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('raw');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.raw),sort_keys=True))
