"""Complete observed REMOVE retirement callbacks from original owned members.

Require the continuous physical/network/export/retention gate first. Derive
capacity-driven image borrowing rather than choosing a branch from the log.
Transient retirement file bytes and fresh-process crashes require later captures.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import remove_retention_evidence as retention
from . import joining_retirement_replay as sources
from . import retirement_images_evidence as images

r=retention;e=r.e;n=r.n;c=r.c;f=r.f;need=r.need;sha=r.sha
APPLICATION_LIMIT=7
PREFIXES=('RETIREMENT_','SOURCE_RETIREMENT_','JOURNAL_ROTATION_')


def physical(files):
    return {k:dict(directory=True) if raw is None else images.old.entry(raw) for k,raw in files.items()}


def generation_plan(files,node,copies):
    current,members,packet=c.current(files)
    old_slots={name.split('/')[1] for name in files if name.startswith('generations/') and not name.startswith(current) and name!=current[:-1]}
    need(len(old_slots)==1,'REMOVE retirement exact inactive generation')
    slot=old_slots.pop();prefix='generations/'+slot+'/'
    original={k[len(prefix):]:v for k,v in files.items() if k.startswith(prefix)}
    manifest=f.decode(original['generation.gsr'],'records','GENERATION')
    need(manifest['node']==node and manifest['generation']==slot and manifest['root']==packet['capsule']['root'] and
         manifest['files']==[dict(path=k,size=len(v),sha256=sha(v)) for k,v in sorted(original.items()) if k!='generation.gsr'],
         'REMOVE retirement inactive member authority')
    available=r.peer.t.confirmation.endpoints(packet,members.get('ancestry.gsr',b''))
    point=c.anchor(c.p.decode(original['source.gscp'])['capsule'])
    need(available.get(point['cut']['index'])==point,'REMOVE retirement inactive generation coverage')
    need(files['pending.accept']==c.EMPTY and not any(k=='applied-end' or k.startswith('applied-end/') for k in files),
         'REMOVE retirement unsettled original')
    record=f.encode('records','RETIREMENT',dict(root=packet['capsule']['root'],node=node,
        floor=sha(files['floor-copies/floor.gsr']),selector=sha(files['selector.gsr']),
        files=[dict(path=prefix+k,size=len(v),sha256=sha(v)) for k,v in sorted(original.items())]))
    # Every physical image owns its own APPLICATION reservation, even when its
    # bytes are equal to another image. Complete floor copies are already added.
    count=sum(k.endswith('.image') for k in files);saved=sum(k.endswith('.image') for k in original)
    need(0<saved and count<=APPLICATION_LIMIT,'REMOVE retirement original application capacity')
    borrow=count+saved>APPLICATION_LIMIT;binding=None
    if borrow:
        local=copies[node];rows=[]
        for name,raw in sorted(original.items()):
            if not name.endswith('.image'):continue
            need(local['members'].get(name)==raw and name==sha(raw)+'.image','REMOVE retirement exact borrowed local image')
            rows.append(dict(path=prefix+name,generation=sha(local['manifest']),size=len(raw),sha256=sha(raw)))
        binding=f.canonical(dict(schema='gse-v53-retirement-floor-images-v1',retirement=sha(record),
            floor=sha(files['floor-copies/floor.gsr']),root=packet['capsule']['root'],node=node,
            storage=local['identity']['storage'],selector=sha(files['selector.gsr']),images=rows))
    steps,_=images.transaction(physical(files),original,record,binding,borrow,slot=slot)
    after={k:v for k,v in files.items() if k!=prefix[:-1] and not k.startswith(prefix)}
    need(steps and steps[-1][1]==physical(after),'REMOVE retirement generation final projection')
    return after,steps,dict(slot=slot,borrowedImages=borrow,physicalImagesBefore=count,
        physicalImagesPeak=count+(0 if borrow else saved),members=len(original),imageMembers=saved,authority=sha(record))


def source_plans(files,node,available):
    _,members,packet=c.current(files);journal=c.journal(files['grants.gsr'],packet['capsule']['root'],node)
    promises={v['basisId']:(raw,v) for kind,raw,v in journal if kind=='PROMISE' and v['basisId'] is not None}
    latest=next(v['ballot'] for kind,_,v in reversed(journal) if kind=='PROMISE');decisions=[]
    for name in sorted(files):
        if not name.startswith('sources/') or not name.endswith('/source.gscp'):continue
        identifier=name.split('/')[1];promise,value=promises[identifier]
        if promise==members['promise.gsr'] or value['ballot']==latest:continue
        need(value['ballot']['counter']<latest['counter'],'REMOVE retirement old source ballot')
        authority,compact=sources.decision(files,node,identifier,coverage=available)
        steps=sources.observed.release.transaction(physical(files),authority,compact,identifier)
        prefix='sources/'+identifier
        after={k:v for k,v in files.items() if k!=prefix and not k.startswith(prefix+'/')};after['grants.gsr']=compact
        need(steps and steps[-1][1]==physical(after),'REMOVE retirement source final projection')
        decisions.append(dict(identifier=identifier,steps=steps,authority=sha(authority),journal=sha(compact)))
        files=after
    return files,decisions


class Replay(r.PeerReplay):
    def __init__(self,root,profile):
        super().__init__(root,profile);self.maintained={};self.retirements=[]

    def floor(self,row):
        super().floor(row);self.maintained[row['start']]=self.state[row['own']['node']]

    def run(self):
        peer_result=super().run();bound=set();counts=Counter();peak=0
        for row in self.floor_inputs:
            own=row['own'];node=own['node'];start=row['start'];files=self.files(own)
            files=sources.governing(files,{k:self.files(v) for k,v in row['copies'].items()},node)
            files[r.peer.FILE]=self.maintained[start]
            packet=own['packet'];available=r.peer.t.confirmation.endpoints(packet,own['members'].get('ancestry.gsr',b''))
            plan=r.peer.peers.decode(files[r.peer.FILE])['plan']
            for peer in plan['peers']:
                for point in peer['possible']+peer.get('renewals',[]):
                    need(available.get(point['cut']['index'])==point,'REMOVE retirement retained endpoint coverage')
            after,steps,details=generation_plan(files,node,row['copies']);after,decisions=source_plans(after,node,available)
            expected=[point for point,_ in steps]+[point for decision in decisions for point,_ in decision['steps']]
            lower=next(i for i,v in enumerate(self.events) if i>start and v.get('node')==node and v['event']=='FLOOR_BEFORE_RETURN')
            upper=next(i for i,v in enumerate(self.events) if i>lower and v.get('node')==node and v['event']=='FLOOR_RELEASE_AUTHORITY_CREATED')
            actual=[(i,v) for i,v in enumerate(self.events) if lower<i<upper and v.get('node')==node and v['event'].startswith(PREFIXES)]
            need([v['event'] for _,v in actual]==expected,'REMOVE retirement complete transaction callbacks')
            need(all(set(v)=={'node','event'} for _,v in actual),'REMOVE retirement callback shape')
            bound.update(i for i,_ in actual);counts.update(dict(generations=1,sources=len(decisions),borrowedGenerations=int(details['borrowedImages']),
                generationMembers=details['members'],callbacks=len(expected)))
            peak=max(peak,details['physicalImagesPeak'])
            self.retirements.append(dict(node=node,path=own['path'],start=lower,end=upper,**details,
                sources=[{k:v for k,v in value.items() if k!='steps'} for value in decisions],events=expected,
                finalInventory=sha(f.canonical(physical(after)))))
        eligible={i for i,v in enumerate(self.events) if v['event'].startswith(PREFIXES)}
        need(bound==eligible,'REMOVE retirement unbound callback')
        return dict(status='PARTIAL',profile=self.profile,**dict(counts),physicalImagePeak=peak,
            transactionChainSha256=sha(f.canonical(self.retirements)),peerPrecondition=peer_result,
            completeObservedRetirementCallbacksQualified=True,transientRetirementBytesQualified=False,
            processDeathQualified=False,phase3Complete=False)


def replay(root,profile):return Replay(root,profile).run()


def validate(root,profile):
    root=Path(root);need(profile in n.original.PROFILES,'REMOVE retirement profile');before=n.collection.inventory(root)
    original=r.validate(root,profile);result=replay(root,profile)
    need(n.collection.inventory(root)==before,'REMOVE retirement original changed')
    return dict(result,precondition=original)


OMISSIONS=('RETIREMENT_OLD_FILES_FORCED','RETIREMENT_CREATED','RETIREMENT_PROPOSAL_WRITTEN','RETIREMENT_PROPOSAL_FORCED',
    'RETIREMENT_SOURCE_CREATED','RETIREMENT_MANIFEST_WRITTEN','RETIREMENT_MANIFEST_FORCED',
    'RETIREMENT_MEMBER_WRITTEN','RETIREMENT_MEMBER_FORCED','RETIREMENT_IMAGE_WRITTEN','RETIREMENT_IMAGE_FORCED',
    'RETIREMENT_SOURCE_FORCED','RETIREMENT_BORROW_PREFIX_WRITTEN','RETIREMENT_BORROW_WRITTEN','RETIREMENT_BORROW_FORCED',
    'RETIREMENT_BORROWED_IMAGES_FORCED','RETIREMENT_FILE_DELETED','RETIREMENT_DIRECTORY_DELETED',
    'RETIREMENT_SAVED_FILE_DELETED','RETIREMENT_SAVED_DIRECTORY_DELETED','RETIREMENT_PROPOSAL_CLEARED',
    'RETIREMENT_BORROW_CLEARED','RETIREMENT_AUTHORITY_CLEARED','RETIREMENT_CLEARED',
    'SOURCE_RETIREMENT_WRITTEN','JOURNAL_ROTATION_CREATED','JOURNAL_ROTATION_WRITTEN','JOURNAL_ROTATION_RENAMED',
    'SOURCE_RETIREMENT_DIRECTORY_DELETED','SOURCE_RETIREMENT_CLEARED')
NEGATIVES={name:'REMOVE retirement complete transaction callbacks' for name in OMISSIONS}
NEGATIVES.update({name:'REMOVE retirement complete transaction callbacks' for name in
    ('member-force-before-write','saved-delete-before-original-delete','journal-rename-before-force','duplicate-delete')})
NEGATIVES.update({'callback-extra-field':'REMOVE retirement callback shape','unbound-callback':'REMOVE retirement unbound callback'})


def mutate(root,name):
    root=Path(root);events=n.collection.read_json(root,'events.json',n.collection.EVENT_BYTES)
    def first(point):return next(i for i,v in enumerate(events) if v['event']==point)
    def move(point,before):
        at=first(point);row=events.pop(at);target=next(i for i,v in enumerate(events) if v['node']==row['node'] and v['event']==before)
        events.insert(target,row)
    if name in OMISSIONS:events.pop(first(name))
    elif name=='member-force-before-write':move('RETIREMENT_MEMBER_FORCED','RETIREMENT_MEMBER_WRITTEN')
    elif name=='saved-delete-before-original-delete':move('RETIREMENT_SAVED_FILE_DELETED','RETIREMENT_FILE_DELETED')
    elif name=='journal-rename-before-force':move('JOURNAL_ROTATION_RENAMED','JOURNAL_ROTATION_FORCED')
    elif name=='duplicate-delete':
        at=first('RETIREMENT_FILE_DELETED');events.insert(at,dict(events[at]))
    elif name=='callback-extra-field':events[first('RETIREMENT_PROPOSAL_WRITTEN')]['claimedHash']='a'*64
    elif name=='unbound-callback':events.append(dict(node='node-1',event='RETIREMENT_SAVED_FILE_DELETED'))
    else:raise ValueError('REMOVE retirement unknown negative')
    (root/'events.json').write_bytes(f.canonical(events))


def negative(root,profile,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-remove-retirement-negative-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name);after=n.collection.inventory(changed)
        protected=lambda v:{k:h for k,h in v['files'].items() if k!='events.json'}
        need(protected(before)==protected(after) and before['directories']==after['directories'],'REMOVE retirement negative changed original files')
        other=lambda path:[v for v in n.collection.read_json(Path(path),'events.json',n.collection.EVENT_BYTES) if not v['event'].startswith(PREFIXES)]
        need(other(root)==other(changed),'REMOVE retirement negative changed other observations')
        r.replay(changed,profile)
        try:replay(changed,profile)
        except ValueError as error:need(str(error)==NEGATIVES[name],'REMOVE unrelated retirement negative: '+name+': '+str(error))
        else:raise ValueError('REMOVE retirement mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],retentionReplay='PASS',originalFilesAndOtherObservationsUnchanged=True)


def qualify(root,profile,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'REMOVE retirement replay workers')
    root=Path(root);original=validate(root,profile);before=n.collection.inventory(root);outcomes=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(negative,root,profile,before,name):name for name in NEGATIVES}
        for task in as_completed(pending):
            name=pending[task]
            try:result=task.result()
            except Exception as error:result=dict(case=name,status='FAIL',failure=str(error),type=type(error).__name__)
            outcomes.append(result);print(json.dumps(dict(result,profile=profile,completed=len(outcomes),total=len(pending))),file=sys.stderr,flush=True)
    need(n.collection.inventory(root)==before,'REMOVE retirement negative changed original')
    need(all(v['status']=='REJECTED' for v in outcomes),'REMOVE retirement negative matrix failed')
    return dict(original=original,negatives=sorted(outcomes,key=lambda v:v['case']),
        negativePrecondition='full-original-physical-network-export-retention; mutated retention replay; unchanged files and other events',
        mutatedFullPrerequisiteReplayed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--profile',required=True,choices=n.original.PROFILES)
    p.add_argument('--qualify',action='store_true');p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    result=qualify(a.root,a.profile,workers=a.workers) if a.qualify else validate(a.root,a.profile)
    print(json.dumps(result,sort_keys=True))
