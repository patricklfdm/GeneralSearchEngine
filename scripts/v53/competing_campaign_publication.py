"""Derive selected installation and two published slots after competing grants.

The preceding original grant/retirement reader is mandatory. Final files are
comparison targets; losing owners and their retained grants stay in the model.
Complete activation transport/export and process cohorts remain separate gates.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from . import competing_campaign_maintenance as preceding
from . import joining_install_storage as installs
from . import joining_slot_storage as storage
from . import competing_node_network as network

p,f,disk,need,sha=preceding.p,preceding.f,preceding.disk,preceding.need,preceding.sha


def selected_install(group, chosen):
    selected=f.decode(chosen,'records','SELECTED');proposer=selected['ballot']['proposer']
    names=[v['voter'] for v in selected['sources']];sources={};grants={};ledgers=[]
    need(proposer in names and len(names)==2 and set(names)<=set(group),'competing installation original majority')
    for node in names:
        files=group[node];_,_,current=disk.current(files)
        need(files['pending.accept']==disk.EMPTY and selected['nextEntry'] is None and
             current['capsule']['cut']==selected['cut'],'competing installation bootstrap no carried tail')
        rows=disk.journal(files['grants.gsr'],selected['root'],node)
        need([v[0] for v in rows[-3:]]==['PROMISE','BASIS','SELECTED'] and rows[-1][1]==chosen,
             'competing installation latest original decision')
        promise,basis=rows[-3][1],rows[-2][1];value=rows[-2][2]
        packet=disk.p.decode(files['sources/'+value['basisId']+'/source.gscp']);disk.p.bind(packet,basis)
        need(value['ballot']==selected['ballot'] and value['accepted'] is None,
             'competing installation selected original source')
        wrappers=[raw for raw in packet['objects'].values() if raw[:4]==b'GSRP']
        need(len(wrappers)==1,'competing installation original retention wrapper')
        original,ledger=p.n.s.s.unwrap(wrappers[0])
        need(original==promise and ledger==files[p.n.s.FILE],
             'competing installation unchanged frozen retention')
        sources[node]=(basis,packet,wrappers[0]);grants[node]=(promise,basis);ledgers.append(ledger)
    result=copy.deepcopy(group)
    for node in names:
        files=group[node];prefix,old,_=disk.current(files);packet=sources[proposer][1]
        slot='b' if prefix=='generations/a/' else 'a'
        need('generations/'+slot not in files,'competing installation occupied destination')
        owner=f.decode(files['node.gsr'],'records','NODE')['identity']
        intent=p.n.s.intent(owner,chosen,files[p.n.s.FILE],[sources[n] for n in names])
        objects=p.n.slot.prefix(packet,files['root.gsr']);objects[sha(intent)]=intent
        raw=disk.packet_bytes(packet['capsule'],objects,packet['images'])
        members=dict(zip(('promise.gsr','basis.gsr'),grants[node]),**{'selected.gsr':chosen,
                     'selected-sources.gsr':b''.join(grants[n][1] for n in names),'source.gscp':raw})
        for digest,size in packet['images'].items():
            image=old[digest+'.image']
            need(len(image)==size and sha(image)==digest,'competing installation exact source image')
            members[digest+'.image']=image
        selector,generation=disk.generation(members,disk.p.decode(raw)['capsule'],node,slot,None)
        result[node]=dict(files,**generation,**{'selector.gsr':selector,
                         p.n.s.FILE:p.n.s.merged(files[p.n.s.FILE],ledgers)})
    return result


def installation_order(replay, installed, chosen, selected, at):
    expected={ref['voter'] for ref in selected['sources']};count=0
    found={v['node'] for v in replay.events[replay.stop:at] if v['event']=='INSTALL_RESERVED'}
    need(found==expected,'competing installation exact selected owners')
    for node in expected:
        bound=[v for v in replay.bindings if v['node']==node and v['selection']==sha(chosen)]
        need(len(bound)==1 and bound[0]['forced']<at,'competing installation original selection force')
        prefix,members,_=disk.current(installed[node])
        full=dict(members,**{'generation.gsr':installed[node][prefix+'generation.gsr']})
        count+=installs.interval(replay.events,node,None,bound[0]['forced'],at,full,
                    ['SELECTED_BEFORE_RETURN'],'competing installation complete write chain')
    permitted=set(installs.sequence(full))|{'NETWORK_SEND','NETWORK_REQUEST','NETWORK_RECEIVED','WIRE_RESPONSE'}
    need(all(v['event'] in permitted or preceding.prefix.collection.network.capture_callback(v['event'])
             for v in replay.events[replay.stop:at]),'competing installation unmodeled owner work')
    return dict(owners=len(expected),callbacks=count)


def failed_checkpoints(history,entries,by_hash,sends,index,lower,upper):
    """Derive unsuccessful original-owner ACK pulls; they never supply votes.

    PublicationEndpoint.collect visits sorted eligible voters until a majority
    completes. For this bootstrap pair, an earlier unselected owner can exhaust
    its three identical first-request attempts before the selected peer succeeds.
    """
    allowed=set();traces=set();ids=set();applied=history.snapshots[f'slot-{index}-applied']
    unused=next(v for v in history.initial if v not in history.voters)
    for node in history.voters:
        peer=next(v for v in history.voters if v!=node)
        if unused>peer:continue
        identity=network.n.future.identity(history.initial[unused])
        statements=[raw for name,raw in applied[node].items() if name.startswith('applied-end/')
                    and (name=='applied-end/statement.gsr' or name.endswith('-statement.gsr'))]
        for raw in statements:
            statement=f.decode(raw,'records','CHECKPOINT')
            def ack(who):
                owner=network.n.future.identity(history.initial[who])
                return f.encode('records','CHECKPOINT_ACK',dict(root=statement['root'],voter=who,
                    incarnation=owner['storage'],cut=statement['end'],statement=sha(raw)))
            digest=sha(ack(unused))
            matches=[(h,q) for h,(kind,q) in by_hash.items() if kind=='CHUNK' and
                     q['sender']['node']==node and q['recipient']['node']==unused and
                     q['payload']['digest']==digest and lower<sends[h][0]<upper]
            need(len(matches)==1,'competing missing unsuccessful checkpoint pull')
            h,q=matches[0];payload=q['payload']
            publications=[v for v in entries if v['kind']=='PUBLISH' and v['request']['recipient']['node']==node
                          and lower<v['received']<min(sends[h])]
            need(publications,'competing checkpoint pull before publication request')
            need(q['ballot']==history.selected['ballot'] and q['recipient']==identity and q['sequence']==1 and
                 payload==dict(action='REQUEST',bytes='',digest=digest,id=payload['id'],offset=0) and
                 len(sends[h])==3 and all(lower<at<upper for at in sends[h]) and
                 not any(v['request']==q for v in entries),'competing unsuccessful checkpoint has no receipt')
            need(q['trace'] not in traces and payload['id'] not in ids and
                 all(str(uuid.UUID(v))==v and uuid.UUID(v).int for v in (q['trace'],payload['id'])),
                 'competing unsuccessful checkpoint fresh identities')
            # A later complete transfer from the actual peer was already replayed
            # by slot(); compare its first send too, not a producer annotation.
            fallback=[h2 for h2,(kind,z) in by_hash.items() if kind=='CHUNK' and z['sender']['node']==node
                      and z['recipient']['node']==peer and z['payload']['digest']==sha(ack(peer))
                      and z['sequence']==1 and lower<sends[h2][0]<upper]
            need(len(fallback)==1 and max(sends[h])<min(sends[fallback[0]]),
                 'competing checkpoint fallback before exhaustion')
            allowed.add(h);traces.add(q['trace']);ids.add(payload['id'])
    return allowed,traces


def published_network(replay, history, held):
    events=replay.events;entries=replay.rows;identities=replay.identities
    by_hash,sends,unanswered=network.raw_sends(events,entries,identities,history.selected)
    nonheartbeat=[v for v in entries if v['kind']!='HEARTBEAT'];results=[];callbacks=0
    unused=next(v for v in identities if v not in history.voters);allowed=set();traces=set();failed=set()
    for index,(lower,upper) in enumerate(((held[0][0],held[2][0]),(held[2][0],held[5][0])),1):
        result=network.slot(history,events,nonheartbeat,identities,lower,upper,index,sends)
        request=dict(root=history.selected['root'],view=history.selected['view'],ballot=history.selected['ballot'],
                     sender=identities[history.proposer],recipient=identities[unused],trace=result.pop('_intentTrace'),
                     sequence=network.intent_sequence(identities,history.proposer,unused),payload=result.pop('_intent'))
        h=sha(f.encode('wire','FUTURE_RETENTION_INTENT',request))
        need(h in by_hash and by_hash[h]==('FUTURE_RETENTION_INTENT',request) and 1<=len(sends[h])<=3,
             'competing original unused intent')
        begin=held[1 if index==1 else 4][0]
        need(all(begin<at<upper for at in sends[h]) and not any(v['request']==request for v in entries),
             'competing unused intent cannot acknowledge')
        allowed.add(h)
        own_traces=result.pop('_traces')
        misses,miss_traces=failed_checkpoints(history,entries,by_hash,sends,index,lower,upper)
        need(not own_traces & miss_traces,'competing unique phase traces')
        own_traces|=miss_traces;allowed|=misses;failed|=misses
        need(not traces & own_traces,'competing unique phase traces');traces.update(own_traces)
        results.append(result)
        for node in history.voters:
            own={v['event']:at for at,v in enumerate(events) if lower<at<upper and v['node']==node}
            files=history.snapshots[f'slot-{index}-published'][node];prefix,members,_=disk.current(files)
            full=dict(members,**{'generation.gsr':files[prefix+'generation.gsr']})
            callbacks+=storage.validate_slot(events,node,None,own,history.snapshots[f'slot-{index}-applied'][node],
                         full,'BARRIER' if index==1 else 'DATA',allow_data=True)
    remaining={h for h in unanswered if any(at>held[0][0] for at in sends[h])}
    need(all(h in allowed or by_hash[h][0]=='HEARTBEAT' for h in remaining),
         'competing publication unclassified unanswered request')
    heartbeat=network.heartbeats(history,events,entries,sends,by_hash,held)
    need(not traces & heartbeat.pop('_traces'),'competing unique phase traces')
    need(sum(v['exchanges'] for v in results)==len([v for v in nonheartbeat if v['offered']>held[0][0]]),
         'competing publication complete exchange coverage')
    return dict(exchanges=sum(v['exchanges'] for v in results),slots=results,heartbeat=heartbeat,
                unansweredIntents=len(allowed-failed),exhaustedCheckpointPulls=len(failed),slotStorageCallbacks=callbacks)


def closed(root,replay,history,events,activation_at):
    need((root/'failure.txt').read_bytes()==(root/'close-failure.txt').read_bytes()==b'',
         'competing retained execution failure')
    need(p.n.read(root/'result.json')==dict(status='PARTIAL',producerPassed=True,nodes=3,automaticOwners=3,
         defaultBounds=True,physicalReplay=False,phase3Complete=False),'competing producer scope')
    rows=p.n.read(root/'diagnostics.json')
    need(type(rows) is list and [v.get('node') for v in rows]==sorted(history.initial), 'competing diagnostics owners')
    for row in rows:
        need(set(row)=={'node','state','rounds','losses','failure'} and type(row['rounds']) is int and
             1<=row['rounds']<=len(events) and row['failure']=='' and type(row['losses']) is list and
             all(type(v) is str and 0<len(v)<=128 for v in row['losses']) and len(row['losses'])<=row['rounds'] and
             row['state'] in ('READY','STARTING','RESTARTING') and
             (row['state']=='READY')==(row['node']==history.proposer),'competing diagnostics shape')
    # Observed diagnostics cannot grant authority. Prior losing writes have
    # already been derived; the nonselected owner stays nonwriting after install.
    unused=next(v for v in history.initial if v not in history.voters)
    need(all(v['event'] in ('NETWORK_SEND','NETWORK_REQUEST','NETWORK_RECEIVED','WIRE_RESPONSE')
             for v in events[activation_at+1:] if v['node']==unused),
         'competing publication nonselected owner work')
    # Activation owns OUTGOING before reserving its ballot. A higher PREPARE
    # may fence it before any local grant exists; retained grants alone cannot
    # inventory these drained owners. Reservations come from physical replay.
    outgoing={v['node'] for v in replay.allocations}
    p.scratch(root,history,outgoing)


class Replay:
    def __init__(self,root):self.root=Path(root)

    def run(self):
        p.inventory(self.root)
        replay=preceding.Replay(self.root);prior=replay.run();events=replay.events
        rounds=[(i,v) for i,v in enumerate(events) if v['event']=='ROUND_INSTALLED']
        need(len(rounds)==1,'competing publication one successful activation')
        at,row=rounds[0];chosen,selected=p.record(row,'records','SELECTED')
        need(row['node']==selected['ballot']['proposer'] and sha(chosen) in replay.selections,
             'competing publication original activated choice')
        group=selected_install(replay.group,chosen)
        order=installation_order(replay,group,chosen,selected,at)
        history=p.History(self.root,group,selected,events)
        history.initial=replay.initial;history.prepared=replay.group;history.installed=copy.deepcopy(group)
        history.selected=selected;history.chosen=chosen
        history.advance('BARRIER');history.advance('DATA');p.b.match(self.root,'after-close',history.group)
        held=p.completion_lifecycle(self.root,history,events)
        net=published_network(replay,history,held);closed(self.root,replay,history,events,at)
        self.preceding=replay;self.history=history;self.activation_at=at
        return dict(status='PARTIAL',scope='competing-bootstrap-installed-and-published-files',precondition=prior,
                    installation=order,proposer=history.proposer,selected=list(history.voters),slots=2,
                    clientMutations=1,finalInventories=len(group),physicalPublicationQualified=True,
                    publicationNetwork=net,clientCompletionQualified=True,scratchTransfersDrained=True,
                    fullNetworkQualified=False,fullLifecycleQualified=False,exportLifetimeQualified=False,
                    processDeathQualified=False,phase3Complete=False)


def validate(root):return Replay(root).run()


NEGATIVES = {
    'install-image-write':'competing installation complete write chain',
    'install-member-force':'competing installation complete write chain',
    'install-selector-rename':'competing installation complete write chain',
    'install-current-force':'competing installation complete write chain',
    'install-force-before-write':'competing installation complete write chain',
    'accept-prefix':'joining slot complete accept storage order',
    'proof-prefix':'joining slot complete proof storage order',
    'data-output-cleanup':'joining slot complete application storage order',
    'data-image-write':'joining slot complete application storage order',
    'published-member-force':'joining slot complete publication storage order',
    'published-vote-prefix':'joining slot complete covered retirement order',
    'wrong-quorum':'competing original slot hooks',
    'readiness-before-completion':'competing exact round lifecycle',
    'client-completion':'competing original client observations',
    'failed-checkpoint-attempt':'competing unsuccessful checkpoint has no receipt',
    'failed-checkpoint-digest':'competing missing unsuccessful checkpoint pull',
    'data-ack-delivery':'discovered selection response delivered',
    'leftover-scratch':'competing exact drained scratch',
    'live-lease':'competing exact drain receipt',
    'retained-failure':'competing retained execution failure',
    'producer-pass':'competing producer scope',
    'nonselected-write':'competing publication nonselected owner work',
    'final-extra-file':'admitted exact after-close: node-2',
    'final-future-retention':'admitted exact after-close: node-1',
    'final-selector':'admitted exact after-close: node-1',
}


def mutate(root,name):
    import base64
    root=Path(root);need(name in NEGATIVES,'unknown competing publication mutation')
    if name.startswith('final-'):
        paths={'final-extra-file':'node-2/unexpected.gsr','final-future-retention':'node-1/'+p.n.future.FILE,
               'final-selector':'node-1/selector.gsr'}
        (root/'after-close'/paths[name]).write_bytes(b'changed');return
    if name=='client-completion':
        path=root/'observations.json';rows=p.n.read(path);rows.pop();path.write_bytes(f.canonical(rows));return
    if name=='leftover-scratch':
        path=next((root/'drain-scratch').glob('*/incoming'));(path/'leftover').write_bytes(b'undrained');return
    if name=='live-lease':
        path=root/'drains.json';rows=p.n.read(path);rows[0]['leases']=1;path.write_bytes(f.canonical(rows));return
    if name=='retained-failure':(root/'failure.txt').write_text('original failure');return
    if name=='producer-pass':
        path=root/'result.json';value=p.n.read(path);value['status']='PASS';path.write_bytes(f.canonical(value));return
    events=p.n.read(root/'events.json')
    def at(point,last=False):
        indices=[i for i,v in enumerate(events) if v['event']==point];need(indices,'mutation missing original '+point)
        return indices[-1 if last else 0]
    if name=='wrong-quorum':events[at('SLOT_FUTURE_QUORUM_COMPLETE')]['voters']=['node-1','node-2']
    elif name=='readiness-before-completion':
        a,b=at('ROUND_SLOT_COMPLETE'),at('ROUND_BEFORE_READY')
        for key in ('event','record','bytes'):events[a][key],events[b][key]=events[b][key],events[a][key]
    elif name=='install-force-before-write':
        a,b=at('INSTALL_MANIFEST_WRITTEN'),at('INSTALL_MANIFEST_FORCED')
        events[a]['event'],events[b]['event']=events[b]['event'],events[a]['event']
    elif name=='nonselected-write':
        unused=next(v['node'] for v in p.n.read(root/'diagnostics.json') if v['state']=='STARTING')
        events.append(dict(node=unused,event='ACCEPT_PREFIX_WRITTEN',nanoTime=events[-1]['nanoTime']))
    elif name.startswith('failed-checkpoint-'):
        unused=next(v['node'] for v in p.n.read(root/'diagnostics.json') if v['state']=='STARTING')
        candidates=[(i,v) for i,v in enumerate(events) if i>at('ROUND_INSTALLED') and v['event']=='NETWORK_SEND'
                    and v['kind']=='CHUNK' and network.n.transfer.t.wire(v['bytes'])[1]['recipient']['node']==unused]
        h=candidates[0][1]['request']
        if name=='failed-checkpoint-attempt':
            # Delete both endpoints of one attempt; don't invent an unpaired
            # receive that would fail for an unrelated transport reason.
            start=candidates[0][0];end=next(i for i in range(start+1,len(events)) if events[i]['event']=='NETWORK_REQUEST' and events[i]['request']==h)
            events.pop(end);events.pop(start)
        else:
            q=network.n.transfer.t.wire(candidates[0][1]['bytes'])[1];q['payload']['digest']='e'*64
            raw=f.encode('wire','CHUNK',q);changed=sha(raw)
            for v in events:
                if v.get('request')==h:
                    v['request']=changed
                    if v['event']=='NETWORK_SEND':v['bytes']=base64.b64encode(raw).decode()
    elif name=='data-ack-delivery':
        i=next(i for i in range(at('ROUND_SLOT_BEGIN',True),len(events)) if events[i]['event']=='NETWORK_RECEIVED' and events[i]['kind']=='ACCEPT_ACK')
        events.pop(i)
    else:
        points={'install-image-write':'INSTALL_IMAGE_WRITTEN','install-member-force':'INSTALL_MEMBER_FORCED',
                'install-selector-rename':'INSTALL_SELECTOR_RENAMED','install-current-force':'CURRENT_FILES_FORCED',
                'accept-prefix':'ACCEPT_PREFIX_WRITTEN','proof-prefix':'PROOF_PREFIX_WRITTEN',
                'data-output-cleanup':'REPLAY_DELETED','data-image-write':'APPLY_IMAGE_WRITTEN',
                'published-member-force':'INSTALL_MEMBER_FORCED','published-vote-prefix':'COVERED_VOTE_PREFIX_WRITTEN'}
        lower=at('ROUND_SLOT_BEGIN',True) if name.startswith(('data-','published-')) else at('INSTALL_RESERVED')
        i=next(i for i in range(lower,len(events)) if events[i]['event']==points[name]);events.pop(i)
    (root/'events.json').write_bytes(f.canonical(events))


def qualify(root):
    root=Path(root);original=validate(root);before=preceding.prefix.collection.h.inventory(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-competing-publication-negative-') as temp:
            copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,name)
            try:validate(copied)
            except ValueError as error:need(str(error)==reason,'unrelated competing publication negative: '+name+': '+str(error))
            else:raise ValueError('competing publication mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(preceding.prefix.collection.h.inventory(root)==before,'competing publication original changed')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('raw');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.raw),sort_keys=True))
