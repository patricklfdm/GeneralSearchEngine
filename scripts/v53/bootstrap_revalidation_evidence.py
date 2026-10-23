"""Reconcile original plans, actual core exports and private receipts for all sizes.

Python verifies exact bytes/CRC and manifest administration normalization, not the
application's Java codec semantics or proof that a callback was executed.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
from scripts.v43.derived_format_v12 import checked, crc32c
from . import bootstrap_plan_evidence as plans, bootstrap_transaction_evidence as transaction
from . import pending_context_evidence as e
from .journal_context_evidence import read_snapshot

MEMBERS=('gse-backup-checkpoint','gse-backup-manifest','gse-backup-metadata')
STAGES=('planning-scratch','validation-1','validation-2','validation-complete')


def image_members(raw):
    e.need(24<len(raw)<=64*e.MIB and struct.unpack('>4sHHI',raw[:12])==(b'GSAI',1,3,len(raw)-12), 'bootstrap validation image header')
    result=[];offset=12
    for _ in MEMBERS:
        e.need(offset+4<=len(raw),'bootstrap validation image member size');size=struct.unpack('>I',raw[offset:offset+4])[0];offset+=4
        e.need(0<size<=len(raw)-offset,'bootstrap validation image member size');result.append(raw[offset:offset+size]);offset+=size
    e.need(offset==len(raw),'bootstrap validation image trailer')
    for member in result:
        e.need(len(member)>=64 and crc32c(member[:-4])==struct.unpack('>I',member[-4:])[0], 'bootstrap validation core CRC')
    e.need(result[1][-16:-4]==b'\0'*12,'bootstrap validation canonical manifest administration')
    return dict(zip(MEMBERS,result))


def exported(path,expected):
    files,dirs=read_snapshot(path)
    e.need(not dirs and set(files)==set(MEMBERS),'bootstrap validation export inventory')
    e.need(all((path/name).stat().st_nlink==1 for name in files),'bootstrap validation linked export')
    e.need(files[MEMBERS[0]]==expected[MEMBERS[0]] and files[MEMBERS[2]]==expected[MEMBERS[2]],'bootstrap validation exact exported state')
    raw=files[MEMBERS[1]];canonical=expected[MEMBERS[1]];prefix=len(canonical)-16
    e.need(len(raw)>=prefix+16 and raw[:prefix]==canonical[:prefix], 'bootstrap validation original manifest content')
    e.need(crc32c(raw[:-4])==struct.unpack('>I',raw[-4:])[0], 'bootstrap validation manifest CRC')
    created,length=struct.unpack('>qI',raw[prefix:prefix+12])
    e.need(created>=0 and length<=256 and len(raw)==prefix+16+length, 'bootstrap validation manifest administration')
    raw[prefix+12:-4].decode('utf-8',errors='strict')
    e.need(checked(raw[:prefix]+b'\0'*12)==canonical,'bootstrap validation normalized image')
    return sum(map(len,files.values()))


def validate(root):
    root=Path(root);names={f'size-{n}-{s}' for n in (3,4,5) for s in ('empty','backup')}
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}==names|{'receipt.json'},'bootstrap validation case inventory')
    rows=[];exports=0
    for size in (3,4,5):
        for source in ('EMPTY','VERIFIED_DURABLE_BACKUP'):
            name=f"size-{size}-{'empty' if source=='EMPTY' else 'backup'}";case=root/name
            e.need(case.is_dir() and not case.is_symlink(),'bootstrap validation case type')
            e.need({p.name for p in case.iterdir()}==set(STAGES)|{'original-plan.gsbp','original-application.image','receipt.gsbp'}|({'original-source'} if source!='EMPTY' else set()),'bootstrap validation case members')
            raw=plans.read(case/'original-plan.gsbp',2*e.MIB);image=plans.read(case/'original-application.image',64*e.MIB)
            decoded=plans.decode(raw,image,details=True,size=size,source=source);expected=image_members(image);retained=0
            if source!='EMPTY':
                files,dirs=read_snapshot(case/'original-source')
                inventory=[dict(path=k,kind=1,size=len(v),sha256=e.digest(v)) for k,v in sorted(files.items())]
                e.need(not dirs and e.f.canonical(inventory)==e.f.canonical(decoded['plan']['descriptor']['sourceInventory']), 'bootstrap validation original source bytes')
            data=transaction.derived(raw,image,size=size,source=source)
            for stage in STAGES:
                directory=case/stage
                e.need(directory.is_dir() and not directory.is_symlink() and {p.name for p in directory.iterdir()}=={f'application-{n}' for n in range(size)},'bootstrap validation target export count')
                if stage!='planning-scratch':
                    e.need(data['completionBytes']+retained+size*64*e.MIB<=decoded['plan']['maximumOperation'],'bootstrap validation reserved capacity')
                for n in range(size):retained+=exported(directory/f'application-{n}',expected);exports+=1
            e.need(plans.read(case/'receipt.gsbp',65536)==data['receipt'],'bootstrap validation exact original receipt')
            rows.append(dict(case=name,size=size,source=source,callbacks=2,plan=e.digest(raw),retainedBytes=retained,status='PASS'))
    receipt=e.parse(plans.read(root/'receipt.json',65536))
    e.need(e.f.canonical(receipt)==e.f.canonical(dict(schema='gse-v53-bootstrap-revalidation-v1',status='PASS',cases=rows,publicBootstrap=False,freshProcesses=False)), 'bootstrap validation producer scope/accounting')
    return dict(status='PASS',cases=6,exports=exports,callbackPairs=6,scope='exact-export-and-receipt-reconciliation',independentTypedSemantics=False,publicBootstrap=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={
        'missing-case':'bootstrap validation case inventory',
        'missing-target':'bootstrap validation target export count',
        'extra-export-file':'bootstrap validation export inventory',
        'exported-state':'bootstrap validation exact exported state',
        'manifest-content':'bootstrap validation original manifest content',
        'manifest-crc':'bootstrap validation manifest CRC',
        'source-bytes':'bootstrap validation original source bytes',
        'original-image':'bootstrap original image binding',
        'original-receipt':'bootstrap validation exact original receipt',
        'scratch-accounting':'bootstrap validation producer scope/accounting',
        'callback-type':'bootstrap validation producer scope/accounting',
        'public-claim':'bootstrap validation producer scope/accounting',
        'linked-export':'owner context linked/nonregular member',
    }
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-revalidation-negative-') as temp:
            moved=Path(temp)/'evidence';shutil.copytree(root,moved);case=moved/'size-3-backup';export=case/'validation-2/application-0'
            if name=='missing-case':shutil.rmtree(moved/'size-5-empty')
            elif name=='missing-target':shutil.rmtree(export)
            elif name=='extra-export-file':(export/'unknown').write_bytes(b'x')
            elif name=='exported-state':(export/MEMBERS[0]).write_bytes(b'changed')
            elif name in ('manifest-content','manifest-crc'):
                p=export/MEMBERS[1];raw=bytearray(p.read_bytes());raw[0 if name=='manifest-content' else -1]^=1;p.write_bytes(raw)
            elif name=='source-bytes':(case/'original-source'/MEMBERS[0]).write_bytes(b'changed')
            elif name=='original-image':(case/'original-application.image').write_bytes(b'changed')
            elif name=='original-receipt':(case/'receipt.gsbp').write_bytes(b'changed')
            elif name=='linked-export':
                p=export/MEMBERS[0];p.unlink();p.symlink_to((root/'size-3-backup/validation-2/application-0'/MEMBERS[0]).resolve())
            else:
                p=moved/'receipt.json';value=e.parse(p.read_bytes())
                if name=='scratch-accounting':value['cases'][0]['retainedBytes']-=1
                elif name=='callback-type':value['cases'][0]['callbacks']=True
                else:value['publicBootstrap']=True
                p.write_bytes(e.f.canonical(value))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong bootstrap validation negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted bootstrap validation mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-revalidation-portable-') as temp:
        moved=Path(temp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'bootstrap validation portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(json.dumps(qualify(a.root),sort_keys=True))
