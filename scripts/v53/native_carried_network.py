"""Original-wire replay across a whole-group carried DATA crash and recovery."""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import native_carried_process_evidence as process
from . import node_owner_network as net
from . import node_current_network as current

p=process.physical
a,n,c,e,f,need=net.a,net.n,net.c,net.e,net.f,net.need


class View:
    """Map shared reader names to retained files without changing originals."""
    def __init__(self,root): self.root=root

    def __truediv__(self,name):
        if name=='before-reopen':name='life-2-opened'
        elif name.startswith('selected-'):name='life-'+name[len('selected-'):-4]+'-installed-1.gsr'
        elif name.startswith('installed-'):name='life-'+name[len('installed-'):]+'-installed-1'
        elif name.startswith(('applied-','published-')):name='life-2-'+name
        return self.root/name


def maintenance(phase,before,owner,ballot,lower,upper,*,voters,after_accept=False):
    # Physical replay already derives old-end retirement and preserves the
    # exact selected tail. Staging is not a governing floor copy.
    copies={node:p.staging.without_staging(files) if node in voters else files for node,files in before.items()}
    p.current.maintenance_network(phase,copies,owner,ballot,lower,upper,voters=voters,after_accept=after_accept)


def activate(root,events,entries,start,stop,identities,life):
    before=a.group(root,'before-network' if life==1 else 'before-reopen')
    installed=a.group(root,f'installed-{life}')
    chosen=(root/f'selected-{life}.gsr').read_bytes();selected=f.decode(chosen,'records','SELECTED')
    ballot=selected['ballot'];voters=tuple(v['voter'] for v in selected['sources']);peer=voters[1]
    old=f.decode(c.current(before['node-1'])[1]['promise.gsr'],'records','PROMISE')['ballot']
    phase=a.Phase(events,entries,start,stop,identities);allocation=phase.at('node-1','ALLOCATOR_BEFORE_WRITE')
    previous=start
    for voter in ('node-2','node-3'):
        previous=phase.probe('node-1',voter,old,c.current(before[voter])[2]['capsule']['cut'],previous,allocation)
    if life==2:
        projected=p.maintain(before,p.NODES)
        for node in p.NODES:
            floors=[i for i in range(start+1,stop) if events[i].get('node')==node and events[i]['event']=='FLOOR_PARENT_FORCED']
            if projected[node]==before[node]:
                need(not floors,'native carried no invented pre-grant maintenance');continue
            need(len(floors)==1,'native carried required pre-grant maintenance')
            old_voters=tuple(v['voter'] for v in f.decode(c.current(before[node])[1]['selected.gsr'],'records','SELECTED')['sources'])
            maintenance(phase,before,node,old if node=='node-1' else ballot,
                        previous if node=='node-1' else allocation,phase.at(node,'PROMISE_FORCED'),voters=old_voters)
    local_promise=a.frozen(installed['node-1'],ballot)[0]
    phase.ordered('node-1',['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN','PROMISE_FORCED'])
    for voter in voters:
        phase.ordered(voter,['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN',
            'SELECTED_FORCED','SELECTED_BEFORE_RETURN','INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN'])
    local_selected=phase.at('node-1','SELECTED_FORCED')
    prepared=[v for v in ('node-2','node-3') if ('PREPARE','node-1',v) in phase.controls]
    need(prepared in (['node-2'],['node-2','node-3']) and peer in prepared,'native carried received campaign candidates')
    campaign_trace=None
    for ordinal,voter in enumerate(prepared,1):
        promise,basis,raw,packet=a.frozen(installed[voter],ballot)
        phase.ordered(voter,['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'])
        phase.transfer(voter,'node-1',a.record(local_promise),ballot,phase.at('node-1','BASIS_FORCED'),phase.at(voter,'PROMISE_FORCED'))
        if voter!=peer and not any(v['deliveries'] for v in phase.controls['PREPARE','node-1',voter]):
            trace=net.unreceived_prepare(phase,voter,local_promise,basis,ballot,
                phase.at(voter,'GRANT_BEFORE_RETURN'),stop,ordinal,campaign_trace);delivery=None
        else:
            delivery,trace,_=phase.control('PREPARE','node-1',voter,dict(promise=e.digest(local_promise)),
                'PROMISE',dict(basis=e.digest(basis)),ballot,phase.at(voter,'GRANT_BEFORE_RETURN'),stop,
                sequence=ordinal,trace=campaign_trace)
        if campaign_trace is None:campaign_trace=trace
        if voter==peer:phase.transfer('node-1',voter,[net.source(installed[voter],ballot)],ballot,delivery,local_selected)
        else:
            pulls=[v for v in phase.sources if v['sender']=='node-1' and v['peer']==voter and v['first']==e.digest(basis)]
            need(len(pulls)<=1,'native carried one unused source')
            if pulls:net.unused_source(phase,pulls[0],net.source(installed[voter],ballot),ballot,delivery)
            need(not any(v.get('node')==voter and v['event'] in ('SELECTED_FORCED','INSTALL_SELECTOR_FORCED')
                         for v in events[start+1:stop]),'native carried unused grant cannot install')
    phase.transfer(peer,'node-1',a.record(chosen),ballot,local_selected,phase.at(peer,'SELECTED_FORCED'))
    packet=a.frozen(installed['node-1'],ballot)[3];prior_images=c.current(before[peer])[2]['images']
    phase.transfer(peer,'node-1',[net.source(installed['node-1'],ballot,
        application=any(h not in prior_images for h in packet['images']))],ballot,
        phase.at('node-1','BASIS_FORCED'),phase.at(peer,'SELECTED_FORCED'))
    delivered,_,_=phase.control('SELECTED','node-1',peer,dict(selection=e.digest(chosen)),
        'INSTALL_ACK',dict(selection=e.digest(chosen),cut=selected['cut']),ballot,phase.at(peer,'INSTALL_BEFORE_RETURN'),stop,
        sequence=len(prepared)+1,trace=campaign_trace)
    need(delivered<phase.at('node-1','INSTALL_SELECTOR_FORCED'),'native carried installed peer before local')
    result=phase.finish();result['voters']=list(voters);return result


def interrupted(root,events,entries,start,stop,identities,point):
    before=a.group(root,'installed-1');selected=f.decode(c.current(before['node-1'])[1]['selected.gsr'],'records','SELECTED')
    ballot=selected['ballot'];voters=tuple(v['voter'] for v in selected['sources']);peer=voters[1]
    phase=a.Phase(events,entries,start,stop,identities)
    if point in ('NATIVE_RETIREMENT_CERTIFICATE_RETAINED','ACCEPT_RENAMED'):return phase.finish()
    frames,_=p.pending(c.inventory(root/'at-cut'/'node-1'))
    def observed(node,kind):return f.canonical(dict(root=selected['root'],voter=node,incarnation=identities[node]['storage'],
                                                 phase=kind,record=e.digest(frames[kind])))
    local=phase.at('node-1','ACCEPT_PARENT_FORCED');remote=phase.at(peer,'ACCEPT_PARENT_FORCED')
    proof=phase.at('node-1','PROOF_RENAMED' if point=='PROOF_RENAMED' else 'PROOF_PARENT_FORCED')
    for kind in ('ACCEPT','ENTRY','PAYLOAD'):phase.transfer(peer,'node-1',a.record(frames[kind]),ballot,local,remote)
    phase.transfer(peer,'node-1',a.record(observed('node-1','ACCEPT'),True),ballot,local,remote)
    phase.transfer('node-1',peer,a.record(observed(peer,'ACCEPT'),True),ballot,remote,proof)
    phase.control('ACCEPT','node-1',peer,dict(acceptance=e.digest(frames['ACCEPT'])),'ACCEPT_ACK',
        dict(entry=e.digest(frames['ENTRY']),receipt=e.digest(observed(peer,'ACCEPT'))),ballot,remote,proof)
    maintenance(phase,before,'node-1',ballot,local,proof,voters=voters,after_accept=True)
    if point=='PROOF_RENAMED':return phase.finish()
    peer_proof=phase.at(peer,'PROOF_PARENT_FORCED');certificate=phase.at('node-1','CERTIFICATE_PARENT_FORCED')
    maintenance(phase,before,peer,ballot,remote,peer_proof,voters=voters,after_accept=True)
    phase.transfer(peer,'node-1',a.record(frames['PROOF']),ballot,proof,peer_proof)
    phase.transfer(peer,'node-1',a.record(observed('node-1','ACCEPT'),True),ballot,remote,peer_proof)
    phase.transfer('node-1',peer,a.record(observed(peer,'PROOF'),True),ballot,peer_proof,certificate)
    phase.control('PROOF','node-1',peer,dict(proof=e.digest(frames['PROOF'])),'PROOF_ACK',
        dict(entry=e.digest(frames['ENTRY']),receipt=e.digest(observed(peer,'PROOF'))),ballot,peer_proof,certificate)
    return phase.finish()


def request_phases(sent,boundaries,originals,entries=()):
    for attempts in sent.values():
        for row in attempts:
            matches=[(i,start,stop) for i,(start,stop) in enumerate(boundaries) if start<row['at']<stop]
            need(len(matches)==1,'native carried request outside history')
            ordinal,start,stop=matches[0];life=1 if ordinal<2 else 2
            need(all(start<row[k]<stop for k in ('received','response') if row[k] is not None),
                 'native carried request crosses phase or death')
            need(all(originals[row[k]]['incarnation']==life for k in ('at','received','response') if row[k] is not None),
                 'native carried request wrong group lifetime')
    for entry in entries:
        life=originals[entry['offered']]['incarnation']
        need(all(originals[at]['incarnation']==life for at in entry['deliveries']),
             'native carried delivery crosses group death')


def replay(root,point):
    original=process.read(root/'events.json');events=[{k:v for k,v in row.items() if k!='incarnation'} for row in original]
    view=View(root);identities={node:n.future.identity(files) for node,files in a.group(view,'before-network').items()}
    entries=a.x.exchanges(root,events,-1,len(events),identities);a.deliveries(events,entries)
    selected=f.decode((view/'selected-1.gsr').read_bytes(),'records','SELECTED')
    need(all(v['request']['root']==selected['root'] and v['request']['view']==selected['view'] for v in entries),
         'native carried original network authority')
    sent=net.request_attempts(events,entries,identities,selected['root'],selected['view'])
    held=[i for i,v in enumerate(events) if v['event'].startswith('ROUND_')]
    death=next(i for i,v in enumerate(events) if v['event']=='GROUP_CRASH')
    boundaries=[(-1,held[0]),(held[0],death),(death,held[2]),(held[2],held[4]),(held[4],held[6])]
    request_phases(sent,boundaries,original,entries)
    background=current.heartbeats(view,events,entries,sent,boundaries,
        stages={0:'installed-1',2:'installed-2',3:'published-1',4:'published-2'})
    ignored=background.pop('_events');traces=background.pop('_traces')
    work=[v for v in entries if v['kind']!='HEARTBEAT'];results=[];silents=[]
    for ordinal,(start,stop) in enumerate(boundaries):
        if ordinal in (0,2):result=activate(view,events,work,start,stop,identities,1 if ordinal==0 else 2)
        elif ordinal==1:result=interrupted(view,events,work,start,stop,identities,point)
        else:
            index=ordinal-2;stage='installed-2' if index==1 else 'published-1'
            voters=tuple(v['voter'] for v in f.decode(c.current(a.group(view,stage)['node-1'])[1]['selected.gsr'],'records','SELECTED')['sources'])
            result=a.slot(view,events,work,start,stop,identities,index,before_stage=stage,voters=voters,
                received_requests=True,carried=index==1,maintenance_replay=maintenance,background_events=ignored)
            silents.append((start,stop,index,result.pop('_rejected'),voters))
        own=result.pop('_traces')
        need(not traces.intersection(own) and all(str(uuid.UUID(v))==v and uuid.UUID(v).int!=0 for v in own),
             'native carried fresh phase traces');traces.update(own);results.append(result)
    need(sum(v['exchanges'] for v in results)==len(work),'native carried complete response coverage')
    unanswered={digest:rows for digest,rows in sent.items() if not any(v['response'] is not None for v in rows) and rows[0]['kind']!='HEARTBEAT'}
    silent=net.silent_attempts(view,events,unanswered,silents,identities,traces)
    return dict(fullWireReplay=True,phases=results,exchanges=len(entries),requests=sum(len(v) for v in sent.values()),
        silent=silent,silentRequests=sum(v['attempts'] for v in silent),background=background)


def validate(root):
    root=Path(root);component=process.validate(root)
    result=replay(root,component['cut'])
    return dict(status='PASS',scope='native-carried-whole-group-process-history',originalFirst=True,
        process=component,network=result,fullWireReplay=True,processHistoryQualified=True,
        phase3Complete=False,cohortAdmitted=False,powerLoss=False,publicRuntime=False)


NETWORK_NEGATIVES={
    'network-missing-send':'node network received request without write',
    'network-missing-receipt':'node network response without original receipt',
    'network-invented-delivery':'restart network delivery without original response',
    'network-early-delivery':'restart network delivery without original response',
    'network-cross-life-delivery':'native carried delivery crosses group death',
    'network-discovery-cut':'restart network exact delivered control',
    'network-source-bytes':'restart network source exact data',
    'network-source-offer':'restart network source original offer',
    'network-basis-reply':'restart network exact delivered control',
    'network-reply-identity':'discovered selection wire correlation',
    'network-vote-receipt':'restart network exact delivered control',
    'network-apply-statement':'restart network exact delivered control',
    'network-future-revision':'restart network exact delivered control',
    'network-future-digest':'restart network exact delivered control',
    'network-install-reply':'restart network exact delivered control',
    'network-publish-generation':'restart network exact delivered control',
    'network-heartbeat-request':'current heartbeat original request cut',
    'network-heartbeat-reply':'current heartbeat original reply cut',
    'network-heartbeat-no-contact':'current heartbeat contact before continuation',
    'network-wrong-quorum':'restart network actual recording majority',
    'network-early-publication':'restart network recording before every publication send',
    'network-missing-install-force':'current heartbeat original selector boundary',
    'network-missing-parent-ack':'restart network required original source',
    'network-silent-retention-reference':'node network exact unused retention attempt',
}


def negative_cases(point):
    cases=dict(process.negative_cases(point),**NETWORK_NEGATIVES)
    if point!='APPLY_ACK_DIRECTORY_FORCED':cases['network-pregrant-retirement']='current node exact maintenance forces: node-2'
    return cases


def mutate(root,name):
    if not name.startswith('network-'):return process.mutate(root,name)
    def edit(lives):
        messages=[v for life in lives for v in life]
        def events():return [v['value'] for v in messages if v['action']=='event']
        def responses():return [v['value'] for v in messages if v['action']=='response']
        def remove(message):
            for life in lives:
                if message in life:life.remove(message);return
            raise ValueError('native carried network mutation message absent')
        def response(kind,predicate=lambda q,k,r:True):
            for row in responses():
                k,q=n.transfer.t.wire(row['wire']['request']);answer,r=n.transfer.t.wire(row['wire']['response'])
                if k==kind and predicate(q,answer,r):return row
            raise ValueError('native carried network mutation response absent: '+kind)
        def rewrite(row,change):
            kind,q=n.transfer.t.wire(row['wire']['request']);answer,z=n.transfer.t.wire(row['wire']['response'])
            old_q,old_z=row['wire']['request'],row['wire']['response']
            qhash,rhash=[e.digest(base64.b64decode(v,validate=True)) for v in (old_q,old_z)]
            change(q,z);qraw=f.encode('wire',kind,q);zraw=f.encode('wire',answer,z)
            for r in responses():
                if r['wire']['request']==old_q and r['wire']['response']==old_z:
                    r['wire'].update(request=base64.b64encode(qraw).decode(),response=base64.b64encode(zraw).decode())
                    r['event'].update(request=e.digest(qraw),response=e.digest(zraw))
            for v in events():
                if v['event'] in ('NETWORK_SEND','NETWORK_REQUEST') and v['request']==qhash:
                    v['request']=e.digest(qraw)
                    if v['event']=='NETWORK_SEND':v['bytes']=base64.b64encode(qraw).decode()
                elif v['event']=='NETWORK_RECEIVED' and v['response']==rhash:v['response']=e.digest(zraw)
        def drop_response(row):
            q,r=row['wire']['request'],row['wire']['response'];digest=e.digest(base64.b64decode(r,validate=True))
            for message in messages:
                if message['action']=='response' and message['value']['wire']['request']==q and message['value']['wire']['response']==r:
                    remove(message)
                elif message['action']=='event' and message['value']['event']=='NETWORK_RECEIVED' and message['value']['response']==digest:
                    remove(message)
        if name in ('network-missing-send','network-missing-receipt'):
            kind='NETWORK_SEND' if name=='network-missing-send' else 'NETWORK_REQUEST'
            remove(next(v for v in lives[0] if v['action']=='event' and v['value']['event']==kind))
        elif name=='network-invented-delivery':
            at=next(i for i,v in enumerate(lives[0]) if v['action']=='opened')+1
            lives[0].insert(at,dict(action='event',value=dict(node='node-1',incarnation=1,event='NETWORK_RECEIVED',
                                                          kind='TRANSFER_COMMIT',response='0'*64)))
        elif name=='network-early-delivery':
            delivery=next(v for v in lives[0] if v['action']=='event' and v['value'].get('kind')=='TRANSFER_COMMIT' and v['value']['event']=='NETWORK_RECEIVED')
            remove(delivery)
            before=next(i for i,v in enumerate(lives[0]) if v['action']=='response' and v['value']['event']['response']==delivery['value']['response'])
            lives[0].insert(before,delivery)
        elif name=='network-cross-life-delivery':
            delivery=next(v for v in lives[0] if v['action']=='event' and v['value']['event']=='NETWORK_RECEIVED')
            remove(delivery);delivery['value']['incarnation']=2
            at=next(i for i,v in enumerate(lives[1]) if v['action']=='opened')+1
            lives[1].insert(at,delivery)
        elif name=='network-discovery-cut':rewrite(response('STATUS_PROBE'),lambda q,z:z['payload']['cut'].update(index=99))
        elif name=='network-source-bytes':rewrite(response('CHUNK',lambda q,k,z:k=='CHUNK'),
            lambda q,z:z['payload'].update(bytes=base64.b64encode(b'changed').decode(),digest=e.digest(b'changed')))
        elif name=='network-source-offer':rewrite(response('CHUNK',lambda q,k,z:k=='SOURCE_OFFER'),lambda q,z:z['payload'].update(digest='0'*64))
        elif name in ('network-heartbeat-request','network-heartbeat-reply'):
            def change(q,z):(q if name=='network-heartbeat-request' else z)['payload']['cut'].update(index=99)
            rewrite(response('HEARTBEAT'),change)
        elif name=='network-heartbeat-no-contact':
            row=response('HEARTBEAT');trace=n.transfer.t.wire(row['wire']['request'])[1]['trace']
            hashes={r['event']['response'] for r in responses() if n.transfer.t.wire(r['wire']['request'])[1]['trace']==trace}
            for v in messages:
                if v['action']=='event' and v['value']['event']=='NETWORK_RECEIVED' and v['value']['response'] in hashes:remove(v)
        elif name in ('network-wrong-quorum','network-early-publication'):
            quorum=next(v for v in lives[1] if v['action']=='event' and v['value']['event']=='FUTURE_QUORUM_COMPLETE')
            if name=='network-wrong-quorum':quorum['value']['voters']=['node-1']
            else:
                send=next(v for v in lives[1] if v['action']=='event' and v['value']['event']=='PUBLICATION_SEND_BOUNDARY')
                remove(send);lives[1].insert(lives[1].index(quorum),send)
        elif name=='network-missing-install-force':
            remove(next(v for v in lives[0] if v['action']=='event' and v['value']['node']=='node-1' and v['value']['event']=='INSTALL_SELECTOR_FORCED'))
        elif name=='network-pregrant-retirement':
            stop=next(i for i,v in enumerate(lives[1]) if v['action']=='installed')
            remove(next(v for v in lives[1][:stop] if v['action']=='event' and v['value']['node']=='node-2' and v['value']['event']=='RETIREMENT_CLEARED'))
        elif name=='network-missing-parent-ack':
            # The peer may be node 3. Use the selected original identity.
            chosen=f.decode((root/'life-2-installed-1.gsr').read_bytes(),'records','SELECTED');peer=chosen['sources'][1]['voter']
            applied=c.inventory(root/'life-2-applied-2'/peer)
            raw=applied['applied-end/parent-ack.gsr'];reference=e.digest(raw)
            first=response('CHUNK',lambda q,k,z:q['payload']['digest']==reference)
            trace=n.transfer.t.wire(first['wire']['request'])[1]['trace']
            for row in list(responses()):
                if n.transfer.t.wire(row['wire']['request'])[1]['trace']==trace:drop_response(row)
        elif name=='network-silent-retention-reference':
            answered={r['event']['request'] for r in responses()}
            first=next(v for v in events() if v['event']=='NETWORK_SEND' and v['kind']=='FUTURE_RETENTION_INTENT' and v['request'] not in answered)
            digest=first['request'];q=f.decode(base64.b64decode(first['bytes']),'wire','FUTURE_RETENTION_INTENT');q['payload']['certificate']='0'*64
            raw=f.encode('wire','FUTURE_RETENTION_INTENT',q)
            for v in events():
                if v['event'] in ('NETWORK_SEND','NETWORK_REQUEST') and v['request']==digest:
                    v['request']=e.digest(raw)
                    if v['event']=='NETWORK_SEND':v['bytes']=base64.b64encode(raw).decode()
        else:
            kinds={'network-basis-reply':('PREPARE','basis'),'network-vote-receipt':('ACCEPT','receipt'),
                'network-apply-statement':('APPLY','statement'),'network-future-revision':('FUTURE_RETENTION_INTENT','revision'),
                'network-future-digest':('FUTURE_RETENTION_INTENT','digest'),'network-install-reply':('SELECTED','selection'),
                'network-publish-generation':('PUBLISH','generation'),'network-reply-identity':('PREPARE',None)}
            need(name in kinds,'unknown native carried network mutation');kind,key=kinds[name]
            def change(q,z):
                if name=='network-reply-identity':z['sender']=z['recipient']
                elif key=='revision':z['payload'][key]+=1
                else:z['payload'][key]='0'*64
            rewrite(response(kind),change)
    process.rewrite_lives(root,edit)


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in negative_cases(original['process']['cut']).items():
        with tempfile.TemporaryDirectory(prefix='v53-native-carried-network-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            try:validate(changed)
            except ValueError as error:need(str(error)==reason,'native carried network unrelated negative '+name+': '+str(error))
            else:raise ValueError('native carried network accepted negative '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
