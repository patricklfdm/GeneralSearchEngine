"""Reconcile one retained projection with completed all-voter bootstrap bytes.

Typed calls and absence of writes are Java test claims; this replay independently
checks retained input/output bytes and capacity, not execution of those calls.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import bootstrap_revalidation_evidence as r
from . import bootstrap_plan_evidence as p, bootstrap_transaction_evidence as t
from . import pending_context_evidence as e
from .journal_context_evidence import read_snapshot


def validate(root,*,coordinator=False):
    root=Path(root);names={f'size-{n}-{s}' for n in (3,4,5) for s in ('empty','backup')}
    e.need(root.is_dir() and not root.is_symlink() and {v.name for v in root.iterdir()}==names|{'receipt.json'},'bootstrap recheck case inventory');rows=[];exports=0;histories=set()
    for size in (3,4,5):
        for source in ('EMPTY','VERIFIED_DURABLE_BACKUP'):
            name=f"size-{size}-{'empty' if source=='EMPTY' else 'backup'}";case=root/name
            e.need(case.is_dir() and not case.is_symlink(),'bootstrap recheck case type')
            e.need({v.name for v in case.iterdir()}=={'original-plan.gsbp','original-application.image','planning-scratch','receipt.gsbp','final'}|({'original-source'} if source!='EMPTY' else set()),'bootstrap recheck case members')
            raw=p.read(case/'original-plan.gsbp',2*e.MIB);image=p.read(case/'original-application.image',64*e.MIB);d=p.decode(raw,image,size=size,source=source,details=True)
            if coordinator:
                history=uuid.UUID(d['root']['historyId']);e.need(history.version==4 and history not in histories,'bootstrap coordinator unique random history');histories.add(history)
            expected=r.image_members(image);directory=case/'planning-scratch'
            e.need(directory.is_dir() and not directory.is_symlink() and {v.name for v in directory.iterdir()}=={f'application-{i}' for i in range(size)},'bootstrap recheck bounded projection')
            actual=sum(r.exported(directory/f'application-{i}',expected) for i in range(size));exports+=size
            if source!='EMPTY':
                files,dirs=read_snapshot(case/'original-source');inventory=[dict(path=k,kind=1,size=len(v),sha256=e.digest(v)) for k,v in sorted(files.items())]
                e.need(not dirs and e.f.canonical(inventory)==e.f.canonical(d['plan']['descriptor']['sourceInventory']),'bootstrap recheck original source')
            data=t.derived(raw,image,size=size,source=source)
            e.need(actual+data['completionBytes']<=d['plan']['maximumOperation'],'bootstrap recheck completion capacity')
            e.need(p.read(case/'receipt.gsbp',65536)==data['receipt'],'bootstrap recheck receipt')
            files={'operation/operation.lock':b'','operation/plan.gsbp':raw,'operation/application.image':image,
                   'operation/'+t.JOURNAL:b''.join(data['rows']),'operation/'+t.RECEIPT:data['receipt']};dirs={'operation'}
            for i,payload in enumerate(data['payloads']):
                prefix=f'target-{2*i}/';files.update({prefix+k:v for k,v in payload.items()});files[prefix+t.PREPARED]=data['preps'][i];files[prefix+t.SEAL]=data['seals'][i]
                dirs.update({prefix[:-1],prefix+'generations',prefix+'generations/a',prefix+'sources'})
            e.need(read_snapshot(case/'final')==(files,dirs),'bootstrap recheck exact final authority')
            rows.append(dict(case=name,size=size,source=source,checks=4,plan=e.digest(raw),projectionBytes=actual,status='PASS'))
    receipt=e.parse(p.read(root/'receipt.json',65536))
    e.need(e.f.canonical(receipt)==e.f.canonical(dict(schema='gse-v53-bootstrap-coordinator-v1' if coordinator else 'gse-v53-bootstrap-recheck-v1',status='PASS',cases=rows,publicBootstrap=False,freshProcesses=False)),'bootstrap recheck producer scope/accounting')
    return dict(status='PASS',cases=6,retainedExports=exports,reportedTypedChecks=24,scope='private-coordinator-physical-reconciliation' if coordinator else 'retained-projection-and-completed-authority',independentTypedSemantics=False,independentExecutionTrace=False,publicBootstrap=False)


def qualify(root,*,coordinator=False):
    root=Path(root);result=validate(root,coordinator=coordinator);negatives=[]
    variants={
        'missing-case':'bootstrap recheck case inventory',
        'extra-stage':'bootstrap recheck case members',
        'extra-projection':'bootstrap recheck bounded projection',
        'source-bytes':'bootstrap recheck original source',
        'projection-bytes':'bootstrap validation exact exported state',
        'original-image':'bootstrap original image binding',
        'receipt':'bootstrap recheck receipt',
        'local-seal':'bootstrap recheck exact final authority',
        'final-allocator':'bootstrap recheck exact final authority',
        'unknown-final-file':'bootstrap recheck exact final authority',
        'underreported-bytes':'bootstrap recheck producer scope/accounting',
        'check-type':'bootstrap recheck producer scope/accounting',
        'public-claim':'bootstrap recheck producer scope/accounting',
        'linked-projection':'owner context linked/nonregular member',
    }
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-recheck-negative-') as temp:
            moved=Path(temp)/'evidence';shutil.copytree(root,moved);case=moved/'size-3-backup'
            if name=='missing-case':shutil.rmtree(moved/'size-5-empty')
            elif name=='extra-stage':(case/'retry-2').mkdir()
            elif name=='extra-projection':(case/'planning-scratch/application-3').mkdir()
            elif name=='source-bytes':(case/'original-source/gse-backup-checkpoint').write_bytes(b'changed')
            elif name=='projection-bytes':(case/'planning-scratch/application-0/gse-backup-checkpoint').write_bytes(b'changed')
            elif name=='original-image':(case/'original-application.image').write_bytes(b'changed')
            elif name=='receipt':(case/'receipt.gsbp').write_bytes(b'changed')
            elif name=='local-seal':(case/'final/target-0'/t.SEAL).unlink()
            elif name=='final-allocator':(case/'final/target-0/allocator.gsr').write_bytes(b'changed')
            elif name=='unknown-final-file':(case/'final/target-0/unknown').write_bytes(b'changed')
            elif name=='linked-projection':
                path=case/'planning-scratch/application-0/gse-backup-checkpoint';path.unlink();path.symlink_to((root/'size-3-backup/planning-scratch/application-0/gse-backup-checkpoint').resolve())
            else:
                path=moved/'receipt.json';value=e.parse(path.read_bytes())
                if name=='underreported-bytes':value['cases'][0]['projectionBytes']-=1
                elif name=='check-type':value['cases'][0]['checks']=True
                else:value['publicBootstrap']=True
                path.write_bytes(e.f.canonical(value))
            try:validate(moved,coordinator=coordinator)
            except ValueError as error:
                e.need(str(error)==reason,'wrong bootstrap recheck negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted bootstrap recheck mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-recheck-portable-') as temp:
        moved=Path(temp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved,coordinator=coordinator)==result,'bootstrap recheck portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
