"""Whole interrupted 5-REPLACE transport, exports and original floor lifetimes.

One explicit cold-owner boundary joins the original and resumed floor. No event
is dropped, renamed or reassigned to another physical execution.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import joint_floor_maintenance_evidence as recovered
from . import joining_profile_control_evidence as control
from . import joining_profile_maintenance_evidence as maintenance
from . import joining_retirement_replay as retirement
from .joining_same_view_physical import floor_voters

v = recovered.continuation
p = recovered.prior
e, m = control.e, maintenance.m
f, disk, need, h, sha = recovered.f, recovered.disk, recovered.need, recovered.h, recovered.sha


def lifetimes(events):
    start, _ = recovered.boundary(events)
    return {recovered.NODE: (start, recovered.SCOPE)}


class History(v.p.History):
    def maintain(self):
        self.group = v.c.t.maintenance(self.group, self.retirements.compare, voters=self.voters)


class Initialization(v.p.Initialization):
    def maintain(self, copies):
        self.group = v.c.t.maintenance(self.group, self.retirements.compare, copies, voters=self.voters)


class Continuation(v.Continuation):
    def maintenance(self, group, node):
        return v.c.maintenance(group, node, self.retirements.compare, voters=floor_voters(group,node))


def physical(root, events, *, owner_lifetimes=None, initialization_class=Initialization):
    life = lifetimes(events) if owner_lifetimes is None else owner_lifetimes
    old = p.NODES[:-1]
    retires = retirement.Retirements(root, events, voters=p.NODES)
    observed = v.p.Captures(root, events, voters=old, old_owner_lifetimes=life)
    model = v.s.Replay(root, size=5, kind='REPLACE')
    for index in range(1,12): model.step(index)
    model.publication_receipts = v.c.t.publication.CheckpointReceipts(root, model, old_owner_lifetimes=life)
    history = History(root, model, observed); history.retirements = retires; prefix = history.run()
    owner = v.init.placement.Placement(root, history); owner.run()
    handoff = v.init.retirement.Retirement(root, owner); handoff.run()
    initialized = initialization_class(root, handoff, observed); initialized.retirements = retires; initialized.run()
    continued = Continuation(root, initialized, observed, old_owner_lifetimes=life); continued.retirements = retires
    result = continued.run(); retires.complete()
    return dict(prefix=prefix, continuation=result, sourceRetirementTransactions=retires.transactions,
                sourceRetirementPrefixes=retires.prefixes, governingFloors=len(retires.floors))


ENDPOINTS = {'initial-endpoint':'initial-owner', 'continuation-endpoint':'continuation-owner',
             'joint-floor-export':'initial-owner'}


def retirement_coverage(events, resumed):
    need(0 <= resumed < len(events) and events[resumed].get('node') == recovered.NODE and
         events[resumed]['event'] == 'FLOOR_RESERVED', 'joint history exact resumed reservation')
    active=set();count=0
    for at,row in enumerate(events):
        node=row.get('node');point=row['event']
        if point=='FLOOR_RESERVED':
            need((node in active)==(at==resumed),'joint history unexplained overlapping floor');active.add(node)
        elif point=='FLOOR_RELEASE_BEFORE_RETURN':
            need(node in active,'joining profile maintenance floor release without reservation');active.remove(node)
        elif point.startswith(('RETIREMENT_','SOURCE_RETIREMENT_')):
            need(node in active,'joining profile maintenance unbound retirement event');count+=1
    need(not active,'joining profile maintenance incomplete floor')
    return count


def exports(reader):
    result = e.authorize_contents(reader.model, reader.events, reader.contents, reader.windows, reader.sources, reader.records)
    bound = 0
    for values in reader.groups:
        first, last = values[0]['offer'], values[-1]['commit']; node = first['request']['recipient']['node']
        if node != reader.model.joining or values[0]['raw'] == e.pending_ack(reader.model): continue
        scope = ENDPOINTS.get(reader.events[first['received']].get('scope'))
        need(scope is not None, 'joint history export endpoint owner')
        control.c.owner_lifetime(reader.events, node, scope, first['received'], last['offered']); bound += 1
    result['joiningExportLifetimes'] = bound
    return result


class Replay(maintenance.Replay):
    joining_status_scopes = ENDPOINTS
    recovered_counts = (1, 1)  # One native reacquisition after one direct fixture floor.

    def direct_fixture_nodes(self):
        return self.expected_confirmations

    def __init__(self, reader):
        self.__dict__.update(vars(reader)); self.direct_nodes = set(); self.floor_inputs = []
        cold, self.released = recovered.boundary(self.events)
        starts = [i for i,row in enumerate(self.events) if row.get('node') == recovered.NODE and row['event'] == 'FLOOR_RESERVED']
        before = [i for i in starts if i < cold]; after = [i for i in starts if cold < i < self.released]
        need(before and len(after) == 1, 'joint history exact interrupted floor boundary')
        self.interrupted, self.resumed, self.cold = before[-1], after[0], cold

    def recovered_floor(self):
        node = recovered.NODE; start, end = self.interrupted, self.released
        own = self.current(node,start,end)
        direct = self.direct(own,start); self.floor_inputs.pop()
        copies, used = self.acquired(own,start,self.resumed)
        need(copies.keys() == direct.keys() and all(copies[n]['manifest'] == direct[n]['manifest'] and
             copies[n]['members'] == direct[n]['members'] for n in copies), 'joint history reacquired exact interrupted cohort')
        self.governing(copies,own)
        original = {sha(c['manifest']):dict(c['members'], **{'generation.gsr':c['manifest']}) for c in copies.values()}
        proposal = (self.root/'joint-floor-recovery/proposal.gsr').read_bytes()
        first = p.writer_prefix(original,proposal,p.read(self.root/'joint-floor-recovery/receipt.json'))['events']
        expected = first + sum((p.resume.resume_events(dict(copies[n]['members'], **{'generation.gsr':copies[n]['manifest']}))
                               for n in ('node-6','node-1','node-3','node-2')), [])
        expected += [row['event'] for row in p.generation.floor.transaction(original,proposal,handoff=True)[0]]
        complete = m.floor_events(copies,node,True)
        expected += complete[complete.index('FLOOR_RELEASE_AUTHORITY_CREATED'):]
        actual = [(i,row) for i,row in enumerate(self.events) if start <= i <= end and row.get('node') == node and
                  row['event'].startswith('FLOOR_') and row['event'] != 'FLOOR_COPY_BEFORE_RETURN']
        need([row['event'] for _,row in actual] == expected and all(row == dict(node=node,event=row['event'],
             **({'scope':recovered.SCOPE} if i >= self.cold else {})) for i,row in actual),
             'joint history complete interrupted floor callbacks')
        generations = m.retirement_order(self.events,node,self.resumed,end,recovered.SCOPE)
        recovered.reclaimed(self.root,self.events)
        return set(i for i,_ in actual),used,len(copies)*2,generations

    def floors(self):
        previous={}; covered=set(); used=set(); network=direct=copies_total=generations=0
        starts=[i for i,row in enumerate(self.events) if row['event']=='FLOOR_RESERVED']
        for start in starts:
            if start==self.resumed:continue  # included, byte-for-byte, by recovered_floor
            node=self.events[start]['node'];scope=self.events[start].get('scope')
            if start==self.interrupted:
                need(previous.get(node,-1)<start,'joining maintenance overlapping floors')
                points,new,copies,retired=self.recovered_floor()
                need(not covered.intersection(points) and not used.intersection(new),'joint history recovery reused observations')
                covered.update(points);used.update(new)
                network+=self.recovered_counts[0];direct+=self.recovered_counts[1];copies_total+=copies;generations+=retired
                previous[node]=self.released;continue
            ends=[i for i,row in enumerate(self.events) if i>start and row.get('node')==node and row['event']=='FLOOR_RELEASE_BEFORE_RETURN']
            need(ends,'joining maintenance incomplete floor release');end=ends[0]
            own=self.current(node,start,end);lower=max(own['start'],previous.get(node,-1))
            need(lower<start,'joining maintenance overlapping floors')
            actual=[(i,row) for i,row in enumerate(self.events) if start<=i<=end and row.get('node')==node and
                    row['event'].startswith('FLOOR_') and row['event']!='FLOOR_COPY_BEFORE_RETURN']
            is_network=any(row['event']=='FLOOR_COPY_HANDED_OFF' for _,row in actual)
            if is_network:
                copies,new=self.acquired(own,lower,start)
                need(not used.intersection(new),'joining maintenance discovery reused by floor');used.update(new);network+=1
            else:copies=self.direct(own,start);direct+=1
            self.governing(copies,own)
            need([row['event'] for _,row in actual]==m.floor_events(copies,node,is_network) and
                 all(row.get('scope')==scope for _,row in actual),'joining maintenance exact copy force/release order')
            if node==self.model.joining:control.c.owner_lifetime(self.events,node,'continuation-owner',start,end)
            generations+=m.retirement_order(self.events,node,start,end,scope)
            covered.update(i for i,_ in actual);copies_total+=len(copies);previous[node]=end
        eligible={i for i,row in enumerate(self.events) if row['event'].startswith('FLOOR_') and row['event']!='FLOOR_COPY_BEFORE_RETURN'}
        need(covered==eligible,'joining maintenance unbound floor events')
        need(self.direct_nodes==self.direct_fixture_nodes() and direct==len(self.direct_fixture_nodes()),
             'joining profile maintenance complete direct cohort')
        retirements=retirement_coverage(self.events,self.resumed)
        return dict(networkFloors=network,directFixtureFloors=direct,completeCopies=copies_total,
                    acquiredRemoteCopies=len(used),retiredGenerations=generations,floorEvents=len(covered),
                    boundRetirementEvents=retirements,interruptedFloors=1)


def validate(directory, progress=None):
    root=Path(directory);before=h.inventory(root);events=p.read(root/'events.json');life=lifetimes(events)
    preceding=p.validate(root)
    derived=physical(root,events)
    if progress:progress(dict(stage='physical',status='PASS'))
    network=e.n.network(root,size=5,kind='REPLACE',old_owner_lifetimes=life)
    reader=control.Replay(root,'5-REPLACE',old_owner_lifetimes=life)
    exported=exports(reader);controls=reader.run(exported)
    need(controls['observedCommittedContents']==network['committedTransfers'] and controls['observedContentSessions']==
         network['transferSessions']-network['rejectedTransferAttempts'],'joint history complete export coverage')
    if progress:progress(dict(stage='network-and-exports',status='PASS'))
    floors=Replay(reader).run()
    need(h.inventory(root)==before,'joint history original changed')
    return dict(status='PASS',scope='whole-interrupted-history-network-exports-maintenance',profile='5-REPLACE',
        preceding=preceding,physical=derived,network=network,exports=exported,controls=controls,maintenance=floors,
        wholeNetworkExportQualified=True,wholeFloorMaintenanceQualified=True,
        peerLedgerCompositionQualified=False,transientGenerationRetirementPrefixesCaptured=False,
        processDeathQualified=False,phase3Complete=False)


NEGATIVES = {
    'selection-before-cold': ('network','joining network selection lifetime'),
    'selection-after-cold': ('network','joining network selection lifetime'),
    'post-cold-slot-scope': ('network','joining force event shape'),
    'temporary-export-owner': ('exports','joining control original owner lifetime'),
    'interrupted-copy-force': ('floors','joint history complete interrupted floor callbacks'),
    'resumed-copy-force': ('floors','joint history complete interrupted floor callbacks'),
    'resumed-floor-owner': ('floors','joint history complete interrupted floor callbacks'),
    'ordinary-floor-missing': ('floors','joining profile maintenance unbound retirement event'),
    'source-capture-missing': ('physical','retirement capture missing copy/start'),
    'wrong-source-floor': ('physical','retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN'),
    'extra-source-prefix-file': ('physical','retirement capture exact prefix: SOURCE_RETIREMENT_BEFORE_RETURN'),
}


def mutate(root,name):
    need(name in NEGATIVES,'joint history unknown mutation');root=Path(root)
    if name in ('source-capture-missing','wrong-source-floor','extra-source-prefix-file'):
        retirement.observed.mutate(root,{'source-capture-missing':'missing-copy',
            'wrong-source-floor':'wrong-floor','extra-source-prefix-file':'extra-preserved-file'}[name]);return
    events=p.read(root/'events.json');cold,end=recovered.boundary(events)
    def point(event,lower=0,upper=None):
        return next(row for row in events[lower:upper] if row.get('node')==recovered.NODE and row['event']==event)
    if name=='selection-before-cold':point('SELECTED_FORCED',upper=cold)['scope']='foreign-owner'
    elif name=='selection-after-cold':point('SELECTED_FORCED',lower=cold).pop('scope')
    elif name=='post-cold-slot-scope':point('CERTIFICATE_ACTIVE_FORCED',lower=cold).pop('scope')
    elif name=='temporary-export-owner':
        for row in events[cold:end+1]:
            if row.get('scope')=='joint-floor-export':row['scope']='continuation-endpoint'
    elif name=='interrupted-copy-force':
        start=max(i for i,row in enumerate(events[:cold]) if row.get('node')==recovered.NODE and row['event']=='FLOOR_RESERVED')
        point('FLOOR_COPIES_FORCED',start,cold)['event']='REMOVED_FLOOR_COPIES_FORCE'
    elif name=='resumed-copy-force':point('FLOOR_MANIFEST_FORCED',cold,end)['event']='REMOVED_FLOOR_MANIFEST_FORCE'
    elif name=='resumed-floor-owner':point('FLOOR_AUTHORITY_FORCED',cold,end)['scope']='foreign-owner'
    elif name=='ordinary-floor-missing':
        reader=control.Replay(root,'5-REPLACE',old_owner_lifetimes=lifetimes(events))
        maintenance.mutate(root,'missing-floor-transaction',reader);return
    (root/'events.json').write_bytes(f.canonical(events))


def negative(root,name,before):
    """One designated layer, used only after qualify's complete original pass."""
    stage,reason=NEGATIVES[name]
    with tempfile.TemporaryDirectory(prefix='v53-joint-history-negative-') as tmp:
        changed=Path(tmp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
        allowed=('events.json',)
        if name in ('wrong-source-floor','extra-source-prefix-file'):allowed+=('source-retirement-captures/',)
        def protected(inventory):
            return {n:v for n,v in inventory['files'].items() if not any(
                n.startswith(a) if a.endswith('/') else n==a for a in allowed)}
        after=h.inventory(changed)
        need(after!=before and protected(after)==protected(before) and after['directories']==before['directories'],
             'joint history mutation changed protected inputs')
        try:
            events=p.read(changed/'events.json');life=lifetimes(events)
            if stage=='physical':physical(changed,events)
            elif stage=='network':e.n.network(changed,size=5,kind='REPLACE',old_owner_lifetimes=life)
            else:
                reader=control.Replay(changed,'5-REPLACE',old_owner_lifetimes=life)
                if stage=='exports':exports(reader)
                else:Replay(reader).run()
        except ValueError as error:need(str(error)==reason,'joint history unrelated rejection: '+name+': '+str(error))
        else:raise ValueError('joint history mutation accepted: '+name)
    return dict(case=name,stage=stage,status='REJECTED',reason=reason)


def qualify(directory,progress=None):
    root=Path(directory);before=h.inventory(root);original=validate(root,progress);results=[]
    if progress:progress(dict(stage='original',status='PASS'))
    for name in NEGATIVES:
        results.append(negative(root,name,before))
        if progress:progress(results[-1])
    need(h.inventory(root)==before,'joint history qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    args=parser.parse_args()
    def progress(row):print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(args.root,progress) if args.qualify else validate(args.root,progress),sort_keys=True))
