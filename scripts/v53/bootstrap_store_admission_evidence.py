"""Original-first replay of admitted private initial-voter storage.

Original plan and application fix all bootstrap files. Actual post-open journals
are decoded independently; only fresh UUID basis identities are observational.
No typed decoder, remote force, power-loss or public readiness claim.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import bootstrap_plan_evidence as p, bootstrap_transaction_evidence as t
from . import bootstrap_admission_evidence as a, pending_context_evidence as e
from .ancestry_pruning_evidence import frames
from .journal_context_evidence import read_snapshot


def validate(root,*,with_result=False,public_bootstrap=False):
    e.need(not public_bootstrap or with_result,"public bootstrap requires original result")
    root=Path(root);names={f'size-{n}-{s}' for n in (3,4,5) for s in ('empty','backup')}
    e.need(root.is_dir() and not root.is_symlink() and {v.name for v in root.iterdir()}==names|{'receipt.json'},'bootstrap store case inventory')
    rows=[];targets=0
    for size in (3,4,5):
        for source in ('EMPTY','VERIFIED_DURABLE_BACKUP'):
            name=f"size-{size}-{'empty' if source=='EMPTY' else 'backup'}";case=root/name
            e.need(case.is_dir() and not case.is_symlink() and {v.name for v in case.iterdir()}=={'original-plan.gsbp','original-application.image','initial','final','calls.json'}|({'result.json'} if with_result else set()),'bootstrap store case members')
            raw=p.read(case/'original-plan.gsbp',2*e.MIB);image=p.read(case/'original-application.image',64*e.MIB);data=t.derived(raw,image,size=size,source=source)
            admission=a.envelope(data['receipt'],data['rows'][2],data['rows'][3]);targets+=size
            files={'operation/operation.lock':b'','operation/plan.gsbp':raw,'operation/application.image':image,'operation/'+t.JOURNAL:b''.join(data['rows']),'operation/'+t.RECEIPT:data['receipt']};dirs={'operation'}
            for i,payload in enumerate(data['payloads']):
                prefix=f'target-{2*i}/';files.update({prefix+k:v for k,v in payload.items()});files[prefix+t.PREPARED]=data['preps'][i];files[prefix+t.SEAL]=data['seals'][i];files[prefix+'bootstrap-admission.gsbp']=admission
                dirs.update({prefix[:-1],prefix+'generations',prefix+'generations/a',prefix+'sources'})
            e.need(read_snapshot(case/'initial')==(files,dirs),'bootstrap store original admitted authority')
            final,final_dirs=read_snapshot(case/'final');calls=e.parse(p.read(case/'calls.json',e.MIB))
            e.need(type(calls) is list and len(calls)==size,'bootstrap store call inventory')
            for i,payload in enumerate(data['payloads']):
                prefix=f'target-{2*i}/';node=f'node-{i+1}';root_hash=payload['root.gsr'][16:48].hex();node_record=e.f.decode(payload['node.gsr'],'records','NODE')
                parts=frames(final.get(prefix+'grants.gsr',b''));e.need(len(parts)==3 and parts[0]==payload['grants.gsr'],'bootstrap store original fence retained')
                promise=e.f.decode(parts[1],'records','PROMISE');basis=e.f.decode(parts[2],'records','BASIS');original=e.f.decode(parts[0],'records','PROMISE')
                identifier=promise['basisId'];e.need(str(uuid.UUID(identifier))==identifier,'bootstrap store basis UUID')
                ballot=dict(counter=2,proposer=node,incarnation=node_record['identity']['storage'])
                wanted=dict(root=root_hash,view=original['view'],ballot=ballot,basisId=identifier)
                e.need(promise==wanted,'bootstrap store actual grant context')
                packet=e.p.decode(payload['generations/a/source.gscp']);cap=packet['capsule']
                expected=dict(wanted,voter=node,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=cap['inventory'],accepted=None)
                e.need(basis==expected,'bootstrap store actual frozen basis')
                files[prefix+'grants.gsr']=parts[0]+e.f.encode('records','PROMISE',wanted)+e.f.encode('records','BASIS',expected)
                files[prefix+'allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(root=root_hash,node=node,counter=3))
                saved=prefix+'sources/'+identifier+'/';dirs.add(saved[:-1]);files[saved+'source.gscp']=payload['generations/a/source.gscp'];files[saved+cap['application']+'.image']=image
                core=f'target-{2*i+1}';dirs.add(core);files[core+'/derived-marker']=b'retained'
                call=calls[i];e.exact(call,'node basis events leasesAfterClose')
                e.need(call['node']==node and call['basis']==e.digest(parts[2]) and type(call['leasesAfterClose']) is int and call['leasesAfterClose']==0,'bootstrap store original call/lease binding')
                events=call['events'];e.need(type(events) is list and all(type(v) is str for v in events),'bootstrap store event shape')
                # Required file force/return order, without interpreting other cuts as extra authority.
                wanted_events=['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN','PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN','ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN']
                selected=[v for v in events if v in set(wanted_events)]
                e.need(selected==wanted_events,'bootstrap store grant force order')
            e.need((final,final_dirs)==(files,dirs),'bootstrap store exact progressed authority')
            if with_result:
                record=e.f.decode(data['payloads'][0]['root.gsr'],'records','ROOT');wanted_result=dict(root=data['payloads'][0]['root.gsr'][16:48].hex(),history=record['historyId'],plan=e.digest(raw),receipt=e.digest(data['receipt']),sequence=record['baseSequence'],operation=p.decode(raw,image,size=size,source=source,details=True)['plan']['descriptor']['paths'][0]['path'])
                e.need(e.f.canonical(e.parse(p.read(case/'result.json',65536)))==e.f.canonical(wanted_result),'bootstrap result exact original result')
            rows.append(dict(case=name,targets=size,status='PASS'))
    wanted=dict(schema='gse-v53-bootstrap-public-v1' if public_bootstrap else 'gse-v53-bootstrap-result-reader-v1' if with_result else 'gse-v53-bootstrap-store-admission-v1',status='PASS',cases=rows,typedCoordinator=with_result,publicRuntime=False)
    if public_bootstrap:wanted['publicBootstrap']=True
    e.need(e.f.canonical(e.parse(p.read(root/'receipt.json',65536)))==e.f.canonical(wanted),'bootstrap store receipt scope')
    result=dict(status='PASS',cases=6,initialVoters=targets,originalFirst=True,typedCoordinator=with_result,publicRuntime=False,independentTypedImageSemantics=False)
    if public_bootstrap:result['publicBootstrap']=True
    return result


def qualify(root,*,with_result=False,public_bootstrap=False):
    root=Path(root);result=validate(root,with_result=with_result,public_bootstrap=public_bootstrap);negatives=[]
    variants={'missing-case':'bootstrap store case inventory','original-plan':'bootstrap original plan checksum','original-image':'bootstrap original image binding',
              'initial-admission':'bootstrap store original admitted authority','final-admission':'bootstrap store exact progressed authority',
              'counter-reset':'bootstrap store exact progressed authority','missing-source':'bootstrap store exact progressed authority','core-reset':'bootstrap store exact progressed authority',
              'lost-fence':'bootstrap store original fence retained','basis-context':'bootstrap store actual frozen basis','grant-context':'bootstrap store actual grant context',
              'force-order':'bootstrap store grant force order','leases':'bootstrap store original call/lease binding','scope':'bootstrap store receipt scope',
              'linked-seal':'owner context linked/nonregular member'}
    if with_result:variants['result-counter']='bootstrap result exact original result';variants['result-receipt']='bootstrap result exact original result'
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-store-admission-negative-') as temp:
            moved=Path(temp)/'raw';shutil.copytree(root,moved);case=moved/'size-3-backup';node=case/'final/target-0'
            if name in ('result-counter','result-receipt'):
                path=case/'result.json';value=e.parse(path.read_bytes());value['sequence' if name=='result-counter' else 'receipt']=3 if name=='result-counter' else '0'*64;path.write_bytes(e.f.canonical(value))
            elif name=='missing-case':shutil.rmtree(case)
            elif name=='original-plan':
                path=case/'original-plan.gsbp';raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='original-image':(case/'original-application.image').write_bytes(b'wrong')
            elif name=='initial-admission':(case/'initial/target-0/bootstrap-admission.gsbp').unlink()
            elif name=='final-admission':(node/'bootstrap-admission.gsbp').unlink()
            elif name=='counter-reset':(node/'allocator.gsr').write_bytes((case/'initial/target-0/allocator.gsr').read_bytes())
            elif name=='missing-source':next((node/'sources').rglob('*.image')).unlink()
            elif name=='core-reset':(case/'final/target-1/derived-marker').unlink()
            elif name in ('lost-fence','basis-context','grant-context'):
                path=node/'grants.gsr';parts=frames(path.read_bytes())
                if name=='lost-fence':parts=parts[1:]
                else:
                    index=2 if name=='basis-context' else 1;kind='BASIS' if index==2 else 'PROMISE';value=e.f.decode(parts[index],'records',kind)
                    if index==2:value['voter']='node-2'
                    else:value['ballot']['counter']=3
                    parts[index]=e.f.encode('records',kind,value)
                path.write_bytes(b''.join(parts))
            elif name in ('force-order','leases'):
                path=case/'calls.json';value=e.parse(path.read_bytes())
                if name=='force-order':value[0]['events'].remove('PROMISE_FORCED')
                else:value[0]['leasesAfterClose']=1
                path.write_bytes(e.f.canonical(value))
            elif name=='linked-seal':
                path=node/t.SEAL;path.unlink();path.symlink_to((root/'size-3-backup/final/target-0'/t.SEAL).resolve())
            else:
                path=moved/'receipt.json';value=e.parse(path.read_bytes());value['publicRuntime']=True;path.write_bytes(e.f.canonical(value))
            try:validate(moved,with_result=with_result,public_bootstrap=public_bootstrap)
            except ValueError as error:e.need(str(error)==reason,'bootstrap store unexpected negative: '+name+': '+str(error))
            else:raise ValueError('bootstrap store negative accepted: '+name)
            negatives.append(dict(case=name,reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-store-admission-portable-') as temp:
        moved=Path(temp)/'raw';shutil.copytree(root,moved);e.need(validate(moved,with_result=with_result,public_bootstrap=public_bootstrap)==result,'bootstrap store portable mismatch')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
