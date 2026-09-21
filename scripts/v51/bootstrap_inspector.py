"""Independent offline coordinator oracle; no product classes or fixture encoder."""
import base64
import hashlib
import json
from pathlib import Path
import struct
from . import format_inspector as f
from . import storage_inspector as storage


def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def raw(text): return base64.b64decode(text,validate=True)


def inspect(root, committed=False):
    root=Path(root); operation=root/'operation'
    plan_bytes=(operation/'plan.gsr').read_bytes(); plan=f.inspect(plan_bytes,'PLAN'); digest=plan_bytes[16:48].hex()
    binding_bytes=(operation/'bootstrap-binding.gsr').read_bytes()
    binding=f.json_body(raw(f.inspect(binding_bytes,'BOOTSTRAP_BINDING')['descriptor']))
    f.need(binding['operation']['path']==plan['operationPath']==str(operation.resolve()),'coordinator binding')
    f.need(set(binding)=={'operation','source','application','replicas','sourceInventory'},'descriptor fields')
    manifest=f.inspect(raw(plan['manifest']),'MANIFEST'); genesis=f.inspect(raw(plan['genesis']),'GENESIS')
    f.need(manifest['genesisDigest']==raw(plan['genesis'])[16:48].hex(),'genesis digest')
    f.need(genesis['sourceDigest']==(None if plan['sourcePath'] is None else sha(canonical(binding['sourceInventory']))),'source inventory binding')
    previous='0'*64; rows=[]; journal=(operation/'operation.gsr').read_bytes()
    offset=0
    while offset<len(journal):
        f.need(len(journal)-offset>=48,'ambiguous decision header')
        size=struct.unpack('>i',journal[offset+12:offset+16])[0]
        f.need(0<size<=65536-48 and offset+48+size<=len(journal),'ambiguous decision body')
        frame=journal[offset:offset+48+size]; row=f.inspect(frame,'DECISION'); rows.append(row)
        f.need(row==dict(planDigest=digest,sequence=len(rows),state=('PREPARING','PREPARED','COMMITTING','COMMITTED')[len(rows)-1],previousDigest=previous),'decision chain')
        previous=frame[16:48].hex(); offset+=len(frame)
    f.need(rows,'missing decision')
    for i,target in enumerate(plan['targets']):
        local=binding['replicas'][i]
        f.need(local['target']['path']==target['authorityPath'] and local['materialization']['directory']['path']==target['materializationPath'],'local path binding')
        f.need(local['replicationBounds']==target['bounds'],'bound local limits')
        b=next(x for x in target['files'] if x['path']=='bootstrap-binding.gsr')
        f.need(b==dict(path='bootstrap-binding.gsr',size=len(binding_bytes),sha256=sha(binding_bytes)),'bound descriptor bytes')
        path=Path(target['authorityPath'])
        if len(rows)>=2:
            for file in target['files']:
                data=(path/file['path']).read_bytes(); f.need(len(data)==file['size'] and sha(data)==file['sha256'],'prepared inventory')
            prep=f.inspect((path/'bootstrap-prepared.gsr').read_bytes(),'PREPARED')
            f.need(prep==dict(node=target['node'],planDigest=digest,manifestDigest=raw(plan['manifest'])[16:48].hex(),inventoryDigest=sha(canonical(target['files']))),'all-three preparation')
        if committed: storage.inspect(path)
    if committed:
        f.need(len(rows)==4,'missing committed decision')
        receipt=f.inspect((operation/'receipt.gsr').read_bytes(),'RECEIPT'); f.need(raw(receipt['plan'])==plan_bytes,'receipt plan')
        for target in plan['targets']:
            seal=f.inspect((Path(target['authorityPath'])/'bootstrap-seal.gsr').read_bytes(),'SEAL')
            f.need(raw(seal['receipt'])==(operation/'receipt.gsr').read_bytes(),'seal global receipt')
    return dict(status='PASS',phase=rows[-1]['state'],sequence=genesis['baseSequence'],planDigest=digest)
