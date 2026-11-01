"""Continuous REMOVE peer/future revisions bound to original durable events.

The physical, transport and export readers run first. Start once at the derived
before-network state; never reset a ledger from an intermediate observation.
Successful in-process writes and open reseals are not process-death evidence.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import remove_export_evidence as exports
from . import joining_peer_evidence as peer
from . import joining_same_view_future as future

e=exports;n=e.n;c=e.c;f=e.f;need=e.need;sha=e.sha


def peer_reseals(events,nodes):
    result=[];used=set()
    for node in nodes:
        names=['CURRENT_VALIDATED',*peer.RESEAL,future.RESEAL[0]]
        points={name:[i for i,v in enumerate(events) if v.get('node')==node and v['event']==name] for name in names}
        need(points[names[0]] and all(len(points[name])==1 for name in names[1:]),'joining peer exact open reseal count')
        order=[points[name][0] for name in names]
        need(all(a<b for a,b in zip(order,order[1:])),'joining peer open reseal force order')
        used.update(order[1:3]);result.append((order[2],node))
    need(used=={i for i,v in enumerate(events) if v['event'] in peer.RESEAL},'joining peer unbound open reseal')
    return result


def peer_event_shapes(events,nodes):
    for row in events:
        point=row['event']
        if not point.startswith('RETENTION_') and point!='SELECTED_RETENTION_COMPLETED':continue
        need(point in peer.WRITES+peer.RESEAL+['SELECTED_RETENTION_COMPLETED'],'joining peer unsupported retention event')
        need(set(row)=={'node','event'} and row['node'] in nodes,'REMOVE peer event shape')


class PeerReplay(peer.Replay,e.Replay):
    expected_write_counts=None

    def __init__(self,root,profile):
        e.Replay.__init__(self,root,profile)
        self.phases=n.phase.blocks(self.events,self.history)
        self.floor_inputs=[];self.state={};self.steps=[];self.used=set();self.files_cache={};self.comparisons=0
        self.tx=peer.transactions(self.events);self.completions=set();self.reseals=peer_reseals(self.events,self.history.old)
        peer_event_shapes(self.events,self.history.old)

    def acquired(self,own,lower,start):
        copies,used=e.Replay.acquired(self,own,lower,start)
        self.floor_inputs.append(dict(start=start,own=own,copies=copies,order=list(copies)))
        return copies,used

    def floor(self,row):
        own=row['own'];node=own['node'];start=row['start'];copies=row['copies'];changes=[]
        lower=next(i for i in range(start+1,len(self.events)) if self.events[i].get('node')==node and self.events[i]['event']=='FLOOR_BEFORE_RETURN')
        upper=next(i for i in range(lower+1,len(self.events)) if self.events[i].get('node')==node and
                   self.events[i]['event'] in ('RETIREMENT_RESERVED','FLOOR_RELEASE_AUTHORITY_CREATED'))
        files=dict(self.files(own),**{peer.FILE:self.state[node]})
        view=own['packet']['capsule']['cut']['view'];plan=copy.deepcopy(peer.peers.decode(self.state[node])['plan'])
        if plan['view']!=view:
            wanted=set(view['old']+view['new']);plan['view']=view
            plan['peers']=[v for v in plan['peers'] if v['identity']['node'] in wanted]
            need({v['identity']['node'] for v in plan['peers']}==wanted,'REMOVE peer retained view identities')
            self.change(node,peer.updated(self.state[node],plan),'reconcile',changes)
        for remote in row['order']:
            files[peer.FILE]=self.state[node]
            after=peer.t.observation.observe_same_cut(self.state[node],files,self.files(copies[remote]),defer_renewal=True)
            self.change(node,after,'observe:'+remote,changes)
        self.sequence(node,changes,lower,upper,'maintenance')

    def selection(self,own):
        node=own['node'];end=own['start'];raw=own['members']['selected.gsr'];selected=f.decode(raw,'records','SELECTED')
        lower=max(i for i,v in enumerate(self.events[:end]) if v.get('node')==node and v['event']=='INSTALL_PARENT_FORCED')
        rows=[];plans=[peer.peers.decode(self.state[node])['plan']]
        for row in selected['sources']:
            found=[v for v in self.sources if sha(v['basis'])==row['basisDigest']]
            need(len(found)==1 and found[0]['node']==row['voter'] and found[0]['start']<lower,'joining peer selected original source')
            source=found[0];wrapper,state=peer.init.retention.source(source['packet'],source['value'],0x47535250,65536)
            plans.append(state['plan']);rows.append((source['basis'],source['packet'],wrapper))
        packet=own['packet'];ids=n.shared.s.catalog.identities(peer.c.catalog(own)['identities'])
        intent=peer.t.selected.intent(own['identity'],raw,self.state[node],rows)
        need(packet['objects'].get(sha(intent))==intent,'joining peer selected original before ledger')
        plan=peer.t.confirmation.merge(plans,packet,ids,[]);changes=[]
        self.change(node,peer.updated(self.state[node],plan),'selected:'+sha(raw),changes)
        completions=[i for i,v in enumerate(self.events) if lower<i<end and v.get('node')==node and v['event']=='SELECTED_RETENTION_COMPLETED']
        need(len(completions)==int(bool(changes)),'joining peer selected completion count')
        self.sequence(node,changes,lower,completions[0] if changes else end,'selected')
        self.completions.update(completions);self.compare(node,self.files(own)[peer.FILE],own['path'])

    def publication(self,index,node):
        points=self.phases[index,node];files=self.history.owner('applied',index,node)
        self.compare(node,files[peer.FILE],'applied-'+str(index));plan=copy.deepcopy(peer.peers.decode(self.state[node])['plan'])
        upper=c.anchor(c.current(self.history.published[index,node])[2]['capsule'])
        proof=f.decode(self.history.phases[index-1]['CERTIFICATE'],'records','CERTIFICATE')
        for vote in proof['proofs']:
            target=vote['voter']
            if target=='node-1':continue
            identity=n.d.future.identity(self.history.applied[index,target])
            row=next(v for v in plan['peers'] if v['identity']==identity)
            need(row['possible'][0]==self.history.future_lower(index,target),'REMOVE peer original future lower')
            row['possible'].append(upper)
        changes=[];self.change(node,peer.updated(self.state[node],plan),'publication:'+str(index),changes)
        self.sequence(node,changes,points['PUBLICATION_RETIRED'],points['FUTURE_RETENTION_PROMOTED'],'publication')
        self.compare(node,self.history.published[index,node][peer.FILE],'published-'+str(index))

    def reseal(self,value):
        _,node=value;self.compare(node,c.inventory(self.root/'before-network'/node)[peer.FILE],'open-reseal')

    def run(self):
        self.statuses();self.floors()
        before={node:c.inventory(self.root/'before-network'/node) for node in self.history.old}
        original=n.d.b.original(self.root,len(self.history.old),False)
        for node,files in peer.t.selected.initialize(original).items():
            self.state[node]=files[peer.FILE];self.compare(node,before[node][peer.FILE],'before-network')
        actions=[]
        for row in self.floor_inputs:
            start=row['start'];node=row['own']['node']
            end=next(i for i in range(start+1,len(self.events)) if self.events[i].get('node')==node and self.events[i]['event']=='FLOOR_RELEASE_BEFORE_RETURN')
            actions.append((end,'floor',(row,)))
        for own in self.windows:
            if own['start']>=0 and self.events[own['start']]['event']=='INSTALL_BEFORE_RETURN':actions.append((own['start'],'selection',(own,)))
        for (index,node),points in self.phases.items():actions.append((points['PUBLICATION_BEFORE_RETURN'],'publication',(index,node)))
        actions.extend((v['start'],'capture',(v,)) for v in self.sources if v['start']>=0)
        actions.extend((at,'reseal',((at,node),)) for at,node in self.reseals)
        for _,kind,values in sorted(actions,key=lambda v:v[0]):getattr(self,kind)(*values)
        need(self.used=={v['start'] for v in self.tx},'joining peer unbound durable writes')
        need(self.completions=={i for i,v in enumerate(self.events) if v['event']=='SELECTED_RETENTION_COMPLETED'},
             'joining peer unbound selected completions')
        for node in self.state:self.compare(node,c.inventory(self.root/'after-close'/node)[peer.FILE],'closed')
        return dict(status='PASS',durableWrites=len(self.steps),writesByKind=dict(Counter(v['kind'] for v in self.steps)),
            ledgerComparisons=self.comparisons,capturedLedgers=sum(v['start']>=0 for v in self.sources),openReseals=len(self.reseals),
            finalRevisions={node:peer.peers.decode(raw)['revision'] for node,raw in self.state.items()},
            chainSha256=sha(f.canonical(sorted(self.steps,key=lambda v:v['start']))))


class FutureReplay(future.Replay):
    def __init__(self,root,profile):
        self.root=Path(root);self.base=e.Replay(root,profile);self.events=self.base.events;self.model=self.base.history
        self.base.phases=n.phase.blocks(self.events,self.model)
        self.tx,self.write_events=future.observations(self.events,joining=None)
        self.state={};self.used=set();self.callbacks=set();self.steps=[];self.comparisons=0;self.reseals=0

    def run(self):
        for node in self.model.old:self.initialize(node,c.inventory(self.root/'before-network'/node))
        actions=[]
        for (index,node),points in self.base.phases.items():actions.append((points['PUBLICATION_BEFORE_RETURN'],'phase',(index,node)))
        for own in self.base.windows:
            if own['start']>=0 and self.events[own['start']]['event']=='INSTALL_BEFORE_RETURN':
                actions.append((own['start'],'compare',(own['node'],c.inventory(self.root/own['path']),'installed')))
        for node in self.model.old:
            found=[i for i,v in enumerate(self.events) if v.get('node')==node and v['event']==future.RESEAL[-1]]
            need(len(found)==1,'joining future exact reopen count');actions.append((found[0],'reopen',(node,None,found[0])))
        for _,kind,values in sorted(actions,key=lambda v:v[0]):getattr(self,kind)(*values)
        need(self.used=={v['start'] for v in self.tx},'joining future unbound durable writes')
        need(self.callbacks=={i for i,v in enumerate(self.events) if v['event'] in future.RETURNS+future.RESEAL},'joining future unbound completion/reopen')
        for node in self.state:self.compare(node,c.inventory(self.root/'after-close'/node),'closed')
        return dict(status='PASS',durableWrites=len(self.steps),writesByKind=dict(Counter(v['kind'] for v in self.steps)),
            openReseals=self.reseals,ledgerComparisons=self.comparisons,finalRevisions={node:v['meta']['revision'] for node,v in self.state.items()},
            chainSha256=sha(f.canonical(sorted(self.steps,key=lambda v:v['start']))))


def replay(root,profile):
    return dict(status='PARTIAL',profile=profile,peers=PeerReplay(root,profile).run(),future=FutureReplay(root,profile).run(),
        retentionRevisionCompositionQualified=True,completeRetirementTransactions=False,processDeathQualified=False,phase3Complete=False)


def validate(root,profile):
    root=Path(root);need(profile in n.original.PROFILES,'REMOVE retention profile');before=n.collection.inventory(root)
    original=e.validate(root,profile);result=replay(root,profile)
    need(n.collection.inventory(root)==before,'REMOVE retention original changed')
    return dict(result,precondition=original)


NEGATIVES={'peers':dict(peer.NEGATIVES),'future':dict(future.NEGATIVES)}
NEGATIVES['peers'].update({'foreign-write-owner':'REMOVE peer event shape',
                          'unbound-reseal':'joining peer exact open reseal count',
                          'completion-forged-scope':'REMOVE peer event shape',
                          'write-forged-field':'REMOVE peer event shape'})


def mutate(root,profile,stage,name):
    root=Path(root)
    if stage=='peers':
        if name in peer.NEGATIVES:peer.mutate(root,name,reader=PeerReplay(root,profile))
        else:
            reader=PeerReplay(root,profile);reader.run();events=reader.events
            if name=='completion-forged-scope':
                next(v for v in events if v['event']=='SELECTED_RETENTION_COMPLETED')['scope']='foreign-owner'
            elif name=='write-forged-field':next(v for v in events if v['event']==peer.WRITES[0])['revision']=99
            else:raise ValueError('REMOVE unknown peer mutation')
            (root/'events.json').write_bytes(f.canonical(events))
        # Older mutation drivers mark removed callbacks. Delete those markers
        # so all non-retention observations remain byte-for-byte equivalent.
        events=n.collection.read_json(root,'events.json',n.collection.EVENT_BYTES)
        events=[v for v in events if not v['event'].startswith('REMOVED_')]
        (root/'events.json').write_bytes(f.canonical(events))
    else:future.mutate(root,name,reader=FutureReplay(root,profile))


def unrelated(events,stage):
    def targeted(row):
        return (row['event'].startswith('RETENTION_') or row['event']=='SELECTED_RETENTION_COMPLETED') if stage=='peers' else row['event'].startswith('FUTURE_RETENTION_')
    return [v for v in events if not targeted(v)]


def negative(root,profile,before,stage,name):
    reason=NEGATIVES[stage][name]
    with tempfile.TemporaryDirectory(prefix='v53-remove-retention-negative-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,profile,stage,name)
        after=n.collection.inventory(changed);protected=lambda v:{k:h for k,h in v['files'].items() if k!='events.json'}
        need(protected(before)==protected(after) and before['directories']==after['directories'],'REMOVE retention negative changed original files')
        read=lambda path:n.collection.read_json(Path(path),'events.json',n.collection.EVENT_BYTES)
        need(unrelated(read(root),stage)==unrelated(read(changed),stage),'REMOVE retention negative changed other observations')
        try:(PeerReplay if stage=='peers' else FutureReplay)(changed,profile).run()
        except ValueError as error:need(str(error)==reason,'REMOVE unrelated retention negative: '+stage+': '+name+': '+str(error))
        else:raise ValueError('REMOVE retention mutation accepted: '+stage+': '+name)
    return dict(stage=stage,case=name,status='REJECTED',reason=reason,originalFilesAndOtherObservationsUnchanged=True)


def qualify(root,profile,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'REMOVE retention replay workers')
    root=Path(root);original=validate(root,profile);before=n.collection.inventory(root);outcomes=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(negative,root,profile,before,stage,name):(stage,name) for stage,cases in NEGATIVES.items() for name in cases}
        for task in as_completed(pending):
            stage,name=pending[task]
            try:result=task.result()
            except Exception as error:result=dict(stage=stage,case=name,status='FAIL',failure=str(error),type=type(error).__name__)
            outcomes.append(result)
            print(json.dumps(dict(result,profile=profile,completed=len(outcomes),total=len(pending))),file=sys.stderr,flush=True)
    need(n.collection.inventory(root)==before,'REMOVE retention negative changed original')
    need(all(v['status']=='REJECTED' for v in outcomes),'REMOVE retention negative matrix failed')
    return dict(original=original,negatives=sorted(outcomes,key=lambda v:(v['stage'],v['case'])),
        negativePrecondition='full-original-physical-network-export; unchanged files, wire and non-target observations',
        mutatedPrerequisiteReplayed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--profile',required=True,choices=n.original.PROFILES)
    p.add_argument('--qualify',action='store_true');p.add_argument('--workers',type=int,default=1)
    args=p.parse_args();result=qualify(args.root,args.profile,workers=args.workers) if args.qualify else validate(args.root,args.profile)
    print(json.dumps(result,sort_keys=True))
