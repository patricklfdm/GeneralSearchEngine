"""Replay original admission-file publication and twice-interrupted recovery.

This extends the original transaction model only for an explicitly selected
admission profile. Historical component receipts keep their original inventory.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import bootstrap_plan_evidence as p, bootstrap_transaction_evidence as t
from . import bootstrap_admission_evidence as a, pending_context_evidence as e
from .journal_context_evidence import read_snapshot


def model(raw,image):
    data=t.derived(raw,image);admission=a.envelope(data['receipt'],data['rows'][2],data['rows'][3])
    plan=p.decode(raw,image,details=True)['plan'];e.need(data['completionBytes']+3*len(admission)<=plan['maximumOperation'],'bootstrap admission completion capacity')
    return t.Model(raw,image,admission=admission)


def cuts(events):
    return list(dict.fromkeys(event for event in events if event.startswith(('BOOTSTRAP_ADMISSION_0_','BOOTSTRAP_ADMISSION_2_','BOOTSTRAP_SEAL_0_')) or event in
                             ('BOOTSTRAP_COMMITTED_PREFIX_WRITTEN','BOOTSTRAP_COMMITTED_DURABLE','BOOTSTRAP_COMMITTED_BEFORE_RETURN')))


def validate(root):
    root=Path(root);e.need(root.is_dir() and not root.is_symlink(),'bootstrap admission files evidence root')
    first=root/'case-000';raw=p.read(first/'original-plan.gsbp',2*e.MIB);image=p.read(first/'original-application.image',64*e.MIB)
    points=cuts(model(raw,image).execute());e.need({v.name for v in root.iterdir()}=={f'case-{i:03d}' for i in range(len(points))}|{'receipt.json'},'bootstrap admission files case inventory');rows=[]
    for i,stop in enumerate(points):
        name=f'case-{i:03d}';case=root/name
        e.need(case.is_dir() and not case.is_symlink() and {v.name for v in case.iterdir()}=={'original-plan.gsbp','original-application.image','events.json','crash','second-crash','final'},'bootstrap admission files case members')
        raw=p.read(case/'original-plan.gsbp',2*e.MIB);image=p.read(case/'original-application.image',64*e.MIB);m=model(raw,image);events=e.parse(p.read(case/'events.json',e.MIB));e.exact(events,'first second resumed')
        for key,stage,cut in [('first','crash',stop),('second','second-crash','BOOTSTRAP_ADMISSION_0_FORCED'),('resumed','final',None)]:
            expected=m.execute(cut);e.need(events[key]==expected,'bootstrap admission files '+key+' force order')
            e.need(read_snapshot(case/stage)==(m.files,m.dirs),'bootstrap admission files exact '+stage+' bytes')
        rows.append(dict(case=name,cut=stop,plan=e.digest(raw),status='PASS'))
    expected=dict(schema='gse-v53-bootstrap-admission-files-v1',status='PASS',cases=rows,freshProcesses=False,typedCoordinator=False,publicBootstrap=False)
    e.need(e.f.canonical(e.parse(p.read(root/'receipt.json',65536)))==e.f.canonical(expected),'bootstrap admission files receipt scope')
    return dict(status='PASS',cases=len(points),privateCommittedTargets=3*len(points),freshProcesses=False,typedCoordinator=False,publicBootstrap=False,originalFirst=True)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'missing-case':'bootstrap admission files case inventory','original-plan':'bootstrap original plan checksum','original-image':'bootstrap original image binding',
              'first-order':'bootstrap admission files first force order','second-order':'bootstrap admission files second force order','resumed-order':'bootstrap admission files resumed force order',
              'crash':'bootstrap admission files exact crash bytes','second-crash':'bootstrap admission files exact second-crash bytes','final':'bootstrap admission files exact final bytes',
              'lost-other-admission':'bootstrap admission files exact final bytes','early-admission':'bootstrap admission files exact crash bytes',
              'scope':'bootstrap admission files receipt scope','type':'bootstrap admission files receipt scope','linked-admission':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-admission-files-negative-') as temp:
            moved=Path(temp)/'raw';shutil.copytree(root,moved);case=moved/'case-001'
            if name=='missing-case':shutil.rmtree(case)
            elif name=='original-plan':
                path=case/'original-plan.gsbp';raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='original-image':(case/'original-application.image').write_bytes(b'wrong')
            elif name.endswith('-order'):
                path=case/'events.json';value=e.parse(path.read_bytes());value[name[:-6]]=[];path.write_bytes(e.f.canonical(value))
            elif name in ('crash','second-crash','final'):(case/name/'operation/plan.gsbp').write_bytes(b'wrong')
            elif name=='lost-other-admission':(case/'final/target-4/bootstrap-admission.gsbp').unlink()
            elif name=='early-admission':
                first=moved/'case-000';(first/'crash/target-0/bootstrap-admission.gsbp').write_bytes((first/'final/target-0/bootstrap-admission.gsbp').read_bytes())
            elif name=='linked-admission':
                path=case/'final/target-0/bootstrap-admission.gsbp';path.unlink();path.symlink_to((root/'case-001/final/target-0/bootstrap-admission.gsbp').resolve())
            else:
                path=moved/'receipt.json';value=e.parse(path.read_bytes());value['typedCoordinator']=True if name=='scope' else 0;path.write_bytes(e.f.canonical(value))
            try:validate(moved)
            except ValueError as error:e.need(str(error)==reason,'bootstrap admission files unexpected negative: '+name+': '+str(error))
            else:raise ValueError('bootstrap admission files negative accepted: '+name)
            negatives.append(dict(case=name,reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-admission-files-portable-') as temp:
        moved=Path(temp)/'raw';shutil.copytree(root,moved);e.need(validate(moved)==result,'bootstrap admission files portable mismatch')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
