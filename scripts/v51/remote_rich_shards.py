"""Prepared immutable source, partial rich shards, and independent complete replay."""
import argparse
import os
from pathlib import Path
import re
import shutil
import signal
import tempfile
from scripts import ci_v51_bundle as build
from . import remote_workload as workload, remote_rich_evidence as evidence
from . import remote_rich_negatives as negatives, remote_collection as collection
from . import performance_model as m, performance_harness as base
from .remote_rich_plan import SHARDS, MODES

SCHEMA = 'gse-v51-rich-shard-v1'


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    base.save(path,value)


def read(path):
    m.need(path.is_file() and not path.is_symlink() and path.stat().st_size<=4<<20,'rich metadata file/size')
    return m.strict_json(path.read_bytes())


def build_identity(manifest,source):
    value=read(manifest)
    m.need(value['schema']==build.SCHEMA and value['binding']==build.binding(base.ROOT,source),
           'rich checkout/toolchain/build mismatch')
    return value


def record_provenance(raw,manifest,kind,shard=None,seed=None):
    shutil.copyfile(manifest,raw/'ci-build-manifest.json')
    value=dict(schema=SCHEMA,kind=kind,shard=shard,seedBindingSha256=seed,
               buildManifestSha256=m.sha(manifest.read_bytes()))
    save(raw/'provenance.json',value)
    return value


def inspect(root,kind,shard,source,manifest_sha):
    expected=() if kind=='inputs' else SHARDS[shard]
    execution,location=evidence.header(root,expected)
    m.need(execution['source']==source and execution['preset']=='canonical' and
           execution['fullRemoteQualification'] is False,'rich source/preset/qualification scope')
    provenance=read(root/'provenance.json')
    m.need(provenance['schema']==SCHEMA and provenance['kind']==kind and provenance['shard']==shard and
           provenance['buildManifestSha256']==manifest_sha==m.sha((root/'ci-build-manifest.json').read_bytes()),
           'rich build/scope provenance')
    seed=provenance['seedBindingSha256']
    m.need(seed is None if kind=='inputs' else isinstance(seed,str) and re.fullmatch('[0-9a-f]{64}',seed),
           'rich seed binding')
    manifest=read(root/'ci-build-manifest.json')
    m.need(manifest['schema']==build.SCHEMA and manifest['binding']['source']==source,'rich build source')
    files={v['path']:v['sha256'] for v in manifest['files']}
    for artifact in execution['adapters'][MODES[2]]['artifacts']:
        name=Path(artifact['path']).name
        path=('general-search-engine-replication/target/' if name.startswith('general-search-engine-replication-') else 'target/')+name
        m.need(files.get(path)==artifact['sha256'],'rich candidate differs from verification build')
    identity=evidence.common_identity(root,execution)
    inventory=read(root/'source-inventory.json')
    names=build.git(base.ROOT,'ls-files','-z','--cached','--others','--exclude-standard').split(b'\0')
    actual={os.fsdecode(n):m.sha((base.ROOT/os.fsdecode(n)).read_bytes()) for n in set(names) if n}
    m.need(inventory==actual,'rich evidence differs from checked-out source')
    return execution,provenance,identity


def binding(root):
    return m.sha(m.canonical(dict(execution=read(root/'execution.json'),provenance=read(root/'provenance.json'))))


def retain(root,output,kind,shard,source,manifest_sha):
    execution,provenance,identity=inspect(root,kind,shard,source,manifest_sha)
    digest=binding(root)
    parts=collection.pack(root,output/'parts',digest)
    with tempfile.TemporaryDirectory(prefix='v51-rich-shard-replay-') as temp:
        replay_root=Path(temp)/'raw'
        retained=collection.unpack(output/'parts',replay_root,digest)
        replay=inspect(replay_root,kind,shard,source,manifest_sha)
        m.need(replay==(execution,provenance,identity),'relocated rich shard identity changed')
        if kind=='shard':
            result=evidence.validate_partial(replay_root,shard)
            m.need(result==read(root/'validation.json'),'relocated rich shard validation changed')
            rejected=negatives.verify(replay_root) if shard=='automatic-concurrent' else []
            m.need(rejected==read(root/'negatives.json'),'relocated rich shard negative qualification changed')
    return dict(schema=SCHEMA,status='PREPARED' if kind=='inputs' else 'PARTIAL',kind=kind,shard=shard,
                source=source,buildManifestSha256=manifest_sha,seedBindingSha256=provenance['seedBindingSha256'],
                bindingSha256=digest,identity=identity,collection=retained,parts=len(parts['parts']),
                paidCloud=False,fullRemoteQualification=False)


def unpack_input(folder,target,kind,shard,source,manifest_sha):
    m.need(folder.is_dir() and not folder.is_symlink(),'rich handoff directory')
    receipt=read(folder/'receipt.json')
    m.need(receipt['schema']==SCHEMA and receipt['status']==('PREPARED' if kind=='inputs' else 'PARTIAL') and
           receipt['kind']==kind and receipt['shard']==shard and receipt['source']==source and
           receipt['buildManifestSha256']==manifest_sha and receipt['paidCloud'] is False and
           receipt['fullRemoteQualification'] is False,'incomplete/stale/wrong rich handoff')
    digest=receipt['bindingSha256']
    retained=collection.unpack(folder/'parts',target,digest)
    m.need(retained==receipt['collection'] and binding(target)==digest,'rich handoff binary binding')
    execution,provenance,identity=inspect(target,kind,shard,source,manifest_sha)
    m.need(identity==receipt['identity'] and provenance['seedBindingSha256']==receipt['seedBindingSha256'],
           'rich handoff identity mismatch')
    return receipt,execution


def prepare(output,manifest,source):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    handoff=output/'handoff';handoff.mkdir();receipt=dict(schema=SCHEMA,status='FAIL',kind='inputs')
    try:
        build_identity(manifest,source)
        workload.run(output/'raw',selected=())
        record_provenance(output/'raw',manifest,'inputs')
        receipt=retain(output/'raw',handoff,'inputs',None,source,m.sha(manifest.read_bytes()))
        return receipt
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        save(handoff/'receipt.json',receipt)
        print(m.canonical({k:v for k,v in receipt.items() if k not in ('identity','collection')}).decode(),flush=True)


def run(output,manifest,source,shard,inputs):
    m.need(shard in SHARDS,'unknown rich shard')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    handoff=output/'handoff';handoff.mkdir();receipt=dict(schema=SCHEMA,status='FAIL',kind='shard',shard=shard)
    try:
        build_identity(manifest,source);manifest_sha=m.sha(manifest.read_bytes())
        with tempfile.TemporaryDirectory(prefix='v51-rich-source-') as temp:
            seed_root=Path(temp)/'raw'
            seed,_=unpack_input(inputs,seed_root,'inputs',None,source,manifest_sha)
            workload.run(output/'raw',selected=SHARDS[shard],source_seed=seed_root/'source')
        raw=output/'raw'
        record_provenance(raw,manifest,'shard',shard,seed['bindingSha256'])
        _,_,identity=inspect(raw,'shard',shard,source,manifest_sha)
        m.need(identity==seed['identity'],'shard differs from prepared input identities')
        result=evidence.validate_partial(raw,shard);save(raw/'validation.json',result)
        rejected=negatives.verify(raw) if shard=='automatic-concurrent' else []
        save(raw/'negatives.json',rejected)
        receipt=retain(raw,handoff,'shard',shard,source,manifest_sha)
        receipt.update(calls=sum(c['calls'] for c in result['cells']),negativeCases=len(rejected))
        return receipt
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        save(handoff/'receipt.json',receipt)
        print(m.canonical({k:v for k,v in receipt.items() if k not in ('identity','collection')}).decode(),flush=True)


def combined_limits(roots,inputs):
    """The original total budgets apply to all shard bytes, including repeated setup."""
    totals=dict(files=0,expandedBytes=0,traceBytes=0,compressedBytes=0,parts=0)
    limits=collection.LIMITS
    for name,root in roots.items():
        index=read(root/collection.INDEX)
        totals['files']+=len(index)+1
        totals['expandedBytes']+=sum(v['bytes'] for v in index.values())+(root/collection.INDEX).stat().st_size
        totals['traceBytes']+=sum(v['bytes'] for path,v in index.items() if path.endswith(('.jsonl','.jsonl.gz','.log')))
        manifest=read(inputs/name/'parts/parts.json')
        totals['compressedBytes']+=manifest['compressedBytes'];totals['parts']+=len(manifest['parts'])
    m.need(all(totals[k]<=limits[k] for k in totals),'combined rich evidence budget')
    return totals


def aggregate(output,manifest,source,inputs):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='FAIL',kind='aggregate',paidCloud=False,fullRemoteQualification=False)
    try:
        build_identity(manifest,source);manifest_sha=m.sha(manifest.read_bytes())
        m.need(inputs.is_dir() and not inputs.is_symlink() and {p.name for p in inputs.iterdir()}==set(SHARDS),
               'missing/duplicate/extra rich shard handoff')
        with tempfile.TemporaryDirectory(prefix='v51-rich-aggregate-') as temp:
            roots={name:Path(temp)/name for name in SHARDS};receipts={}
            for name,root in roots.items():
                receipts[name],_=unpack_input(inputs/name,root,'shard',name,source,manifest_sha)
            seeds={v['seedBindingSha256'] for v in receipts.values()}
            m.need(len(seeds)==1,'mixed prepared source bindings')
            totals=combined_limits(roots,inputs)
            # All physical/read/resource checks run again across the complete set,
            # with one shared decoded-trace budget and the original cell order.
            result=evidence.validate_group(roots);save(output/'validation.json',result)
            rejected=negatives.verify(roots['automatic-concurrent'])
            save(output/'negatives.json',rejected)
            for name,root in roots.items():
                expected=rejected if name=='automatic-concurrent' else []
                m.need(read(root/'negatives.json')==expected and receipts[name]['negativeCases']==len(expected),
                       'rich shard negative qualification')
            receipt.update(status='PASS',source=source,buildManifestSha256=manifest_sha,seedBindingSha256=next(iter(seeds)),
                           calls=sum(c['calls'] for c in result['cells']),negativeCases=len(rejected),budgets=totals,
                           shards={name:dict(bindingSha256=r['bindingSha256'],
                                            partsManifestSha256=m.sha((inputs/name/'parts/parts.json').read_bytes()))
                                   for name,r in receipts.items()})
        return receipt
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        save(output/'receipt.json',receipt)
        print(m.canonical({k:v for k,v in receipt.items() if k not in ('identity','collection')}).decode(),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','run','aggregate'));p.add_argument('output',type=Path)
    p.add_argument('--source',required=True);p.add_argument('--build-manifest',required=True,type=Path)
    p.add_argument('--inputs',type=Path);p.add_argument('--shard',choices=tuple(SHARDS))
    a=p.parse_args()
    def terminate(*_):raise TimeoutError('rich shard qualification terminated')
    signal.signal(signal.SIGTERM,terminate)
    if a.action=='prepare':prepare(a.output,a.build_manifest,a.source)
    elif a.action=='run':
        m.need(a.inputs is not None and a.shard is not None,'shard and inputs required')
        run(a.output,a.build_manifest,a.source,a.shard,a.inputs)
    else:
        m.need(a.inputs is not None,'inputs required')
        aggregate(a.output,a.build_manifest,a.source,a.inputs)


if __name__=='__main__':main()
