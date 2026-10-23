"""Original-first physical replay of fresh-process private bootstrap commits."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import bootstrap_transaction_evidence as t
from . import bootstrap_plan_evidence as plans
from . import pending_context_evidence as e
from .journal_context_evidence import read_snapshot

CUTS=('BOOTSTRAP_PREPARING_PREFIX_WRITTEN','BOOTSTRAP_PREPARING_DURABLE',
      'BOOTSTRAP_TARGET_1_CREATED','BOOTSTRAP_DIRECTORY_0_generations/a_CREATED','BOOTSTRAP_PAYLOAD_0_root.gsr_PREFIX_WRITTEN',
      'BOOTSTRAP_PAYLOAD_0_grants.gsr_FORCED','BOOTSTRAP_PAYLOAD_0_selector.gsr_PARENT_FORCED','BOOTSTRAP_PREPARATION_0_PREFIX_WRITTEN',
      'BOOTSTRAP_PREPARATION_2_PARENT_FORCED','BOOTSTRAP_PREPARED_PREFIX_WRITTEN','BOOTSTRAP_PREPARED_DURABLE',
      'BOOTSTRAP_COMMITTING_PREFIX_WRITTEN','BOOTSTRAP_COMMITTING_DURABLE','BOOTSTRAP_RECEIPT_CANDIDATE_PREFIX_WRITTEN',
      'BOOTSTRAP_RECEIPT_CANDIDATE_PARENT_FORCED','BOOTSTRAP_RECEIPT_RENAMED','BOOTSTRAP_RECEIPT_ACTIVE_FORCED',
      'BOOTSTRAP_COMMITTED_PREFIX_WRITTEN','BOOTSTRAP_COMMITTED_DURABLE','BOOTSTRAP_SEAL_0_CANDIDATE_PREFIX_WRITTEN',
      'BOOTSTRAP_SEAL_0_RENAMED','BOOTSTRAP_SEAL_2_CANDIDATE_PARENT_FORCED','BOOTSTRAP_SEAL_2_ACTIVE_PARENT_FORCED','BOOTSTRAP_COMMITTED_BEFORE_RETURN')


def trace(path):
    raw=plans.read(path,2*e.MIB);e.need(raw.endswith(b'\n'),'bootstrap process trace termination');rows=[]
    for line in raw.splitlines():
        row=e.parse(line);e.need(e.f.canonical(row)==line,'bootstrap process canonical trace');rows.append(row)
    return rows


def validate(root):
    root=Path(root);cases=[(cut,mode) for cut in CUTS for mode in ('halt','kill')]
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}=={f'case-{n:03d}' for n in range(len(cases))}|{'receipt.json'},'bootstrap process case inventory')
    rows=[]
    for n,(cut,mode) in enumerate(cases):
        name=f'case-{n:03d}';path=root/name
        e.need(path.is_dir() and not path.is_symlink() and {p.name for p in path.iterdir()}=={'original-plan.gsbp','original-application.image','crash','second-crash','final'}|{key+suffix for key in ('first','second','resumed') for suffix in ('.stdout','.stderr')},'bootstrap process case members')
        raw=plans.read(path/'original-plan.gsbp',2*e.MIB);image=plans.read(path/'original-application.image',64*e.MIB);model=t.Model(raw,image);history=plans.decode(raw,image)
        for label,stage,stop in [('first','crash',cut),('second','second-crash','BOOTSTRAP_RESEAL_0_root.gsr_FORCED'),('resumed','final',None)]:
            e.need(plans.read(path/(label+'.stderr'),2*e.MIB)==b'','bootstrap process unexpected stderr')
            events=model.execute(stop);expected=[dict(event=event) for event in events]
            if label=='resumed':expected.append(dict(status='PASS',plan=e.digest(raw),receipt=e.digest(model.data['receipt']),history=history))
            elif mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=stop))
            e.need(trace(path/(label+'.stdout'))==expected,'bootstrap process '+label+' trace')
            e.need(read_snapshot(path/stage)==(model.files,model.dirs),'bootstrap process exact '+stage+' bytes')
        rows.append(dict(case=name,cut=cut,mode=mode,plan=e.digest(raw),status='PASS'))
    receipt=dict(schema='gse-v53-bootstrap-transaction-process-v1',status='PASS',cases=rows,freshProcesses=3*len(cases),publicBootstrap=False)
    e.need(e.f.canonical(e.parse(plans.read(root/'receipt.json',65536)))==e.f.canonical(receipt),'bootstrap process receipt scope')
    return dict(status='PASS',cases=len(cases),freshProcesses=3*len(cases),originalFirst=True,publicBootstrap=False,powerLoss=False,typedCodecIndependentlyVerified=False)


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    variants={'missing-case':'bootstrap process case inventory','changed-plan':'bootstrap original plan checksum','changed-image':'bootstrap original image binding',
        'first-trace':'bootstrap process first trace','second-trace':'bootstrap process second trace','result':'bootstrap process resumed trace',
        'stderr':'bootstrap process unexpected stderr','crash':'bootstrap process exact crash bytes','second-crash':'bootstrap process exact second-crash bytes',
        'final':'bootstrap process exact final bytes','scope':'bootstrap process receipt scope','early-target':'bootstrap process exact crash bytes','linked-file':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-bootstrap-process-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'case-001'
            if name=='missing-case':shutil.rmtree(case)
            elif name=='changed-plan':
                p=case/'original-plan.gsbp';raw=p.read_bytes();p.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='changed-image':(case/'original-application.image').write_bytes(b'changed')
            elif name in ('first-trace','second-trace','result'):
                label={'first-trace':'first','second-trace':'second','result':'resumed'}[name];p=case/(label+'.stdout');lines=p.read_bytes().splitlines();p.write_bytes(b'\n'.join(lines[:-1])+b'\n')
            elif name=='stderr':(case/'resumed.stderr').write_bytes(b'failure')
            elif name in ('crash','second-crash','final'):(case/name/'operation/plan.gsbp').write_bytes(b'changed')
            elif name=='scope':
                p=moved/'receipt.json';v=e.parse(p.read_bytes());v['freshProcesses']=1;p.write_bytes(e.f.canonical(v))
            elif name=='early-target':(case/'crash/target-0').mkdir()
            elif name=='linked-file':
                p=case/'final/operation/plan.gsbp';p.unlink();p.symlink_to(case/'original-plan.gsbp')
            try:validate(moved)
            except ValueError as error:e.need(str(error)==reason,'bootstrap process wrong negative: '+name+': '+str(error))
            else:raise ValueError('bootstrap process negative accepted: '+name)
            negatives.append(dict(case=name,reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-bootstrap-process-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==original,'bootstrap process portable mismatch')
    return dict(original,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('evidence');a=p.parse_args();print(json.dumps(qualify(a.evidence),sort_keys=True))
