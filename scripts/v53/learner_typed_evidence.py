"""Original native PREPARE, retained image, typed-owner trace and READY replay.

The Java core checks codec semantics; this reader independently checks original
physical history, bytes, receipt binding and force order, never recorded paths.
This focused history does not qualify process death or autonomous membership.
"""
import argparse
import base64
import copy
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from . import learner_store_evidence as s
from . import bootstrap_revalidation_evidence as images

source,e,f,need=s.source,s.e,s.f,s.need
b,c,d,a=source.b,source.c,source.d,source.r.a
VOTERS=('node-1','node-2')


def trace(resume):
    def write(prefix):
        return [prefix+n for n in (('_FORCED','_PARENT_FORCED') if resume else
                                  ('_CREATED','_PREFIX_WRITTEN','_WRITTEN','_FORCED','_PARENT_FORCED'))]
    prefix='LEARNER_TYPED_'
    result=[] if resume else [prefix+'DIRECTORY_FORCED']+write(prefix+'PLAN')+[
        prefix+'CANDIDATE_FORCED',prefix+'CANDIDATE_FORCED_PARENT',prefix+'PLAN_RENAMED']
    result += [prefix+'ACTIVE_FORCED',prefix+'ACTIVE_FORCED_PARENT']
    if not resume:result += [prefix+'BACKUP_CREATED']
    result += write(prefix+'MEMBER')*3+[prefix+'BACKUP_FORCED',prefix+'SEMANTICS_VERIFIED']
    return result+write(prefix+'RECEIPT')+[prefix+'BEFORE_RETURN']


def check_trace(rows,resume):
    need(type(rows) is list and all(type(v) is str for v in rows),'learner typed force events')
    need([v for v in rows if v.startswith('LEARNER_TYPED_')]==trace(resume),'learner typed exact force order')


def physical(root):
    group=d.s.initialize(b.original(root,3,False))
    group={n:dict(v,**{d.future.FILE:d.future.frame(d.future.initial(v),{})}) for n,v in group.items()}
    b.match(root,'before-network',group)
    _,_,installed=d.s.campaign(root,{n:group[n] for n in VOTERS},2,'installed',selected_prefix=d.slot.prefix)
    group=dict(group,**installed);b.match(root,'installed',group)
    need((root/'selected.gsr').read_bytes()==c.current(group['node-1'])[1]['selected.gsr'],'learner typed original selection')
    model=a.NativeSlot.__new__(a.NativeSlot)
    model.root=root;model.group=group;model.active=list(VOTERS);model.voters=VOTERS
    model.required=set();model.slot=0;model.counter=2;model.first=None;model.observed=set();model.phases={};model.documents=[]
    model.history=f.decode(group['node-1']['root.gsr'],'records','ROOT')['historyId']
    supplied=e.parse((root/'learner-reserve-payload.bin').read_bytes());request=supplied['request']
    need(set(supplied)=={'request'} and request['kind']=='ADD' and request['number']==1 and len(request['target'])==4,
         'learner typed native request')
    learner=next(v for v in request['target'] if v['node']=='node-4')
    for kind,command in [('BARRIER',None),('RESERVE',supplied),('PREPARE',dict(number=1,revision=1))]:
        model.group=a.maintenance(model.group,VOTERS);model.publish(kind,command)
    b.match(root,'before-learner-source',model.group);b.match(root,'after-learner-source',model.group)
    prepared=copy.deepcopy(model.group);packet=c.current(prepared['node-1'])[2]
    catalog=f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG');operation=catalog['results'][0]
    need(catalog['active']==1 and operation['phase']=='PREPARING' and operation['revision']==1 and operation['request']==request,
         'learner typed native preparation')
    receipt=dict(root=request['root'],number=1,request=e.digest(f.canonical(request)),identity=learner,
                 image=operation['prepared']['application'],prepared=operation['prepared'])
    raw=f.encode('records','LEARNER',dict(root=request['root'],receipt=receipt))
    need((root/'learner-receipt.gsr').read_bytes()==raw,'learner typed exact receipt')
    ready=dict(number=1,receipt=receipt)
    need((root/'learner-ready-payload.bin').read_bytes()==f.canonical(ready),'learner typed ready uses original receipt')
    for kind,command in [('READY',ready),('CANCEL',dict(number=1))]:
        model.group=a.maintenance(model.group,VOTERS);model.publish(kind,command)
    b.match(root,'after-close',model.group)
    return prepared,request,learner,raw


def binding(value):
    need(type(value) is dict and set(value)=={'path','parentRealPath','fileStoreName','fileStoreType','parentFileKey'}
         and all(type(v) is str and v.strip() and len(v.encode())<=4096 for v in value.values()),'learner typed binding fields')
    path=PurePosixPath(value['path'])
    need(path.is_absolute() and str(path)==value['path'] and '..' not in path.parts and str(path.parent)==value['parentRealPath'],
         'learner typed canonical path')
    return path


def sidecar(root,typed,plan,original,request,receipt,raw,*,selected=False):
    prepared_receipt=f.decode(receipt,'records','LEARNER')['receipt']
    image=original[prepared_receipt['image']+'.image'];backup=images.image_members(image)
    need(set(typed)==({'preparation.lock','preparation.json','learner.gsr','backup'}|({'prepared.json'} if selected else set()))|{'backup/'+n for n in backup},'learner typed sidecar inventory')
    need(typed['backup'] is None and typed['preparation.lock']==b'' and typed['learner.gsr']==receipt and
         all(typed['backup/'+n]==data for n,data in backup.items()),'learner typed original backup and receipt')
    metadata=typed['preparation.json'];need(len(metadata)<=256*1024,'learner typed plan capacity')
    value=e.parse(metadata);descriptor=e.parse((root/'original-plan.gsbp').read_bytes()[48:])['descriptor']
    need(f.canonical(value)==metadata and set(value)=={'schema','plan','source','receipt','configuration','path','materialization','directoryKey'},
         'learner typed plan shape')
    need(value['schema']=='gse-v53-learner-typed/1.3' and value['plan']==e.digest(raw) and value['source']==e.digest(original['source.gscp'])
         and value['receipt']==base64.b64encode(receipt).decode() and value['configuration']=={k:descriptor[k] for k in ('application','core')},
         'learner typed plan originals')
    path=binding(value['path']);core=binding(value['materialization']);paths=[binding(v) for v in plan['paths']]
    operation_path=next(p for p in paths if p.name=='learner-operation')
    need(path==operation_path.parent/('.gse-v53-learner-'+e.digest(raw)),'learner typed deterministic sidecar')
    paths += [path,core]
    need(all(p!=q and p not in q.parents and q not in p.parents for i,p in enumerate(paths) for q in paths[i+1:]),'learner typed disjoint paths')
    need(type(value['directoryKey']) is str and value['directoryKey'].strip(),'learner typed original directory identity')
    if selected:
        replica_path=next(p for p in paths if p.name=='learner-replica')
        marker=dict(schema='gse-v53-learner-prepared/1.3',root=request['root'],identity=prepared_receipt['identity'],
                    plan=e.digest(raw),typedPlan=e.digest(metadata),source=e.digest(original['source.gscp']),
                    receipt=e.digest(receipt),location=str(replica_path/'learner'))
        need(typed['prepared.json']==f.canonical(marker) and len(typed['prepared.json'])<=16384,'learner prepared original selection')


def validate(root):
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'learner typed evidence directory');total=0
    for count,p in enumerate(root.rglob('*'),1):
        need(not p.is_symlink() and (p.is_file() or p.is_dir()),'learner typed regular evidence')
        if p.is_file():
            size=p.stat().st_size;need(size<=64*e.MIB,'learner typed file capacity');total+=size
        need(count<=65536 and total<=512*e.MIB,'learner typed evidence capacity')
    names={'initial','original-plan.gsbp','original-application.image','before-network','installed','selected.gsr','after-close',
           'calls.json','events.json','wire.json','failures.json','before-learner-source','after-learner-source',
           'learner-reserve-payload.bin','learner-source-copy','learner-source-wire.json','learner-receipt.gsr','learner-ready-payload.bin',
           'learner-plan.gslp','admitted','typed','typed-resumed','learner-typed-events.json','learner-resume-events.json','learner-typed-result.json'}
    names|={f'{stage}-{i}' for stage in ('applied','published') for i in range(1,6)}
    b.selection.layout(root,names,'learner typed')
    prepared,request,learner,receipt=physical(root);network=source.network(root,prepared,request,learner)
    original=c.inventory(root/'learner-source-copy');root_bytes=prepared['node-1']['root.gsr']
    raw=(root/'learner-plan.gslp').read_bytes();peer=next(v for v in request['target'] if v['node']=='node-1')
    plan=s.p.plan(raw,root_bytes,original,request,learner,peer)
    retained=(root/'admitted/operation'/s.RETAIN).read_bytes();decision=s.retention(retained,raw,plan)
    operation={'operation.lock':b'','learner.gslp':raw,s.RETAIN:retained}
    replica={'replica.lock':b'','root.gsr':root_bytes,'node.gsr':f.encode('records','NODE',dict(root=request['root'],identity=learner)),s.ADMISSION:retained}
    s.state(root/'admitted',operation,replica,original,decision,'retained')
    typed=c.inventory(root/'typed');need(typed==c.inventory(root/'typed-resumed'),'learner typed exact reopen bytes')
    sidecar(root,typed,plan,original,request,receipt,raw)
    check_trace(d.read(root/'learner-typed-events.json'),False);check_trace(d.read(root/'learner-resume-events.json'),True)
    need(d.read(root/'learner-typed-result.json')==dict(status='PASS',scope='native-typed-learner',voter=False,liveCore=False,publicReady=False,phase3Complete=False,testBudgetSeconds=600),
         'learner typed result scope')
    return dict(status='PASS',scope='native-typed-learner',network=network,physicalQualification=True,
                semanticReader='Java core',processDeathQualified=False,autonomous=False,phase3Complete=False)


NEGATIVES={'receipt':'learner typed exact receipt','ready':'learner typed ready uses original receipt',
           'prepared-selector':'admitted exact before-learner-source: node-1','reopened':'learner typed exact reopen bytes',
           'backup':'learner typed original backup and receipt','descriptor':'learner typed plan originals',
           'missing-force':'learner typed exact force order','early-receipt':'learner typed exact force order',
           'false-ready':'learner typed result scope'}


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-typed-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            if name=='receipt':(path/'learner-receipt.gsr').write_bytes(b'bad')
            elif name=='ready':(path/'learner-ready-payload.bin').write_bytes(b'bad')
            elif name=='prepared-selector':(path/'before-learner-source/node-1/selector.gsr').write_bytes(b'bad')
            elif name=='reopened':(path/'typed-resumed/learner.gsr').write_bytes(b'bad')
            elif name=='backup':
                for stage in ('typed','typed-resumed'):(path/stage/'backup/gse-backup-checkpoint').write_bytes(b'bad')
            elif name=='descriptor':
                value=d.read(path/'typed/preparation.json');value['configuration']['core']['storageIdentity']='different'
                for stage in ('typed','typed-resumed'):(path/stage/'preparation.json').write_bytes(f.canonical(value))
            elif name in ('missing-force','early-receipt'):
                p=path/'learner-typed-events.json';rows=d.read(p)
                if name=='missing-force':rows.remove('LEARNER_TYPED_RECEIPT_FORCED')
                else:
                    rows.remove('LEARNER_TYPED_RECEIPT_CREATED');rows.insert(rows.index('LEARNER_TYPED_SEMANTICS_VERIFIED'),'LEARNER_TYPED_RECEIPT_CREATED')
                p.write_bytes(f.canonical(rows))
            else:
                p=path/'learner-typed-result.json';value=d.read(p);value['publicReady']=True;p.write_bytes(f.canonical(value))
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'learner typed unrelated negative: '+name+': '+str(error))
            else:raise ValueError('learner typed accepted negative: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root)))
