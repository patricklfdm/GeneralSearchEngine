"""Replay actual current/PROMISE and receiving-copy accounting in one budget.

This is neither the complete physical metadata maximum nor transition-completion
qualification. Every expected copy and charge is derived from the native source.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import source_export_evidence as x
from . import joining_history_run as h

e,c,need=x.e,x.c,x.e.need
MODES=('image-count','shared-short','shared-exact')
CASES=tuple((size,mode) for size in (3,4,5) for mode in MODES)
SCHEMA='gse-v53-combined-receive-v1'
COUNTER_CUTS=('ALLOCATOR_BEFORE_WRITE','ALLOCATOR_CREATED','ALLOCATOR_WRITTEN','ALLOCATOR_FORCED',
              'ALLOCATOR_RENAMED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN')


def same(actual,expected,reason):need(e.f.canonical(actual)==e.f.canonical(expected),reason)


def usage(metadata,packet,image,control,complete=0,denied=False,closed=False):
    if closed:return dict(metadata=0,staging=0,queued=0,leases=0,counts={})
    counts=dict(GENERATION=1,JOURNAL=1,MISC=1,SOURCE=1+max(0,complete-1)+int(denied),APPLICATION=2+complete,CONTROL=1+complete+int(denied))
    if complete:counts['LEARNER']=1
    return dict(metadata=34*e.MIB+metadata+packet*(1+complete+int(denied)),
        staging=packet*(1+complete+int(denied))+image*(2+complete),
        queued=control*(1+max(0,complete-1)+int(denied))+(4096 if complete else 0),
        leases=sum(counts.values()),counts=counts)


def case(root,size,mode):
    x.case(root,size,additional=('states','events.json','counter-events.json','result.json'))
    original=c.inventory(root/'captured/node-1');prefix,members,packet=c.current(original)
    image_files={key:value for key,value in members.items() if key.endswith('.image')}
    need(len(image_files)==1,'combined single original image')
    metadata=len(original[prefix+'generation.gsr'])+sum(len(v) for k,v in members.items() if not k.endswith('.image'))
    packet_bytes=members['source.gscp'];p=len(packet_bytes);image=sum(map(len,image_files.values()))
    grants=c.journal(original['grants.gsr'],packet['capsule']['root'],'node-1');control=sum(len(v[1]) for v in grants[-2:])
    copies=4 if mode=='shared-short' else 5;limit=512*e.MIB if mode=='image-count' else 6*p+7*image-(1 if mode=='shared-short' else 0)
    stages=['baseline',*[f'complete-{n}' for n in range(copies)],'refused','refused-clean','counter-forced','scratch-drained','owner-closed']
    events=x.load(root/'events.json');need(type(events) is list,'combined events')
    need([row.get('stage') for row in events]==stages,'combined complete ordered stages')
    need((root/'states').is_dir() and not (root/'states').is_symlink() and {p.name for p in (root/'states').iterdir()}==set(stages),'combined exact state inventory')
    scratch={};live=0;forced=False;maximum=dict(metadata=0,staging=0,queued=0,images=0)
    for row in events:
        stage=row['stage'];need(set(row)=={'stage','usage'},'combined event fields')
        denied=stage=='refused' and mode!='shared-exact'
        if stage.startswith('complete-'):
            scratch['copy-'+str(live)]=None
            scratch.update({'copy-'+str(live)+'/'+k:v for k,v in dict(image_files,**{'source.gscp':packet_bytes}).items()});live+=1
        if denied:scratch.update({'denied':None,'denied/source.gscp':packet_bytes})
        if stage=='refused-clean':scratch={k:v for k,v in scratch.items() if k!='denied' and not k.startswith('denied/')}
        if stage=='counter-forced':forced=True
        if stage in ('scratch-drained','owner-closed'):scratch={};live=0
        expected=usage(metadata,p,image,control,live,denied,stage=='owner-closed')
        same(row['usage'],expected,'combined exact resource accounting')
        need(expected['staging']<=limit and expected['metadata']<=384*e.MIB and expected['queued']<=64*e.MIB,'combined declared capacity')
        state=root/'states'/stage
        need(state.is_dir() and not state.is_symlink() and {p.name for p in state.iterdir()}=={'scratch','authority'},'combined exact state members')
        need(c.inventory(state/'scratch')==scratch,'combined exact physical copies')
        authority=dict(original)
        if forced:
            allocator=e.f.decode(original['allocator.gsr'],'records','ALLOCATOR');need(allocator['counter']==2,'combined original counter')
            authority['allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(allocator,counter=3))
        need(c.inventory(state/'authority')==authority,'combined original authority changed')
        for key in ('metadata','staging','queued'):maximum[key]=max(maximum[key],expected[key])
        maximum['images']=max(maximum['images'],expected['counts'].get('APPLICATION',0))
    rejection='resource ownership/count' if mode=='image-count' else 'shared staging capacity'
    same(x.load(root/'result.json'),dict(size=size,mode=mode,stagingLimit=limit,rejection=rejection,status='PASS'),'combined result scope')
    peak=usage(metadata,p,image,control,copies)
    same(x.load(root/'counter-events.json'),[dict(point=point,usage=peak) for point in COUNTER_CUTS],
         'combined ordered counter forces under pressure')
    need((mode!='shared-exact' or peak['staging']==limit) and
         (mode!='shared-short' or peak['staging']+p+image==limit+1),'combined exact byte boundary')
    return dict(case=f'stable-{size}-{mode}',size=size,mode=mode,completeCopies=copies,peak=maximum,stagingLimit=limit,rejection=rejection,
                originalPlanSha256=e.digest((root/'original-plan.gsbp').read_bytes()))


def validate(directory):
    root=Path(directory);before=h.inventory(root)
    names=[f'stable-{n}-{mode}' for n,mode in CASES]
    need({p.name for p in root.iterdir()}==set(names)|{'receipt.json'},'combined complete case inventory')
    rows=[case(root/name,n,mode) for name,(n,mode) in zip(names,CASES)]
    need(len({r['originalPlanSha256'] for r in rows})==9,'combined distinct original plans')
    wanted=dict(schema=SCHEMA,status='PASS',cases=[dict(case=name,size=n,mode=mode) for name,(n,mode) in zip(names,CASES)],
                network=False,simultaneousMaximumQualified=False,phase3Complete=False)
    same(x.load(root/'receipt.json'),wanted,'combined receipt scope')
    need(h.inventory(root)==before,'combined original changed during replay')
    return dict(status='PASS',scope='native-current-promise-and-receiving-copy-overlap',caseCount=9,cases=rows,
                simultaneousMaximumQualified=False,transitionCompletionQualified=False,network=False,phase3Complete=False)


NEGATIVES={
    'scope':'combined receipt scope','missing-case':'combined complete case inventory',
    'missing-stage':'combined complete ordered stages','reordered-stage':'combined complete ordered stages',
    'uncharged-packet':'combined exact resource accounting','uncharged-image':'combined exact resource accounting',
    'uncharged-control':'combined exact resource accounting','invented-lease':'combined exact resource accounting',
    'boolean-usage':'combined exact resource accounting','early-release':'combined exact resource accounting',
    'missing-image':'combined exact physical copies','changed-packet':'combined exact physical copies',
    'extra-file':'combined exact physical copies','lost-original':'combined original authority changed',
    'counter-not-forced':'combined original authority changed','leftover-scratch':'combined exact physical copies',
    'relaxed-limit':'combined result scope','wrong-rejection':'combined result scope',
    'missing-force':'combined ordered counter forces under pressure',
    'reordered-force':'combined ordered counter forces under pressure',
    'released-during-force':'combined ordered counter forces under pressure',
}


def mutate(root,name):
    member=root/'stable-3-image-count';path=member/'events.json';events=x.load(path)
    def save(p,v):p.write_text(json.dumps(v))
    if name=='scope':
        value=x.load(root/'receipt.json');value['simultaneousMaximumQualified']=True;save(root/'receipt.json',value)
    elif name=='missing-case':shutil.rmtree(root/'stable-5-shared-short')
    elif name in ('missing-stage','reordered-stage'):
        if name=='missing-stage':events.pop(1)
        else:events[1],events[2]=events[2],events[1]
        save(path,events)
    elif name in ('uncharged-packet','uncharged-image','uncharged-control','invented-lease','boolean-usage','early-release'):
        row=next(r for r in events if r['stage']==('refused' if name=='early-release' else 'complete-4'))['usage']
        if name=='boolean-usage':row['counts']['LEARNER']=True
        elif name=='early-release':row['staging']-=1
        else:row[{'uncharged-packet':'metadata','uncharged-image':'staging','uncharged-control':'queued','invented-lease':'leases'}[name]]-=1
        save(path,events)
    elif name in ('missing-image','changed-packet','extra-file'):
        scratch=member/'states/complete-4/scratch/copy-0'
        if name=='missing-image':next(scratch.glob('*.image')).unlink()
        else:(scratch/('source.gscp' if name=='changed-packet' else 'extra')).write_bytes(b'changed')
    elif name=='lost-original':(member/'states/refused/authority/grants.gsr').write_bytes(b'lost original')
    elif name=='counter-not-forced':shutil.copyfile(member/'captured/node-1/allocator.gsr',member/'states/counter-forced/authority/allocator.gsr')
    elif name=='leftover-scratch':(member/'states/owner-closed/scratch/extra').write_bytes(b'residue')
    elif name in ('missing-force','reordered-force','released-during-force'):
        path=member/'counter-events.json';value=x.load(path)
        if name=='missing-force':value.pop(3)
        elif name=='reordered-force':value[3],value[4]=value[4],value[3]
        else:value[3]['usage']['staging']-=1
        save(path,value)
    else:
        need(name in ('relaxed-limit','wrong-rejection'),'combined declared mutation')
        value=x.load(member/'result.json')
        if name=='relaxed-limit':value['stagingLimit']+=1
        else:value['rejection']='unrelated failure'
        save(member/'result.json',value)


def qualify(directory):
    before=h.inventory(Path(directory));original=validate(directory);rows=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-combined-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(directory,target);mutate(target,name)
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'combined unrelated negative: '+name+': '+str(error))
            else:raise ValueError('combined accepted mutation: '+name)
            rows.append(dict(case=name,status='REJECTED',reason=reason))
    need(h.inventory(Path(directory))==before,'combined original changed during negatives')
    return dict(original=original,negatives=rows,originalPreserved=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
