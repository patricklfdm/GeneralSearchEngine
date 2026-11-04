"""Original-byte replay of conditional pinned-floor process death and cold recovery.

Every crash/reopen/final inventory and force sequence is projected from the seed.
The prior history is conditional; there is no native network or power-loss claim.
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import pinned_floor_evidence as e
from .membership_model import need

CUTS=('FLOOR_DIRECTORY_CREATED','FLOOR_LOCAL_ORIGINAL_FORCED','FLOOR_LOCAL_SELECTOR_WRITTEN',
      'FLOOR_LOCAL_SELECTOR_FORCED','FLOOR_LOCAL_PARENT_FORCED','FLOOR_PROPOSAL_FORCED','FLOOR_IMAGE_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN',
      'RETIREMENT_PARENT_FORCED','RETIREMENT_FILE_DELETED','RETIREMENT_DIRECTORY_DELETED','SOURCE_RETIREMENT_JOURNAL_PRUNED',
      'FLOOR_RELEASE_PARENT_FORCED','FLOOR_RELEASE_RELINQUISHED','FLOOR_RELEASE_FILE_DELETED','FLOOR_RELEASE_LOCAL_CLEARED','FLOOR_RELEASE_AUTHORITY_CLEARED')
PHYSICAL={'seed','inputs.json','receipt.json'}
read=e.original.read


def cases():return [dict(case=mode+'-'+cut,mode=mode,cut=cut) for mode in ('halt','kill') for cut in CUTS]


def inventory(root):
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'pinned process history root')
    result={};total=0
    for path in root.rglob('*'):
        need(len(result)<20000 and not path.is_symlink() and (path.is_dir() or path.is_file()),'pinned process history type/count')
        if path.is_file():
            need(path.stat().st_nlink==1,'pinned process history alias');total+=path.stat().st_size
            need(total<=512*1024*1024,'pinned process history bytes')
            value=e.original.info(e.g.read(path,64*1024*1024))
        else:value=dict(directory=True)
        result[path.relative_to(root).as_posix()]=value
    return result


def floor_steps(initial,plan):
    own=e.f.decode(plan['selector'],'records','SELECTOR')['digest']
    events,files,writes,dirs=e.floor.transaction({h:v for h,v in plan['copies'].items() if h!=own},plan['floor'])
    state=dict(initial);result=[]
    for at,row in enumerate(events):
        if at==2:
            for name in ('FLOOR_LOCAL_ORIGINAL_FORCED','FLOOR_LOCAL_SELECTOR_WRITTEN','FLOOR_LOCAL_SELECTOR_FORCED','FLOOR_LOCAL_PARENT_FORCED'):
                if name=='FLOOR_LOCAL_SELECTOR_WRITTEN':state[e.PIN]=e.original.info(plan['selector'])
                result.append((name,dict(state)))
        state.update({n:dict(directory=True) for n,i in dirs.items() if i==at})
        state.update({n:e.original.info(files[n]) for n,i in writes.items() if i==at})
        result.append((row['event'],dict(state)))
    return result


def release_steps(initial,plan):
    state=dict(initial);steps=[];authority='floor-copies/release.gsr'
    def event(name):steps.append((name,dict(state)))
    def remove(path,name):state.pop(path);event(name)
    if 'floor-copies' not in state:return steps
    if any(n.startswith('floor-copies/') for n in state):
        files=plan['expected']['compacted']
        value=dict(root=e.node_root(plan['floor']),node='node-1',floor=e.c.sha(plan['floor']),selector=e.c.sha(plan['selector']),
             files=[dict(path=n,size=v['bytes'],sha256=v['sha256']) for n,v in sorted(files.items()) if n.startswith('floor-copies/') and 'directory' not in v])
        raw=e.f.encode('records','RETIREMENT',value)
        if authority not in state:state[authority]=e.original.info(b'');event('FLOOR_RELEASE_AUTHORITY_CREATED')
        state[authority]=e.original.info(raw)
        for point in ('FLOOR_RELEASE_AUTHORITY_WRITTEN','FLOOR_RELEASE_AUTHORITY_FORCED','FLOOR_RELEASE_PARENT_FORCED'):event(point)
        if 'floor-copies/floor.gsr' in state:remove('floor-copies/floor.gsr','FLOOR_RELEASE_RELINQUISHED')
        for name in sorted(state):
            if name.startswith('floor-copies/') and name.count('/')==2:remove(name,'FLOOR_RELEASE_FILE_DELETED')
        for name in sorted(state):
            if name.startswith('floor-copies/') and 'directory' in state[name]:remove(name,'FLOOR_RELEASE_COPY_DELETED')
        if 'floor-copies/proposal.gsr' in state:remove('floor-copies/proposal.gsr','FLOOR_RELEASE_PROPOSAL_CLEARED')
        if e.PIN in state:remove(e.PIN,'FLOOR_RELEASE_LOCAL_CLEARED')
        remove(authority,'FLOOR_RELEASE_AUTHORITY_CLEARED')
    remove('floor-copies','FLOOR_RELEASE_CLEARED');event('FLOOR_RELEASE_BEFORE_RETURN');return steps


def maintain(initial,plan):
    state=dict(initial);steps=[]
    def add(rows):
        nonlocal state
        steps.extend(rows)
        if rows:state=rows[-1][1]
    if 'generations/b' in state and 'floor-copies/floor.gsr' not in state:
        add([('FLOOR_COPY_BEFORE_RETURN',dict(state))]*2);add(floor_steps(state,plan))
    if 'generations/b' in state or 'retirement' in state:
        rows,_=e.retirement.transaction(state,plan['old'],plan['retirement'],plan['binding'],True,slot='b');add(rows)
    if 'sources/'+plan['oldSource'] in state:
        add(e.source_release.transaction(state,plan['authority'],plan['compact'],plan['oldSource']))
    if 'floor-copies' in state:add(release_steps(state,plan))
    return steps


def opened(crash,plan):
    state=dict(crash);events=list(e.c.OPEN)
    if e.source_release.AUTHORITY in state:
        rows=e.source_release.transaction(state,plan['authority'],plan['compact'],plan['oldSource'])
        state=rows[-1][1];events.extend(name for name,_ in rows)
    if 'floor-copies/release.gsr' in state:
        rows=release_steps(state,plan);state=rows[-1][1];events.extend(name for name,_ in rows)
    return state,events


def exact(path,state,label):need(e.s.inventory(path)==state,'pinned process exact '+label)


def physical(state,original):
    current={n:v for n,v in original.items() if n=='generations/a' or n.startswith('generations/a/')}
    need({n:v for n,v in state.items() if n=='generations/a' or n.startswith('generations/a/')}==current,
         'pinned process current original lifetime')
    images=sum(n.endswith('.image') for n in state)
    sources=sum('directory' in v and n.count('/')==1 and n.startswith(('sources/','floor-copies/')) for n,v in state.items())
    sources+=int('retirement/source' in state or e.retirement.BINDING in state)
    need(images<=7 and sources<=6,'pinned process physical capacity')
    return sources,images


def process(path,metadata,action,row,wanted):
    need(type(metadata) is dict and set(metadata)=={'pid','action','exit','lockProbe'} and type(metadata['pid']) is int and metadata['pid']>0 and
         metadata['action']==action,'pinned process identity')
    fault=action=='fault';expected=73 if row['mode']=='halt' else 137
    need(type(metadata['exit']) is int and metadata['exit']==(expected if fault else 0) and type(metadata['lockProbe']) is bool and
         metadata['lockProbe']==(fault and row['mode']=='kill'),'pinned process actual outcome')
    need(e.g.read(path/(action+'.stderr'),1024*1024)==b'','pinned process unexpected stderr')
    rows=[e.original.parse(v) for v in e.g.read(path/(action+'.stdout'),1024*1024).splitlines()]
    need(rows and rows[0]==dict(event='STARTED',action=action,pid=metadata['pid']),'pinned process original start')
    ending=[dict(event='CUT',cut=row['cut'],pid=metadata['pid'])] if fault else [rows[-1]]
    if fault and row['mode']=='kill':ending.append(dict(event='AWAITING_KILL',cut=row['cut']))
    need(rows[-len(ending):]==ending and all('status' not in v for v in rows[:-len(ending)]),'pinned process terminal order')
    callbacks=rows[1:-len(ending)]
    need(all(type(v) is dict and set(v)=={'event','sources','images'} for v in callbacks) and [v['event'] for v in callbacks]==wanted,
         'pinned process exact force order: '+action)
    need(all(type(v[k]) is int and 0<=v[k]<=limit for v in callbacks for k,limit in (('sources',6),('images',7))),'pinned process observed capacity')
    if not fault:
        value=ending[0]
        need(type(value) is dict and value.get('nativeHistory') is False and type(value.get('peakSources')) is int and type(value.get('peakImages')) is int and
             type(value.get('pid')) is int and value==dict(status='PASS',action=action,pid=metadata['pid'],peakSources=max(v['sources'] for v in callbacks),
                        peakImages=max(v['images'] for v in callbacks),nativeHistory=False),'pinned process return binding')
    return metadata['pid']


def validate(root):
    root=Path(root);before=inventory(root);plan=e.derive(root);receipt=read(root/'receipt.json');wanted=cases()
    need(read(root/'inputs.json')==dict(oldSource=plan['oldSource']),'pinned process original source identity')
    need(type(receipt) is dict and set(receipt)=={'schema','status','cases','expectedCases','historicalAuthority','nativeHistoryQualified','powerLossQualified','phase3Complete'} and
         receipt['schema']=='gse-v53-pinned-floor-process-v1' and receipt['status']=='PASS' and receipt['expectedCases']==len(wanted) and
         receipt['historicalAuthority']=='conditional-fixture' and all(receipt[k] is False for k in ('nativeHistoryQualified','powerLossQualified','phase3Complete')) and
         type(receipt['cases']) is list and len(receipt['cases'])==len(wanted),'pinned process complete receipt')
    need({p.name for p in root.iterdir()}==PHYSICAL|{v['case'] for v in wanted},'pinned process root inventory')
    complete=maintain(plan['initial'],plan);need(complete[-1][1]==plan['expected']['released'],'pinned process projected final')
    for _,state in complete:physical(state,plan['initial'])
    peers={node:e.s.inventory(root/'seed'/node) for node in e.OWNERS if node!='node-1'};results=[]
    for actual,row in zip(receipt['cases'],wanted):
        need(type(actual) is dict and set(actual)=={'case','cut','mode','processes','status'} and all(actual[k]==v for k,v in row.items()) and actual['status']=='PASS'
             and type(actual['processes']) is list and len(actual['processes'])==3,'pinned process exact cases')
        path=root/row['case'];need({p.name for p in path.iterdir()}=={'owners','crash','reopened','final','cold',*[a+s for a in ('fault','resume','inspect') for s in ('.stdout','.stderr')]},
                                 'pinned process case inventory')
        need({p.name for p in (path/'owners').iterdir()}==set(e.OWNERS),'pinned process live owners')
        at=next(i for i,(name,_) in enumerate(complete) if name==row['cut']);crash=complete[at][1]
        reopened,opening=opened(crash,plan);continued=maintain(reopened,plan);final=continued[-1][1] if continued else reopened
        physical(reopened,plan['initial'])
        for _,state in continued:physical(state,plan['initial'])
        need(final==plan['expected']['released'],'pinned process recovery projection')
        for label,state in (('crash',crash),('reopened',reopened),('final',final),('cold',final),('owners/node-1',final)):exact(path/label,state,label)
        for node,state in peers.items():exact(path/'owners'/node,state,'peer '+node)
        expected=[list(e.c.OPEN)+[n for n,_ in complete[:at+1]],opening+[n for n,_ in continued],list(e.c.OPEN)]
        need(all(type(v) is dict and type(v.get('pid')) is int for v in actual['processes']) and
             len({v['pid'] for v in actual['processes']})==3,'pinned process fresh identities')
        for meta,action,events in zip(actual['processes'],('fault','resume','inspect'),expected):process(path,meta,action,row,events)
        results.append(dict(case=row['case'],status='PASS',freshProcesses=3))
    need(inventory(root)==before,'pinned process original changed')
    return dict(status='PASS',scope='conditional-pinned-floor-process',cases=results,freshProcesses=3*len(results),
                exactPhysicalRecoveryQualified=True,nativeHistoryQualified=False,fullResourceCompositionQualified=False,powerLossQualified=False,phase3Complete=False)


NEGATIVES={
    'missing-pin':'pinned process exact crash',
    'changed-local-image':'pinned process exact crash',
    'deleted-predecessor':'pinned process exact crash',
    'changed-retirement-backup':'pinned process exact crash',
    'changed-reopened-original':'pinned process exact reopened',
    'cold-selector':'pinned process exact cold',
    'invented-floor':'pinned process exact crash',
    'missing-force':'pinned process exact force order: fault',
    'false-kill-exit':'pinned process actual outcome',
    'reused-process':'pinned process fresh identities',
    'missing-case':'pinned process complete receipt',
}


def mutate(root,name):
    root=Path(root)
    if name=='missing-pin':(root/'halt-FLOOR_LOCAL_SELECTOR_FORCED/crash'/e.PIN).unlink()
    elif name=='changed-local-image':next((root/'halt-FLOOR_PARENT_FORCED/crash/generations/a').glob('*.image')).write_bytes(b'changed')
    elif name=='deleted-predecessor':shutil.rmtree(root/'halt-FLOOR_BEFORE_RETURN/crash/generations/b')
    elif name=='changed-retirement-backup':(root/'halt-RETIREMENT_FILE_DELETED/crash/retirement/source/source.gscp').write_bytes(b'changed')
    elif name=='changed-reopened-original':(root/'halt-RETIREMENT_FILE_DELETED/reopened/generations/a/source.gscp').write_bytes(b'changed')
    elif name=='cold-selector':(root/'halt-FLOOR_BEFORE_RETURN/cold/selector.gsr').write_bytes(b'changed')
    elif name=='invented-floor':(root/'halt-FLOOR_LOCAL_SELECTOR_FORCED/crash/floor-copies/floor.gsr').write_bytes(e.derive(root)['floor'])
    elif name=='missing-force':
        path=root/'halt-FLOOR_LOCAL_SELECTOR_FORCED/fault.stdout';rows=[e.original.parse(v) for v in path.read_bytes().splitlines()]
        rows=[v for v in rows if v.get('event')!='FLOOR_LOCAL_ORIGINAL_FORCED'];path.write_bytes(b''.join(e.f.canonical(v)+b'\n' for v in rows))
    elif name in ('false-kill-exit','reused-process','missing-case'):
        path=root/'receipt.json';value=read(path)
        if name=='missing-case':value['cases'].pop()
        elif name=='reused-process':value['cases'][0]['processes'][1]['pid']=value['cases'][0]['processes'][0]['pid']
        else:next(v for v in value['cases'] if v['mode']=='kill')['processes'][0]['exit']=0
        path.write_bytes(e.f.canonical(value))
    else:raise ValueError('unknown pinned process negative')


def qualify(root,progress=None):
    root=Path(root);before=inventory(root);original=validate(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-pinned-process-negative-') as temp:
            copy=Path(temp)/'raw';shutil.copytree(root,copy);mutate(copy,name)
            try:validate(copy)
            except ValueError as error:need(str(error)==reason,'pinned process unrelated negative: '+name+': '+str(error))
            else:raise ValueError('pinned process mutation accepted: '+name)
        row=dict(case=name,status='REJECTED',reason=reason);results.append(row)
        if progress:progress(row)
    need(inventory(root)==before,'pinned process qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('evidence');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.evidence) if args.qualify else validate(args.evidence),sort_keys=True))
