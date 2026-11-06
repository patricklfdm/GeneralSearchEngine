"""Continuous original peer/future revisions across carried group death.

Derive the admitted prefix once; later snapshots compare rather than seed state.
The original physical, callback, wire, export and complete-copy readers are
mandatory. This component does not invent transient files or admit a cohort.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_transition_maintenance as maintenance
from . import remove_retention_evidence as shared

m=maintenance; h=shared; peer=h.peer; future=h.future
x=m.x; p=m.p; c=m.c; f=m.f; need=m.need; sha=m.sha


def open_reseals(base):
    result=[];used=set();names=peer.RESEAL+future.RESEAL
    for node,lives in base.live.items():
        for life,(opened,closed) in enumerate(lives,1):
            lower=-1 if life==1 else lives[life-2][1]
            rows=[(i,v) for i,v in enumerate(base.events) if lower<i<opened and v.get('node')==node]
            selected=[(i,v) for i,v in rows if v['event'] in names]
            need([v['event'] for _,v in selected]==names and all(set(v)=={'node','event'} for _,v in selected),
                 'transition retention exact open reseal order')
            need(rows[0][1]['event']=='CURRENT_VALIDATED' and rows[0][0]<selected[0][0] and
                 any(i>selected[-1][0] and v['event'] in ('ACCEPT_ACTIVE_PARENT_FORCED','PROOF_ACTIVE_PARENT_FORCED') for i,v in rows),
                 'transition retention original open recovery interval')
            used.update(i for i,_ in selected)
            result.append(dict(node=node,path=f'life-{life}-opened',peer=selected[1][0],future=selected[3][0],
                futureEvents=[i for i,_ in selected[2:]],life=life))
    need(used=={i for i,v in enumerate(base.events) if v['event'] in names},'transition retention unbound open reseal')
    return result


def phases(base):
    slots=[v for v in base.history.ranges if v['kind']=='slot']
    observed=[v if any(s['start']<i<s['stop'] for s in slots) else dict(event='OUTSIDE_SLOT')
              for i,v in enumerate(base.events)]
    return x.network.network.phase.blocks(observed,base.history)


def snapshots(base):
    points=x.snapshots(base.root,base.events)
    death=next(i for i,v in enumerate(base.events) if v['event']=='GROUP_CRASH')
    return sorted(points+[(death,'before-reopen')])


def summary(reader,*,future_ledger=False):
    revisions={node:value['meta']['revision'] if future_ledger else peer.peers.decode(value)['revision']
               for node,value in reader.state.items()}
    return dict(status='PASS',durableWrites=len(reader.steps),writesByKind=dict(Counter(v['kind'] for v in reader.steps)),
        ledgerComparisons=reader.comparisons,openReseals=len(reader.opens),openRevisions=reader.open_steps,
        finalRevisions=revisions,chainSha256=sha(f.canonical(sorted(reader.steps,key=lambda v:v['start']))))


class PeerReplay(m.Replay):
    files=peer.Replay.files
    compare=peer.Replay.compare
    change=peer.Replay.change
    capture=peer.Replay.capture
    floor=h.PeerReplay.floor
    selection=h.PeerReplay.selection
    publication=h.PeerReplay.publication

    def __init__(self,root,kind):
        super().__init__(root,kind)
        self.state={};self.steps=[];self.used=set();self.comparisons=0;self.completions=set();self.open_steps=[]
        self.floor_inputs=[];self.files_cache={};self.phases=phases(self)
        h.peer_event_shapes(self.events,self.history.old)
        self.tx=peer.transactions(self.events);self.opens=open_reseals(self)

    def sequence(self,node,changes,lower,upper,kind):
        actual=[v for v in self.tx if v['node']==node and lower<v['start'] and v['end']<upper]
        need(len(actual)==len(changes),'joining peer '+kind+' durable write count')
        for tx,(before,after,cause) in zip(actual,changes):
            need(tx['start'] not in self.used and tx['scope'] is None and peer.peers.decode(before)['owner']['node']==node,
                 'joining peer original write owner')
            need(any(start<tx['start']<=tx['end']<end for start,end in self.live[node]),
                 'transition retention write crosses owner death')
            peer.revision(before,after);self.used.add(tx['start'])
            self.steps.append(dict(node=node,start=tx['start'],end=tx['end'],kind=kind,cause=cause,
                before=sha(before),after=sha(after),revision=peer.peers.decode(after)['revision']))

    def acquired(self,own,lower,start):
        copies,used=super().acquired(own,lower,start)
        end=next(i for i in range(start+1,len(self.events)) if self.events[i].get('node')==own['node'] and
                 self.events[i]['event']=='FLOOR_RELEASE_BEFORE_RETURN')
        self.floor_inputs.append(dict(start=start,end=end,own=own,copies=copies,order=list(copies)))
        return copies,used

    def reseal(self,row):
        self.compare(row['node'],c.inventory(self.root/row['path']/row['node'])[peer.FILE],row['path']+'-reseal')
        raw=self.state[row['node']]
        self.open_steps.append(dict(node=row['node'],life=row['life'],revision=peer.peers.decode(raw)['revision'],digest=sha(raw)))

    def snapshot(self,path):
        for node in self.history.old:self.compare(node,c.inventory(self.root/path/node)[peer.FILE],path)

    def initial_states(self):
        walk,_,_=p.t.prelude(self.root,self.kind)
        return walk.group

    def run(self):
        m.Replay.run(self)
        self.state={node:files[peer.FILE] for node,files in self.initial_states().items()}
        actions=[(row['end'],'floor',(row,)) for row in self.floor_inputs]
        actions.extend((own['start'],'selection',(own,)) for own in self.windows
            if self.events[own['start']]['event']=='INSTALL_BEFORE_RETURN')
        actions.extend((points['PUBLICATION_BEFORE_RETURN'],'publication',(index,node)) for (index,node),points in self.phases.items())
        actions.extend((v['start'],'capture',(v,)) for v in self.sources if v['start']>=0)
        actions.extend((v['peer'],'reseal',(v,)) for v in self.opens)
        actions.extend((at,'snapshot',(path,)) for at,path in snapshots(self))
        for _,kind,values in sorted(actions,key=lambda v:v[0]):getattr(self,kind)(*values)
        need(self.used=={v['start'] for v in self.tx},'joining peer unbound durable writes')
        need(self.completions=={i for i,v in enumerate(self.events) if v['event']=='SELECTED_RETENTION_COMPLETED'},
             'joining peer unbound selected completions')
        return dict(summary(self),capturedLedgers=sum(v['start']>=0 for v in self.sources))


class FutureReplay(future.Replay):
    def __init__(self,root,kind):
        self.base=m.Replay(root,kind);self.root=self.base.root;self.events=self.base.events;self.model=self.base.history;self.kind=kind
        self.base.phases=phases(self.base);self.tx,self.write_events=future.observations(self.events,joining=None)
        need(all(v['node'] in self.model.old for v in self.events if v['event'].startswith('FUTURE_RETENTION_')),
             'transition retention future original owner')
        self.state={};self.used=set();self.callbacks=set();self.steps=[];self.comparisons=0;self.open_steps=[]
        self.opens=open_reseals(self.base)

    def transaction(self,node,lower,upper):
        tx=super().transaction(node,lower,upper)
        need(any(start<tx['start']<=tx['end']<end for start,end in self.base.live[node]),
             'transition retention write crosses owner death')
        return tx

    def reseal(self,row):
        self.compare(row['node'],c.inventory(self.root/row['path']/row['node']),row['path']+'-reseal')
        self.callbacks.update(row['futureEvents']);state=self.state[row['node']]
        self.open_steps.append(dict(node=row['node'],life=row['life'],revision=state['meta']['revision'],digest=sha(state['raw'])))

    def snapshot(self,path):
        for node in self.model.old:self.compare(node,c.inventory(self.root/path/node),path)

    def run(self):
        walk,_,_=p.t.prelude(self.root,self.kind)
        for node,files in walk.group.items():self.initialize(node,files)
        actions=[(v['future'],'reseal',(v,)) for v in self.opens]
        actions.extend((points['PUBLICATION_BEFORE_RETURN'],'phase',(index,node)) for (index,node),points in self.base.phases.items())
        actions.extend((at,'snapshot',(path,)) for at,path in snapshots(self.base))
        for _,kind,values in sorted(actions,key=lambda v:v[0]):getattr(self,kind)(*values)
        need(self.used=={v['start'] for v in self.tx},'joining future unbound durable writes')
        need(self.callbacks=={i for i,v in enumerate(self.events) if v['event'] in future.RETURNS+future.RESEAL},
             'joining future unbound completion/reopen')
        return summary(self,future_ledger=True)


def replay(root,kind):
    return dict(status='PARTIAL',kind=kind,peers=PeerReplay(root,kind).run(),future=FutureReplay(root,kind).run(),
        retentionRevisionCompositionQualified=True,transientBytesCaptured=False,coreScratchInventoryReplay=False,
        cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=x.process.collection.inventory(root);original=m.validate(root)
    result=replay(root,original['maintenance']['kind'])
    need(x.process.collection.inventory(root)==before,'transition retention original changed')
    return dict(original=original,retention=result,status='PARTIAL',phase3Complete=False)


COMMON={
    'force-missing':'exact write force order',
    'rename-before-force':'exact write force order',
    'incomplete-write':'incomplete durable write',
    'unbound-write':'unbound durable writes',
    'resumed-parent-missing':'transition retention exact open reseal order',
    'resumed-parent-before-active':'transition retention exact open reseal order',
}
NEGATIVES={
    'peers':{**{name:reason if reason.startswith('transition') else 'joining peer '+reason for name,reason in COMMON.items()},
        'maintenance-before-floor':'joining peer maintenance durable write count',
        'maintenance-after-retirement':'joining peer maintenance durable write count',
        'maintenance-omit-write':'joining peer maintenance durable write count',
        'selected-before-install':'joining peer selected durable write count',
        'selected-before-force':'joining peer selected durable write count',
        'selected-without-completion':'joining peer selected completion count',
        'publication-after-promotion':'joining peer publication durable write count',
        'publication-before-retirement':'joining peer publication durable write count',
        'duplicate-write':'joining peer publication durable write count'},
    'future':{**{name:reason if reason.startswith('transition') else 'joining future '+reason for name,reason in COMMON.items()},
        'record-omitted':'joining future exact recording count',
        'record-duplicated':'joining future exact recording count',
        'record-after-publication':'joining future exact recording count',
        'clear-before-promotion':'joining future exact bounded write count',
        'clear-after-completion':'joining future exact bounded write count',
        'return-before-force':'joining future exact completion lifetime: FUTURE_RETENTION_BEFORE_RETURN',
        'ack-before-return':'joining future exact completion lifetime: FUTURE_RETENTION_ACK_BEFORE_RETURN'},
}


def mutate(root,kind,stage,name):
    need(stage in NEGATIVES and name in NEGATIVES[stage],'transition retention mutation case')
    reader=(PeerReplay if stage=='peers' else FutureReplay)(root,kind);reader.run();events=reader.events
    names=peer.WRITES if stage=='peers' else future.WRITES
    def selected(kind):return next(v for v in reader.steps if v['kind']==kind)
    def indices(step):return [i for i in range(step['start'],step['end']+1) if events[i].get('node')==step['node'] and events[i]['event'] in names]
    def boundary(step,point,before=False):
        found=[i for i,v in enumerate(events) if v.get('node')==step['node'] and v['event']==point and
               (i<step['start'] if before else i>step['end'])]
        return found[-1] if before else found[0]
    def edit(lives,indexed):
        def remove(values):
            ids={id(indexed[i]) for i in values}
            for life in lives:life[:]=[v for v in life if id(v) not in ids]
        def move(values,target,*,after=False,duplicate=False):
            rows=[copy.deepcopy(indexed[i]) if duplicate else indexed[i] for i in values]
            if not duplicate:remove(values)
            for life in lives:
                places=[i for i,v in enumerate(life) if v is indexed[target]]
                if places:
                    at=places[0]+int(after);life[at:at]=rows;return
            raise ValueError('transition retention mutation target')
        first=reader.steps[0];write=indices(first)
        if name=='force-missing':remove([write[3]])
        elif name=='rename-before-force':move([write[5]],write[3])
        elif name=='incomplete-write':remove([max(reader.tx,key=lambda v:v['end'])['end']])
        elif name=='unbound-write':
            # Keep the observation inside its original owner lifetime and
            # before the final snapshot, but outside any legal transaction.
            last=max(reader.steps,key=lambda v:v['end']);target=next(
                i for i in range(last['end']+1,len(events)) if events[i]['event']=='ROUND_SLOT_COMPLETE')
            move(indices(last),target,duplicate=True)
        elif name.startswith('resumed-'):
            row=next(v for v in reader.opens if v['node']=='node-1' and v['life']==2)
            end=row['peer' if stage=='peers' else 'future'];points=peer.RESEAL if stage=='peers' else future.RESEAL
            pair=[max(i for i,v in enumerate(events[:end+1]) if v.get('node')=='node-1' and v['event']==point) for point in points]
            if name=='resumed-parent-missing':remove([pair[1]])
            else:move([pair[1]],pair[0])
        elif stage=='peers':
            if name.startswith('maintenance-'):
                step=selected('maintenance');rows=indices(step)
                if name=='maintenance-omit-write':remove(rows)
                elif name=='maintenance-before-floor':move(rows,boundary(step,'FLOOR_BEFORE_RETURN',True))
                else:move(rows,boundary(step,'RETIREMENT_RESERVED'),after=True)
            elif name.startswith('selected-'):
                step=selected('selected');rows=indices(step);completed=boundary(step,'SELECTED_RETENTION_COMPLETED')
                if name=='selected-without-completion':remove([completed])
                elif name=='selected-before-force':move([completed],rows[-1])
                else:move(rows,boundary(step,'INSTALL_PARENT_FORCED',True))
            else:
                step=selected('publication');rows=indices(step)
                if name=='duplicate-write':move(rows,rows[-1],after=True,duplicate=True)
                elif name=='publication-after-promotion':move(rows,boundary(step,'FUTURE_RETENTION_PROMOTED'),after=True)
                else:move(rows,boundary(step,'PUBLICATION_RETIRED',True))
        else:
            record=selected('record');clear=selected('clear');rows=indices(record)
            if name=='record-omitted':remove(rows)
            elif name=='record-duplicated':move(rows,rows[0],duplicate=True)
            elif name=='record-after-publication':move(rows,boundary(record,'PUBLICATION_VALIDATED'),after=True)
            elif name=='clear-before-promotion':move(indices(clear),boundary(clear,future.RETURNS[2],True))
            elif name=='clear-after-completion':move(indices(clear),boundary(clear,future.RETURNS[3]),after=True)
            elif name=='return-before-force':move([boundary(record,future.RETURNS[0])],rows[3])
            else:move([boundary(record,future.RETURNS[1])],boundary(record,future.RETURNS[0]))
    m.edit_observations(Path(root),edit)


def non_target(root,stage):
    # Preserve all parent snapshots, responses and child ownership information,
    # not only the flattened event stream. Only this ledger's callbacks vary.
    return [[row for row in x.process.process.process.transcript(Path(root)/f'process/life-{life}.jsonl')
             if row['action']!='event' or h.unrelated([row['value']],stage)] for life in (1,2)]


def negative(root,kind,before,stage,name):
    observations={'events.json','process/life-1.jsonl','process/life-2.jsonl'}
    protected=lambda inv:{k:v for k,v in inv['files'].items() if k not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-transition-retention-negative-') as temporary:
        changed=Path(temporary)/'raw';shutil.copytree(root,changed);mutate(changed,kind,stage,name)
        after=x.process.collection.inventory(changed)
        need(protected(before)==protected(after) and before['directories']==after['directories'],
             'transition retention negative changed physical or wire inputs')
        need(non_target(root,stage)==non_target(changed,stage) and
             h.unrelated(x.process.read(Path(root)/'events.json'),stage)==h.unrelated(x.process.read(changed/'events.json'),stage),
             'transition retention negative changed other observations')
        try:(PeerReplay if stage=='peers' else FutureReplay)(changed,kind).run()
        except ValueError as error:need(str(error)==NEGATIVES[stage][name],
            'transition retention wrong negative '+stage+': '+name+': '+str(error))
        else:raise ValueError('transition retention accepted mutation '+stage+': '+name)
    return dict(stage=stage,case=name,status='REJECTED',reason=NEGATIVES[stage][name],physicalWireAndOtherObservationsUnchanged=True)


def qualify(root):
    root=Path(root);original=validate(root);before=x.process.collection.inventory(root);results=[]
    for stage,cases in NEGATIVES.items():
        for name in cases:
            results.append(negative(root,original['retention']['kind'],before,stage,name))
            print(json.dumps(dict(stage=stage,case=name,completed=len(results),total=sum(map(len,NEGATIVES.values())))),file=sys.stderr,flush=True)
    need(x.process.collection.inventory(root)==before,'transition retention qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='full-original-physical-callback-network-export-floor; unchanged files, wire and non-target child observations')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
