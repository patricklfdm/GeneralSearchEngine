"""Independently replay compact admission data against actual committed originals.

This qualifies a metadata decoder, not publication of the new file, a complete
store opening or a durable/local voting admission. Original-first and portable.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import bootstrap_plan_evidence as p, bootstrap_transaction_evidence as t
from . import pending_context_evidence as e
from .journal_context_evidence import read_snapshot


def envelope(receipt,committing,committed):
    body=b''.join(struct.pack('>I',len(v))+v for v in (receipt,committing,committed))
    e.need(len(body)+48<=65536,'bootstrap admission envelope capacity')
    prefix=struct.pack('>4sHHHHI',b'GSBP',1,3,5,0,len(body))
    return prefix+bytes.fromhex(e.digest(prefix+body))+body


def validate(root):
    root=Path(root);names={f'size-{n}-{s}' for n in (3,4,5) for s in ('empty','backup')}
    e.need(root.is_dir() and not root.is_symlink() and {v.name for v in root.iterdir()}==names|{'receipt.json'},'bootstrap admission case inventory')
    rows=[];targets=0;maximum=0
    for size in (3,4,5):
        for source in ('EMPTY','VERIFIED_DURABLE_BACKUP'):
            name=f"size-{size}-{'empty' if source=='EMPTY' else 'backup'}";case=root/name
            e.need(case.is_dir() and not case.is_symlink() and {v.name for v in case.iterdir()}=={'original-plan.gsbp','original-application.image','final','derived-admissions'},'bootstrap admission case members')
            raw=p.read(case/'original-plan.gsbp',2*e.MIB);image=p.read(case/'original-application.image',64*e.MIB);data=t.derived(raw,image,size=size,source=source)
            files={'operation/operation.lock':b'','operation/plan.gsbp':raw,'operation/application.image':image,'operation/'+t.JOURNAL:b''.join(data['rows']),'operation/'+t.RECEIPT:data['receipt']};dirs={'operation'}
            for i,payload in enumerate(data['payloads']):
                prefix=f'target-{2*i}/';files.update({prefix+k:v for k,v in payload.items()});files[prefix+t.PREPARED]=data['preps'][i];files[prefix+t.SEAL]=data['seals'][i]
                dirs.update({prefix[:-1],prefix+'generations',prefix+'generations/a',prefix+'sources'})
            e.need(read_snapshot(case/'final')==(files,dirs),'bootstrap admission original committed authority')
            wanted=envelope(data['receipt'],data['rows'][2],data['rows'][3]);maximum=max(maximum,len(wanted));targets+=size
            expected={f'target-{i}.gsbp':wanted for i in range(size)}
            e.need(read_snapshot(case/'derived-admissions')==(expected,set()),'bootstrap admission derived original bytes')
            rows.append(dict(case=name,size=size,source=source,admissionBytes=len(wanted),plan=e.digest(raw),status='PASS'))
    wanted=dict(schema='gse-v53-bootstrap-admission-data-v1',status='PASS',cases=rows,storeIntegrated=False,publicBootstrap=False)
    e.need(e.f.canonical(e.parse(p.read(root/'receipt.json',65536)))==e.f.canonical(wanted),'bootstrap admission scope/accounting')
    return dict(status='PASS',cases=6,targets=targets,maximumAdmissionBytes=maximum,storeIntegrated=False,publicBootstrap=False,scope='compact-original-metadata-only')


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'missing-case':'bootstrap admission case inventory','extra-case-member':'bootstrap admission case members',
        'original-image':'bootstrap original image binding','original-plan':'bootstrap original plan checksum',
        'prepared':'bootstrap admission original committed authority','seal':'bootstrap admission original committed authority',
        'receipt':'bootstrap admission original committed authority','decision':'bootstrap admission original committed authority',
        'admission-missing':'bootstrap admission derived original bytes','admission-checksum':'bootstrap admission derived original bytes',
        'admission-foreign':'bootstrap admission derived original bytes','admission-extra':'bootstrap admission derived original bytes',
        'scope':'bootstrap admission scope/accounting','accounting':'bootstrap admission scope/accounting',
        'linked-admission':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-admission-negative-') as temp:
            moved=Path(temp)/'raw';shutil.copytree(root,moved);case=moved/'size-3-backup';admission=case/'derived-admissions/target-0.gsbp'
            if name=='missing-case':shutil.rmtree(case)
            elif name=='extra-case-member':(case/'extra').write_bytes(b'')
            elif name=='original-image':(case/'original-application.image').write_bytes(b'wrong')
            elif name=='original-plan':
                path=case/'original-plan.gsbp';raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name in ('prepared','seal','receipt','decision'):
                path=case/'final'/dict(prepared='target-0/'+t.PREPARED,seal='target-0/'+t.SEAL,receipt='operation/'+t.RECEIPT,decision='operation/'+t.JOURNAL)[name];path.write_bytes(b'wrong')
            elif name=='admission-missing':admission.unlink()
            elif name=='admission-checksum':
                raw=admission.read_bytes();admission.write_bytes(raw[:16]+bytes([raw[16]^1])+raw[17:])
            elif name=='admission-foreign':admission.write_bytes((moved/'size-4-backup/derived-admissions/target-0.gsbp').read_bytes())
            elif name=='admission-extra':(admission.parent/'extra.gsbp').write_bytes(admission.read_bytes())
            elif name=='linked-admission':admission.unlink();admission.symlink_to((root/'size-3-backup/derived-admissions/target-0.gsbp').resolve())
            else:
                path=moved/'receipt.json';receipt=e.parse(path.read_bytes())
                if name=='scope':receipt['storeIntegrated']=True
                else:receipt['cases'][0]['admissionBytes']-=1
                path.write_bytes(e.f.canonical(receipt))
            try:validate(moved)
            except ValueError as error:e.need(str(error)==reason,'bootstrap admission unexpected negative: '+name+': '+str(error))
            else:raise ValueError('bootstrap admission negative accepted: '+name)
            negatives.append(dict(case=name,reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-admission-portable-') as temp:
        moved=Path(temp)/'raw';shutil.copytree(root,moved);e.need(validate(moved)==result,'bootstrap admission portable mismatch')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
