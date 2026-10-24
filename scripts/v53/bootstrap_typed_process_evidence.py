"""Exact typed-coordinator process-death replay, including live completed voters."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import bootstrap_transaction_evidence as t, bootstrap_plan_evidence as p
from . import bootstrap_admission_evidence as a, pending_context_evidence as e
from .bootstrap_admission_process_evidence import trace
from .ancestry_pruning_evidence import frames
from .journal_context_evidence import read_snapshot

CUTS=('BOOTSTRAP_TYPED_RECHECKED','BOOTSTRAP_PREPARED_DURABLE','BOOTSTRAP_COMMITTING_DURABLE',
      'BOOTSTRAP_ADMISSION_0_FORCED','BOOTSTRAP_SEAL_0_ACTIVE_PARENT_FORCED','BOOTSTRAP_COMMITTED_BEFORE_RETURN')


def progress(model,before):
    payload=model.data['payloads'][0];prefix='target-0/';root=payload['root.gsr'][16:48].hex();node=e.f.decode(payload['node.gsr'],'records','NODE')['identity']
    parts=frames(before.get(prefix+'grants.gsr',b''));e.need(len(parts)==3 and parts[0]==payload['grants.gsr'],'bootstrap typed original fence')
    promise=e.f.decode(parts[1],'records','PROMISE');basis=e.f.decode(parts[2],'records','BASIS');initial=e.f.decode(parts[0],'records','PROMISE');identifier=promise['basisId']
    e.need(str(uuid.UUID(identifier))==identifier,'bootstrap typed basis UUID');wanted=dict(initial,basisId=identifier,ballot=dict(counter=2,proposer=node['node'],incarnation=node['storage']))
    packet=e.p.decode(payload['generations/a/source.gscp']);cap=packet['capsule'];expected=dict(wanted,voter=node['node'],cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=cap['inventory'],accepted=None)
    e.need(promise==wanted and basis==expected,'bootstrap typed actual running grant')
    model.files[prefix+'grants.gsr']=parts[0]+e.f.encode('records','PROMISE',wanted)+e.f.encode('records','BASIS',expected)
    saved=prefix+'sources/'+identifier+'/';model.dirs.add(saved[:-1]);model.files[saved+'source.gscp']=payload['generations/a/source.gscp'];model.files[saved+cap['application']+'.image']=payload['generations/a/'+cap['application']+'.image']
    model.dirs.add('target-1');model.files['target-1/derived-marker']=b'retained'
    return lambda counter:e.f.encode('records','ALLOCATOR',dict(root=root,node=node['node'],counter=counter))


def validate(root):
    root=Path(root);cases=[(size,source,cut,mode) for size in (3,4,5) for source in ('EMPTY','VERIFIED_DURABLE_BACKUP') for cut in CUTS for mode in ('halt','kill')]
    e.need(root.is_dir() and not root.is_symlink() and {v.name for v in root.iterdir()}=={f'case-{i:03d}' for i in range(len(cases))}|{'receipt.json'},'bootstrap typed case inventory');rows=[];live=0
    for n,(size,source,cut,mode) in enumerate(cases):
        name=f'case-{n:03d}';case=root/name
        members={'original-plan.gsbp','original-application.image','crash','before','second-crash','final','store-events.json'}|{label+suffix for label in ('first','second','resumed') for suffix in ('.stdout','.stderr')}
        e.need(case.is_dir() and not case.is_symlink() and {v.name for v in case.iterdir()}==members,'bootstrap typed case members')
        raw=p.read(case/'original-plan.gsbp',2*e.MIB);image=p.read(case/'original-application.image',64*e.MIB);data=t.derived(raw,image,size=size,source=source)
        admission=a.envelope(data['receipt'],data['rows'][2],data['rows'][3]);m=t.Model(raw,image,admission=admission,size=size,source=source,progress=True,typed=True)
        second='BOOTSTRAP_RECOVERY_JOURNAL_FORCED' if cut=='BOOTSTRAP_COMMITTED_BEFORE_RETURN' else 'BOOTSTRAP_SEAL_1_CANDIDATE_PREFIX_WRITTEN'
        def replay(label,stop):
            e.need(p.read(case/(label+'.stderr'),2*e.MIB)==b'','bootstrap typed unexpected stderr');expected=[dict(event=v) for v in m.execute(stop)]
            if label=='resumed':expected.append(dict(status='PASS',plan=e.digest(raw),receipt=e.digest(data['receipt']),history=p.decode(raw,image,size=size,source=source)))
            elif mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=stop))
            e.need(trace(case/(label+'.stdout'))==expected,'bootstrap typed '+label+' trace')
        replay('first',cut);e.need(read_snapshot(case/'crash')==(m.files,m.dirs),'bootstrap typed exact first crash')
        progressed='target-0/'+t.SEAL in m.files;before,before_dirs=read_snapshot(case/'before');allocator=None
        if progressed:
            live+=1;allocator=progress(m,before);m.files['target-0/allocator.gsr']=allocator(3)
        e.need((before,before_dirs)==(m.files,m.dirs),'bootstrap typed exact running state')
        replay('second',second);e.need(read_snapshot(case/'second-crash')==(m.files,m.dirs),'bootstrap typed exact second crash')
        replay('resumed',None)
        if progressed:m.files['target-0/allocator.gsr']=allocator(4)
        e.need(read_snapshot(case/'final')==(m.files,m.dirs),'bootstrap typed exact final state')
        store=e.parse(p.read(case/'store-events.json',e.MIB));e.need(type(store) is list and all(type(v) is str for v in store),'bootstrap typed store trace shape')
        ordered=['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN','PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN']+['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN']*2
        e.need(([v for v in store if v in set(ordered)]==ordered) if progressed else store==[],'bootstrap typed running grant force order')
        rows.append(dict(case=name,size=size,source=source,cut=cut,secondCut=second,mode=mode,progressed=progressed,plan=e.digest(raw),status='PASS'))
    expected=dict(schema='gse-v53-bootstrap-typed-process-v1',status='PASS',cases=rows,freshWorkers=3*len(cases),lockProbeProcesses=2*live,freshProcesses=3*len(cases)+2*live,typedCoordinator=True,planningInParent=True,publicRuntime=False)
    e.need(e.f.canonical(e.parse(p.read(root/'receipt.json',65536)))==e.f.canonical(expected),'bootstrap typed receipt scope')
    return dict(status='PASS',cases=len(cases),freshWorkers=3*len(cases),lockProbeProcesses=2*live,freshProcesses=3*len(cases)+2*live,liveCompletedVoterCases=live,originalFirst=True,typedCoordinator=True,planningInParent=True,publicRuntime=False,powerLoss=False,independentTypedSemantics=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'missing-case':'bootstrap typed case inventory','original-plan':'bootstrap original plan checksum','original-image':'bootstrap original image binding',
              'first-trace':'bootstrap typed first trace','second-trace':'bootstrap typed second trace','resumed-trace':'bootstrap typed resumed trace','stderr':'bootstrap typed unexpected stderr',
              'crash':'bootstrap typed exact first crash','running':'bootstrap typed exact running state','second-crash':'bootstrap typed exact second crash','final':'bootstrap typed exact final state',
              'grant':'bootstrap typed actual running grant','store':'bootstrap typed running grant force order','admission':'bootstrap typed exact final state','scope':'bootstrap typed receipt scope','linked-file':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-bootstrap-typed-negative-') as temp:
            moved=Path(temp)/'raw';shutil.copytree(root,moved);case=moved/'case-009'
            if name=='missing-case':shutil.rmtree(case)
            elif name=='original-plan':
                path=case/'original-plan.gsbp';raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='original-image':(case/'original-application.image').write_bytes(b'wrong')
            elif name.endswith('-trace'):
                path=case/(name[:-6]+'.stdout');lines=path.read_bytes().splitlines();path.write_bytes(b'\n'.join(lines[:-1])+b'\n')
            elif name=='stderr':(case/'resumed.stderr').write_bytes(b'failure')
            elif name=='crash':(case/'crash/target-0'/t.SEAL).unlink()
            elif name=='running':(case/'before/target-0/allocator.gsr').write_bytes((case/'crash/target-0/allocator.gsr').read_bytes())
            elif name=='second-crash':(case/'second-crash/target-2'/t.SEAL_PENDING).write_bytes(b'wrong')
            elif name=='final':(case/'final/target-0/allocator.gsr').write_bytes((case/'crash/target-0/allocator.gsr').read_bytes())
            elif name=='grant':
                path=case/'before/target-0/grants.gsr';parts=frames(path.read_bytes());value=e.f.decode(parts[2],'records','BASIS');value['voter']='node-2';parts[2]=e.f.encode('records','BASIS',value);path.write_bytes(b''.join(parts))
            elif name=='store':(case/'store-events.json').write_bytes(b'[]')
            elif name=='admission':(case/'final/target-4/bootstrap-admission.gsbp').unlink()
            elif name=='scope':
                path=moved/'receipt.json';value=e.parse(path.read_bytes());value['planningInParent']=False;path.write_bytes(e.f.canonical(value))
            else:
                path=case/'final/target-0/replica.lock';path.unlink();path.symlink_to((root/'case-009/final/target-0/replica.lock').resolve())
            try:validate(moved)
            except ValueError as error:e.need(str(error)==reason,'bootstrap typed unexpected negative: '+name+': '+str(error))
            else:raise ValueError('bootstrap typed negative accepted: '+name)
            negatives.append(dict(case=name,reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-bootstrap-typed-portable-') as temp:
        moved=Path(temp)/'raw';shutil.copytree(root,moved);e.need(validate(moved)==result,'bootstrap typed portable mismatch')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
