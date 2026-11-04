"""Original scratch recovery while the interrupted floor remains charged.

This reader covers the cold recovery interval, not the complete live writer's
resource maximum. The enclosing process/history readers authenticate originals.
"""
from collections import Counter
import json
from pathlib import Path
import re
import shutil
import tempfile
from . import native_process_joint_floor as p

h,f,c,need=p.h,p.floor.f,p.floor.c,p.need
MIB=1024*1024
SCHEMA='gse-v53-joint-floor-scratch-recovery-v1'
UUID=r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
LIMITS={'GENERATION':(2,32*MIB),'SOURCE':(6,32*MIB),'JOURNAL':(1,32*MIB),
        'MISC':(1,2*MIB),'APPLICATION':(7,64*MIB),'CONTROL':(256,8*MIB)}


def same(actual,expected,reason):p.floor.same(actual,expected,'joint scratch '+reason)


def usage(charges):
    counts=Counter();metadata=staging=queued=0
    for unit,size in charges:
        need(unit in LIMITS and type(size) is int and 0<size<=LIMITS[unit][1],'joint scratch bounded charge')
        counts[unit]+=1
        if unit in ('GENERATION','SOURCE','JOURNAL','MISC'):metadata+=size
        if unit in ('SOURCE','APPLICATION'):staging+=size
        if unit=='CONTROL':queued+=size
    need(all(count<=LIMITS[unit][0] for unit,count in counts.items()) and
         metadata<=384*MIB and staging<=512*MIB and queued<=64*MIB,'joint scratch combined capacity')
    return dict(metadata=metadata,staging=staging,queued=queued,leases=sum(counts.values()),counts=dict(counts))


def baseline(files):
    """Cold storage charges from actual retained bytes, never observed counters."""
    need(files.get('generations') is None and 'generations' in files and
         files.get('sources') is None and 'sources' in files and len(files.get('pending.accept',b''))==12,
         'joint scratch supported cold owner')
    need({name for name,v in files.items() if v is None and '/' not in name}<=
         {'generations','sources','floor-copies'},'joint scratch unexpected live storage')
    charges=[('JOURNAL',32*MIB),('MISC',2*MIB)]
    for area,unit in [('generations','GENERATION'),('sources','SOURCE'),('floor-copies','SOURCE')]:
        directories=sorted(name for name,v in files.items() if v is None and name.startswith(area+'/'))
        for name in directories:
            need(name.count('/')==1,'joint scratch direct retained copy')
            local={key[len(name)+1:]:v for key,v in files.items() if key.startswith(name+'/')}
            need(all(v is not None and '/' not in key for key,v in local.items()),'joint scratch flat retained copy')
            if area=='sources':
                need('source.gscp' in local and all(k=='source.gscp' or re.fullmatch('[0-9a-f]{64}\\.image',k) for k in local),
                     'joint scratch original source inventory')
            if area=='generations':need(name in ('generations/a','generations/b'),'joint scratch generation slot')
            if area=='floor-copies':need(re.fullmatch('floor-copies/[0-9a-f]{64}',name) is not None,'joint scratch floor copy path')
            charges.append((unit,max(1,sum(len(v) for k,v in local.items() if not k.endswith('.image')))))
            charges.extend(('APPLICATION',max(1,len(v))) for k,v in sorted(local.items()) if k.endswith('.image'))
    usage(charges);return charges


def marker(files,spec,role):
    need(files.get('scope.lock')==b'' and type(files.get('owner.json')) is bytes,'joint scratch original owner files')
    raw=files['owner.json'];need(0<len(raw)<=32768,'joint scratch owner marker capacity');value=json.loads(raw)
    need(type(value) is dict and set(value)=={'schema','root','identity','role','parent','directoryKey'} and
         f.canonical(value)==raw,'joint scratch canonical owner marker')
    same({key:value[key] for key in ('schema','root','identity','role')},dict(schema='gse-v53-derived-scratch-v1',
         root=spec['root']['digest'],identity=spec['identity'],role=role),'original owner binding')
    parent=value['parent'];path=Path(spec['paths']['scratch'])/role.lower()
    need(type(parent) is dict and set(parent)=={'path','parentRealPath','fileStoreName','fileStoreType','parentFileKey'} and
         all(type(v) is str and v for v in parent.values()) and parent['path']==str(path) and
         parent['parentRealPath']==str(path.parent) and type(value['directoryKey']) is str and value['directoryKey'],
         'joint scratch original path binding')
    return value


def copy_inventory(side):
    copies={};manifests={}
    for node in p.floor.NODES:
        files=c.inventory(side/'originals'/node);prefix,members,_=c.current(files)
        copies[node]=dict(members,**{'generation.gsr':files[prefix+'generation.gsr']})
        manifests[node]=h.digest(files[prefix+'generation.gsr'])
    return copies,manifests


def originals(raw,spec):
    side=Path(raw)/'joint-floor-recovery';cut=c.inventory(side/'process/at-cut-scratch')
    need({k for k in cut if '/' not in k}=={'incoming','outgoing'} and cut['incoming'] is None and cut['outgoing'] is None,
         'joint scratch exact original roles')
    result={role:{key[len(role)+1:]:v for key,v in cut.items() if key.startswith(role+'/')} for role in ('incoming','outgoing')}
    markers=[marker(result[role.lower()],spec,role) for role in ('INCOMING','OUTGOING')]
    need(markers[0]['directoryKey']!=markers[1]['directoryKey'] and
         {k:v for k,v in markers[0]['parent'].items() if k!='path'}=={k:v for k,v in markers[1]['parent'].items() if k!='path'},
         'joint scratch distinct sibling scopes')
    need(set(result['incoming'])=={'owner.json','scope.lock'},'joint scratch idle incoming original')
    copies,manifests=copy_inventory(side)
    # All four original copies describe the same application. Remote prefix
    # acquisition borrows those exact local images instead of copying them.
    images={k:v for k,v in copies['node-2'].items() if k.endswith('.image')}
    need(images and all({k:v for k,v in members.items() if k.endswith('.image')}==images for members in copies.values()),
         'joint scratch original borrowed images')
    ordered=sorted((node for node in manifests if node!='node-2'),key=manifests.get);remaining=ordered[spec['ordinal']-1:]
    outgoing=result['outgoing'];dirs=sorted(k for k,v in outgoing.items() if v is None)
    need(len(dirs)==len(remaining) and all(re.fullmatch('source-'+UUID,name) for name in dirs),
         'joint scratch outstanding receiver count')
    need(set(outgoing)=={'owner.json','scope.lock',*dirs,*(name+'/source.gscp' for name in dirs)},
         'joint scratch exact abandoned receiver files')
    same(sorted(outgoing[name+'/source.gscp'].hex() for name in dirs),
         sorted(copies[node]['source.gscp'].hex() for node in remaining),'original borrowed receiver bytes')
    need(c.inventory(side/'process/after-death-scratch')==cut,'joint scratch original death unchanged')
    return result


def writer_charges(copies,order,retained,copied,handed,owner_scopes=2):
    need(1<=copied<=4 and 0<=handed<=copied and copied<=handed+1,'joint scratch writer overlap position')
    charges=list(retained)+[('CONTROL',32768)]*owner_scopes+[('CONTROL',4096)]
    # The already forced physical originals coexist with whole planned copies.
    for node in order[:copied]:
        files=copies[node]
        charges.append(('SOURCE',sum(len(v) for k,v in files.items() if not k.endswith('.image'))))
        charges.extend(('APPLICATION',len(v)) for k,v in sorted(files.items()) if k.endswith('.image'))
    # Receiver/source-record storage leaves only at its own completed handoff.
    for node in order[handed:]:
        if node=='node-2':continue
        files=copies[node];charges.extend([('SOURCE',len(files['source.gscp'])),('CONTROL',4096)])
        charges.extend(('CONTROL',len(v)) for k,v in sorted(files.items()) if k!='source.gscp' and not k.endswith('.image'))
    return charges


def initial_writer(raw,spec,*,owner_scopes=2):
    side=Path(raw)/'joint-floor-recovery';copies,manifests=copy_inventory(side)
    order=sorted(manifests,key=lambda node:(node=='node-2',manifests[node]))
    retained=baseline(c.inventory(side/'process/before-open'))
    rows=p.floor.read(side/'interrupted-usage.json');start=next(i for i,v in enumerate(rows) if v['event']=='FLOOR_RESERVED')
    rows=rows[start:];copied=0;handed=0;peak=usage(retained)
    for row in rows:
        if row['event']=='FLOOR_COPY_CREATED':copied+=1
        if row['event']=='FLOOR_COPY_HANDED_OFF':handed+=1
        expected=usage(writer_charges(copies,order,retained,max(1,copied),handed,owner_scopes))
        same(row['usage'],expected,'exact interrupted writer overlap')
        for field in ('metadata','staging','queued','leases'):peak[field]=max(peak[field],expected[field])
        for unit,count in expected['counts'].items():peak['counts'][unit]=max(peak['counts'].get(unit,0),count)
    need(copied==spec['ordinal'] and handed==copied-1 and rows[-1]['event']==spec['point'],
         'joint scratch exact writer overlap cut')
    return dict(callbacks=len(rows),copied=copied,handedOff=handed,peak=peak)


def resume_charges(planned,prefix,files,remote,common):
    prior={k[len(prefix):]:v for k,v in planned.items() if k.startswith(prefix)}
    borrowed=prior==files;extra=[]
    if remote:
        if not borrowed:extra.extend([('SOURCE',len(files['source.gscp'])),('CONTROL',4096)])
        extra.extend(('CONTROL',len(v)) for k,v in sorted(files.items()) if k!='source.gscp' and not k.endswith('.image'))
    after=dict(planned);after[prefix[:-1]]=None;after.update({prefix+k:v for k,v in files.items()})
    return after,baseline(after)+common+extra,borrowed


def resumed_writer(raw,*,owner_scopes=2):
    side=Path(raw)/'joint-floor-recovery';copies,manifests=copy_inventory(side)
    cold=c.inventory(side/'after-reopen');planned=dict(cold)
    events=p.floor.read(side/'floor-events.json');rows=p.floor.read(side/'resumed-usage.json')
    need([row['event'] for row in rows]==[v['event'] for v in events if v.get('node')=='node-2' and
         v.get('scope')=='joint-floor-reopened' and 'request' not in v],'joint scratch resumed resource callback coverage')
    starts=[i for i,v in enumerate(rows) if v['event']=='FLOOR_RESUME_RESERVED']
    need(len(starts)==4,'joint scratch resumed original copy count')
    common=[('CONTROL',32768)]*owner_scopes+[('CONTROL',4096)];checked=0;borrows=0;peak=usage(baseline(cold))
    def check(segment,charges):
        nonlocal checked
        expected=usage(charges)
        for row in segment:same(row['usage'],expected,'exact resumed writer overlap');checked+=1
        for field in ('metadata','staging','queued','leases'):peak[field]=max(peak[field],expected[field])
        for unit,count in expected['counts'].items():peak['counts'][unit]=max(peak['counts'].get(unit,0),count)
    # The admitted joiner is required first; original remaining voters follow
    # permanent node order. The local original resumes after remote acquisition.
    order=['node-6','node-1','node-3','node-2']
    for at,node in zip(starts,order):
        files=copies[node];prefix='floor-copies/'+manifests[node]+'/'
        planned,charges,borrowed=resume_charges(planned,prefix,files,node!='node-2',common)
        if node!='node-2' and borrowed:borrows+=1
        expected=p.floor.resume.resume_events(files);segment=rows[at:at+len(expected)]
        need([v['event'] for v in segment]==expected,'joint scratch resumed copy force order')
        check(segment,charges)
    at=next(i for i,v in enumerate(rows) if v['event']=='FLOOR_RESERVED')
    need(at>starts[-1] and rows[-1]['event']=='FLOOR_BEFORE_RETURN','joint scratch final floor follows all resumes')
    expected=p.floor.generation.floor.transaction({manifests[n]:v for n,v in copies.items()},
             (side/'proposal.gsr').read_bytes(),handoff=True)[0]
    need([row['event'] for row in rows[at:]]==[row['event'] for row in expected],'joint scratch final floor force order')
    check(rows[at:],baseline(planned)+common)
    return dict(callbacks=checked,remoteBorrowedCopies=borrows,remoteReceivedCopies=3-borrows,peak=peak)


def interval(files,charges):
    """Expected snapshots/forces and charges throughout one direct scope open."""
    current=dict(files);base=list(charges);owned=base+[('CONTROL',32768)]
    dirs=sorted(k for k,v in files.items() if v is None)
    names=sorted(k for k,v in files.items() if '/' in k and v is not None)
    need(all(re.fullmatch('source-'+UUID,k) for k in dirs) and
         all(k.split('/')[0] in dirs and k.count('/')==1 and
             (k.endswith('/source.gscp') or re.fullmatch('.*/[0-9a-f]{64}\\.image',k)) for k in names),
         'joint scratch direct recovery layout')
    pending={name:('SOURCE' if name.endswith('/source.gscp') else 'APPLICATION',max(1,len(files[name]))) for name in names}
    def row(event,leases):return dict(event=event,files=dict(current),usage=usage(leases))
    result=[row('BEFORE_OPEN',base),row('OWNER_FORCED',owned),row('RECOVERY_VALIDATED',owned+list(pending.values()))]
    discarded=[]
    for name in names:
        value=current.pop(name);pending.pop(name);discarded.append(dict(path=name,directory=False,bytes=len(value)))
        result.extend(row(event,owned+list(pending.values())) for event in ('FILE_REMOVED','FILE_REMOVAL_FORCED'))
    for name in reversed(dirs):
        current.pop(name);discarded.append(dict(path=name,directory=True,bytes=0))
        result.extend(row(event,owned) for event in ('DIRECTORY_REMOVED','DIRECTORY_REMOVAL_FORCED'))
    result.extend(row(event,owned if event!='CLOSED' else base) for event in ('RECOVERY_COMPLETE','OPEN_RETURN','CLOSED'))
    return result,discarded


def replay(area,receipt,original,charges,authority,start,end,events):
    need(type(receipt.get('rows')) is list and type(receipt.get('discarded')) is dict,'joint scratch recovery record shape')
    expected=[];discarded={}
    for role in ('INCOMING','OUTGOING'):
        rows,discarded[role]=interval(original[role.lower()],charges)
        expected.extend(dict(row,role=role) for row in rows)
    observed=receipt['rows'];need(len(observed)==len(expected),'joint scratch complete recovery callbacks')
    need({path.name for path in (area/'states').iterdir()}=={f'{i:03d}' for i in range(len(expected))},'joint scratch exact state inventory')
    prior=start;peak=usage(charges)
    for i,(row,wanted) in enumerate(zip(observed,expected)):
        need(type(row) is dict and set(row)=={'event','role','state','eventCount','usage','authority'},'joint scratch exact recovery row')
        same({k:row[k] for k in ('event','role','state')},dict(event=wanted['event'],role=wanted['role'],state=f'{i:03d}'),
             'ordered recovery forces')
        at=row['eventCount'];need(type(at) is int and prior<=at<=end,'joint scratch recovery event bounds');prior=at
        need(not any(v.get('node')=='node-2' and 'request' in v for v in events[start:at]),
             'joint scratch recovery before new requests')
        same(row['usage'],wanted['usage'],'exact overlapping resource accounting')
        same(row['authority'],authority,'recovery preserved authority')
        need(c.inventory(area/'states'/row['state'])==wanted['files'],'joint scratch exact deletion snapshot')
        for field in ('metadata','staging','queued','leases'):peak[field]=max(peak[field],wanted['usage'][field])
        for unit,count in wanted['usage']['counts'].items():peak['counts'][unit]=max(peak['counts'].get(unit,0),count)
    same(receipt['discarded'],discarded,'exact recovered discard list')
    return dict(callbacks=len(expected),discardedFiles=sum(not v['directory'] for rows in discarded.values() for v in rows),peak=peak)


def validate(raw,spec=None):
    raw=Path(raw);before=h.inventory(raw);side=raw/'joint-floor-recovery';producer=p.floor.read(side/'receipt.json')
    case=f"{producer.get('ordinal')},{producer.get('cut')},{producer.get('mode')}"
    need(p.producer_scope(raw,case).get('scratchRecovery') is True,'joint scratch requires v2 original history')
    if spec is None:spec,_=p.boundary(raw,case)
    area=side/'scratch-recovery'
    need({v.name for v in area.iterdir()}=={'recovery.json','states','after-maintenance'},'joint scratch exact recovery inventory')
    receipt=p.floor.read(area/'recovery.json')
    same({k:v for k,v in receipt.items() if k not in ('rows','discarded')},
         dict(schema=SCHEMA,status='PARTIAL',paths=dict(scratch=spec['paths']['scratch'],replica=spec['paths']['replica']),
              processDeathQualified=False,phase3Complete=False),'recovery receipt scope')
    original=originals(raw,spec);files=c.inventory(side/'after-reopen');charges=baseline(files)
    authority=[dict(path=k,sha256=h.digest(v)) for k,v in sorted(files.items()) if v is not None]
    events=p.floor.read(raw/'events.json');cold=[i for i,v in enumerate(events) if v.get('node')=='node-2' and v.get('scope')=='joint-floor-reopened']
    need(cold,'joint scratch original reopened owner')
    first=next((i for i in cold if events[i]['event']=='FLOOR_COPY_BEFORE_RETURN'),None)
    need(first is not None and cold.index(first)>0,'joint scratch original resumed work')
    opened=cold[cold.index(first)-1]+1
    need(not any('request' in events[i] for i in cold if i<first),'joint scratch recovery before new requests')
    result=replay(area,receipt,original,charges,authority,opened,first,events)
    after={role:None for role in ('incoming','outgoing')}
    for role,inventory in original.items():after.update({role+'/'+key:inventory[key] for key in ('owner.json','scope.lock')})
    need(c.inventory(area/'after-maintenance')==after,'joint scratch original scopes reused and drained')
    writer=initial_writer(raw,spec);resumed=resumed_writer(raw)
    need(h.inventory(raw)==before,'joint scratch changed original evidence')
    return dict(status='PARTIAL',sameScratchRecoveryChecked=True,coldBaseline=usage(charges),**result,
                interruptedWriterOverlap=writer,resumedWriterOverlap=resumed,
                liveWriterResourcesQualified=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={
    'receipt-path':'recovery receipt scope',
    'marker-root':'original owner binding',
    'marker-path':'original path binding',
    'receiver-bytes':'original borrowed receiver bytes',
    'baseline-reset':'exact overlapping resource accounting',
    'early-release':'exact overlapping resource accounting',
    'uncharged-owner':'exact overlapping resource accounting',
    'boolean-lease':'exact overlapping resource accounting',
    'missing-force':'ordered recovery forces',
    'reordered-force':'ordered recovery forces',
    'early-deletion':'exact deletion snapshot',
    'authority-change':'recovery preserved authority',
    'late-recovery':'recovery event bounds',
    'discard-omission':'exact recovered discard list',
    'leftover':'original scopes reused and drained',
    'writer-released-copy':'exact interrupted writer overlap',
    'writer-released-receiver':'exact interrupted writer overlap',
    'writer-uncharged-record':'exact interrupted writer overlap',
    'resumed-released-copy':'exact resumed writer overlap',
    'resumed-uncharged-record':'exact resumed writer overlap',
    'resumed-omitted-callback':'resumed resource callback coverage',
}


def negative_cases(case):
    ordinal,_,_=p.selected(case)
    # The fourth copy is local and the three remote receivers have handed off.
    # Choose before replay from the declared cut, never from observed failures.
    absent={'receiver-bytes','early-deletion','discard-omission'} if ordinal==4 else set()
    return {name:reason for name,reason in NEGATIVES.items() if name not in absent}


def mutate(raw,name):
    need(name in NEGATIVES,'joint scratch unknown negative');raw=Path(raw);side=raw/'joint-floor-recovery';area=side/'scratch-recovery'
    path=area/'recovery.json';value=p.floor.read(path);rows=value['rows']
    at=next(i for i,v in enumerate(rows) if v['role']=='OUTGOING' and v['event']=='RECOVERY_VALIDATED')
    def save():path.write_bytes(f.canonical(value))
    if name.startswith('resumed-'):
        path=side/'resumed-usage.json';value=p.floor.read(path)
        at=next(i for i,v in enumerate(value) if v['event']=='FLOOR_RESUME_RESERVED')
        if name=='resumed-omitted-callback':value.pop(at)
        elif name=='resumed-uncharged-record':value[at]['usage']['queued']-=1
        else:value[at]['usage']['staging']-=1
    elif name.startswith('writer-'):
        path=side/'interrupted-usage.json';value=p.floor.read(path)
        u=next(v['usage'] for v in value if v['event']=='FLOOR_RESERVED')
        if name=='writer-uncharged-record':u['queued']-=1;u['counts']['CONTROL']-=1
        elif name=='writer-released-copy':u['staging']-=1;u['counts']['APPLICATION']-=1
        else:u['staging']-=1;u['metadata']-=1;u['counts']['SOURCE']-=1
        u['leases']-=1
    elif name=='receipt-path':value['paths']['scratch']+='/different'
    elif name.startswith('marker-'):
        path=side/'process/at-cut-scratch/outgoing/owner.json';value=p.floor.read(path)
        if name=='marker-root':value['root']='ff'*32
        else:value['parent']['path']+='/different'
    elif name=='receiver-bytes':
        path=next((side/'process/at-cut-scratch/outgoing').glob('source-*/source.gscp'))
        path.write_bytes(path.read_bytes()+b'changed');return path.relative_to(raw).as_posix()
    elif name=='baseline-reset':
        for row in rows:
            u=row['usage'];u['metadata']-=32*MIB;u['leases']-=1;u['counts'].pop('JOURNAL')
    elif name=='early-release':
        u=rows[at]['usage'];u['metadata']-=1;u['staging']-=1;u['leases']-=1;u['counts']['SOURCE']-=1
    elif name=='uncharged-owner':rows[at]['usage']['queued']-=32768
    elif name=='boolean-lease':rows[at]['usage']['leases']=True
    elif name=='missing-force':rows[at]['event']='OMITTED_RECOVERY_VALIDATED'
    elif name=='reordered-force':rows[at],rows[at+1]=rows[at+1],rows[at]
    elif name=='early-deletion':
        path=next((area/'states'/rows[at]['state']).glob('source-*/source.gscp'));path.unlink();return path.relative_to(raw).as_posix()
    elif name=='authority-change':rows[at]['authority'][0]['sha256']='ff'*32
    elif name=='late-recovery':rows[at]['eventCount']=len(p.floor.read(raw/'events.json'))
    elif name=='discard-omission':value['discarded']['OUTGOING'].pop(0)
    elif name=='leftover':
        path=area/'after-maintenance/outgoing/unremoved';path.write_bytes(b'leftover');return path.relative_to(raw).as_posix()
    save();return path.relative_to(raw).as_posix()


def negative(raw,name,before):
    need(name in NEGATIVES,'joint scratch unknown negative');reason='joint scratch '+NEGATIVES[name]
    with tempfile.TemporaryDirectory(prefix='v53-joint-scratch-negative-') as tmp:
        changed=Path(tmp)/'raw';shutil.copytree(raw,changed);path=mutate(changed,name);after=h.inventory(changed)
        need(before!=after and before['directories']==after['directories'] and
             {k:v for k,v in before['files'].items() if k!=path}=={k:v for k,v in after['files'].items() if k!=path},
             'joint scratch negative changed protected input')
        try:
            if name.startswith('writer-'):initial_writer(changed,p.floor.read(changed/'joint-floor-recovery/process/spec.json'))
            elif name.startswith('resumed-'):resumed_writer(changed)
            else:validate(changed)
        except ValueError as error:need(str(error)==reason,'joint scratch unrelated rejection: '+name+': '+str(error))
        else:raise ValueError('joint scratch accepted mutation: '+name)
    return dict(case=name,status='REJECTED',reason=reason)


def qualify(raw,progress=None):
    raw=Path(raw);before=h.inventory(raw);producer=p.floor.read(raw/'joint-floor-recovery/receipt.json')
    case=f"{producer.get('ordinal')},{producer.get('cut')},{producer.get('mode')}"
    original=p.inspect(raw,case)
    need(original.get('scratchRecovery',{}).get('sameScratchRecoveryChecked') is True,
         'joint scratch requires v2 original history')
    ordinal,_,_=p.selected(case)
    need(type(original['scratchRecovery'].get('discardedFiles')) is int and
         original['scratchRecovery']['discardedFiles']==4-ordinal,
         'joint scratch declared cut receiver count')
    results=[]
    for name in negative_cases(case):
        results.append(negative(raw,name,before))
        if progress:progress(results[-1])
    need(h.inventory(raw)==before,'joint scratch negatives changed original')
    return dict(status='PARTIAL',original=original,negatives=results,processDeathQualified=False,phase3Complete=False)


if __name__=='__main__':
    import argparse
    import sys
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('raw');parser.add_argument('--qualify',action='store_true');a=parser.parse_args()
    if a.qualify:result=qualify(a.raw,lambda row:print(json.dumps(row),file=sys.stderr,flush=True))
    else:
        row=p.floor.read(Path(a.raw)/'joint-floor-recovery/receipt.json')
        result=p.inspect(a.raw,f"{row.get('ordinal')},{row.get('cut')},{row.get('mode')}")
        need('scratchRecovery' in result,'joint scratch requires v2 original history')
    print(json.dumps(result,sort_keys=True))
