"""Original continuous learner ledgers, selected merges and retaining opens.

The same-view physical/network/authority/future chain must pass first. Custody
retention callbacks are a distinct admission transaction, not a GSLR revision.
"""
import argparse
from collections import Counter
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_same_view_future as prior

a=prior.a
f,disk,need,sha=a.f,a.disk,a.need,a.sha
learner,init=a.physical.learner,a.physical.init
FILE=learner.FILE
WRITES=['LEARNER_RETENTION_'+v for v in ('BEFORE_WRITE','PREFIX_WRITTEN','WRITTEN','FORCED',
                                       'CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED')]
RESEAL=['LEARNER_RETENTION_RECOVERY_ACTIVE_FORCED','LEARNER_RETENTION_RECOVERY_PARENT_FORCED']
RETURNS=['LEARNER_RETENTION_ACK_BEFORE_RETURN','LEARNER_RETENTION_CONFIRMATION_BEFORE_RETURN',
         'SELECTED_LEARNER_RETENTION_COMPLETED']
ADMISSION=['LEARNER_RETENTION_'+v for v in ('CREATED','PREFIX_WRITTEN','WRITTEN','FORCED','PARENT_FORCED',
           'RESEAL_FORCED','RESEAL_PARENT_FORCED','RENAMED','ACTIVE_FORCED','ACTIVE_PARENT_FORCED','BEFORE_RETURN')]


def relevant(event):return event.startswith('LEARNER_RETENTION_') or event==RETURNS[-1]


def observations(events,joining,*,old_owner_lifetimes=None):
    lifetimes=prior.declared_old_lifetimes(events,joining,old_owner_lifetimes)
    admission=[(i,v) for i,v in enumerate(events) if relevant(v['event']) and v.get('scope')=='learner-admission']
    need([v['event'] for _,v in admission]==ADMISSION and
         all(v==dict(node=joining,scope='learner-admission',event=v['event']) for _,v in admission),
         'joining learner exact admission retention sequence')
    first,last=admission[0][0],admission[-1][0]
    before=[i for i,v in enumerate(events) if v.get('node')==joining and v.get('scope')=='learner-admission' and v['event']=='LEARNER_PLAN_BEFORE_RETURN']
    after=[i for i,v in enumerate(events) if v.get('node')==joining and v.get('scope')=='learner-admission' and v['event']=='LEARNER_REPLICA_CREATED']
    need(len(before)==len(after)==1 and before[0]<first<last<after[0],'joining learner admission before replica')
    excluded={i for i,_ in admission};pending={};tx=[]
    for at,row in enumerate(events):
        point=row['event']
        if not relevant(point) or at in excluded:continue
        need(point in WRITES+RESEAL+RETURNS,'joining learner unsupported retention event')
        cold=lifetimes.get(row.get('node'));scoped=cold is not None and at>=cold[0]
        need(set(row)==({'node','scope','event'} if row.get('node')==joining or scoped else {'node','event'}),'joining learner event shape')
        if scoped:need(row['scope']==cold[1],'joining learner original event owner')
        if point not in WRITES:continue
        node=row['node'];held=pending.setdefault(node,[])
        need(point==WRITES[len(held)] and (not held or row.get('scope')==held[0][1].get('scope')),
             'joining learner exact write force order')
        held.append((at,row))
        if len(held)==len(WRITES):
            tx.append(dict(node=node,scope=row.get('scope'),start=held[0][0],end=at));del pending[node]
    need(not pending,'joining learner incomplete durable write')
    return tx,excluded


class Replay:
    def __init__(self,root,*,base=None,old_owner_lifetimes=None):
        self.root=Path(root);self.base=a.Replay(root) if base is None else base;self.model=self.base.model;self.events=self.base.events
        self.tx,self.admission=observations(self.events,self.model.joining,old_owner_lifetimes=old_owner_lifetimes)
        self.state={};self.steps=[];self.used=set();self.callbacks=set();self.comparisons=0;self.selected=0;self.reseals=0

    def files(self,own):return disk.inventory(self.root/own['path'])

    def write_scope(self,node,at):
        return 'continuation-owner' if node==self.model.joining else None

    def reopen_files(self,node,at):
        return disk.inventory(self.root/'before-network'/node) if node!=self.model.joining else self.files(self.base.current(node,at,at))

    def compare(self,node,raw,label):
        need(self.state.get(node)==raw,'joining learner exact continuous ledger: '+label+': '+node);self.comparisons+=1

    def callback(self,node,name,lower,upper):
        points=[i for i,v in enumerate(self.events) if lower<i<upper and v.get('node')==node and v['event']==name]
        need(len(points)==1,'joining learner exact completion lifetime: '+name)
        at=points[0];need(at not in self.callbacks and self.events[at].get('scope')==self.write_scope(node,at),
                          'joining learner original completion owner')
        return at

    def change(self,node,after,lower,upper,kind):
        before=self.state[node];changed=after!=before
        actual=[v for v in self.tx if v['node']==node and lower<v['start'] and v['end']<upper]
        need(len(actual)==int(changed),'joining learner '+kind+' durable write count')
        if not changed:return
        tx=actual[0];need(tx['start'] not in self.used and tx['scope']==self.write_scope(node,tx['start']),
                          'joining learner original write owner')
        old,new=learner.decode(before),learner.decode(after)
        need(new['root']==old['root'] and new['owner']==old['owner'] and new['revision']==old['revision']+1 and new['previous']==sha(before),
             'joining learner exact revision predecessor')
        self.used.add(tx['start']);self.state[node]=after
        self.steps.append(dict(node=node,kind=kind,start=tx['start'],end=tx['end'],before=sha(before),after=sha(after),revision=new['revision']))

    def record(self,node,row,own,lower,upper):
        files=self.files(own);request=row['request']['payload'];self.compare(node,files[FILE],'record-before')
        after=learner.offer(dict(files,**{FILE:self.state[node]}),request['request'],request['learner'])[FILE]
        need(after!=self.state[node],'joining learner recording must advance')
        finish=self.callback(node,RETURNS[0],lower,upper);self.change(node,after,lower,finish,'record');self.callbacks.add(finish)
        if node==row['request']['recipient']['node']:
            value=learner.decode(after)
            need(row['response']['payload']==dict(intent=sha(f.canonical(request)),revision=value['revision'],ledger=sha(after)),
                 'joining learner exact original recording ACK')

    def confirm(self,row,finish):
        q=row['request'];node=q['sender']['node'];own=self.base.current(node,row['sent'],row['delivered'])
        proof=dict(query=a.c.encoded(f.encode('wire',row['kind'],q)),ack=a.c.encoded(f.encode('wire',row['answer'],row['response'])))
        endpoint=row['response']['payload']['endpoint'];before=self.state[node]
        after=init.confirmed_learner(before,proof,endpoint);need(after!=before,'joining learner confirmation must advance')
        self.change(node,after,row['delivered'],finish,'confirm');self.callbacks.add(finish)
        need((self.root/('joining-confirmed-'+node+'.json')).read_bytes()==f.canonical(learner.decode(after)['plan']),
             'joining learner exact confirmed plan')
        init.transition.require_coverage(dict(self.files(own),**{FILE:after}))

    def selection(self,own):
        node=own['node'];end=own['start'];raw=own['members']['selected.gsr'];chosen=f.decode(raw,'records','SELECTED')
        lower=max(i for i,v in enumerate(self.events[:end]) if v.get('node')==node and v['event']=='INSTALL_PARENT_FORCED')
        rows=[];originals=[]
        for ref in chosen['sources']:
            found=[v for v in self.base.sources if sha(v['basis'])==ref['basisDigest']]
            need(len(found)==1 and found[0]['node']==ref['voter'] and found[0]['start']<lower,'joining learner selected original source')
            source=found[0];wrapper,state=init.retention.source(source['packet'],source['value'],0x47534c46,32768)
            rows.append((source['basis'],source['packet'],wrapper));originals.append(learner.frame(state))
        intent=learner.intent(own['identity'],raw,self.state[node],rows)
        need(own['packet']['objects'].get(sha(intent))==intent,'joining learner selected original before ledger')
        after=a.physical.c.merge_learner(self.state[node],originals,own['packet'])
        changed=after!=self.state[node]
        completes=[i for i,v in enumerate(self.events) if lower<i<end and v.get('node')==node and v['event']==RETURNS[2]]
        need(len(completes)==int(changed),'joining learner selected completion count')
        if completes:self.callback(node,RETURNS[2],lower,end)
        # Peer completion happens first when it changes the peer ledger. A
        # learner write cannot borrow the earlier generation installation force.
        peer=[i for i,v in enumerate(self.events) if lower<i<end and v.get('node')==node and v['event']=='SELECTED_RETENTION_COMPLETED']
        need(len(peer)<=1,'joining learner peer completion count')
        self.change(node,after,max([lower,*peer]),completes[0] if changed else end,'selected')
        self.callbacks.update(completes);self.compare(node,self.files(own)[FILE],'selected');self.selected+=1

    def initialize(self,at):
        node=self.model.joining;need(node not in self.state,'joining learner duplicate initialization')
        own=self.base.current(node,at,at);originals=[];ancestry=[]
        for voter in own['packet']['capsule']['cut']['view']['old']:
            if not any(v['node']==voter and v['start']<at for v in self.base.sources):continue
            remote=self.base.current(voter,at,at);source=a.c.active_source(self.base.sources,self.events,remote,at,at)
            originals.append((source['basis'],source['members']['source.gscp']));ancestry.append(remote['members'].get('ancestry.gsr',b''))
        seed,ledgers=init.retention.derive(own['packet'],own['identity'],originals,confirmed_peers=True,source_ancestry=ancestry)
        need((self.root/'joining-retention-seed.json').read_bytes()==seed,'joining learner exact original joining seed')
        self.state[node]=ledgers[FILE];self.compare(node,self.files(own)[FILE],'joining-initialized')

    def capture(self,source):
        _,state=init.retention.source(source['packet'],source['value'],0x47534c46,32768)
        self.compare(source['node'],learner.frame(state),'grant-'+str(source['value']['ballot']['counter']))

    def reopen(self,node,scope,at):
        rows=[(i,v['event']) for i,v in enumerate(self.events) if v.get('node')==node and v.get('scope')==scope]
        points={p:[i for i,v in rows if v==p] for p in [*RESEAL,'RETENTION_RECOVERY_ACTIVE_FORCED']}
        need(all(len(v)==1 for v in points.values()),'joining learner exact reopen count')
        order=[v[0] for v in points.values()];need(order[0]<order[1]==at<order[2],'joining learner reopen force order')
        prior='JOINING_RETENTION_BEFORE_RETURN' if scope=='initial-owner' else 'CURRENT_DIRECTORY_FORCED'
        starts=[i for i,v in rows if v==prior];need(starts and starts[0]<order[0],'joining learner reopen before current force')
        if node==self.model.joining:
            a.c.owner_lifetime(self.events,node,scope,order[0],at)
        files=self.reopen_files(node,at)
        self.compare(node,files[FILE],'reopen');self.callbacks.update(order[:2]);self.reseals+=1

    def recording_actions(self):
        groups=defaultdict(list);actions=[]
        for row in self.base.rows:
            if row['kind']=='LEARNER_RETENTION_INTENT':
                q=row['request'];groups[q['sender']['node'],q['trace']].append(row)
        for (node,_),rows in groups.items():
            rows=sorted(rows,key=lambda v:v['sent']);first=rows[0];q=first['request']
            context=lambda v:f.canonical({k:v['request'][k] for k in ('sender','view','ballot','payload')})
            need(all(context(v)==context(first) for v in rows),'joining learner mixed original recording round')
            peers=[v['request']['recipient']['node'] for v in rows]
            need(node not in peers and len(peers)==len(set(peers)),'joining learner duplicate original recording voter')
            # A redundant reply can arrive after selection (or never arrive).
            # It still has an original remote force, while the one local force
            # precedes the first send and belongs to this sending generation.
            own=self.base.current(node,first['sent'],rows[-1]['sent'])
            finish=self.callback(node,RETURNS[0],own['start'],first['sent'])
            actions.append((finish,'record',(node,first,own,own['start'],first['sent'])))
            for row in rows:
                peer=row['request']['recipient']['node'];remote=self.base.current(peer,row['received'],row['offered'])
                finish=self.callback(peer,RETURNS[0],row['received'],row['offered'])
                actions.append((finish,'record',(peer,row,remote,row['received'],row['offered'])))
        return actions

    def lifetimes(self):
        return a.peer.owner_lifetimes(self.model)

    def initialization_point(self):
        points=[i for i,v in enumerate(self.events) if v['event']=='JOINING_RETENTION_BEFORE_RETURN']
        need(len(points)==1,'joining learner original initialization count')
        return points[0]

    def run(self):
        for node,files in learner.initialize(self.model.original).items():
            self.state[node]=files[FILE];self.compare(node,disk.inventory(self.root/'before-network'/node)[FILE],'bootstrap')
        actions=[]
        initialized=self.initialization_point();actions.append((initialized,'initialize',(initialized,)))
        actions.extend(self.recording_actions())
        for row in self.base.rows:
            q=row['request'];node=q['sender']['node'];peer=q['recipient']['node']
            if row['kind']=='LEARNER_HEAD_QUERY':
                own=self.base.current(node,row['sent'],row['delivered']);finish=self.callback(node,RETURNS[1],row['delivered'],own['end'])
                actions.append((finish,'confirm',(row,finish)))
        for own in self.base.windows:
            if own['start']<0:continue
            event=self.events[own['start']]['event']
            if event=='INSTALL_BEFORE_RETURN':actions.append((own['start'],'selection',(own,)))
            elif event=='ADOPTION_INSTALL_BEFORE_RETURN':actions.append((own['start'],'compare',(own['node'],self.files(own)[FILE],'adoption')))
        for (index,node),points in self.base.phases.items():
            for label,point in [('applied','APPLY_BEFORE_RETURN'),('published','PUBLICATION_BEFORE_RETURN')]:
                actions.append((points[point],'compare',(node,self.model.owner(label,index,node)[FILE],label+'-'+str(index))))
        actions.extend((v['start'],'capture',(v,)) for v in self.base.sources)
        for node,scope in self.lifetimes():
            found=[i for i,v in enumerate(self.events) if v.get('node')==node and v.get('scope')==scope and v['event']==RESEAL[-1]]
            need(len(found)==1,'joining learner exact reopen count');actions.append((found[0],'reopen',(node,scope,found[0])))
        for _,kind,args in sorted(actions,key=lambda v:v[0]):getattr(self,kind)(*args)
        need(self.used=={v['start'] for v in self.tx},'joining learner unbound durable writes')
        need(self.callbacks=={i for i,v in enumerate(self.events) if v['event'] in RESEAL+RETURNS},'joining learner unbound completion/reopen')
        for node in self.state:
            path='joining-originals-stable-cold/replica' if node==self.model.joining else 'after-close/'+node
            self.compare(node,disk.inventory(self.root/path)[FILE],'cold')
        return dict(status='PASS',scope='one-native-'+self.model.kind+'-continuous-learner-ledger',durableWrites=len(self.steps),
                    writesByKind=dict(Counter(v['kind'] for v in self.steps)),openReseals=self.reseals,selectedTransitions=self.selected,
                    ledgerComparisons=self.comparisons,capturedLedgers=len(self.base.sources),admissionCustodyEvents=len(self.admission),
                    finalRevisions={n:learner.decode(raw)['revision'] for n,raw in self.state.items()},
                    chainSha256=sha(f.canonical(sorted(self.steps,key=lambda v:v['start']))),learnerLedgerCompositionQualified=True,
                    sameViewPhysicalQualified=False,completePhysicalQualified=False,processDeathQualified=False,phase3Complete=False)


def replay(root):return Replay(root).run()


def validate(root):
    root=Path(root);before=a.n.s.collection.inventory(root);original=prior.validate(root);result=replay(root)
    need(a.n.s.collection.inventory(root)==before,'joining learner original changed')
    return dict(status='PARTIAL',precondition=original,learner=result,learnerLedgerCompositionQualified=True,
                futureLedgerCompositionQualified=True,sameViewPhysicalQualified=False,completePhysicalQualified=False,
                forceAndNetworkQualified=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={
    'force-missing':'joining learner exact write force order',
    'rename-before-force':'joining learner exact write force order',
    'incomplete-write':'joining learner incomplete durable write',
    'forged-event-field':'joining learner event shape',
    'wrong-write-scope':'joining learner original write owner',
    'admission-force-missing':'joining learner exact admission retention sequence',
    'admission-duplicate':'joining learner exact admission retention sequence',
    'admission-wrong-owner':'joining learner exact admission retention sequence',
    'admission-before-plan':'joining learner admission before replica',
    'admission-after-replica':'joining learner admission before replica',
    'record-before-generation':'joining learner record durable write count',
    'record-after-ACK':'joining learner record durable write count',
    'confirm-before-delivery':'joining learner confirm durable write count',
    'confirm-after-completion':'joining learner confirm durable write count',
    'selected-before-peer':'joining learner selected durable write count',
    'selected-after-return':'joining learner selected durable write count',
    'selected-completion-missing':'joining learner selected completion count',
    'selected-completion-duplicate':'joining learner selected completion count',
    'unbound-write':'joining learner unbound durable writes',
    'unbound-completion':'joining learner unbound completion/reopen',
    'unsupported-recovery':'joining learner unsupported retention event',
    'reopen-parent-missing':'joining learner exact reopen count',
    'reopen-parent-before-file':'joining learner reopen force order',
    'reopen-before-current':'joining learner reopen before current force',
    'reopen-after-peer':'joining learner reopen force order',
    'unbound-reopen':'joining learner unbound completion/reopen',
}


def mutate(root,name,*,reader=None):
    need(name in NEGATIVES,'joining learner unknown negative');root=Path(root)
    reader=Replay(root) if reader is None else reader;reader.run();events=reader.events
    def move(values,target,after=False):
        ids={id(v) for v in values};events[:]=[v for v in events if id(v) not in ids]
        at=next(i for i,v in enumerate(events) if v is target)+int(after);events[at:at]=values
    def remove(values):
        ids={id(v) for v in values};events[:]=[v for v in events if id(v) not in ids]
    def writes(step):return [v for v in events[step['start']:step['end']+1] if v.get('node')==step['node'] and v['event'] in WRITES]
    def before(step,point):return events[max(i for i,v in enumerate(events[:step['start']]) if v.get('node')==step['node'] and v['event']==point)]
    def after(step,point):return next(v for i,v in enumerate(events) if i>step['end'] and v.get('node')==step['node'] and v['event']==point)
    record=next(v for v in reader.steps if v['kind']=='record');values=writes(record)
    if name=='force-missing':remove([values[3]])
    elif name=='rename-before-force':move([values[5]],values[3])
    elif name=='incomplete-write':del events[reader.tx[-1]['end']]
    elif name=='forged-event-field':values[0]['revision']=1
    elif name=='wrong-write-scope':
        step=next(v for v in reader.steps if v['node']==reader.model.joining)
        for v in writes(step):v['scope']='initial-owner'
    elif name.startswith('admission-'):
        values=[events[i] for i in sorted(reader.admission)]
        if name=='admission-force-missing':remove([values[3]])
        elif name=='admission-duplicate':move([dict(values[3])],values[3])
        elif name=='admission-wrong-owner':values[0]['node']='node-1'
        else:
            point='LEARNER_PLAN_BEFORE_RETURN' if name=='admission-before-plan' else 'LEARNER_REPLICA_CREATED'
            target=next(v for v in events if v.get('scope')=='learner-admission' and v['event']==point)
            move(values,target,name=='admission-after-replica')
    elif name=='record-before-generation':move(values,before(record,'PUBLICATION_BEFORE_RETURN'))
    elif name=='record-after-ACK':move(values,after(record,RETURNS[0]),True)
    elif name.startswith('confirm-'):
        step=next(v for v in reader.steps if v['kind']=='confirm')
        if name=='confirm-after-completion':move(writes(step),after(step,RETURNS[1]),True)
        else:
            row=next(v for v in reader.base.rows if v['kind']=='LEARNER_HEAD_QUERY' and v['request']['sender']['node']==step['node'])
            move(writes(step),events[row['delivered']])
    elif name.startswith('selected-'):
        step=next(v for v in reader.steps if v['kind']=='selected');finish=after(step,RETURNS[2])
        if name=='selected-completion-missing':remove([finish])
        elif name=='selected-completion-duplicate':move([dict(finish)],finish)
        elif name=='selected-before-peer':move(writes(step),before(step,'SELECTED_RETENTION_COMPLETED'))
        else:move(writes(step),after(step,'INSTALL_BEFORE_RETURN'),True)
    elif name=='unbound-write':events.extend(dict(node='node-1',event=p) for p in WRITES)
    elif name=='unbound-completion':events.append(dict(node='node-1',event=RETURNS[0]))
    elif name=='unsupported-recovery':events.append(dict(node='node-1',event='LEARNER_RETENTION_DISCARDED'))
    elif name=='unbound-reopen':events.extend(dict(node='node-9',event=p) for p in RESEAL)
    else:
        values=[next(v for v in events if v.get('node')=='node-1' and v['event']==p) for p in RESEAL]
        if name=='reopen-parent-missing':remove([values[1]])
        elif name=='reopen-parent-before-file':move([values[1]],values[0])
        else:
            point='CURRENT_DIRECTORY_FORCED' if name=='reopen-before-current' else 'RETENTION_RECOVERY_ACTIVE_FORCED'
            target=next(v for v in events if v.get('node')=='node-1' and v['event']==point)
            move(values,target,name=='reopen-after-peer')
    (root/'events.json').write_bytes(f.canonical(events))


def negative(root,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-same-view-learner-') as temp:
        copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,name)
        after=a.n.s.collection.inventory(copied);protected=lambda x:{k:v for k,v in x['files'].items() if k!='events.json'}
        need(protected(before)==protected(after) and before['directories']==after['directories'],
             'joining learner negative changed original files')
        read=lambda p:a.n.s.collection.read_json(p,'events.json',a.n.s.collection.EVENT_BYTES)
        others=lambda events:[v for v in events if not relevant(v['event'])]
        need(others(read(Path(root)))==others(read(copied)),'joining learner negative changed other observations')
        try:replay(copied)
        except ValueError as error:need(str(error)==NEGATIVES[name],'joining learner unrelated negative: '+name+': '+str(error))
        else:raise ValueError('joining learner accepted mutation: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],mutationScope='learner-retention-callbacks-only',
                originalFilesAndOtherObservationsUnchanged=True)


def qualify(root,*,workers=1,progress=None):
    need(type(workers) is int and 1<=workers<=4,'joining learner replay workers')
    root=Path(root);original=validate(root);before=a.n.s.collection.inventory(root);results=[]
    if progress:progress(dict(stage='original',status='PASS',negativeCases=len(NEGATIVES)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,before,name):name for name in NEGATIVES}
        for task in as_completed(tasks):
            name=tasks[task]
            try:result=task.result()
            except Exception as error:result=dict(case=name,status='FAIL',failure=str(error),type=type(error).__name__)
            results.append(result)
            if progress:progress(dict(result,completed=len(results),total=len(NEGATIVES)))
    need(a.n.s.collection.inventory(root)==before,'joining learner qualification changed original')
    need(all(v['status']=='REJECTED' for v in results),'joining learner negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:v['case']),
                negativePrecondition='full-original-authority-and-future; unchanged original files, wire and other observations',
                mutatedPrerequisiteReplayed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    result=qualify(args.root,workers=args.workers,progress=lambda v:print(json.dumps(v),file=sys.stderr,flush=True)) if args.qualify else validate(args.root)
    print(json.dumps(result,sort_keys=True))
