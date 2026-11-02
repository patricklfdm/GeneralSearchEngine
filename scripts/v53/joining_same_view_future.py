"""Continuous original future-retention revisions and force lifetimes.

The complete same-view authority reader is the original-first prerequisite.
This reader never resets the ledger from an observed per-slot snapshot.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_same_view_authority as authority

a=authority
f,disk,need,sha=a.f,a.disk,a.need,a.sha
future=a.physical.future
WRITES=['FUTURE_RETENTION_'+v for v in ('BEFORE_WRITE','PREFIX_WRITTEN','WRITTEN','FORCED',
                                      'CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED')]
RESEAL=['FUTURE_RETENTION_RECOVERY_FORCED','FUTURE_RETENTION_RECOVERY_PARENT_FORCED']
RETURNS=['FUTURE_RETENTION_BEFORE_RETURN','FUTURE_RETENTION_ACK_BEFORE_RETURN',
         'FUTURE_RETENTION_PROMOTED','FUTURE_RETENTION_CLEARED']


def observations(events, *, joining='node-4'):
    active={};transactions=[];used=set()
    for at,row in enumerate(events):
        point=row['event']
        if not point.startswith('FUTURE_RETENTION_'):continue
        need(point in WRITES+RESEAL+RETURNS,'joining future unsupported event')
        need(set(row)==({'node','event','scope'} if row.get('node')==joining else {'node','event'}),
             'joining future event shape')
        if point not in WRITES:continue
        node=row['node'];pending=active.setdefault(node,[])
        need(point==WRITES[len(pending)] and (not pending or row.get('scope')==pending[0][1].get('scope')),
             'joining future exact write force order')
        pending.append((at,row));used.add(at)
        if len(pending)==len(WRITES):
            transactions.append(dict(node=node,scope=row.get('scope'),start=pending[0][0],end=at))
            del active[node]
    need(not active,'joining future incomplete durable write')
    return transactions,used


class Replay:
    def __init__(self,root,*,base=None):
        self.root=Path(root);self.base=a.Replay(root) if base is None else base;self.events=self.base.events;self.model=self.base.model
        self.tx,self.write_events=observations(self.events,joining=self.model.joining)
        self.state={};self.used=set();self.callbacks=set();self.steps=[];self.comparisons=0;self.reseals=0

    def compare(self,node,files,label):
        need(node in self.state and self.state[node]['raw']==files[future.FILE],
             'joining future exact continuous ledger: '+label+': '+node)
        self.comparisons+=1

    def initialize(self,node,files):
        need(node not in self.state,'joining future duplicate initialization')
        meta=future.initial(files);self.state[node]=dict(meta=meta,records={},raw=future.frame(meta,{}))
        self.compare(node,files,'initialize')

    def transaction(self,node,lower,upper):
        found=[v for v in self.tx if v['node']==node and lower<v['start']<=v['end']<upper]
        need(len(found)==1,'joining future exact bounded write count')
        tx=found[0]
        need(tx['start'] not in self.used and tx['scope']==('continuation-owner' if node==self.model.joining else None),
             'joining future original write owner')
        self.used.add(tx['start']);return tx

    def callback(self,node,name,lower,upper):
        matches=[i for i,v in enumerate(self.events) if lower<i<upper and v.get('node')==node and v['event']==name]
        need(len(matches)==1,'joining future exact completion lifetime: '+name)
        at=matches[0];row=self.events[at]
        need(at not in self.callbacks and row.get('scope')==('continuation-owner' if node==self.model.joining else None),
             'joining future original completion owner')
        self.callbacks.add(at);return at

    def change(self,node,meta,records,tx,kind,index):
        before=self.state[node];after=future.frame(meta,records)
        need(meta['root']==before['meta']['root'] and meta['owner']==before['meta']['owner'] and
             meta['revision']==before['meta']['revision']+1 and meta['previous']==sha(before['raw']) and after!=before['raw'],
             'joining future exact revision predecessor')
        self.state[node]=dict(meta=meta,records=records,raw=after)
        self.steps.append(dict(node=node,index=index,kind=kind,start=tx['start'],end=tx['end'],
                               revision=meta['revision'],before=sha(before['raw']),after=sha(after)))

    def phase(self,index,node):
        points=self.base.phases[index,node];parts=self.model.phases[index-1]
        files=self.model.owner('applied',index,node);self.compare(node,files,'applied-'+str(index))
        need(not self.state[node]['records'] and self.state[node]['meta']['parent'] is None,
             'joining future preceding target not cleared')
        _,local,packet=disk.current(files);parent=disk.anchor(packet['capsule'])
        originals={k:files['applied-end/'+k] for k in ('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','ack.gsr')}
        originals.update({k:local[k] for k in ('promise.gsr','selected.gsr')})
        originals.update({k.lower()+'.gsr':parts[k] for k in ('ENTRY','ACCEPT','PROOF')})
        cert=f.decode(parts['CERTIFICATE'],'records','CERTIFICATE');voters=[v['voter'] for v in cert['proofs']]
        proposer=cert['ballot']['proposer'];need(proposer in voters,'joining future original proposer proof')
        targets=[v for v in voters if v!=proposer];ids=a.n.s.catalog.identities(self.model.states[index]['identities'])
        lower=max(self.base.phases[index,n]['APPLY_BEFORE_RETURN'] for n in voters)
        upper=points['PUBLICATION_VALIDATED']
        all_tx=[v for v in self.tx if v['node']==node and lower<v['start'] and v['end']<upper]
        need(len(all_tx)==len(targets),'joining future exact recording count')
        peers=[]
        for ordinal,target in enumerate(targets):
            tx=all_tx[ordinal];finish=self.callback(node,RETURNS[0],tx['end'],all_tx[ordinal+1]['start'] if ordinal+1<len(all_tx) else upper)
            ack=self.callback(node,RETURNS[1],finish,all_tx[ordinal+1]['start'] if ordinal+1<len(all_tx) else upper)
            bound=self.transaction(node,lower if ordinal==0 else all_tx[ordinal-1]['end'],finish)
            lower_point=self.model.future_lower(index,target) if hasattr(self.model,'future_lower') else parent
            peers.append(dict(identity=ids[target],lower=lower_point));before=self.state[node]
            meta=dict(before['meta'],revision=before['meta']['revision']+1,previous=sha(before['raw']),parent=parent,peers=list(peers))
            self.change(node,meta,originals,bound,'record',index)
            # Exact request/reply bytes and the delivered quorum are already
            # checked by the original network reader. Bind the local callback
            # to the very same request's receive/offer or send boundary.
            self.recording_exchange(node,proposer,ids[target],parts['CERTIFICATE'],tx,ack)
        promoted=self.callback(node,RETURNS[2],points['PUBLICATION_RETIRED'],points['PUBLICATION_BEFORE_RETURN'])
        cleared=self.callback(node,RETURNS[3],promoted,points['PUBLICATION_BEFORE_RETURN'])
        tx=self.transaction(node,promoted,cleared);before=self.state[node]
        meta=dict(before['meta'],revision=before['meta']['revision']+1,previous=sha(before['raw']),parent=None,peers=[])
        self.change(node,meta,{},tx,'clear',index)
        self.compare(node,self.model.owner('published',index,node),'published-'+str(index))

    def recording_exchange(self,node,proposer,target,certificate,tx,ack):
        rows=[v for v in self.base.rows if v['kind']=='FUTURE_RETENTION_INTENT' and
              v['request']['sender']['node']==proposer and
              (node==proposer or v['request']['recipient']['node']==node) and
              v['request']['payload']['certificate']==sha(certificate) and v['request']['payload']['peer']==target]
        need(rows,'joining future original recording exchange')
        # The proposer records once before sending to any remote voter, not
        # merely before the request addressed to the eventual publish target.
        if node==proposer:need(ack<min(v['sent'] for v in rows),'joining future local ACK before send')
        else:
            state=self.state[node]
            need(any(v['received']<tx['start']<ack<v['offered'] and
                     v['response']['payload']['revision']==state['meta']['revision'] and
                     v['response']['payload']['digest']==sha(state['raw']) for v in rows),
                 'joining future remote ACK after force')

    def lifetimes(self):
        return a.peer.owner_lifetimes(self.model)

    def initialization_point(self):
        points=[i for i,v in enumerate(self.events) if v['event']=='JOINING_RETENTION_BEFORE_RETURN']
        need(len(points)==1,'joining future original initialization count')
        return points[0]

    def reopen_boundary(self,node,scope,at,order,rows):
        if scope=='initial-owner':
            initialized=[i for i,p in rows if p=='JOINING_RETENTION_BEFORE_RETURN']
            need(len(initialized)==1 and initialized[0]<order[1],'joining future reopen after initialization')
        else:
            recovered={name:[i for i,p in rows if p==name] for name in ('ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED')}
            need(all(len(v)==1 for v in recovered.values()) and at<recovered['ACCEPT_ACTIVE_FORCED'][0]<recovered['ACCEPT_ACTIVE_PARENT_FORCED'][0],
                 'joining future reopen before accept recovery')

    def reopen(self,node,scope,at):
        rows=[(i,v['event']) for i,v in enumerate(self.events) if v.get('node')==node and v.get('scope')==scope]
        points={name:[i for i,p in rows if p==name] for name in ['RETENTION_RECOVERY_PARENT_FORCED',*RESEAL]}
        need(all(len(v)==1 for v in points.values()),'joining future exact reopen count')
        order=[v[0] for v in points.values()]
        need(order[0]<order[1]<order[2]==at,'joining future reopen force order')
        if node==self.model.joining:
            a.c.owner_lifetime(self.events,node,scope,order[1],at)
        self.reopen_boundary(node,scope,at,order,rows)
        if scope=='stable-cold-owner':
            finishes=[i for i,p in rows if p=='FIXTURE_OPEN_RETURNED']
            need(len(finishes)==1 and at<finishes[0],'joining future reopen before owner return')
        own=None if node!=self.model.joining else self.base.current(node,at,at)
        files=disk.inventory(self.root/'before-network'/node) if own is None else disk.inventory(self.root/own['path'])
        self.compare(node,files,'reopen');self.callbacks.update(order[1:]);self.reseals+=1

    def run(self):
        for node,files in self.model.original.items():
            derived=dict(files,**{future.FILE:future.frame(future.initial(files),{})})
            self.initialize(node,derived);self.compare(node,disk.inventory(self.root/'before-network'/node),'before-network')
        actions=[]
        initialized=self.initialization_point()
        actions.append((initialized,'initialize',(self.model.joining,disk.inventory(self.root/'joining-originals-native/replica'))))
        for (index,node),points in self.base.phases.items():actions.append((points['PUBLICATION_BEFORE_RETURN'],'phase',(index,node)))
        for own in self.base.windows:
            if own['start']<0:continue
            if self.events[own['start']]['event'] in ('INSTALL_BEFORE_RETURN','ADOPTION_INSTALL_BEFORE_RETURN'):
                actions.append((own['start'],'compare',(own['node'],disk.inventory(self.root/own['path']),'generation')))
        for node,scope in self.lifetimes():
            found=[i for i,v in enumerate(self.events) if v.get('node')==node and v.get('scope')==scope and v['event']==RESEAL[-1]]
            need(len(found)==1,'joining future exact reopen count');actions.append((found[0],'reopen',(node,scope,found[0])))
        for _,kind,values in sorted(actions,key=lambda v:v[0]):getattr(self,kind)(*values)
        need(self.used=={v['start'] for v in self.tx},'joining future unbound durable writes')
        eligible={i for i,v in enumerate(self.events) if v['event'] in RETURNS+RESEAL}
        need(self.callbacks==eligible,'joining future unbound completion/reopen')
        for node in self.state:
            label='joining-originals-stable-cold/replica' if node==self.model.joining else 'after-close/'+node
            self.compare(node,disk.inventory(self.root/label),'cold')
        return dict(status='PASS',scope='one-native-'+self.model.kind+'-continuous-future-ledger',durableWrites=len(self.steps),
                    writesByKind=dict(Counter(v['kind'] for v in self.steps)),openReseals=self.reseals,ledgerComparisons=self.comparisons,
                    finalRevisions={n:v['meta']['revision'] for n,v in self.state.items()},
                    chainSha256=sha(f.canonical(sorted(self.steps,key=lambda v:v['start']))),futureLedgerCompositionQualified=True,
                    learnerLedgerCompositionQualified=False,completePhysicalQualified=False,processDeathQualified=False,phase3Complete=False)


def replay(root):return Replay(root).run()


def validate(root):
    root=Path(root);before=a.n.s.collection.inventory(root);original=a.validate(root);result=replay(root)
    need(a.n.s.collection.inventory(root)==before,'joining future original changed')
    return dict(status='PARTIAL',precondition=original,future=result,futureLedgerCompositionQualified=True,
                learnerLedgerCompositionQualified=False,sameViewPhysicalQualified=False,completePhysicalQualified=False,
                forceAndNetworkQualified=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={
    'write-force-missing':'joining future exact write force order',
    'rename-before-force':'joining future exact write force order',
    'write-truncated':'joining future incomplete durable write',
    'event-forged-owner-scope':'joining future event shape',
    'event-forged-field':'joining future event shape',
    'unsupported-recovery':'joining future unsupported event',
    'unbound-write':'joining future unbound durable writes',
    'record-write-omitted':'joining future exact recording count',
    'record-write-duplicated':'joining future exact recording count',
    'record-after-publication':'joining future exact recording count',
    'clear-before-promotion':'joining future exact bounded write count',
    'clear-after-completion':'joining future exact bounded write count',
    'record-return-before-force':'joining future exact completion lifetime: FUTURE_RETENTION_BEFORE_RETURN',
    'ack-before-return':'joining future exact completion lifetime: FUTURE_RETENTION_ACK_BEFORE_RETURN',
    'unbound-return':'joining future unbound completion/reopen',
    'reopen-parent-missing':'joining future exact reopen count',
    'reopen-parent-before-file':'joining future reopen force order',
    'reopen-after-accept':'joining future reopen before accept recovery',
    'unbound-reopen':'joining future unbound completion/reopen',
}


def mutate(root,name,*,reader=None):
    need(name in NEGATIVES,'joining future unknown negative')
    reader=Replay(root) if reader is None else reader;reader.run();events=reader.events
    record=next(v for v in reader.steps if v['kind']=='record')
    clear=next(v for v in reader.steps if v['kind']=='clear')
    def write(step):return [v for v in events[step['start']:step['end']+1] if v.get('node')==step['node'] and v['event'] in WRITES]
    def move(values,target,after=False):
        ids={id(v) for v in values};events[:]=[v for v in events if id(v) not in ids]
        at=next(i for i,v in enumerate(events) if v is target)+int(after);events[at:at]=values
    def following(step,point):
        return next(v for i,v in enumerate(events) if i>step['end'] and v.get('node')==step['node'] and v['event']==point)
    values=write(record)
    if name=='write-force-missing':events.remove(next(v for v in values if v['event']==WRITES[3]))
    elif name=='rename-before-force':move([values[5]],values[3])
    elif name=='write-truncated':
        last=reader.tx[-1];del events[last['end']]
    elif name=='event-forged-owner-scope':values[0]['scope']='initial-owner'
    elif name=='event-forged-field':values[0]['claimedRevision']=1
    elif name=='unsupported-recovery':events.append(dict(node='node-1',event='FUTURE_RETENTION_DISCARDED'))
    elif name=='unbound-write':events.extend(dict(node='node-1',event=p) for p in WRITES)
    elif name=='record-write-omitted':
        ids={id(v) for v in values};events[:]=[v for v in events if id(v) not in ids]
    elif name=='record-write-duplicated':move([dict(v) for v in values],values[0])
    elif name=='record-after-publication':move(values,following(record,'PUBLICATION_VALIDATED'),True)
    elif name=='clear-before-promotion':
        target=max((i for i,v in enumerate(events[:clear['start']]) if v.get('node')==clear['node'] and v['event']==RETURNS[2]))
        move(write(clear),events[target])
    elif name=='clear-after-completion':move(write(clear),following(clear,RETURNS[3]),True)
    elif name=='record-return-before-force':move([following(record,RETURNS[0])],values[3])
    elif name=='ack-before-return':move([following(record,RETURNS[1])],following(record,RETURNS[0]))
    elif name=='unbound-return':events.append(dict(node='node-1',event=RETURNS[0]))
    elif name=='unbound-reopen':events.extend(dict(node='node-9',event=p) for p in RESEAL)
    else:
        parent=next(v for v in events if v.get('node')=='node-1' and v['event']==RESEAL[1])
        active=next(v for v in events if v.get('node')=='node-1' and v['event']==RESEAL[0])
        if name=='reopen-parent-missing':events.remove(parent)
        elif name=='reopen-parent-before-file':move([parent],active)
        else:
            target=next(v for v in events if v.get('node')=='node-1' and v['event']=='ACCEPT_ACTIVE_PARENT_FORCED')
            move([active,parent],target,True)
    (Path(root)/'events.json').write_bytes(f.canonical(events))


def negative(root,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-same-view-future-') as temp:
        copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,name)
        after=a.n.s.collection.inventory(copied)
        protected=lambda x:{k:v for k,v in x['files'].items() if k!='events.json'}
        need(protected(before)==protected(after) and before['directories']==after['directories'],
             'joining future negative changed original files')
        read=lambda p:a.n.s.collection.read_json(p,'events.json',a.n.s.collection.EVENT_BYTES)
        others=lambda rows:[v for v in rows if not v['event'].startswith('FUTURE_RETENTION_')]
        need(others(read(Path(root)))==others(read(copied)),'joining future negative changed other observations')
        try:replay(copied)
        except ValueError as error:need(str(error)==NEGATIVES[name],'joining future unrelated negative: '+name+': '+str(error))
        else:raise ValueError('joining future accepted mutation: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],
                mutationScope='future-callbacks-only',originalFilesAndOtherObservationsUnchanged=True)


def qualify(root,*,workers=1,progress=None):
    need(type(workers) is int and 1<=workers<=4,'joining future replay workers')
    root=Path(root);original=validate(root);before=a.n.s.collection.inventory(root);results=[]
    if progress:progress(dict(stage='original',status='PASS',negativeCases=len(NEGATIVES)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(negative,root,before,name):name for name in NEGATIVES}
        for task in as_completed(pending):
            name=pending[task]
            try:result=task.result()
            except Exception as error:result=dict(case=name,status='FAIL',failure=str(error),type=type(error).__name__)
            results.append(result)
            if progress:progress(dict(result,completed=len(results),total=len(NEGATIVES)))
    need(a.n.s.collection.inventory(root)==before,'joining future qualification changed original')
    need(all(v['status']=='REJECTED' for v in results),'joining future negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:v['case']),
                negativePrecondition='full-original-authority; unchanged original files, wire and non-future observations',
                mutatedPrerequisiteReplayed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    result=qualify(args.root,workers=args.workers,progress=lambda v:print(json.dumps(v),file=sys.stderr,flush=True)) if args.qualify else validate(args.root)
    print(json.dumps(result,sort_keys=True))
