"""Replay partial-group seal recovery without resetting a live completed voter."""
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


def validate(root):
    root=Path(root);names={f'size-{n}-{s}' for n in (3,4,5) for s in ('empty','backup')}
    e.need(root.is_dir() and not root.is_symlink() and {v.name for v in root.iterdir()}==names|{'receipt.json'},'bootstrap progress case inventory');rows=[]
    for size in (3,4,5):
        for source in ('EMPTY','VERIFIED_DURABLE_BACKUP'):
            name=f"size-{size}-{'empty' if source=='EMPTY' else 'backup'}";case=root/name
            e.need(case.is_dir() and not case.is_symlink() and {v.name for v in case.iterdir()}=={'original-plan.gsbp','original-application.image','initial','before','second-crash','final','events.json','result.json'},'bootstrap progress case members')
            raw=p.read(case/'original-plan.gsbp',2*e.MIB);image=p.read(case/'original-application.image',64*e.MIB);data=t.derived(raw,image,size=size,source=source)
            admission=a.envelope(data['receipt'],data['rows'][2],data['rows'][3]);m=t.Model(raw,image,admission=admission,size=size,source=source,progress=True,typed=True)
            events=e.parse(p.read(case/'events.json',e.MIB));e.exact(events,'first second resumed store')
            e.need(events['first']==m.execute('BOOTSTRAP_SEAL_0_ACTIVE_PARENT_FORCED'),'bootstrap progress original force order')
            e.need(read_snapshot(case/'initial')==(m.files,m.dirs),'bootstrap progress exact initial authority')
            before,before_dirs=read_snapshot(case/'before');prefix='target-0/';payload=data['payloads'][0];root_hash=payload['root.gsr'][16:48].hex()
            parts=frames(before.get(prefix+'grants.gsr',b''));e.need(len(parts)==3 and parts[0]==payload['grants.gsr'],'bootstrap progress original fence')
            promise=e.f.decode(parts[1],'records','PROMISE');basis=e.f.decode(parts[2],'records','BASIS');initial=e.f.decode(parts[0],'records','PROMISE');node=e.f.decode(payload['node.gsr'],'records','NODE')['identity'];identifier=promise['basisId']
            e.need(str(uuid.UUID(identifier))==identifier,'bootstrap progress basis UUID');wanted=dict(initial,basisId=identifier,ballot=dict(counter=2,proposer=node['node'],incarnation=node['storage']))
            packet=e.p.decode(payload['generations/a/source.gscp']);cap=packet['capsule'];expected=dict(wanted,voter=node['node'],cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=cap['inventory'],accepted=None)
            e.need(promise==wanted and basis==expected,'bootstrap progress actual grant')
            m.files[prefix+'grants.gsr']=parts[0]+e.f.encode('records','PROMISE',wanted)+e.f.encode('records','BASIS',expected)
            allocator=lambda counter:e.f.encode('records','ALLOCATOR',dict(root=root_hash,node=node['node'],counter=counter))
            m.files[prefix+'allocator.gsr']=allocator(3);saved=prefix+'sources/'+identifier+'/';m.dirs.add(saved[:-1]);m.files[saved+'source.gscp']=payload['generations/a/source.gscp'];m.files[saved+cap['application']+'.image']=image
            m.dirs.add('target-1');m.files['target-1/derived-marker']=b'retained'
            e.need((before,before_dirs)==(m.files,m.dirs),'bootstrap progress exact running authority')
            e.need(events['second']==m.execute('BOOTSTRAP_SEAL_1_CANDIDATE_PREFIX_WRITTEN'),'bootstrap progress second force order')
            e.need(read_snapshot(case/'second-crash')==(m.files,m.dirs),'bootstrap progress exact second crash')
            e.need(events['resumed']==m.execute(),'bootstrap progress resumed force order');m.files[prefix+'allocator.gsr']=allocator(4)
            e.need(read_snapshot(case/'final')==(m.files,m.dirs),'bootstrap progress exact final authority')
            ordered=['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN','PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN']+['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN']*2
            e.need([v for v in events['store'] if v in set(ordered)]==ordered,'bootstrap progress live grant/counter order')
            record=e.f.decode(payload['root.gsr'],'records','ROOT');decoded=p.decode(raw,image,size=size,source=source,details=True)
            result=dict(root=root_hash,history=record['historyId'],plan=e.digest(raw),receipt=e.digest(data['receipt']),sequence=record['baseSequence'],operation=decoded['plan']['descriptor']['paths'][0]['path'])
            e.need(e.f.canonical(e.parse(p.read(case/'result.json',65536)))==e.f.canonical(result),'bootstrap progress exact original result')
            rows.append(dict(case=name,targets=size,status='PASS'))
    expected=dict(schema='gse-v53-bootstrap-progress-resume-v1',status='PASS',cases=rows,typedCoordinator=True,freshProcesses=False,publicRuntime=False)
    e.need(e.f.canonical(e.parse(p.read(root/'receipt.json',65536)))==e.f.canonical(expected),'bootstrap progress receipt scope')
    return dict(status='PASS',cases=6,targets=24,progressedVoters=6,originalFirst=True,typedCoordinator=True,freshProcesses=False,publicRuntime=False,independentTypedSemantics=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'missing-case':'bootstrap progress case inventory','original-plan':'bootstrap original plan checksum','original-image':'bootstrap original image binding',
              'initial-seal':'bootstrap progress exact initial authority','before-counter':'bootstrap progress exact running authority','before-grant':'bootstrap progress actual grant',
              'second-crash':'bootstrap progress exact second crash','final-reset':'bootstrap progress exact final authority','final-admission':'bootstrap progress exact final authority',
              'first-order':'bootstrap progress original force order','second-order':'bootstrap progress second force order','resumed-order':'bootstrap progress resumed force order',
              'store-order':'bootstrap progress live grant/counter order','result':'bootstrap progress exact original result','scope':'bootstrap progress receipt scope','linked-lock':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-bootstrap-progress-negative-') as temp:
            moved=Path(temp)/'raw';shutil.copytree(root,moved);case=moved/'size-3-backup'
            if name=='missing-case':shutil.rmtree(case)
            elif name=='original-plan':
                path=case/'original-plan.gsbp';raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='original-image':(case/'original-application.image').write_bytes(b'wrong')
            elif name=='initial-seal':(case/'initial/target-0'/t.SEAL).unlink()
            elif name=='before-counter':(case/'before/target-0/allocator.gsr').write_bytes((case/'initial/target-0/allocator.gsr').read_bytes())
            elif name=='before-grant':
                path=case/'before/target-0/grants.gsr';parts=frames(path.read_bytes());value=e.f.decode(parts[2],'records','BASIS');value['voter']='node-2';parts[2]=e.f.encode('records','BASIS',value);path.write_bytes(b''.join(parts))
            elif name=='second-crash':(case/'second-crash/target-2'/t.SEAL_PENDING).write_bytes(b'wrong')
            elif name=='final-reset':(case/'final/target-0/allocator.gsr').write_bytes((case/'initial/target-0/allocator.gsr').read_bytes())
            elif name=='final-admission':(case/'final/target-4/bootstrap-admission.gsbp').unlink()
            elif name.endswith('-order'):
                path=case/'events.json';value=e.parse(path.read_bytes());value[name[:-6]]=[];path.write_bytes(e.f.canonical(value))
            elif name=='result':
                path=case/'result.json';value=e.parse(path.read_bytes());value['sequence']=4;path.write_bytes(e.f.canonical(value))
            elif name=='scope':
                path=moved/'receipt.json';value=e.parse(path.read_bytes());value['freshProcesses']=True;path.write_bytes(e.f.canonical(value))
            else:
                path=case/'final/target-0/replica.lock';path.unlink();path.symlink_to((root/'size-3-backup/final/target-0/replica.lock').resolve())
            try:validate(moved)
            except ValueError as error:e.need(str(error)==reason,'bootstrap progress unexpected negative: '+name+': '+str(error))
            else:raise ValueError('bootstrap progress negative accepted: '+name)
            negatives.append(dict(case=name,reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-bootstrap-progress-portable-') as temp:
        moved=Path(temp)/'raw';shutil.copytree(root,moved);e.need(validate(moved)==result,'bootstrap progress portable mismatch')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
