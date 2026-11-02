"""Continuous original peer/future revision chains across REMOVE process death.

Start at the independently derived prelude once. Every later snapshot is a
comparison, never a new seed. The complete floor reader is a prerequisite.
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

from . import remove_process_maintenance as maintenance
from . import remove_retention_evidence as healthy

m,h=maintenance,healthy
peer,future=h.peer,h.future
n,p,c,f,need,sha=m.n,m.p,m.c,m.f,m.need,m.sha


def open_reseals(base):
    result=[]
    for node in base.history.old:
        rows=[(i,v) for i,v in enumerate(base.events) if v['node']==node and v['event'] in p.OPEN]
        paths=['before-network']+([base.profile['mode']+'-opened-0','resume-opened-0'] if node=='node-1' else [])
        anchors=[i for i,(_,v) in enumerate(rows) if v['event']==peer.RESEAL[0]]
        need(len(anchors)==len(paths),'REMOVE process retention exact open count')
        used=set()
        for anchor,path in zip(anchors,paths):
            # Installation also revalidates CURRENT; it is not a new open.
            block=rows[max(0,anchor-5):anchor+6]
            need([v['event'] for _,v in block]==list(p.OPEN),'REMOVE process retention exact open force order')
            need(all(set(v)=={'node','event'} for _,v in block),'REMOVE process retention original open owner')
            points={v['event']:i for i,v in block}
            used.update(points[name] for name in peer.RESEAL+future.RESEAL)
            result.append(dict(node=node,path=path,peer=points[peer.RESEAL[-1]],future=points[future.RESEAL[-1]],
                futureEvents=[points[name] for name in future.RESEAL]))
        need(used=={i for i,v in rows if v['event'] in peer.RESEAL+future.RESEAL},'REMOVE process retention unbound open reseal')
    return result


def snapshot_actions(base,method):
    actions=[]
    for at,row in enumerate(base.events):
        if row['event']=='PROCESS_SNAPSHOT':actions.append((at,method,(row['value'],)))
        elif row['event']=='PROCESS_CUT':actions.append((at,method,('interrupted',)))
    return actions


def prepared(root,profile):
    base=m.Replay(root,profile);base.run()
    base.phases=n.n.phase.blocks(base.events,base.history)
    return base


class PeerReplay(h.PeerReplay):
    def __init__(self,root,profile,*,base=None):
        base=prepared(root,profile) if base is None else base
        self.__dict__.update(base.__dict__)
        self.state={};self.steps=[];self.used=set();self.comparisons=0;self.completions=set();self.open_steps=[]
        h.peer_event_shapes(self.events,self.history.old)
        self.tx=peer.transactions(self.events);self.reseals=open_reseals(base)

    def sequence(self,node,changes,lower,upper,kind):
        actual=[v for v in self.tx if v['node']==node and lower<v['start'] and v['end']<upper]
        need(len(actual)==len(changes),'joining peer '+kind+' durable write count')
        for tx,(before,after,cause) in zip(actual,changes):
            need(tx['start'] not in self.used and tx['scope'] is None and peer.peers.decode(before)['owner']['node']==node,
                 'joining peer original write owner')
            peer.revision(before,after);self.used.add(tx['start'])
            self.steps.append(dict(node=node,start=tx['start'],end=tx['end'],kind=kind,cause=cause,
                before=sha(before),after=sha(after),revision=peer.peers.decode(after)['revision']))

    def reseal(self,row):
        self.compare(row['node'],c.inventory(self.root/row['path']/row['node'])[peer.FILE],row['path']+'-reseal')
        self.open_steps.append(dict(node=row['node'],path=row['path'],revision=peer.peers.decode(self.state[row['node']])['revision'],
            digest=sha(self.state[row['node']])))

    def snapshot(self,path):
        for node in self.history.old:self.compare(node,c.inventory(self.root/path/node)[peer.FILE],path)

    def run(self):
        original=peer.t.selected.initialize(n.n.d.b.original(self.root,len(self.history.old),False))
        for node,files in original.items():self.state[node]=files[peer.FILE]
        self.snapshot('before-network')
        actions=[(row['end'],'floor',(row,)) for row in self.floor_inputs]
        for own in self.windows:
            if own['start']>=0 and self.events[own['start']]['event']=='INSTALL_BEFORE_RETURN':
                actions.append((own['start'],'selection',(own,)))
        actions.extend((points['PUBLICATION_BEFORE_RETURN'],'publication',(index,node)) for (index,node),points in self.phases.items())
        actions.extend((v['start'],'capture',(v,)) for v in self.sources if v['start']>=0)
        actions.extend((v['peer'],'reseal',(v,)) for v in self.reseals)
        actions+=snapshot_actions(self,'snapshot')
        for _,kind,values in sorted(actions,key=lambda v:v[0]):getattr(self,kind)(*values)
        need(self.used=={v['start'] for v in self.tx},'joining peer unbound durable writes')
        need(self.completions=={i for i,v in enumerate(self.events) if v['event']=='SELECTED_RETENTION_COMPLETED'},
             'joining peer unbound selected completions')
        self.snapshot('after-close')
        return dict(status='PASS',durableWrites=len(self.steps),writesByKind=dict(Counter(v['kind'] for v in self.steps)),
            ledgerComparisons=self.comparisons,capturedLedgers=sum(v['start']>=0 for v in self.sources),openReseals=len(self.reseals),openRevisions=self.open_steps,
            finalRevisions={node:peer.peers.decode(raw)['revision'] for node,raw in self.state.items()},
            chainSha256=sha(f.canonical(sorted(self.steps,key=lambda v:v['start']))))


class FutureReplay(future.Replay):
    def __init__(self,root,profile,*,base=None):
        self.base=prepared(root,profile) if base is None else base
        self.root=self.base.root;self.events=self.base.events;self.model=self.base.history
        self.tx,self.write_events=future.observations(self.events,joining=None)
        need(all(v['node'] in self.model.old for v in self.events if v['event'].startswith('FUTURE_RETENTION_')),
             'REMOVE process future original owner')
        self.state={};self.used=set();self.callbacks=set();self.steps=[];self.comparisons=0;self.reseals=0;self.open_steps=[]
        self.opens=open_reseals(self.base)

    def reopen_original(self,row):
        self.compare(row['node'],c.inventory(self.root/row['path']/row['node']),row['path']+'-reopen')
        self.callbacks.update(row['futureEvents']);self.reseals+=1
        state=self.state[row['node']]
        self.open_steps.append(dict(node=row['node'],path=row['path'],revision=state['meta']['revision'],digest=sha(state['raw'])))

    def snapshot(self,path):
        for node in self.model.old:self.compare(node,c.inventory(self.root/path/node),path)

    def run(self):
        original=peer.t.selected.initialize(n.n.d.b.original(self.root,len(self.model.old),False))
        for node,files in original.items():
            derived=dict(files,**{future.future.FILE:future.future.frame(future.future.initial(files),{})})
            self.initialize(node,derived)
        self.snapshot('before-network')
        actions=[(v['future'],'reopen_original',(v,)) for v in self.opens]
        for (index,node),points in self.base.phases.items():actions.append((points['PUBLICATION_BEFORE_RETURN'],'phase',(index,node)))
        actions+=snapshot_actions(self.base,'snapshot')
        for _,kind,values in sorted(actions,key=lambda v:v[0]):getattr(self,kind)(*values)
        need(self.used=={v['start'] for v in self.tx},'joining future unbound durable writes')
        need(self.callbacks=={i for i,v in enumerate(self.events) if v['event'] in future.RETURNS+future.RESEAL},
             'joining future unbound completion/reopen')
        self.snapshot('after-close')
        return dict(status='PASS',durableWrites=len(self.steps),writesByKind=dict(Counter(v['kind'] for v in self.steps)),
            openReseals=self.reseals,openRevisions=self.open_steps,ledgerComparisons=self.comparisons,
            finalRevisions={node:v['meta']['revision'] for node,v in self.state.items()},
            chainSha256=sha(f.canonical(sorted(self.steps,key=lambda v:v['start']))))


def replay(root,profile):
    base=prepared(root,profile)
    return dict(status='PARTIAL',peers=PeerReplay(root,profile,base=base).run(),future=FutureReplay(root,profile,base=base).run(),
        retentionRevisionCompositionQualified=True,completeRetirementCallbacksQualified=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=p.run.h.inventory(root);original=m.validate(root)
    result=replay(root,original['precondition']['precondition']['physical']['profile'])
    need(p.run.h.inventory(root)==before,'REMOVE process retention original changed')
    return dict(result,precondition=original)


NEGATIVES={
    'peers':{
        'force-missing':'joining peer exact write force order',
        'rename-before-force':'joining peer exact write force order',
        'incomplete-write':'joining peer incomplete durable write',
        'forged-scope':'REMOVE peer event shape',
        'unbound-write':'joining peer unbound durable writes',
        'maintenance-before-floor':'joining peer maintenance durable write count',
        'maintenance-after-retirement':'joining peer maintenance durable write count',
        'maintenance-omit-write':'joining peer maintenance durable write count',
        'selected-before-install':'joining peer selected durable write count',
        'selected-before-force':'joining peer selected durable write count',
        'selected-without-completion':'joining peer selected completion count',
        'unbound-completion':'joining peer unbound selected completions',
        'publication-after-promotion':'joining peer publication durable write count',
        'publication-before-retirement':'joining peer publication durable write count',
        'duplicate-write':'joining peer publication durable write count',
        'resumed-parent-missing':'REMOVE process retention exact open force order',
        'resumed-parent-before-active':'REMOVE process retention exact open force order',
        'resumed-after-future':'REMOVE process retention exact open force order',
        'unbound-reseal':'REMOVE process retention exact open count',
    },
    'future':{
        'force-missing':'joining future exact write force order',
        'rename-before-force':'joining future exact write force order',
        'incomplete-write':'joining future incomplete durable write',
        'forged-scope':'joining future event shape',
        'foreign-owner':'REMOVE process future original owner',
        'unbound-write':'joining future unbound durable writes',
        'record-omitted':'joining future exact recording count',
        'record-duplicated':'joining future exact recording count',
        'record-after-publication':'joining future exact recording count',
        'clear-before-promotion':'joining future exact bounded write count',
        'clear-after-completion':'joining future exact bounded write count',
        'return-before-force':'joining future exact completion lifetime: FUTURE_RETENTION_BEFORE_RETURN',
        'ack-before-return':'joining future exact completion lifetime: FUTURE_RETENTION_ACK_BEFORE_RETURN',
        'unbound-return':'joining future unbound completion/reopen',
        'resumed-parent-missing':'REMOVE process retention exact open force order',
        'resumed-parent-before-active':'REMOVE process retention exact open force order',
        'resumed-after-accept':'REMOVE process retention exact open force order',
        'unbound-reseal':'REMOVE process retention unbound open reseal',
    },
}


def mutate(root,profile,stage,name):
    reader=(PeerReplay if stage=='peers' else FutureReplay)(root,profile);reader.run();events=reader.events
    shared=[n.e.parse(v) for v in (Path(root)/'history/process-trace.jsonl').read_bytes().splitlines()];mapping=[]
    for row in shared:
        normalized=[row['value']] if row['origin']=='parent' else n.normalize(row['value']['kind'],row['value']['value'])[0]
        mapping.extend([row]*len(normalized))
    need(len(mapping)==len(events),'REMOVE process retention mutation mapping')
    writes=peer.WRITES if stage=='peers' else future.WRITES
    def indices(step):return [i for i in range(step['start'],step['end']+1) if events[i]['node']==step['node'] and events[i]['event'] in writes]
    def selected(kind):return next(v for v in reader.steps if v['kind']==kind)
    def remove(values):
        ids={id(mapping[i]) for i in values};shared[:]=[v for v in shared if id(v) not in ids]
    def move(values,target,*,after=False,duplicate=False):
        rows=[copy.deepcopy(mapping[i]) if duplicate else mapping[i] for i in values]
        if not duplicate:remove(values)
        at=next(i for i,v in enumerate(shared) if v is mapping[target]);shared[at+int(after):at+int(after)]=rows
    def boundary(step,point,before=False):
        found=[i for i,v in enumerate(events) if v['node']==step['node'] and v['event']==point and (i<step['start'] if before else i>step['end'])]
        return found[-1] if before else found[0]
    def value(at):
        row=mapping[at];return row['value'] if row['origin']=='parent' else row['value']['value']
    first=reader.steps[0];write=indices(first)
    if name=='force-missing':remove([write[3]])
    elif name=='rename-before-force':move([write[5]],write[3])
    elif name=='incomplete-write':remove([max(reader.tx,key=lambda v:v['end'])['end']])
    elif name in ('forged-scope','unbound-write'):
        # Child STORE has its own exact schema and process lifetime. Mutate a
        # parent-owned callback so those earlier guards remain valid.
        parent=next(v for v in reader.steps if mapping[v['start']]['origin']=='parent');rows=indices(parent)
        if name=='forged-scope':value(rows[0])['scope']='foreign-owner'
        else:shared.extend(copy.deepcopy(mapping[i]) for i in rows)
    elif name.startswith('resumed-') or name=='unbound-reseal':
        points=peer.RESEAL if stage=='peers' else future.RESEAL
        row=next(v for v in (reader.reseals if stage=='peers' else reader.opens) if v['node']=='node-1' and v['path']=='resume-opened-0')
        end=row['peer' if stage=='peers' else 'future'];cut=(reader if stage=='peers' else reader.base).live[0][1]
        pair=[next(i for i in range(cut+1,end+1) if events[i]['node']=='node-1' and events[i]['event']==point) for point in points]
        if name=='resumed-parent-missing':remove([pair[1]])
        elif name=='resumed-parent-before-active':move([pair[1]],pair[0])
        elif name=='unbound-reseal':shared.extend(copy.deepcopy(mapping[i]) for i in pair)
        else:
            target=next(i for i in range(end+1,len(events)) if events[i]['node']=='node-1' and events[i]['event']==
                (future.RESEAL[0] if stage=='peers' else 'ACCEPT_ACTIVE_PARENT_FORCED'))
            move(pair,target,after=True)
    elif stage=='peers':
        if name.startswith('maintenance-'):
            step=selected('maintenance');rows=indices(step)
            if name=='maintenance-omit-write':remove(rows)
            elif name=='maintenance-before-floor':move(rows,boundary(step,'FLOOR_BEFORE_RETURN',True))
            else:move(rows,boundary(step,'RETIREMENT_RESERVED'),after=True)
        elif name=='unbound-completion':shared.append(dict(origin='parent',value=dict(node='node-1',event='SELECTED_RETENTION_COMPLETED')))
        elif name.startswith('selected-'):
            step=selected('selected');rows=indices(step);completed=boundary(step,'SELECTED_RETENTION_COMPLETED')
            if name=='selected-without-completion':remove([completed])
            elif name=='selected-before-force':move([completed],rows[-1])
            else:move(rows,boundary(step,'INSTALL_PARENT_FORCED',True))
        else:
            step=selected('publication');rows=indices(step)
            if name=='duplicate-write':move(rows,rows[-1],after=True,duplicate=True)
            elif name=='publication-after-promotion':move(rows,boundary(step,'FUTURE_RETENTION_PROMOTED'),after=True)
            elif name=='publication-before-retirement':move(rows,boundary(step,'PUBLICATION_RETIRED',True))
            else:raise ValueError('REMOVE process unknown peer negative')
    else:
        record=selected('record');clear=selected('clear');rows=indices(record)
        if name=='foreign-owner':
            at=next(i for i,v in enumerate(events) if v['event']==future.RETURNS[0] and mapping[i]['origin']=='parent')
            value(at)['node']='unknown'
        elif name=='record-omitted':remove(rows)
        elif name=='record-duplicated':move(rows,rows[0],duplicate=True)
        elif name=='record-after-publication':move(rows,boundary(record,'PUBLICATION_VALIDATED'),after=True)
        elif name=='clear-before-promotion':move(indices(clear),boundary(clear,future.RETURNS[2],True))
        elif name=='clear-after-completion':move(indices(clear),boundary(clear,future.RETURNS[3]),after=True)
        elif name=='return-before-force':move([boundary(record,future.RETURNS[0])],rows[3])
        elif name=='ack-before-return':move([boundary(record,future.RETURNS[1])],boundary(record,future.RETURNS[0]))
        elif name=='unbound-return':shared.append(dict(origin='parent',value=dict(node='node-1',event=future.RETURNS[0])))
        else:raise ValueError('REMOVE process unknown future negative')
    n.rewrite(root,shared)


OBSERVATIONS={'history/events.json','history/process-trace.jsonl','interrupted-worker/stdout','resumed-worker/stdout'}


def negative(root,profile,before,stage,name):
    with tempfile.TemporaryDirectory(prefix='v53-remove-process-retention-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,profile,stage,name)
        after=p.run.h.inventory(changed);protected=lambda inv:{k:v for k,v in inv['files'].items() if k not in OBSERVATIONS}
        need(protected(before)==protected(after) and before['directories']==after['directories'],
             'REMOVE process retention negative changed physical or wire inputs')
        prior,_=n.observations(root,profile);altered,_=n.observations(changed,profile)
        need(h.unrelated(prior,stage)==h.unrelated(altered,stage),'REMOVE process retention negative changed other observations')
        try:(PeerReplay if stage=='peers' else FutureReplay)(changed,profile).run()
        except ValueError as error:need(str(error)==NEGATIVES[stage][name],'REMOVE process unrelated retention negative: '+stage+': '+name+': '+str(error))
        else:raise ValueError('REMOVE process retention mutation accepted: '+stage+': '+name)
    return dict(stage=stage,case=name,status='REJECTED',reason=NEGATIVES[stage][name],physicalWireAndOtherObservationsUnchanged=True)


def qualify(root,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'REMOVE process retention replay workers')
    root=Path(root);original=validate(root);before=p.run.h.inventory(root);results=[]
    profile=original['precondition']['precondition']['precondition']['physical']['profile']
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,profile,before,stage,name):(stage,name) for stage,cases in NEGATIVES.items() for name in cases}
        for task in as_completed(tasks):
            stage,name=tasks[task]
            try:result=task.result()
            except Exception as error:result=dict(stage=stage,case=name,status='FAIL',type=type(error).__name__,failure=str(error))
            results.append(result);print(json.dumps(dict(result,completed=len(results),total=len(tasks))),file=sys.stderr,flush=True)
    need(p.run.h.inventory(root)==before,'REMOVE process retention negatives changed original')
    need(all(v['status']=='REJECTED' for v in results),'REMOVE process retention negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:(v['stage'],v['case'])),
        negativePrecondition='full-original-physical-network-export-floor; unchanged files, wire and non-target observations',
        mutatedPrerequisiteReplayed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    print(json.dumps(qualify(args.root,workers=args.workers) if args.qualify else validate(args.root),sort_keys=True))
