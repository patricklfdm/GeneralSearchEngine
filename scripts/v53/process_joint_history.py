"""Two original cold owners in one native joint-floor process history.

No observation is relabelled or removed. Continuous ledgers compare each cold
snapshot against the derived predecessor; process/cohort admission is separate.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_process_joint_floor as process
from . import joint_history_evidence as history
from . import joint_ledger_evidence as ledger
from . import old_owner_lifetimes as owners

h,f,disk,need=history.h,history.f,history.disk,history.need
NODE,SCOPE=history.recovered.NODE,history.recovered.SCOPE


def case(root):
    row=history.p.read(Path(root)/'joint-floor-recovery/receipt.json')
    value=str(row.get('ordinal'))+','+str(row.get('cut'))+','+str(row.get('mode'))
    history.p.same(row,process.scope(value),'process history exact native producer')
    return value


def lifetimes(events):
    child=[i for i,row in enumerate(events) if row.get('node')==NODE and row.get('scope')==process.SCOPE]
    resumed,end=history.recovered.boundary(events)
    need(child and child[0]<child[-1]<resumed,'process history disjoint original cold owners')
    life={NODE:((child[0],process.SCOPE),(resumed,SCOPE))}
    ledger.future.declared_old_lifetimes(events,'node-6',life)
    points=history.control.c.n.phase.slot_storage.CURRENT
    need([events[i] for i in child[:len(points)]]==[dict(node=NODE,scope=process.SCOPE,event=p) for p in points],
         'process history child current force order')
    return life


def context(root):
    events=history.p.read(Path(root)/'events.json')
    return history.control.Replay(root,'5-REPLACE',old_owner_lifetimes=lifetimes(events))


class Initialization(history.Initialization):
    def confirmations(self):
        super().confirmations()
        side=self.root/'joint-floor-recovery/originals'
        need(disk.inventory(side/NODE)==self.group[NODE],'process history independently derived interrupted owner')
        derived=dict(self.group,**{self.replay.joining:self.joined})
        for node in history.p.NODES:
            before=disk.inventory(side/node)
            prefix,members,_=disk.current(derived[node]);seen,actual,_=disk.current(before)
            need(actual==members and before[seen+'generation.gsr']==derived[node][prefix+'generation.gsr'],
                 'process history independently derived floor generation: '+node)


class Replay(history.Replay):
    recovered_counts=(2,0)

    def __init__(self,reader):
        super().__init__(reader)
        self.process_lifetimes=lifetimes(self.events)
        self.child=self.process_lifetimes[NODE][0][0]
        need(self.child<self.interrupted<self.cold<self.resumed<self.released,
             'process history original floor and death order')

    def direct_fixture_nodes(self):
        return self.expected_confirmations-{NODE}

    def recovered_floor(self):
        start,end=self.interrupted,self.released
        own=self.current(NODE,start,end)
        initial,first_used=self.acquired(own,self.child,start)
        self.floor_inputs.pop()  # The interrupted floor never authorizes ledger maintenance.
        copies,used=self.acquired(own,self.cold,self.resumed)
        need(copies.keys()==initial.keys() and all(copies[n]['manifest']==initial[n]['manifest'] and
             copies[n]['members']==initial[n]['members'] for n in copies),
             'process history reacquired original native copies')
        need(not set(first_used).intersection(used),'process history reused discovery across death')
        self.governing(initial,own);self.governing(copies,own)
        original={history.sha(c['manifest']):dict(c['members'],**{'generation.gsr':c['manifest']}) for c in copies.values()}
        proposal=(self.root/'joint-floor-recovery/proposal.gsr').read_bytes()
        ordinal,cut,_=process.selected(case(self.root))
        expected=history.p.writer_prefix(original,proposal,history.p.partial_scope(ordinal,cut))['events']
        expected+=sum((history.p.resume.resume_events(dict(copies[n]['members'],**{'generation.gsr':copies[n]['manifest']}))
                       for n in ('node-6','node-1','node-3','node-2')),[])
        expected+=[row['event'] for row in history.p.generation.floor.transaction(original,proposal,handoff=True)[0]]
        complete=history.m.floor_events(copies,NODE,True)
        expected+=complete[complete.index('FLOOR_RELEASE_AUTHORITY_CREATED'):]
        actual=[(i,row) for i,row in enumerate(self.events) if start<=i<=end and row.get('node')==NODE and
                row['event'].startswith('FLOOR_') and row['event']!='FLOOR_COPY_BEFORE_RETURN']
        need([row['event'] for _,row in actual]==expected and all(row==dict(node=NODE,event=row['event'],
             scope=process.SCOPE if i<self.cold else SCOPE) for i,row in actual),
             'process history complete interrupted floor callbacks')
        retired=history.m.retirement_order(self.events,NODE,self.resumed,end,SCOPE)
        history.recovered.reclaimed(self.root,self.events)
        return {i for i,_ in actual},set(first_used)|set(used),len(copies)*2,retired


class ColdOwners:
    def cold_lifetimes(self):
        if not hasattr(self,'_process_lifetimes'):self._process_lifetimes=lifetimes(self.events)
        return self._process_lifetimes

    def lifetimes(self):
        return [*super().lifetimes(),*((NODE,scope) for _,scope in self.cold_lifetimes()[NODE])]

    def write_scope(self,node,at):
        return owners.scope(self.cold_lifetimes(),node,at,super().write_scope(node,at))

    def reopen_files(self,node,at):
        scope=owners.scope(self.cold_lifetimes(),node,at)
        if scope is not None:
            name='process/before-open' if scope==process.SCOPE else 'after-reopen'
            return disk.inventory(self.root/'joint-floor-recovery'/name)
        return super().reopen_files(node,at)


class PeerReplay(ColdOwners,ledger.peer.Replay,Replay):
    expected_write_counts=None

    def __init__(self,root,*,base=None):
        Replay.__init__(self,context(root) if base is None else base);self.initialize_chain()

    acquired=Replay.acquired
    direct=Replay.direct
    governing=Replay.governing
    floors=Replay.floors
    floor=ledger.profile.Replay.floor


class LearnerReplay(ColdOwners,ledger.learner.Replay):
    def __init__(self,root,*,base=None):
        base=context(root) if base is None else base
        super().__init__(root,base=base,old_owner_lifetimes=lifetimes(base.events))


class FutureReplay(ColdOwners,ledger.future.Replay):
    def __init__(self,root,*,base=None):
        base=context(root) if base is None else base
        super().__init__(root,base=base,old_owner_lifetimes=lifetimes(base.events))


class BallotReplay(ledger.ballot_profile.ballot.Replay):
    def __init__(self,root,*,base=None):
        base=context(root) if base is None else base
        super().__init__(root,base=base,old_owner_lifetimes=lifetimes(base.events))

    def reopen_actions(self):
        life=lifetimes(self.events)[NODE];_,end=history.recovered.boundary(self.events)
        need(not any(row.get('node')==NODE and row['event'].startswith('ALLOCATOR_') for row in self.events[life[0][0]:end+1]),
             'process history allocation during floor recovery')
        return [(start,'original',(NODE,'joint-floor-recovery/'+path,scope))
                for (start,scope),path in zip(life,('process/before-open','after-reopen'))]


READERS={'peers':PeerReplay,'learner':LearnerReplay,'future':FutureReplay,'ballot':BallotReplay}


def validate(root,progress=None):
    root=Path(root);before=h.inventory(root);precondition=process.inspect(root,case(root))
    events=history.p.read(root/'events.json');life=lifetimes(events)
    physical=history.physical(root,events,owner_lifetimes=life,initialization_class=Initialization)
    if progress:progress(dict(stage='physical',status='PASS'))
    network=history.e.n.network(root,size=5,kind='REPLACE',old_owner_lifetimes=life)
    base=context(root);exports=history.exports(base);controls=base.run(exports)
    need(controls['observedCommittedContents']==network['committedTransfers'] and controls['observedContentSessions']==
         network['transferSessions']-network['rejectedTransferAttempts'],'process history complete export coverage')
    if progress:progress(dict(stage='network-and-exports',status='PASS'))
    maintenance=Replay(base).run()
    if progress:progress(dict(stage='maintenance',status='PASS'))
    ledgers={}
    for name,reader in READERS.items():
        ledgers[name]=reader(root,base=base).run()
        if progress:progress(dict(stage=name,status='PASS'))
    need(h.inventory(root)==before,'process history changed original evidence')
    return dict(status='PARTIAL',case=case(root),precondition=precondition,physical=physical,network=network,
        exports=exports,controls=controls,maintenance=maintenance,ledgers=ledgers,
        wholePhysicalNetworkLedgerReplayChecked=True,processDeathQualified=False,phase3Complete=False,
        outstanding=['expanded-process-negative-matrix','interrupted-resource-overlap','final-source-process-matrix'])


NEGATIVES={
    'child-current':('owners','process history child current force order'),
    'overlapping-child':('owners','process history disjoint original cold owners'),
    'original-allocator':('physical','process history independently derived interrupted owner'),
    'child-request':('network','joining network response without request'),
    'export-owner':('exports','joining control original owner lifetime'),
    'child-copy-force':('maintenance','process history complete interrupted floor callbacks'),
    'resumed-copy-force':('maintenance','process history complete interrupted floor callbacks'),
    'resumed-floor-owner':('maintenance','process history complete interrupted floor callbacks'),
}
for _stage in READERS:
    for _scope in ('child','resumed'):
        _label=process.SCOPE if _scope=='child' else SCOPE
        _reason={'peers':'joining peer exact original ledger: open-reseal: '+NODE,
            'learner':'joining learner exact continuous ledger: reopen: '+NODE,
            'future':'joining future exact continuous ledger: reopen: '+NODE,
            'ballot':'joining ballot exact continuous allocator: '+_label+': '+NODE}[_stage]
        NEGATIVES[_scope+'-'+_stage+'-reset']=(_stage,_reason)


def mutate(root,name):
    need(name in NEGATIVES,'process history unknown negative');root=Path(root)
    if name.endswith('-reset') or name=='original-allocator':
        if name=='original-allocator':path=root/'joint-floor-recovery/originals'/NODE/'allocator.gsr';stage='ballot'
        else:
            scope,stage,_=name.split('-');part='process/before-open' if scope=='child' else 'after-reopen'
            path=root/'joint-floor-recovery'/part/ledger.FILES[stage]
        if stage=='ballot':
            value=f.decode(path.read_bytes(),'records','ALLOCATOR');value['counter']+=1
            path.write_bytes(f.encode('records','ALLOCATOR',value))
        else:path.write_bytes((root/'before-network'/NODE/ledger.FILES[stage]).read_bytes())
        return path.relative_to(root).as_posix()
    path=root/'events.json';events=history.p.read(path);life=lifetimes(events)[NODE]
    def point(scope,event):
        return next(i for i,v in enumerate(events) if v.get('node')==NODE and v.get('scope')==scope and v['event']==event)
    if name=='child-current':events[point(process.SCOPE,'CURRENT_FILES_FORCED')]['event']='REMOVED_CURRENT_FILES_FORCE'
    elif name=='overlapping-child':events.append(dict(node=NODE,scope=process.SCOPE,event='FLOOR_RESERVED'))
    elif name=='original-allocator':raise AssertionError('handled above')
    elif name=='child-request':
        sent=events[point(process.SCOPE,'BEFORE_REQUEST_WRITE')]['request']
        at=next(i for i,v in enumerate(events) if v.get('request')==sent and v['event']=='AFTER_REQUEST_READ')
        events.pop(at)
    elif name=='export-owner':
        for v in events:
            if v.get('scope')=='joint-floor-export':v['scope']='continuation-endpoint'
    elif name in ('child-copy-force','resumed-copy-force'):
        scope=process.SCOPE if name=='child-copy-force' else SCOPE
        # Every selected partial writer has a creation callback, including the
        # earliest cut. The omitted force remains visible as an unknown marker.
        events[point(scope,'FLOOR_COPY_CREATED')]['event']='REMOVED_FLOOR_COPY_CREATED'
    elif name=='resumed-floor-owner':events[point(SCOPE,'FLOOR_AUTHORITY_FORCED')]['scope']='foreign-owner'
    path.write_bytes(f.canonical(events));return 'events.json'


def check_stage(root,stage):
    events=history.p.read(Path(root)/'events.json');life=lifetimes(events)
    if stage=='owners':return life
    if stage=='physical':return history.physical(root,events,owner_lifetimes=life,initialization_class=Initialization)
    if stage=='network':return history.e.n.network(root,size=5,kind='REPLACE',old_owner_lifetimes=life)
    base=context(root)
    if stage=='exports':return history.exports(base)
    if stage=='maintenance':return Replay(base).run()
    need(stage in READERS,'process history unknown negative layer')
    return READERS[stage](root,base=base).run()


def negative(root,name,before):
    need(name in NEGATIVES,'process history unknown negative');stage,reason=NEGATIVES[name]
    with tempfile.TemporaryDirectory(prefix='v53-process-history-negative-') as tmp:
        changed=Path(tmp)/'raw';shutil.copytree(root,changed);path=mutate(changed,name);after=h.inventory(changed)
        need(after!=before and before['directories']==after['directories'] and
             {n:v for n,v in before['files'].items() if n!=path}=={n:v for n,v in after['files'].items() if n!=path},
             'process history negative changed protected input')
        try:check_stage(changed,stage)
        except ValueError as error:need(str(error)==reason,'process history unrelated rejection: '+name+': '+str(error))
        else:raise ValueError('process history accepted mutation: '+name)
    return dict(case=name,stage=stage,status='REJECTED',reason=reason)


def qualify(root,progress=None):
    root=Path(root);before=h.inventory(root);original=validate(root,progress);results=[]
    for name in NEGATIVES:
        results.append(negative(root,name,before))
        if progress:progress(results[-1])
    need(h.inventory(root)==before,'process history negatives changed original')
    return dict(status='PARTIAL',original=original,negatives=results,processDeathQualified=False,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    result=(qualify if args.qualify else validate)(args.root,lambda row:print(json.dumps(row),file=sys.stderr,flush=True))
    print(json.dumps(result,sort_keys=True))
