"""Complete original floor acquisition, cross-process reuse and release.

Replaying original files and attempted exports is a precondition. Discovery
never grants deletion authority; reuse must match the same retained full copies.
Continuous peer/future revisions and complete retirement callbacks remain separate.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import remove_process_exports as exports
from . import joining_maintenance_evidence as maintenance
from . import joining_retirement_replay as originals

e,m=exports,maintenance
n,p,c,f,need,sha=e.n,e.p,e.c,e.f,e.need,e.sha


def floor_files(files):return {k:v for k,v in files.items() if k=='floor-copies' or k.startswith('floor-copies/')}


def same_generation(left,right):
    return all(left[k]==right[k] for k in ('node','identity','manifest','members','packet'))


class Replay(m.Replay):
    expected_status_count=None

    def __init__(self,root,profile):
        original=e.Replay(root,profile);self.__dict__.update(original.__dict__)
        self.process_root=Path(root);self.floor_inputs=[];self.files_cache={}

    def files(self,own):
        if own['path'] not in self.files_cache:self.files_cache[own['path']]=c.inventory(self.root/own['path'])
        return self.files_cache[own['path']]

    def statuses(self):
        self.status_rows=[]
        for row in self.rows:
            if row['kind']!='STATUS_PROBE':continue
            q,a=row['request'],row['response'];own=self.current(q['recipient']['node'],row['received'],row['offered'])
            ids=m.n.s.catalog.identities(m.c.catalog(own)['identities']);proposer=ids.get(q['ballot']['proposer'])
            need(q['sequence']==1 and set(q['payload'])=={'nonce'} and q['sender']==ids.get(q['sender']['node']) and
                 proposer is not None and q['ballot']['incarnation']==proposer['storage'],'joining maintenance discovery original identity')
            need(row['answer']=='STATUS' and a['payload']==dict(nonce=q['payload']['nonce'],cut=own['packet']['capsule']['cut'],ready=False),
                 'joining maintenance exact discovery hint')
            self.status_rows.append(row)

    def retained(self,copies,own):
        before=self.files(own);expected=floor_files(originals.governing(before,{node:self.files(value) for node,value in copies.items()},own['node']))
        for stage in ('interrupted','resume-opened-0'):
            need(floor_files(c.inventory(self.root/stage/own['node']))==expected,'REMOVE process exact retained floor across death')
        return expected

    def floors(self):
        events=self.events
        need(all(set(v)=={'node','event'} and v['node'] in self.history.old for v in events if v['event'].startswith('FLOOR_')),
             'REMOVE process floor observation shape')
        positions=[i for i,v in enumerate(events) if v['event']=='FLOOR_RESERVED']
        previous={};used=set();covered=set();retired=set();pending=None;network=reused=copies_total=0
        cut,resumed=self.live[0][1],self.live[1][0]
        original=p.physical(self.process_root,self.profile)['retirement']
        for ordinal,start in enumerate(positions):
            node=events[start]['node'];following=[i for i in positions if i>start and events[i]['node']==node]
            next_start=following[0] if following else len(events)
            returns=[i for i,v in enumerate(events) if start<i<next_start and v['node']==node and v['event']=='FLOOR_BEFORE_RETURN']
            need(len(returns)==1,'REMOVE process complete floor establishment');returned=returns[0]
            own=self.current(node,start,returned);lower=max(own['start'],previous.get(node,-1))
            local=[i for i,v in enumerate(events) if lower<i<start and v['node']==node and v['event']=='FLOOR_COPY_BEFORE_RETURN']
            need(len(local)==2,'REMOVE process exact local copy observations');covered.update(local)
            is_reuse=pending is not None and node=='node-1' and start>resumed
            if is_reuse:
                need(reused==0 and same_generation(pending['own'],own),'REMOVE process retained floor current generation')
                copies=dict(pending['copies'],**{node:own});new=[]
                # A second acquisition cannot be hidden as retained-copy reuse.
                need(not any(lower<row['sent']<start and row['request']['sender']['node']==node for row in self.rows),
                     'REMOVE process retained floor unexpected network acquisition')
                need(self.retained(copies,own)==pending['files'],'REMOVE process retained floor proposal changed');reused+=1
            else:
                copies,new=self.acquired(own,lower,start);network+=1
                need(not used.intersection(new),'joining maintenance discovery reused by floor');used.update(new)
                need(all(local[0]<row['sent']<row['delivered']<local[1] for row in self.status_rows if row['requestHash'] in new),
                     'REMOVE process discovery between local copy checks')
            self.governing(copies,own);expected=m.floor_events(copies,node,True)
            release_at=expected.index('FLOOR_RELEASE_AUTHORITY_CREATED');acquisition=expected[:release_at];release=expected[release_at:]
            actual=[(i,v) for i,v in enumerate(events) if start<=i<=returned and v['node']==node and v['event'].startswith('FLOOR_')]
            need([v['event'] for _,v in actual]==acquisition and all(set(v)=={'node','event'} for _,v in actual),
                 'REMOVE process complete floor acquisition force order');covered.update(i for i,_ in actual)
            interrupted=node=='node-1' and start<cut<next_start
            if interrupted:
                need(pending is None and returned<cut<resumed<next_start,'REMOVE process interrupted floor lifetime')
                prefix=[(i,v) for i,v in enumerate(events) if returned<i<cut and v['node']==node and v['event'].startswith(p.retirement.PREFIXES)]
                recovery=[(i,v) for i,v in enumerate(events) if cut<i<resumed and v['node']==node and v['event'].startswith(p.retirement.PREFIXES)]
                need([v['event'] for _,v in prefix]==original['prefixEvents'] and [v['event'] for _,v in recovery]==original['recoveryEvents'],
                     'REMOVE process retirement recovery within retained floor')
                retired.update(i for i,_ in prefix+recovery)
                pending=dict(own=own,copies=copies,files=self.retained(copies,own));end=cut
            else:
                ends=[i for i,v in enumerate(events) if returned<i<next_start and v['node']==node and v['event']=='FLOOR_RELEASE_BEFORE_RETURN']
                need(len(ends)==1,'REMOVE process complete floor release');end=ends[0]
                self.current(node,start,end)
                actual=[(i,v) for i,v in enumerate(events) if returned<i<=end and v['node']==node and v['event'].startswith('FLOOR_')]
                need([v['event'] for _,v in actual]==release and all(set(v)=={'node','event'} for _,v in actual),
                     'REMOVE process complete floor release force order');covered.update(i for i,_ in actual)
                m.retirement_order(events,node,start,end,None)
                release_start=actual[0][0]
                retired.update(i for i,v in enumerate(events) if returned<i<release_start and v['node']==node and v['event'].startswith(p.retirement.PREFIXES))
                if is_reuse:pending=None
            copies_total+=len(copies);previous[node]=end
            self.floor_inputs.append(dict(start=start,returned=returned,end=end,own=own,copies=copies,order=list(copies),
                interrupted=interrupted,reused=is_reuse))
        need(pending is None and reused==1,'REMOVE process original retained floor was not consumed')
        need(covered=={i for i,v in enumerate(events) if v['event'].startswith('FLOOR_')},'REMOVE process unbound floor observation')
        need(retired=={i for i,v in enumerate(events) if v['event'].startswith(p.retirement.PREFIXES)},'REMOVE process retirement outside original floor')
        need(used=={v['requestHash'] for v in self.status_rows},'REMOVE process unused discovery observations')
        need(all(not floor_files(c.inventory(self.root/'after-close'/node)) for node in self.history.old),'REMOVE process unreleased final floor')
        return dict(networkFloors=network,retainedFloorReuses=reused,completeCopies=copies_total,acquiredRemoteCopies=len(used),
            floorObservations=len(covered),retirementLifetimeObservations=len(retired),floorReleases=len(positions)-1,
            interruptedFloors=1,proposerLifetimes=len(self.live))

    def run(self):
        self.statuses();result=self.floors()
        return dict(status='PARTIAL',**result,discoveryHints=len(self.status_rows),completeCopyFloorsQualified=True,
            retainedFloorRecoveryQualified=True,retentionRevisionCompositionQualified=False,
            completeRetirementCallbacksQualified=False,phase3Complete=False)


def replay(root,profile):return Replay(root,profile).run()


def validate(root):
    root=Path(root);before=p.run.h.inventory(root);original=e.validate(root);result=replay(root,original['precondition']['physical']['profile'])
    need(p.run.h.inventory(root)==before,'REMOVE process maintenance original changed')
    return dict(result,precondition=original)


NEGATIVES={
    'local-copy-missing':'REMOVE process exact local copy observations',
    'local-copy-duplicate':'REMOVE process exact local copy observations',
    'manifest-force':'REMOVE process complete floor acquisition force order',
    'handoff-before-directory':'REMOVE process complete floor acquisition force order',
    'authority-before-copies':'REMOVE process complete floor acquisition force order',
    'retained-reseal-force':'REMOVE process complete floor acquisition force order',
    'release-before-force':'REMOVE process complete floor release force order',
    'release-member-count':'REMOVE process complete floor release force order',
    'missing-release':'REMOVE process complete floor release',
    'unbound-floor':'REMOVE process unbound floor observation',
    'discovery-after-packet':'joining maintenance acquisition before discovery',
    'copy-after-reservation':'joining maintenance copy delivered after floor',
    'retirement-after-release':'joining maintenance generation retirement lifetime',
    'journal-outside-floor':'REMOVE process retirement outside original floor',
    'floor-forged-scope':'REMOVE process floor observation shape',
}


def mutate(root,profile,name):
    root=Path(root);reader=Replay(root,profile);reader.run();events=reader.events
    shared=[n.e.parse(v) for v in (root/'history/process-trace.jsonl').read_bytes().splitlines()];mapping=[]
    for row in shared:
        normalized=[row['value']] if row['origin']=='parent' else n.normalize(row['value']['kind'],row['value']['value'])[0]
        mapping.extend([row]*len(normalized))
    need(len(mapping)==len(events),'REMOVE process floor mutation mapping')
    def index(point,node='node-2',lower=-1):return next(i for i,v in enumerate(events) if i>lower and v['node']==node and v['event']==point)
    def remove(at):shared.pop(next(i for i,v in enumerate(shared) if v is mapping[at]))
    def move(at,target,after=False):
        value=mapping[at];remove(at);where=next(i for i,v in enumerate(shared) if v is mapping[target]);shared.insert(where+int(after),value)
    if name in ('local-copy-missing','local-copy-duplicate'):
        at=index('FLOOR_COPY_BEFORE_RETURN')
        if name=='local-copy-missing':remove(at)
        else:shared.insert(next(i for i,v in enumerate(shared) if v is mapping[at]),dict(mapping[at]))
    elif name=='manifest-force':remove(index('FLOOR_MANIFEST_FORCED'))
    elif name=='handoff-before-directory':move(index('FLOOR_COPY_HANDED_OFF'),index('FLOOR_COPY_DIRECTORY_FORCED'))
    elif name=='authority-before-copies':move(index('FLOOR_AUTHORITY_FORCED'),index('FLOOR_COPIES_FORCED'))
    elif name=='retained-reseal-force':remove(index('FLOOR_MANIFEST_FORCED','node-1',reader.live[1][0]))
    elif name=='release-before-force':move(index('FLOOR_RELEASE_RELINQUISHED'),index('FLOOR_RELEASE_AUTHORITY_FORCED'))
    elif name=='release-member-count':remove(index('FLOOR_RELEASE_FILE_DELETED'))
    elif name=='missing-release':remove(index('FLOOR_RELEASE_BEFORE_RETURN'))
    elif name=='unbound-floor':shared.append(dict(origin='parent',value=dict(node='node-4',event='FLOOR_MANIFEST_FORCED')))
    elif name=='floor-forged-scope':mapping[index('FLOOR_MANIFEST_FORCED')]['value']['scope']='foreign-floor'
    elif name in ('retirement-after-release','journal-outside-floor'):
        point='RETIREMENT_BEFORE_RETURN' if name=='retirement-after-release' else 'JOURNAL_ROTATION_PARENT_FORCED'
        move(index(point),index('FLOOR_RELEASE_RELINQUISHED'),True)
    elif name=='copy-after-reservation':
        floor=reader.floor_inputs[0];start=floor['start'];last=max(v[-1]['commit']['delivered'] for v in reader.groups if
            v[0]['offer']['request']['sender']['node']==floor['own']['node'] and v[-1]['commit']['delivered']<start)
        move(last,start,True)
    elif name=='discovery-after-packet':
        row=reader.status_rows[0];q=row['request'];packet=next(v for v in reader.groups if v[0]['offer']['request']['sender']==q['sender'] and
            v[0]['offer']['request']['recipient']==q['recipient'] and v[0]['offer']['sent']>row['delivered'])
        move(row['delivered'],packet[0]['offer']['sent'],True)
    else:raise ValueError('REMOVE process unknown floor negative')
    n.rewrite(root,shared)


def negative(root,profile,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-process-maintenance-negative-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,profile,name);after=p.run.h.inventory(changed)
        protected=lambda v:{k:h for k,h in v['files'].items() if k not in n.OBSERVATIONS}
        need(protected(before)==protected(after) and before['directories']==after['directories'],'REMOVE process maintenance negative changed physical inputs')
        e.validate(changed)
        try:replay(changed,profile)
        except ValueError as error:need(str(error)==NEGATIVES[name],'REMOVE process unrelated maintenance negative: '+name+': '+str(error))
        else:raise ValueError('REMOVE process maintenance mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],physicalNetworkExportPrecondition='PASS')


def qualify(root,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'REMOVE process maintenance replay workers')
    root=Path(root);original=validate(root);before=p.run.h.inventory(root);results=[]
    profile=original['precondition']['precondition']['physical']['profile']
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,profile,before,name):name for name in NEGATIVES}
        for task in as_completed(tasks):
            name=tasks[task]
            try:result=task.result()
            except Exception as error:result=dict(case=name,status='FAIL',type=type(error).__name__,failure=str(error))
            results.append(result);print(json.dumps(dict(result,completed=len(results),total=len(tasks))),file=sys.stderr,flush=True)
    need(p.run.h.inventory(root)==before,'REMOVE process maintenance negatives changed original')
    need(all(v['status']=='REJECTED' for v in results),'REMOVE process maintenance negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:v['case']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    print(json.dumps(qualify(args.root,workers=args.workers) if args.qualify else validate(args.root),sort_keys=True))
