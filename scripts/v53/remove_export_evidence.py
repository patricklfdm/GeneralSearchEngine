"""Original REMOVE exports and complete-copy maintenance lifetimes.

Require the original physical/network gate first. Snapshot bytes are not proof
of availability at another time: original selector, grant, retirement and reply
boundaries delimit every exported capability. No new native execution is needed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace

from . import remove_network_evidence as network
from . import joining_export_evidence as exports
from . import joining_maintenance_evidence as maintenance
from . import remove_maintenance_evidence as original_maintenance

n=network;e=exports;c=n.c;f=n.f;need=n.need;sha=n.sha


def generation_windows(root,events,history):
    windows=[]
    for node in history.old:
        changes=[]
        for ordinal in range(1,4):
            if (ordinal,node) not in history.installed:continue
            changes.extend([('INSTALL_BEFORE_RETURN',history.installed[ordinal,node],f'installed-{ordinal}/{node}'),
                ('PUBLICATION_BEFORE_RETURN',history.published[ordinal,node],f'published-{ordinal+4}/{node}')])
        renames=[i for i,v in enumerate(events) if v['node']==node and v['event']=='INSTALL_SELECTOR_RENAMED']
        returns=[(i,v['event']) for i,v in enumerate(events) if v['node']==node and v['event'] in ('INSTALL_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN')]
        need(len(renames)==len(returns)==len(changes) and [p for _,p in returns]==[p for p,_,_ in changes],
             'REMOVE export complete generation timeline')
        def add(files,path,start,end):
            need(start<end,'REMOVE export generation lifetime')
            prefix,members,packet=c.current(files);identity=f.decode(files['node.gsr'],'records','NODE')['identity']
            need(identity['node']==node,'REMOVE export generation owner')
            windows.append(dict(node=node,start=start,end=end,path=path,members=members,packet=packet,
                manifest=files[prefix+'generation.gsr'],identity=identity))
        add(c.inventory(root/'before-network'/node),'before-network/'+node,-1,renames[0] if renames else len(events))
        for at,((_,files,path),(returned,_)) in enumerate(zip(changes,returns)):
            need(renames[at]<returned and (at==0 or returns[at-1][0]<renames[at]),'REMOVE export selector completion order')
            add(files,path,returned,renames[at+1] if at+1<len(renames) else len(events))
    return windows


def source_windows(root,events,history):
    sources={};bound_grants=set();bound_retirements=set()
    def collect(node,files,start,selected_basis=None):
        root_id=files['root.gsr'][16:48].hex()
        journal=c.journal(files['grants.gsr'],root_id,node)
        promises={v['basisId']:raw for kind,raw,v in journal if kind=='PROMISE' and v['basisId'] is not None}
        for kind,raw,value in journal:
            prefix='sources/'+str(value.get('basisId'))+'/'
            if kind!='BASIS' or prefix+'source.gscp' not in files:continue
            key=node,value['basisId'];members={k[len(prefix):]:v for k,v in files.items() if k.startswith(prefix)}
            if key in sources:
                prior=sources[key];need(prior['basis']==raw and prior['promise']==promises[value['basisId']] and prior['members']==members,
                                       'REMOVE export original frozen source changed');continue
            need(start==-1 or sha(raw)==selected_basis,'REMOVE export new source without original grant')
            packet=c.p.decode(members['source.gscp']);c.p.bind(packet,raw)
            sources[key]=dict(node=node,start=start,end=len(events),basis=raw,promise=promises[value['basisId']],value=value,packet=packet,members=members)
    for node in history.old:collect(node,c.inventory(root/'before-network'/node),-1)
    prior=-1
    for ordinal,parts in enumerate(history.phases,1):
        selected=f.decode(parts['SELECTED'],'records','SELECTED');digest=sha(parts['SELECTED'])
        ends=[i for i,v in enumerate(events) if v['event']=='ROUND_INSTALLED' and v['record']==digest]
        need(len(ends)==1 and prior<ends[0],'REMOVE export original activation interval');end=ends[0]
        for row in selected['sources']:
            node=row['voter'];grants=[i for i,v in enumerate(events) if prior<i<end and v['node']==node and v['event']=='GRANT_BEFORE_RETURN']
            need(len(grants)==1,'REMOVE export original grant lifetime');bound_grants.add(grants[0])
            files=history.installed[ordinal,node];collect(node,files,grants[0],row['basisDigest'])
            removed={k.split('/')[1] for k in files if k.startswith('sources/') and k not in history.applied[ordinal,node]}
            upper=next(i for i,v in enumerate(events) if i>end and v['node']==node and v['event']=='ACCEPT_VALIDATED')
            retirements=[i for i,v in enumerate(events) if end<i<upper and v['node']==node and v['event']=='SOURCE_RETIREMENT_CREATED']
            need(bool(removed) and len(retirements)==1,'REMOVE export exact source retirement interval');bound_retirements.add(retirements[0])
            for identifier in removed:
                held=sources.get((node,identifier));need(held is not None and held['end']==len(events),'REMOVE export original retired source')
                need(held['start']<retirements[0],'REMOVE export source retirement before grant');held['end']=retirements[0]
        prior=end
    need(bound_grants=={i for i,v in enumerate(events) if v['event']=='GRANT_BEFORE_RETURN'} and
         bound_retirements=={i for i,v in enumerate(events) if v['event']=='SOURCE_RETIREMENT_CREATED'},'REMOVE export unexplained source lifetime')
    return list(sources.values())


class Replay(maintenance.Replay):
    expected_status_count=None
    expected_floor_counts=None

    def __init__(self,root,profile):
        self.root=Path(root);self.history=n.History(self.root,profile);self.profile=profile
        self.events=n.collection.read_json(self.root,'events.json',n.collection.EVENT_BYTES)
        wires=n.collection.read_json(self.root,'wire.json',n.collection.WIRE_BYTES)
        ids={node:n.d.future.identity(c.inventory(self.root/'before-network'/node)) for node in self.history.old}
        root_id=f.decode(self.history.phases[0]['SELECTED'],'records','SELECTED')['root']
        self.rows=n.transcript.causal(self.events,wires,ids,root_id);contents=[];n.transcript.transfers(self.rows,contents=contents)
        self.groups=e.sessions(contents);self.windows=generation_windows(self.root,self.events,self.history)
        self.sources=source_windows(self.root,self.events,self.history)
        phases=[dict(v,PAYLOAD=(self.root/f'native-payload-{i+4}.bin').read_bytes()) for i,v in enumerate(self.history.phases,1)]
        self.model=SimpleNamespace(root=root_id,phases=phases,old=self.history.old,joining=None,owner=self.history.owner)
        self.records=e.record_windows(self.root,self.events,self.model,self.windows,self.sources,nodes=self.history.old)
        sizes=[len(f.decode(v['SELECTED'],'records','SELECTED')['sources']) for v in self.history.phases]
        floors=sizes+sizes[1:]
        self.expected_floor_counts=(sum(floors),0,sum(v*v for v in floors),sum(v*(v-1) for v in floors))
        self.expected_status_count=self.expected_floor_counts[3]

    def direct(self,own,start):
        raise ValueError('REMOVE maintenance unexpected direct fixture floor')

    def exports(self):
        families=Counter();transfers=Counter()
        for values in self.groups:
            first=values[0];kind=e.record_kind(first['raw'])
            if kind=='GENERATION' or first['kind']=='CAPSULE':scope=e.authorize_generation(values,self.windows)
            elif kind=='BASIS':e.authorize_source(values,self.windows,self.sources);scope='frozen-source'
            else:scope=e.authorize_record(values,self.windows,self.records)
            families[scope]+=1;transfers[scope]+=len(values)
        need(families['current-generation'] and families['frozen-source'] and sum(families.values())==len(self.groups),
             'REMOVE export complete observed families')
        return dict(generationWindows=len(self.windows),sourceWindows=len(self.sources),recordWindows=len(self.records),
                    boundSessions=dict(families),boundTransfers=dict(transfers),unqualifiedTransfers=0)

    def run(self):
        result=self.exports();self.statuses();result.update(self.floors())
        # Cached physical bytes do not waive the placement of maintenance
        # between the original publication, next grant and first slot vote.
        for ordinal,parts in enumerate(self.history.phases,1):
            voters=[v['voter'] for v in f.decode(parts['SELECTED'],'records','SELECTED')['sources']]
            original_maintenance.boundaries(self.root,ordinal,voters,
                {v:self.history.installed[ordinal,v] for v in voters},
                {v:self.history.applied[ordinal,v] for v in voters})
        return dict(status='PARTIAL',profile=self.profile,**result,discoveryHints=len(self.status_rows),
            observedExportAuthorityQualified=True,completeCopyFloorLifetimesQualified=True,
            retentionRevisionCompositionQualified=False,processDeathQualified=False,phase3Complete=False)


def replay(root,profile):return Replay(root,profile).run()


def validate(root,profile):
    need(profile in n.original.PROFILES,'REMOVE export profile');root=Path(root);before=n.collection.inventory(root)
    precondition=n.validate(root,profile);result=replay(root,profile)
    need(n.collection.inventory(root)==before,'REMOVE export original changed')
    return dict(result,precondition=precondition)


NEGATIVES={k:v for k,v in e.NEGATIVES.items() if k!='pending-after-retain'}
NEGATIVES.update({k:v for k,v in maintenance.NEGATIVES.items() if k not in
    ('status-cut','status-ready','status-nonce','direct-copy-missing')})
NEGATIVES['all-floors-missing']='joining maintenance complete original floors'


def mutate(root,profile,name):
    reader=Replay(root,profile)
    if name in e.NEGATIVES:e.mutate(Path(root),name,reader=reader)
    elif name in maintenance.NEGATIVES:maintenance.mutate(Path(root),name,reader=reader)
    elif name=='all-floors-missing':
        (Path(root)/'events.json').write_bytes(f.canonical([v for v in reader.events if not v['event'].startswith('FLOOR_')]))
    else:raise ValueError('REMOVE unknown export mutation: '+name)


def qualify(root,profile):
    root=Path(root);passed=validate(root,profile);before=n.collection.inventory(root);outcomes=[]
    protected={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-remove-export-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,profile,name);after=n.collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==protected and
                 after['directories']==before['directories'],'REMOVE export negative changed physical input')
            n.network(changed,profile)
            try:replay(changed,profile)
            except ValueError as error:need(str(error)==reason,'REMOVE unrelated export negative: '+name+': '+str(error))
            else:raise ValueError('REMOVE export mutation accepted: '+name)
        outcomes.append(dict(case=name,status='REJECTED',networkPrecondition='PASS',reason=reason))
        print(json.dumps(dict(profile=profile,case=name,completed=len(outcomes),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(n.collection.inventory(root)==before,'REMOVE export negative changed original')
    return dict(original=passed,negatives=outcomes)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--profile',required=True,choices=n.original.PROFILES)
    p.add_argument('--qualify',action='store_true')
    a=p.parse_args();print(json.dumps((qualify if a.qualify else validate)(a.root,a.profile),sort_keys=True))
