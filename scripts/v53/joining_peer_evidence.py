"""Derive the original peer-ledger chain and bind every durable write.

Complete physical/network/control/maintenance replay is a prerequisite. Floor
copies and frozen selected sources supply original bytes, never a claimed PASS.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_maintenance_evidence as maintenance

m=maintenance; c=m.c; e=m.e; n=m.n; f=m.f; disk=m.disk; need=m.need; sha=m.sha
init=c.init; t=init.transition; peers=init.peers; FILE=init.PEERS
WRITES=['RETENTION_'+v for v in ('BEFORE_WRITE','PREFIX_WRITTEN','WRITTEN','FORCED','CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED')]
RESEAL=['RETENTION_RECOVERY_ACTIVE_FORCED','RETENTION_RECOVERY_PARENT_FORCED']
JOINING_SCOPES=('initial-owner','retaining-owner','repeated-basis-owner','continuation-owner','stable-cold-owner')
OWNERS=[('node-'+str(i),None) for i in (1,2,3)]+[('node-4',s) for s in JOINING_SCOPES]


def owner_lifetimes(model):
    need(model.joining not in model.old and len(set(model.old))==len(model.old),'joining peer original owner cohort')
    return [(node,None) for node in model.old]+[(model.joining,scope) for scope in JOINING_SCOPES]


def reseal_lifetimes(events,owners=OWNERS):
    """Existing active bytes are forced again on every declared original open."""
    result=[];used=set()
    for node,scope in owners:
        rows=[(i,v['event']) for i,v in enumerate(events) if v.get('node')==node and v.get('scope')==scope]
        points={name:[i for i,event in rows if event==name] for name in
                ['CURRENT_VALIDATED','LEARNER_RETENTION_RECOVERY_PARENT_FORCED',*RESEAL,'FUTURE_RETENTION_RECOVERY_FORCED']}
        need(points['CURRENT_VALIDATED'] and all(len(v)==1 for k,v in points.items() if k!='CURRENT_VALIDATED'),
             'joining peer exact open reseal count')
        order=[points[k][0] for k in points]
        need(all(a<b for a,b in zip(order,order[1:])),'joining peer open reseal force order')
        used.update(points[k][0] for k in RESEAL);result.append((points[RESEAL[1]][0],node))
    need(used=={i for i,v in enumerate(events) if v['event'] in RESEAL},'joining peer unbound open reseal')
    return result


def transactions(events):
    active={};result=[]
    for at,row in enumerate(events):
        if row['event'] not in WRITES:continue
        node=row['node'];pending=active.setdefault(node,[])
        need(row['event']==WRITES[len(pending)] and (not pending or row.get('scope')==pending[0][1].get('scope')),
             'joining peer exact write force order')
        pending.append((at,row))
        if len(pending)==len(WRITES):
            result.append(dict(node=node,start=pending[0][0],end=at,scope=row.get('scope')));del active[node]
    need(not active,'joining peer incomplete durable write');return result


def updated(before,plan):
    state=peers.decode(before)
    return before if plan==state['plan'] else peers.frame(dict(state,revision=state['revision']+1,previous=sha(before),plan=plan))


def revision(before,after):
    a,b=peers.decode(before),peers.decode(after)
    need(before!=after and b['root']==a['root'] and b['owner']==a['owner'] and b['revision']==a['revision']+1 and
         b['previous']==sha(before),'joining peer exact revision chain')
    t.confirmation.confirmed.plan(b['plan'])


class Replay(m.Replay):
    expected_write_counts=dict(maintenance=54,selected=12,publication=24)

    def __init__(self,root):
        super().__init__(root);self.initialize_chain()

    def initialize_chain(self):
        self.floor_inputs=[];self.state={};self.steps=[];self.used=set();self.files_cache={};self.comparisons=0
        self.owner_lifetimes=self.lifetimes()
        self.tx=transactions(self.events);self.completions=set();self.reseals=reseal_lifetimes(self.events,self.owner_lifetimes)
        need(all(not v['event'].startswith('RETENTION_') or v['event'] in WRITES+RESEAL for v in self.events),
             'joining peer unsupported retention event')

    def lifetimes(self):
        return owner_lifetimes(self.model)

    def initialization_point(self):
        points=[i for i,v in enumerate(self.events) if v['event']=='JOINING_RETENTION_BEFORE_RETURN']
        need(len(points)==1,'joining peer original initialization count')
        return points[0]

    def acquired(self,own,lower,start):
        copies,used=super().acquired(own,lower,start)
        self.floor_inputs.append(dict(start=start,own=own,copies=copies,order=list(copies)))
        return copies,used

    def direct(self,own,start):
        copies=super().direct(own,start)
        self.floor_inputs.append(dict(start=start,own=own,copies=copies,order=list(copies)))
        return copies

    def files(self,own):
        if own['path'] not in self.files_cache:self.files_cache[own['path']]=disk.inventory(self.root/own['path'])
        return self.files_cache[own['path']]

    def compare(self,node,raw,label):
        need(self.state.get(node)==raw,'joining peer exact original ledger: '+label+': '+node);self.comparisons+=1

    def sequence(self,node,changes,lower,upper,kind):
        actual=[v for v in self.tx if v['node']==node and lower<v['start'] and v['end']<upper]
        need(len(actual)==len(changes),'joining peer '+kind+' durable write count')
        for tx,change in zip(actual,changes):
            need(tx['start'] not in self.used and tx['scope']==('continuation-owner' if node==self.model.joining else None),
                 'joining peer original write owner')
            before,after,cause=change
            need(peers.decode(before)['owner']['node']==node,'joining peer original write owner')
            revision(before,after);self.used.add(tx['start'])
            self.steps.append(dict(node=node,start=tx['start'],end=tx['end'],kind=kind,cause=cause,
                                   before=sha(before),after=sha(after),revision=peers.decode(after)['revision']))

    def change(self,node,after,cause,changes):
        before=self.state[node]
        if before!=after:changes.append((before,after,cause));self.state[node]=after

    def floor(self,row):
        own=row['own'];node=own['node'];start=row['start'];copies=row['copies'];changes=[]
        lower=next(i for i in range(start+1,len(self.events)) if self.events[i].get('node')==node and self.events[i]['event']=='FLOOR_BEFORE_RETURN')
        upper=next(i for i in range(lower+1,len(self.events)) if self.events[i].get('node')==node and
                   self.events[i]['event'] in ('RETIREMENT_RESERVED','FLOOR_RELEASE_AUTHORITY_CREATED'))
        files=dict(self.files(own),**{FILE:self.state[node]});plan=copy.deepcopy(peers.decode(self.state[node])['plan'])
        view=own['packet']['capsule']['cut']['view'];wanted=set(view['old']+view['new']);known={v['identity']['node'] for v in plan['peers']}
        if plan['view']!=view:
            if wanted-known:
                need(wanted-known=={self.model.joining} and self.model.joining in copies,'joining peer reconcile original joining copy')
                changed=init.reconcile(self.state[node],files,self.files(copies[self.model.joining]))
            else:
                need(wanted==known,'joining peer reconcile exact retained identities');plan['view']=view;changed=updated(self.state[node],plan)
            self.change(node,changed,'reconcile',changes)
        for peer in row['order']:
            files[FILE]=self.state[node]
            after=t.observation.observe_same_cut(self.state[node],files,self.files(copies[peer]),defer_renewal=True)
            self.change(node,after,'observe:'+peer,changes)
        self.sequence(node,changes,lower,upper,'maintenance')

    def selection(self,own):
        node=own['node'];end=own['start'];raw=own['members']['selected.gsr'];selected=f.decode(raw,'records','SELECTED')
        lower=max(i for i,v in enumerate(self.events[:end]) if v.get('node')==node and v['event']=='INSTALL_PARENT_FORCED')
        rows=[];plans=[peers.decode(self.state[node])['plan']];learner_points=[]
        for row in selected['sources']:
            found=[v for v in self.sources if sha(v['basis'])==row['basisDigest']]
            need(len(found)==1 and found[0]['node']==row['voter'] and found[0]['start']<lower,'joining peer selected original source')
            source=found[0];packet=source['packet'];value=source['value']
            wrapper,state=init.retention.source(packet,value,0x47535250,65536);plans.append(state['plan'])
            rows.append((source['basis'],packet,wrapper))
            _,nonvoting=init.retention.source(packet,value,0x47534c46,32768);learner_points+=nonvoting['plan']['possible']
        packet=own['packet'];ids=n.s.catalog.identities(c.catalog(own)['identities'])
        intent=t.selected.intent(own['identity'],raw,self.state[node],rows)
        need(packet['objects'].get(sha(intent))==intent,'joining peer selected original before ledger')
        plan=t.confirmation.merge(plans,packet,ids,learner_points);changes=[]
        self.change(node,updated(self.state[node],plan),'selected:'+sha(raw),changes)
        completions=[i for i,v in enumerate(self.events) if lower<i<end and v.get('node')==node and v['event']=='SELECTED_RETENTION_COMPLETED']
        need(len(completions)==int(bool(changes)),'joining peer selected completion count')
        self.sequence(node,changes,lower,completions[0] if changes else end,'selected')
        self.completions.update(completions)
        self.compare(node,self.files(own)[FILE],own['path'])

    def publication(self,index,node):
        points=self.phases[index,node];files=self.model.owner('applied',index,node)
        self.compare(node,files[FILE],'applied-'+str(index))
        after=t.publication.promoted_ledgers(self.model,dict(files,**{FILE:self.state[node]}),index)[FILE];changes=[]
        self.change(node,after,'publication:'+str(index),changes)
        self.sequence(node,changes,points['PUBLICATION_RETIRED'],points['FUTURE_RETENTION_PROMOTED'],'publication')
        self.compare(node,self.model.owner('published',index,node)[FILE],'published-'+str(index))

    def initialize(self,at):
        node=self.model.joining;need(node not in self.state,'joining peer duplicate joining initialization')
        own=self.current(node,at,at);originals=[];ancestry=[]
        for peer in own['packet']['capsule']['cut']['view']['old']:
            available=[v for v in self.sources if v['node']==peer and v['start']<at]
            if not available:continue
            remote=self.current(peer,at,at);source=c.active_source(self.sources,self.events,remote,at,at)
            originals.append((source['basis'],source['members']['source.gscp']));ancestry.append(remote['members'].get('ancestry.gsr',b''))
        seed,ledgers=init.retention.derive(own['packet'],own['identity'],originals,confirmed_peers=True,source_ancestry=ancestry)
        need((self.root/'joining-retention-seed.json').read_bytes()==seed,'joining peer exact original joining seed')
        self.state[node]=ledgers[FILE];self.compare(node,self.files(own)[FILE],'joining-initialized')

    def capture(self,source):
        _,state=init.retention.source(source['packet'],source['value'],0x47535250,65536)
        self.compare(source['node'],peers.frame(state),'grant-'+str(source['value']['ballot']['counter']))

    def reseal(self,value):
        at,node=value
        # Old owners open only at bootstrap, including original voters unused
        # by later selections. Their original bootstrap files bind each reseal.
        files=disk.inventory(self.root/'before-network'/node) if node!=self.model.joining else self.files(self.current(node,at,at))
        self.compare(node,files[FILE],'open-reseal')

    def adoption(self,own):
        # New authority changes CURRENT but must preserve this continuous
        # ledger; an observed generation cannot reset the derived predecessor.
        self.compare(own['node'],self.files(own)[FILE],'adoption')

    def run(self):
        self.statuses();self.floors()
        original=t.selected.initialize(self.model.original)
        for node,files in original.items():
            self.state[node]=files[FILE];self.compare(node,disk.inventory(self.root/'before-network'/node)[FILE],'before-network')
        actions=[]
        for row in self.floor_inputs:
            start=row['start'];node=row['own']['node']
            end=next(i for i in range(start+1,len(self.events)) if self.events[i].get('node')==node and self.events[i]['event']=='FLOOR_RELEASE_BEFORE_RETURN')
            actions.append((end,'floor',row))
        for own in self.windows:
            if own['start']>=0 and self.events[own['start']]['event']=='INSTALL_BEFORE_RETURN':actions.append((own['start'],'selection',own))
            elif own['start']>=0 and self.events[own['start']]['event']=='ADOPTION_INSTALL_BEFORE_RETURN':actions.append((own['start'],'adoption',own))
        for (index,node),points in self.phases.items():actions.append((points['PUBLICATION_BEFORE_RETURN'],'publication',(index,node)))
        initialized=self.initialization_point();actions.append((initialized,'initialize',initialized))
        actions.extend((v['start'],'capture',v) for v in self.sources)
        actions.extend((at,'reseal',(at,node)) for at,node in self.reseals)
        for _,kind,value in sorted(actions,key=lambda v:v[0]):
            if kind=='publication':self.publication(*value)
            else:getattr(self,kind)(value)
        need(self.used=={v['start'] for v in self.tx},'joining peer unbound durable writes')
        need(self.completions=={i for i,v in enumerate(self.events) if v['event']=='SELECTED_RETENTION_COMPLETED'},
             'joining peer unbound selected completions')
        for node in self.state:
            path='joining-originals-stable-cold/replica' if node==self.model.joining else 'after-close/'+node
            self.compare(node,disk.inventory(self.root/path)[FILE],'cold')
        counts=Counter(v['kind'] for v in self.steps)
        if self.expected_write_counts is not None:
            need(counts==self.expected_write_counts,'joining peer complete original write composition')
        return dict(status='PASS',scope='one-native-'+self.kind+'-original-peer-ledger-chain',durableWrites=len(self.steps),
                    writesByKind=dict(counts),ledgerComparisons=self.comparisons,capturedLedgers=len(self.sources),
                    openReseals=len(self.reseals),
                    finalRevisions={n:peers.decode(raw)['revision'] for n,raw in self.state.items()},
                    chainSha256=sha(f.canonical(sorted(self.steps,key=lambda v:v['start']))),
                    peerLedgerCompositionQualified=True,completePhysicalQualified=False,forceAndNetworkQualified=False,
                    processDeathQualified=False,phase3Complete=False)


def replay(root):return Replay(root).run()


def validate(root):
    root=Path(root);before=n.s.collection.inventory(root);m.validate(root);result=replay(root)
    need(n.s.collection.inventory(root)==before,'joining peer original changed');return result


NEGATIVES={
    'force-missing':'joining peer exact write force order',
    'rename-before-force':'joining peer exact write force order',
    'candidate-parent-missing':'joining peer exact write force order',
    'foreign-write-owner':'joining peer original write owner',
    'incomplete-write':'joining peer incomplete durable write',
    'unbound-write':'joining peer unbound durable writes',
    'maintenance-before-floor':'joining peer maintenance durable write count',
    'maintenance-after-retirement':'joining peer maintenance durable write count',
    'selected-before-force':'joining peer selected durable write count',
    'selected-before-install':'joining peer selected durable write count',
    'unbound-completion':'joining peer unbound selected completions',
    'publication-after-promotion':'joining peer publication durable write count',
    'publication-before-retirement':'joining peer publication durable write count',
    'duplicate-write':'joining peer publication durable write count',
    'selected-without-completion':'joining peer selected completion count',
    'maintenance-omit-write':'joining peer maintenance durable write count',
    'reseal-parent-missing':'joining peer exact open reseal count',
    'reseal-parent-before-active':'joining peer open reseal force order',
    'reseal-after-future-recovery':'joining peer open reseal force order',
    'unbound-reseal':'joining peer unbound open reseal',
}


def mutate(root,name,*,reader=None):
    need(name in NEGATIVES,'joining peer unknown negative')
    reader=Replay(root) if reader is None else reader;reader.run();events=reader.events
    def selected(kind):return next(v for v in reader.steps if v['kind']==kind)
    def rows(step):return [v for v in events[step['start']:step['end']+1] if v.get('node')==step['node'] and v['event'] in WRITES]
    def move(values,target,after=False):
        # Object identity matters: different writes have identical callback rows.
        ids={id(v) for v in values};events[:]=[v for v in events if id(v) not in ids]
        at=next(i for i,v in enumerate(events) if v is target)+int(after);events[at:at]=values
    def boundary(step,point,before):
        candidates=[v for i,v in enumerate(events) if v.get('node')==step['node'] and v['event']==point and
                    (i<step['start'] if before else i>step['end'])]
        return candidates[-1] if before else candidates[0]
    first=reader.steps[0];write=rows(first)
    if 'reseal' in name:
        pair=[next(v for v in events if v.get('node')=='node-1' and v['event']==point) for point in RESEAL]
        if name=='reseal-parent-missing':pair[1]['event']='REMOVED_PEER_RESEAL_PARENT'
        elif name=='reseal-parent-before-active':move([pair[1]],pair[0])
        elif name=='reseal-after-future-recovery':
            target=next(v for v in events if v.get('node')=='node-1' and v['event']=='FUTURE_RETENTION_RECOVERY_FORCED')
            move(pair,target,True)
        else:events.extend(dict(v,scope='unbound-owner') for v in pair)
    elif name=='force-missing':write[3]['event']='REMOVED_PEER_FORCE'
    elif name=='rename-before-force':move([write[5]],write[3])
    elif name=='candidate-parent-missing':write[4]['event']='REMOVED_PEER_CANDIDATE_PARENT'
    elif name=='foreign-write-owner':
        for row in write:row['scope']='foreign-owner'
    elif name=='incomplete-write':rows(max(reader.steps,key=lambda v:v['end']))[-1]['event']='REMOVED_PEER_FINAL_PARENT'
    elif name=='unbound-write':events.extend(copy.deepcopy(write))
    elif name.startswith('maintenance-'):
        step=selected('maintenance');values=rows(step)
        if name=='maintenance-omit-write':
            for row in values:row['event']='REMOVED_'+row['event']
        elif name=='maintenance-before-floor':move(values,boundary(step,'FLOOR_BEFORE_RETURN',True))
        else:move(values,boundary(step,'RETIREMENT_RESERVED',False),True)
    elif name=='unbound-completion':events.append(dict(node='node-1',event='SELECTED_RETENTION_COMPLETED'))
    elif name.startswith('selected-'):
        step=selected('selected');values=rows(step)
        completed=boundary(step,'SELECTED_RETENTION_COMPLETED',False)
        if name=='selected-without-completion':completed['event']='REMOVED_PEER_COMPLETION'
        elif name=='selected-before-force':move([completed],values[-1])
        else:move(values,boundary(step,'INSTALL_PARENT_FORCED',True))
    else:
        step=selected('publication');values=rows(step)
        if name=='duplicate-write':move(copy.deepcopy(values),values[-1],True)
        elif name=='publication-after-promotion':move(values,boundary(step,'FUTURE_RETENTION_PROMOTED',False),True)
        else:move(values,boundary(step,'PUBLICATION_RETIRED',True))
    (root/'events.json').write_bytes(f.canonical(events))


def qualify(root,progress=None):
    root=Path(root);original=validate(root);before=n.s.collection.inventory(root);outcomes=[]
    if progress:progress(dict(stage='original',status='PASS'))
    protected={k:v for k,v in before['files'].items() if k!='events.json'}
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-peer-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name);after=n.s.collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k!='events.json'}==protected and after['directories']==before['directories'],
                 'joining peer negative changed physical inputs')
            n.network(changed);prior=e.replay(changed);c.replay(changed,prior);m.replay(changed)
            try:replay(changed)
            except ValueError as error:need(str(error)==reason,'joining unrelated peer negative: '+name+': '+str(error))
            else:raise ValueError('joining peer mutation accepted: '+name)
        result=dict(case=name,status='REJECTED',networkExportControlMaintenancePrecondition='PASS',reason=reason);outcomes.append(result)
        if progress:progress(result)
    need(n.s.collection.inventory(root)==before,'joining peer negative changed original')
    return dict(original=original,negatives=outcomes)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    result=qualify(args.root,lambda row:print(json.dumps(row),file=sys.stderr,flush=True)) if args.qualify else validate(args.root)
    print(json.dumps(result,sort_keys=True))
