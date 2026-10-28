"""Independent native-source-bound learner plan persistence and process replay.

A forced plan is not a learner store, materialized application or voting authority.
Recorded paths are original bindings; portable replay never reads those locations.
"""
import argparse
import base64
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import tempfile
from . import learner_source_evidence as source
e,f,need=source.e,source.f,source.need
CUTS=('LEARNER_OPERATION_CREATED','LEARNER_OPERATION_LOCKED','LEARNER_PLAN_CREATED',
      'LEARNER_PLAN_PREFIX_WRITTEN','LEARNER_PLAN_WRITTEN','LEARNER_PLAN_FORCED','LEARNER_PLAN_PARENT_FORCED',
      'LEARNER_RESEAL_PLAN_FORCED','LEARNER_RESEAL_PLAN_PARENT_FORCED','LEARNER_PLAN_RENAMED',
      'LEARNER_ACTIVE_PLAN_FORCED','LEARNER_ACTIVE_PLAN_PARENT_FORCED','LEARNER_PLAN_BEFORE_RETURN')
LOCK='operation.lock';FILE='learner.gslp';NEXT='learner.next.gslp'


def encode(value):
    body=f.canonical(value);prefix=struct.pack('>4sHHHHI',b'GSLP',1,3,1,0,len(body))
    return prefix+bytes.fromhex(e.digest(prefix+body))+body


def plan(raw,original,files,request,learner,peer):
    need(48<len(raw)<=65536,'learner plan bounded frame')
    need(struct.unpack('>4sHHHHI',raw[:16])==(b'GSLP',1,3,1,0,len(raw)-48),'learner plan header')
    need(raw[16:48]==bytes.fromhex(e.digest(raw[:16]+raw[48:])),'learner plan checksum')
    value=e.parse(raw[48:]);need(set(value)=={'schema','root','learner','request','source','cut','generation','files','paths'},'learner plan fields')
    generation=f.decode(files['generation.gsr'],'records','GENERATION')
    expected=dict(schema='gse-v53-learner-plan/1.3',root=base64.b64encode(original).decode(),learner=learner,request=request,
                  source=peer,cut=generation['cut'],generation=base64.b64encode(files['generation.gsr']).decode(),
                  files=[dict(path=k,size=len(v),sha256=e.digest(v)) for k,v in sorted(files.items())])
    need({k:v for k,v in value.items() if k!='paths'}==expected,'learner plan exact native originals')
    bindings=value['paths'];need(type(bindings) is list and len(bindings)==2,'learner plan binding count');paths=[]
    for bound in bindings:
        need(type(bound) is dict and set(bound)=={'path','parentRealPath','fileStoreName','fileStoreType','parentFileKey'}
             and all(type(v) is str and v.strip() and len(v.encode())<=4096 for v in bound.values()),'learner plan binding fields')
        path=PurePosixPath(bound['path']);need(path.is_absolute() and str(path)==bound['path'] and '..' not in path.parts
             and str(path.parent)==bound['parentRealPath'],'learner plan canonical original path')
        need(all(path!=old and path not in old.parents and old not in path.parents for old in paths),'learner plan overlapping paths');paths.append(path)
    return value


def snapshot(path):
    need(path.is_dir() and not path.is_symlink(),'learner plan snapshot directory')
    names={p.name for p in path.iterdir()};need(names<=set((LOCK,FILE,NEXT)),'learner plan nonvoting inventory')
    need(all((path/name).is_file() and not (path/name).is_symlink() and (path/name).stat().st_size<=65536 for name in names),
         'learner plan snapshot member capacity')
    return {name:(path/name).read_bytes() for name in names}


def validate(root):
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'learner plan evidence directory');total=0
    for count,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_file() or path.is_dir()),'learner plan regular evidence')
        if path.is_file():
            size=path.stat().st_size;need(size<=64*e.MIB,'learner plan file capacity');total+=size
        need(count<=65536 and total<=512*e.MIB,'learner plan evidence capacity')
    names={point+'-'+mode for point in CUTS for mode in ('halt','kill')}
    need({p.name for p in root.iterdir()}==names|{'source-history','native-plan','cases.json'},'learner plan case inventory')
    original_result=source.validate(root/'source-history')
    history=root/'source-history';files=source.c.inventory(history/'learner-source-copy')
    original=(history/'before-learner-source/node-1/root.gsr').read_bytes()
    request=e.parse((history/'learner-reserve-payload.bin').read_bytes())['request']
    learner=next(v for v in request['target'] if v['node']=='node-4');peer=next(v for v in request['target'] if v['node']=='node-1')
    native=snapshot(root/'native-plan');need(set(native)=={LOCK,FILE} and native[LOCK]==b'','learner native forced plan')
    plan(native[FILE],original,files,request,learner,peer)
    rows=e.parse((root/'cases.json').read_bytes());need(type(rows) is list and len(rows)==26,'learner plan complete process count');pids=set()
    for n,row in enumerate(rows):
        index=n//2;point=CUTS[index];mode=('halt','kill')[n%2];name=point+'-'+mode;path=root/name
        need({p.name for p in path.iterdir()}=={'original.gslp','interrupted.stdout','interrupted.stderr','resumed.stdout','resumed.stderr','interrupted','resumed'},'learner plan process inventory')
        raw=(path/'original.gslp').read_bytes();plan(raw,original,files,request,learner,peer)
        expected={} if index==0 else {LOCK:b''}
        if index>=2:expected[NEXT if index<9 else FILE]=b'' if index==2 else raw[:len(raw)//2] if index==3 else raw
        need(snapshot(path/'interrupted')==expected,'learner plan exact interrupted bytes')
        recovered={LOCK:b'',FILE:raw} if index>=4 else expected
        need(snapshot(path/'resumed')==recovered,'learner plan exact recovered bytes')
        need(type(row) is dict and set(row)=={'point','mode','pid','resumePid','exit','resumeExit','resumed','lockRefused','replicaExists'}
             and row['point']==point and row['mode']==mode and row['exit']==(23 if mode=='halt' else 137)
             and type(row['resumeExit']) is int and (row['resumeExit']==0)==(index>=4)
             and row['resumed'] is (index>=4) and row['lockRefused'] is (mode=='kill' and index>0) and row['replicaExists'] is False,
             'learner plan process result')
        for key in ('pid','resumePid'):
            pid=row[key];need(type(pid) is int and pid>0 and pid not in pids,'learner plan distinct processes');pids.add(pid)
        interrupted=(path/'interrupted.stdout').read_text().splitlines()
        need(interrupted==['POINT '+cut for cut in CUTS[:index+1]]+['CUT '+point]
             and (path/'interrupted.stderr').read_bytes()==b'','learner plan original force trace')
        resumed=(path/'resumed.stdout').read_text().splitlines()
        if index>=4:
            points=(['LEARNER_RESEAL_PLAN_FORCED','LEARNER_RESEAL_PLAN_PARENT_FORCED','LEARNER_PLAN_RENAMED'] if index<9 else [])
            points+=['LEARNER_ACTIVE_PLAN_FORCED','LEARNER_ACTIVE_PLAN_PARENT_FORCED','LEARNER_PLAN_BEFORE_RETURN']
            need(resumed==['POINT '+p for p in points]+['PLAN '+e.digest(raw)] and (path/'resumed.stderr').read_bytes()==b'',
                 'learner plan original reseal trace')
        else:need(resumed==[] and (path/'resumed.stderr').stat().st_size>0,'learner plan incomplete refusal')
    return dict(status='PASS',scope='native-source-forced-plan',source=original_result,processCases=26,processes=len(pids),
                completedResumes=18,retainedIncompletePlans=8,liveLockRefusals=12,learnerStoreQualified=False,phase3Complete=False)


NEGATIVES={
 'extra-file':'learner plan case inventory',
 'missing-case':'learner plan case inventory',
 'changed-root':'learner plan exact native originals',
 'changed-source-inventory':'learner plan exact native originals',
 'changed-parent':'learner plan canonical original path',
 'changed-interruption':'learner plan exact interrupted bytes',
 'repaired-torn-plan':'learner plan exact recovered bytes',
 'missing-forced-plan':'learner plan exact recovered bytes',
 'false-process-success':'learner plan process result',
 'duplicate-process':'learner plan distinct processes',
 'missing-force':'learner plan original reseal trace',
 'invented-voter':'learner plan nonvoting inventory',
}


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-plan-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target)
            early=target/(CUTS[3]+'-halt');late=target/(CUTS[-1]+'-halt')
            if name=='extra-file':(target/'foreign').write_bytes(b'bad')
            elif name=='missing-case':shutil.rmtree(early)
            elif name in ('changed-root','changed-source-inventory','changed-parent'):
                p=target/'native-plan'/FILE;v=e.parse(p.read_bytes()[48:])
                if name=='changed-root':v['root']=base64.b64encode(b'wrong').decode()
                elif name=='changed-source-inventory':v['files'].pop()
                else:v['paths'][0]['parentRealPath']='/different'
                p.write_bytes(encode(v))
            elif name=='changed-interruption':(early/'interrupted'/NEXT).write_bytes(b'bad')
            elif name=='repaired-torn-plan':
                (early/'resumed'/NEXT).unlink();(early/'resumed'/FILE).write_bytes((early/'original.gslp').read_bytes())
            elif name=='missing-forced-plan':(late/'resumed'/FILE).unlink()
            elif name in ('false-process-success','duplicate-process'):
                p=target/'cases.json';rows=e.parse(p.read_bytes())
                if name=='false-process-success':rows[0]['resumed']=True
                else:rows[1]['pid']=rows[0]['pid']
                p.write_bytes(f.canonical(rows))
            elif name=='missing-force':
                p=late/'resumed.stdout';p.write_text('\n'.join(p.read_text().splitlines()[1:])+'\n')
            elif name=='invented-voter':(late/'resumed/promise.gsr').write_bytes(b'bad')
            else:raise ValueError('unknown learner plan negative')
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'learner plan unrelated negative: '+name+': '+str(error))
            else:raise ValueError('learner plan accepted negative: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root)))
