"""Exact offline plan bytes and interrupted persistence, without committed bootstrap claims."""
import argparse
import base64
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import tempfile
from . import pending_context_evidence as e
from .journal_context_evidence import read_snapshot
from .generation_install_evidence import packet_bytes

CUTS=('BOOTSTRAP_OPERATION_CREATED','BOOTSTRAP_OPERATION_LOCKED',
      'BOOTSTRAP_IMAGE_CREATED','BOOTSTRAP_IMAGE_PREFIX_WRITTEN','BOOTSTRAP_IMAGE_WRITTEN','BOOTSTRAP_IMAGE_FORCED','BOOTSTRAP_IMAGE_PARENT_FORCED',
      'BOOTSTRAP_PLAN_CREATED','BOOTSTRAP_PLAN_PREFIX_WRITTEN','BOOTSTRAP_PLAN_WRITTEN','BOOTSTRAP_PLAN_FORCED','BOOTSTRAP_PLAN_PARENT_FORCED',
      'BOOTSTRAP_RESEAL_IMAGE_FORCED','BOOTSTRAP_RESEAL_IMAGE_PARENT_FORCED','BOOTSTRAP_RESEAL_PLAN_FORCED','BOOTSTRAP_RESEAL_PLAN_PARENT_FORCED',
      'BOOTSTRAP_PLAN_RENAMED','BOOTSTRAP_ACTIVE_PLAN_FORCED','BOOTSTRAP_ACTIVE_PLAN_PARENT_FORCED','BOOTSTRAP_PLAN_BEFORE_RETURN')


def read(path,maximum):
    e.need(path.is_file() and not path.is_symlink() and path.stat().st_size<=maximum,'bootstrap plan evidence file type/capacity')
    raw=path.read_bytes();e.need(len(raw)<=maximum,'bootstrap plan evidence grew');return raw


def decode(raw,image,*,details=False,size=3,source="EMPTY"):
    e.need(48<len(raw)<=2*e.MIB,'bootstrap original plan capacity')
    e.need(struct.unpack('>4sHHHHI',raw[:16])==(b'GSBP',1,3,1,0,len(raw)-48),'bootstrap original plan header')
    e.need(bytes.fromhex(e.digest(raw[:16]+raw[48:]))==raw[16:48],'bootstrap original plan checksum')
    value=e.parse(raw[48:]);e.need(e.f.canonical(value)==raw[48:],'bootstrap original canonical plan')
    e.exact(value,'schema root genesis application descriptor maximumSource maximumOperation targets')
    e.need(value['schema']=='gse-v53-bootstrap-plan/1.3','bootstrap plan schema')
    e.need(value['application']==e.info(image),'bootstrap original image binding')
    def frame(field,kind,maximum):
        e.need(type(value[field]) is str and len(value[field])<=4*((maximum+2)//3),'bootstrap encoded original capacity')
        data=base64.b64decode(value[field],validate=True)
        e.need(base64.b64encode(data).decode()==value[field] and len(data)<=maximum,'bootstrap original frame encoding')
        return data,e.f.decode(data,'records',kind)
    root_raw,root=frame('root','ROOT',16384);genesis_raw,genesis=frame('genesis','GENESIS',65536);root_hash=root_raw[16:48].hex()
    desc=value['descriptor'];e.exact(desc,'application core identities paths source sourceInventory')
    e.need(type(size) is int and size in (3,4,5) and source in ('EMPTY','VERIFIED_DURABLE_BACKUP'), 'bootstrap plan declared profile')
    e.need(genesis['source']==source and desc['source']==source, 'bootstrap plan source profile')
    if source=='EMPTY':
        e.need(genesis['sourceDigest'] is None and genesis['baseSequence']==0 and desc['sourceInventory']==[], 'bootstrap plan tested empty profile')
    else:
        inventory=desc['sourceInventory']
        e.need(type(inventory) is list and len(inventory)==3, 'bootstrap plan source inventory')
        for row,name in zip(inventory,('gse-backup-checkpoint','gse-backup-manifest','gse-backup-metadata')):
            e.exact(row,'path kind size sha256')
            e.need(row['path']==name and type(row['kind']) is int and row['kind']==1 and type(row['size']) is int and row['size']>0,
                   'bootstrap plan source inventory')
            e.need(type(row['sha256']) is str and len(row['sha256'])==64 and all(c in '0123456789abcdef' for c in row['sha256']), 'bootstrap plan source digest')
        e.need(genesis['sourceDigest']==e.digest(e.f.canonical(inventory)), 'bootstrap plan source inventory binding')
    e.need(root['genesis']==e.digest(genesis_raw) and all(root[k]==genesis[k] for k in ('groupId','historyId','baseSequence','schema','indexes'))
           and genesis['application']==e.digest(image),'bootstrap plan original root/genesis')
    registry=e.identities(root['initial']);e.need(len(registry)==size and desc['identities']==root['initial'],'bootstrap plan initial identities')
    e.need(root['schema']==e.digest(e.f.canonical(dict(schemaIdentity=desc['core']['schemaIdentity'],application=desc['application'])))
           and root['indexes']==e.digest(e.f.canonical(desc['application']['indexes'])) and root['codecId']==desc['core']['codecId']
           and root['codecVersion']==desc['core']['codecVersion'] and root['limits']==e.digest(e.f.canonical(e.f.catalog()['resources'])),'bootstrap plan configuration binding')
    paths=desc['paths'];e.need(type(paths) is list and len(paths)==1+2*size+(source!='EMPTY'),'bootstrap plan bound path count');names=[]
    for bound in paths:
        e.exact(bound,'path parentRealPath fileStoreName fileStoreType parentFileKey')
        e.need(all(type(v) is str and 0<len(v.encode())<=4096 for v in bound.values()),'bootstrap plan path binding fields')
        p=PurePosixPath(bound['path']);e.need(p.is_absolute() and str(p)==bound['path'] and '..' not in p.parts and str(p.parent)==bound['parentRealPath'],'bootstrap plan canonical path')
        e.need(all(p!=q and p not in q.parents and q not in p.parents for q in names),'bootstrap plan disjoint paths');names.append(p)
    view=dict(generation=0,old=list(registry),new=list(registry),operation=None);cut=dict(entry=root['genesis'],index=0,view=view)
    cat=dict(root=root_hash,application=genesis['application'],applicationSequence=genesis['baseSequence'],cut=cut,identities=root['initial'],active=None,lastDataIndex=0,nextOperation=1,results=[],retiredThrough=0)
    catalog_raw=e.f.encode('records','CATALOG',cat);objects={e.digest(root_raw):root_raw,root['genesis']:genesis_raw,e.digest(catalog_raw):catalog_raw}
    packet=packet_bytes(dict(root=root_hash,application=genesis['application'],catalog=e.digest(catalog_raw),cut=cut,initial=root['genesis'],items=[]),objects,{e.digest(image):len(image)})
    cap=e.p.decode(packet);targets=[];payloads=[];total=0
    for node,identity in registry.items():
        promise=e.f.encode('records','PROMISE',dict(root=root_hash,view=e.authority(root_hash,view),basisId=None,ballot=dict(counter=1,proposer=node,incarnation=identity['storage'])))
        generation={'source.gscp':packet,'promise.gsr':promise,e.digest(image)+'.image':image}
        manifest=e.f.encode('records','GENERATION',dict(root=root_hash,node=node,generation='a',cut=cut,application=e.digest(image),catalog=e.digest(catalog_raw),capsule=e.digest(cap['capsuleBytes']),
            promise=e.digest(promise),basis=None,selection=None,ownedTail=None,files=[dict(path=k,size=len(v),sha256=e.digest(v)) for k,v in sorted(generation.items())]))
        files={'generations/a/'+k:v for k,v in generation.items()};files.update({'generations/a/generation.gsr':manifest,'root.gsr':root_raw,'genesis.gsr':genesis_raw,'replica.lock':b'',
            'node.gsr':e.f.encode('records','NODE',dict(root=root_hash,identity=identity)),
            'allocator.gsr':e.f.encode('records','ALLOCATOR',dict(root=root_hash,node=node,counter=1)),
            'grants.gsr':promise,'pending.accept':struct.pack('>4sHHI',b'GSPV',1,3,12),
            'selector.gsr':e.f.encode('records','SELECTOR',dict(root=root_hash,node=node,generation='a',digest=e.digest(manifest)))})
        payloads.append(files)
        targets.append(dict(identity=identity,directories=['generations','generations/a','sources'],files=[dict(path=k,bytes=len(v),sha256=e.digest(v)) for k,v in sorted(files.items())]));total+=sum(map(len,files.values()))
    e.need(e.f.canonical(value['targets'])==e.f.canonical(targets),'bootstrap plan derived target inventories')
    e.need(type(value['maximumSource']) is int and value['maximumSource']>0 and type(value['maximumOperation']) is int
           and total+len(image)+2*len(raw)<=value['maximumOperation'],'bootstrap plan complete byte budget')
    if details:return dict(plan=value,root=root,rootHash=root_hash,genesis=genesis,payloads=payloads)
    return root['historyId']


def validate(root):
    root=Path(root);e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}==set(CUTS)|{'receipt.json'},'bootstrap plan case inventory');rows=[]
    for at,cut in enumerate(CUTS):
        path=root/cut;complete=at>=9;e.need(path.is_dir() and not path.is_symlink(),'bootstrap plan case type')
        e.need({p.name for p in path.iterdir()}=={'crash','final','events.json','original-plan.gsbp','original-application.image'}|({'second-crash'} if complete else set()),'bootstrap plan case members')
        raw=read(path/'original-plan.gsbp',2*e.MIB);image=read(path/'original-application.image',64*e.MIB);history=decode(raw,image)
        expected={}
        if at>=1:expected['operation.lock']=b''
        if at>=2:expected['application.image']=b'' if at==2 else image[:len(image)//2] if at==3 else image
        if at>=7:expected['plan.next.gsbp']=b'' if at==7 else raw[:len(raw)//2] if at==8 else raw
        if at>=16:expected['plan.gsbp']=expected.pop('plan.next.gsbp')
        e.need(read_snapshot(path/'crash')==(expected,set()),'bootstrap exact interrupted bytes')
        if complete:e.need(read_snapshot(path/'second-crash')==(expected,set()),'bootstrap second recovery changed bytes')
        final={'operation.lock':b'','application.image':image,'plan.gsbp':raw} if complete else expected
        e.need(read_snapshot(path/'final')==(final,set()),'bootstrap exact final/refused bytes')
        events=e.parse(read(path/'events.json',65536));e.exact(events,'first recovery resume')
        e.need(events['first']==list(CUTS[:at+1]),'bootstrap creation force order')
        expected_resume=list(CUTS[12:]) if at<16 else [CUTS[i] for i in (12,13,17,18,19)]
        e.need(events['recovery']==[CUTS[12]] if complete else events['recovery']==[],'bootstrap second recovery force order')
        e.need(events['resume']==expected_resume if complete else events['resume']==[],'bootstrap exact reseal force order')
        rows.append(dict(cut=cut,recovery='EXACT_PLAN_RESEALED' if complete else 'INCOMPLETE_AUTHORITY_REFUSED',history=history,plan=e.digest(raw),status='PASS'))
    expected=dict(schema='gse-v53-bootstrap-plan-files-v1',status='PASS',cases=rows,offlineCommit=False,freshProcesses=False)
    e.need(e.f.canonical(e.parse(read(root/'receipt.json',65536)))==e.f.canonical(expected),'bootstrap plan receipt scope')
    return dict(status='PASS',cases=20,incompleteRefusals=9,exactPlanRecoveries=11,originalFirst=True,freshProcesses=False,offlineCommit=False,imageSemanticsIndependentlyVerified=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'missing-case':'bootstrap plan case inventory','changed-original':'bootstrap original plan checksum','changed-image':'bootstrap original image binding',
        'changed-crash':'bootstrap exact interrupted bytes','changed-second':'bootstrap second recovery changed bytes','changed-final':'bootstrap exact final/refused bytes',
        'repaired-incomplete':'bootstrap exact final/refused bytes','force-order':'bootstrap creation force order','recovery-order':'bootstrap second recovery force order',
        'false-commit':'bootstrap plan receipt scope','linked-plan':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-plan-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/CUTS[9]
            if name=='missing-case':shutil.rmtree(case)
            elif name=='changed-original':
                p=case/'original-plan.gsbp';raw=p.read_bytes();p.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='changed-image':(case/'original-application.image').write_bytes(b'changed')
            elif name in ('changed-crash','changed-second','changed-final'):
                stage={'changed-crash':'crash','changed-second':'second-crash','changed-final':'final'}[name];(case/stage/'application.image').write_bytes(b'changed')
            elif name=='repaired-incomplete':(moved/CUTS[8]/'final/plan.next.gsbp').write_bytes((moved/CUTS[8]/'original-plan.gsbp').read_bytes())
            elif name in ('force-order','recovery-order'):
                p=case/'events.json';v=e.parse(p.read_bytes());v['first' if name=='force-order' else 'recovery']=[];p.write_bytes(e.f.canonical(v))
            elif name=='false-commit':
                p=moved/'receipt.json';v=e.parse(p.read_bytes());v['offlineCommit']=True;p.write_bytes(e.f.canonical(v))
            else:
                p=case/'final/plan.gsbp';p.unlink();p.symlink_to((root/CUTS[9]/'original-plan.gsbp').resolve())
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong bootstrap plan negative reason: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted bootstrap plan mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-plan-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'bootstrap plan portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
