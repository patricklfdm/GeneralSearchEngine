"""Replay actual native learner retention and fresh-process nonvoting recovery.

Only archived bytes and recorded original inode bindings are consulted. No path
recorded inside a plan is opened; local passes do not imply readiness or votes.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import tempfile
from . import learner_plan_evidence as p
source,e,f,need=p.source,p.e,p.f,p.need
CUTS=('LEARNER_RETENTION_RENAMED','LEARNER_ROOT_PREFIX_WRITTEN','LEARNER_NODE_PREFIX_WRITTEN',
      'LEARNER_SOURCE_MOVED','LEARNER_ADMISSION_PREFIX_WRITTEN','LEARNER_STORE_BEFORE_RETURN')
RETAIN='learner-source.gslp';NEXT='learner-source.next.gslp';ADMISSION='learner-admission.gslp'


def retention(raw,plan,original):
    need(48<len(raw)<=256*1024,'learner retention bounded frame')
    need(struct.unpack('>4sHHHHI',raw[:16])==(b'GSLP',1,3,2,0,len(raw)-48),'learner retention header')
    need(raw[16:48]==bytes.fromhex(e.digest(raw[:16]+raw[48:])),'learner retention checksum')
    v=e.parse(raw[48:]);need(set(v)=={'schema','plan','staging','directoryKey','files'} and v['schema']=='gse-v53-learner-retention/1.3'
                           and v['plan']==e.digest(plan),'learner retention original plan')
    binding=v['staging'];need(type(binding) is dict and set(binding)=={'path','parentRealPath','fileStoreName','fileStoreType','parentFileKey'}
                            and all(type(x) is str and x.strip() and len(x.encode())<=4096 for x in binding.values()),'learner retention path fields')
    path=PurePosixPath(binding['path']);need(path.is_absolute() and str(path)==binding['path'] and '..' not in path.parts
                                           and str(path.parent)==binding['parentRealPath'],'learner retention canonical staging')
    for bound in original['paths']:
        other=PurePosixPath(bound['path']);need(path!=other and path not in other.parents and other not in path.parents,'learner retention overlapping paths')
    need(type(v['directoryKey']) is str and v['directoryKey'].strip() and len(v['directoryKey'].encode())<=4096,'learner retention directory key')
    need(type(v['files']) is list and len(v['files'])==len(original['files']),'learner retention original count')
    for row,expected in zip(v['files'],original['files']):
        need(type(row) is dict and set(row)=={'path','size','sha256','key'} and {k:row[k] for k in expected}==expected
             and type(row['key']) is str and row['key'].strip() and len(row['key'].encode())<=4096,'learner retention original inventory')
    return v


def files(path):
    need(path.is_dir() and not path.is_symlink(),'learner store snapshot directory')
    names=list(path.iterdir());need(len(names)<=32 and all(v.is_file() and not v.is_symlink() and v.stat().st_size<=64*e.MIB for v in names),
                                  'learner store snapshot files')
    return {v.name:v.read_bytes() for v in names}


def state(path,operation,replica,original,decision,location):
    need({v.name for v in path.iterdir()}=={'operation','source','identity.json'}|({'replica'} if replica is not None else set()),
         'learner store snapshot inventory')
    need(files(path/'operation')==operation,'learner store exact operation bytes')
    need(files(path/'source')==original,'learner store exact source bytes')
    if replica is not None:need(files(path/'replica')==replica,'learner store exact nonvoting replica bytes')
    need(e.parse((path/'identity.json').read_bytes())==dict(location=location,directoryKey=decision['directoryKey'],
         files=[dict(path=r['path'],key=r['key']) for r in decision['files']]),'learner store original inode/location')


def resume_trace(replica,location,candidate,expected):
    trace=['LEARNER_ACTIVE_PLAN_FORCED','LEARNER_ACTIVE_PLAN_PARENT_FORCED','LEARNER_PLAN_BEFORE_RETURN']
    if candidate:trace+=['LEARNER_RETENTION_RESEAL_FORCED','LEARNER_RETENTION_RESEAL_PARENT_FORCED','LEARNER_RETENTION_RENAMED']
    trace+=['LEARNER_RETENTION_ACTIVE_FORCED','LEARNER_RETENTION_ACTIVE_PARENT_FORCED','LEARNER_RETENTION_BEFORE_RETURN']
    if replica is None:trace+=['LEARNER_REPLICA_CREATED']
    trace+=['LEARNER_REPLICA_LOCKED'];replica=replica or {}
    def write(name,prefix):
        if name not in replica:trace.append(prefix+'_CREATED')
        if len(replica.get(name,b''))<len(expected[name]):trace.extend((prefix+'_PREFIX_WRITTEN',prefix+'_WRITTEN'))
        trace.extend((prefix+'_FORCED',prefix+'_PARENT_FORCED'))
    write('root.gsr','LEARNER_ROOT');write('node.gsr','LEARNER_NODE')
    if location=='staging':trace.append('LEARNER_SOURCE_MOVED')
    trace+=['LEARNER_SOURCE_RETAINED_DIRECTORY_FORCED','LEARNER_SOURCE_MOVE_PARENTS_FORCED']
    write(ADMISSION,'LEARNER_ADMISSION');trace.append('LEARNER_STORE_BEFORE_RETURN');return trace


def native(history,cache):
    # Cache only byte-identical, completely inventoried source histories verified
    # earlier in this call. Mutation of any path or byte changes the key.
    inventory={}
    for path in sorted(history.rglob('*')):
        need(not path.is_symlink() and (path.is_file() or path.is_dir()),'learner store original regular history')
        inventory[path.relative_to(history).as_posix()]=e.digest(path.read_bytes()) if path.is_file() else None
    key=e.digest(f.canonical(inventory))
    if key not in cache:cache[key]=source.validate(history)
    return cache[key]


def case_bytes(path,index,cache):
    point=CUTS[index//2];mode=('halt','kill')[index%2];history=path/'source-history'
    need({v.name for v in path.iterdir()}=={'source-history','original.gslp','preparation.json','before','interrupted','resumed',
         'interrupted.stdout','interrupted.stderr','resumed.stdout','resumed.stderr'},'learner store case inventory')
    native(history,cache);original=source.c.inventory(history/'learner-source-copy')
    original_root=(history/'before-learner-source/node-1/root.gsr').read_bytes()
    request=e.parse((history/'learner-reserve-payload.bin').read_bytes())['request']
    learner=next(v for v in request['target'] if v['node']=='node-4');peer=next(v for v in request['target'] if v['node']=='node-1')
    raw=(path/'original.gslp').read_bytes();plan=p.plan(raw,original_root,original,request,learner,peer)
    decision_raw=(path/'before/operation'/NEXT).read_bytes();decision=retention(decision_raw,raw,plan)
    expected={'replica.lock':b'','root.gsr':original_root,'node.gsr':f.encode('records','NODE',dict(root=request['root'],identity=learner)),ADMISSION:decision_raw}
    operation={'operation.lock':b'','learner.gslp':raw}
    state(path/'before',dict(operation,**{NEXT:decision_raw}),None,original,decision,'staging')
    position=index//2;partial=None if position==0 else {'replica.lock':b'','root.gsr':original_root}
    if position==1:partial['root.gsr']=original_root[:len(original_root)//2]
    if position>=2:partial['node.gsr']=expected['node.gsr'][:len(expected['node.gsr'])//2] if position==2 else expected['node.gsr']
    if position>=4:partial[ADMISSION]=decision_raw[:len(decision_raw)//2] if position==4 else decision_raw
    location='retained' if position>=3 else 'staging'
    state(path/'interrupted',dict(operation,**{RETAIN:decision_raw}),partial,original,decision,location)
    state(path/'resumed',dict(operation,**{RETAIN:decision_raw}),expected,original,decision,'retained')
    preparation=list(p.CUTS)+['LEARNER_SOURCE_METADATA_RESERVED']
    for _ in sorted(n for n in original if n!='source.gscp' and not n.endswith('.image')):
        preparation+=['LEARNER_SOURCE_MEMBER_CREATED','LEARNER_SOURCE_MEMBER_PREFIX_WRITTEN','LEARNER_SOURCE_MEMBER_WRITTEN','LEARNER_SOURCE_MEMBER_FORCED']
    preparation+=['LEARNER_SOURCE_DIRECTORY_FORCED','LEARNER_ACTIVE_PLAN_FORCED','LEARNER_ACTIVE_PLAN_PARENT_FORCED','LEARNER_PLAN_BEFORE_RETURN',
                  'LEARNER_RETENTION_CREATED','LEARNER_RETENTION_PREFIX_WRITTEN','LEARNER_RETENTION_WRITTEN']
    need(e.parse((path/'preparation.json').read_bytes())==preparation,'learner store original preparation force trace')
    trace=resume_trace(None,'staging',True,expected);trace=trace[:trace.index(point)+1]
    need((path/'interrupted.stdout').read_text().splitlines()==['POINT '+v for v in trace]+['CUT '+point]
         and (path/'interrupted.stderr').read_bytes()==b'','learner store original interruption trace')
    trace=resume_trace(partial,location,False,expected)
    need((path/'resumed.stdout').read_text().splitlines()==['POINT '+v for v in trace]+['STORE '+e.digest(raw)]
         and (path/'resumed.stderr').read_bytes()==b'','learner store original completion trace')
    return dict(scope='native-learner-store-bytes-and-traces',status='PASS',processResultQualified=False)


def _validate_cases(root,selected,_cache=None):
    root=Path(root);cache={} if _cache is None else _cache;total=0
    need(root.is_dir() and not root.is_symlink(),'learner store evidence directory')
    for count,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_file() or path.is_dir()),'learner store regular evidence')
        if path.is_file():
            size=path.stat().st_size;need(size<=64*e.MIB,'learner store evidence file capacity');total+=size
        need(count<=262144 and total<=2*1024*e.MIB,'learner store evidence capacity')
    all_names=[point+'-'+mode for point in CUTS for mode in ('halt','kill')]
    need(type(selected) is tuple and selected and len(set(selected))==len(selected)
         and all(v in all_names for v in selected),'learner store declared cases')
    names=set(selected)
    need({v.name for v in root.iterdir()}==names|{'cases.json'},'learner store complete case inventory')
    rows=e.parse((root/'cases.json').read_bytes());need(type(rows) is list and len(rows)==len(selected),'learner store complete process count');pids=set()
    for name,row in zip(selected,rows):
        index=all_names.index(name)
        point=CUTS[index//2];mode=('halt','kill')[index%2];path=root/(point+'-'+mode)
        case_bytes(path,index,cache)
        need(type(row) is dict and set(row)=={'point','mode','pid','resumePid','exit','resumeExit','lockRefused'} and row['point']==point and row['mode']==mode
             and row['exit']==(23 if mode=='halt' else 137) and type(row['resumeExit']) is int and row['resumeExit']==0
             and row['lockRefused'] is (mode=='kill'),'learner store original process result')
        for field in ('pid','resumePid'):
            pid=row[field];need(type(pid) is int and pid>0 and pid not in pids,'learner store distinct processes');pids.add(pid)
    return dict(status='PASS',scope='native-source-nonvoting-store',nativeHistories=len(selected),processCases=len(selected),processes=len(pids),
                liveLockRefusals=sum(v.endswith('-kill') for v in selected),typedPreparationQualified=False,jointEligibilityQualified=False,phase3Complete=False)


def validate(root,_cache=None):
    return _validate_cases(root,tuple(point+'-'+mode for point in CUTS for mode in ('halt','kill')),_cache)


def validate_case(root,name):
    """One complete original history is portable; it never closes the matrix.

    Future hosted aggregation must bind all twelve histories to the same source
    and build. PIDs from different runners are not globally unique identities.
    """
    result=_validate_cases(root,(name,))
    return dict(result,status='PARTIAL',case=name,completeProcessMatrix=False)


NEGATIVES={
 'missing-case':'learner store complete case inventory',
 'wrong-plan':'learner retention original plan',
 'wrong-source':'learner store exact source bytes',
 'changed-inode':'learner store original inode/location',
 'false-move':'learner store original inode/location',
 'invented-promise':'learner store exact nonvoting replica bytes',
 'repaired-foreign-root':'learner store exact nonvoting replica bytes',
 'missing-force':'learner store original completion trace',
 'missing-source-force':'learner store original preparation force trace',
 'false-process-success':'learner store original process result',
 'duplicate-process':'learner store distinct processes',
 'missing-source-byte':'learner source exact original generation',
}


def qualify(root):
    root=Path(root);cache={};original=validate(root,cache);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-store-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target);first=target/(CUTS[0]+'-halt');last=target/(CUTS[-1]+'-halt')
            if name=='missing-case':shutil.rmtree(first)
            elif name=='wrong-plan':
                path=first/'before/operation'/NEXT;raw=path.read_bytes();v=e.parse(raw[48:]);v['plan']='0'*64
                body=f.canonical(v);header=struct.pack('>4sHHHHI',b'GSLP',1,3,2,0,len(body));path.write_bytes(header+bytes.fromhex(e.digest(header+body))+body)
            elif name=='wrong-source':(first/'resumed/source/source.gscp').write_bytes(b'wrong')
            elif name in ('changed-inode','false-move'):
                path=first/'resumed/identity.json';v=e.parse(path.read_bytes())
                if name=='changed-inode':v['directoryKey']='substituted'
                else:v['location']='staging'
                path.write_bytes(f.canonical(v))
            elif name=='invented-promise':(first/'resumed/replica/promise.gsr').write_bytes(b'wrong')
            elif name=='repaired-foreign-root':(first/'resumed/replica/root.gsr').write_bytes(b'wrong')
            elif name=='missing-force':
                path=last/'resumed.stdout';path.write_text(path.read_text().replace('POINT LEARNER_ADMISSION_FORCED\n',''))
            elif name=='missing-source-force':
                path=first/'preparation.json';v=e.parse(path.read_bytes());v.remove('LEARNER_SOURCE_MEMBER_FORCED');path.write_bytes(f.canonical(v))
            elif name in ('false-process-success','duplicate-process'):
                path=target/'cases.json';v=e.parse(path.read_bytes())
                if name=='false-process-success':v[0]['resumeExit']=1
                else:v[1]['pid']=v[0]['pid']
                path.write_bytes(f.canonical(v))
            elif name=='missing-source-byte':(first/'source-history/learner-source-copy/generation.gsr').unlink()
            else:raise ValueError('unknown learner store negative')
            try:validate(target,cache)
            except ValueError as error:need(str(error)==reason,'learner store unrelated negative: '+name+': '+str(error))
            else:raise ValueError('learner store accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--qualify',action='store_true');mode.add_argument('--case');args=parser.parse_args()
    print(json.dumps(validate_case(args.root,args.case) if args.case else (qualify if args.qualify else validate)(args.root)))
