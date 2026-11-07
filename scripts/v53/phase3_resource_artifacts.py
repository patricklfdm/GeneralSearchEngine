"""Bind supplemental original directories to exact-context retained archives.

Large raw archives are streamed without extracting another copy. Every original
still needs its owning physical replay; an archive inventory is not acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import tarfile
from . import phase3_resource_workflows as workflows
from . import phase3_resource_cohort as resources
from .maximum_transition_inventory import inventory,identity

seeds=workflows.seeds;h=seeds.h;need=seeds.need;tc=seeds.shared.tc
SCHEMA='gse-v53-phase3-resource-artifacts-v1'


def raw_archive(bundle,ctx,schema,case,maximum):
    """Read and hash every tar member; never trust a manifest's listed contents."""
    bundle=seeds.unlinked(bundle)
    need(bundle.is_dir() and {p.name for p in bundle.iterdir()}=={'manifest.json','bundle.tar.gz'},'resource artifacts bundle shape')
    manifest_bytes=seeds.read_bytes(bundle/'manifest.json');manifest=seeds.plan.decode(manifest_bytes)
    need(type(manifest) is dict and set(manifest)=={'schema','context','kind','case','inventory','archiveSha256'} and
         manifest['schema']==schema and manifest['context']==ctx and manifest['kind']=='raw' and manifest['case']==case,
         'resource artifacts exact raw binding')
    archive=seeds.unlinked(bundle/'bundle.tar.gz');before=archive.lstat()
    need(type(maximum) is int and maximum>0 and stat.S_ISREG(before.st_mode) and before.st_nlink==1 and
         0<before.st_size<=maximum and tc.file_hash(archive)==manifest['archiveSha256'],'resource artifacts archive digest/bound')
    files={};directories=[];total=0;seen=set();member_bytes=None
    with tarfile.open(archive,'r:gz') as stream:
        for item in stream:
            path=Path(item.name)
            need(item.name not in seen and len(seen)<65536 and len(path.parts)<=64 and len(item.name)<=4096 and
                 not path.is_absolute() and path.as_posix()==item.name and
                 '..' not in path.parts and path.parts and path.parts[0]=='data' and
                 item.type in (tarfile.DIRTYPE,tarfile.REGTYPE,tarfile.AREGTYPE) and not item.sparse,
                 'resource artifacts regular unique member')
            seen.add(item.name)
            need(0<=item.size<=256*1024**2 and total+item.size<=maximum,'resource artifacts raw capacity')
            if item.isdir():
                need(item.size==0,'resource artifacts directory size')
                if item.name!='data':directories.append(path.relative_to('data').as_posix())
                continue
            need(item.name!='data','resource artifacts data root');name=path.relative_to('data').as_posix()
            if name=='hosted-member.json':need(item.size<=8*1024**2,'resource artifacts bounded hosted receipt')
            digest=hashlib.sha256();count=0;parts=[]
            with stream.extractfile(item) as source:
                while True:
                    block=source.read(1024**2)
                    if not block:break
                    count+=len(block);need(count<=item.size,'resource artifacts member grew');digest.update(block)
                    if name=='hosted-member.json':parts.append(block)
            need(count==item.size,'resource artifacts truncated member');total+=count;files[name]=digest.hexdigest()
            if name=='hosted-member.json':member_bytes=b''.join(parts)
    observed=dict(files=files,directories=sorted(directories),bytes=total)
    need('data' in seen and member_bytes is not None and observed==manifest['inventory'],'resource artifacts actual archive inventory')
    need(identity(archive.lstat())==identity(before) and seeds.read_bytes(bundle/'manifest.json')==manifest_bytes,
         'resource artifacts archive changed while reading')
    return manifest,seeds.plan.decode(member_bytes)


def layout(index,artifacts):
    value=seeds.read(index);modules=workflows.adapters();source=workflows.validate_index(value,modules)
    resources.histories.exact_directory(artifacts,modules);bundles={}
    for name,adapter in modules.items():
        ctx=value['cohorts'][name];members=workflows.WORKFLOWS[name][2]
        wanted={workflows.artifact_name(name,ctx,'seed'):seeds.shared.MAX_BYTES}
        wanted.update({workflows.artifact_name(name,ctx,'raw',m):adapter.limit('raw',m) if name=='queue-resources' else adapter.limit('raw') for m in members})
        root=seeds.unlinked(artifacts/name);resources.histories.exact_directory(root,wanted)
        for artifact,maximum in wanted.items():bundles[name+'/'+artifact]=seeds.bundle_identity(root/artifact,maximum=maximum)
    return value,bundles


def check_producer(manifest,producer,maximum):
    actual=inventory(seeds.unlinked(producer),maximum=maximum);listed=manifest['inventory']
    need(set(listed['files'])=={'hosted-member.json'}|{'producer/'+p for p in actual['files']} and
         set(listed['directories'])=={'producer'}|{'producer/'+p for p in actual['directories']} and
         all(listed['files']['producer/'+p]==sha for p,sha in actual['files'].items()),
         'resource artifacts producer differs from actual archive')
    return actual


def bind(execution_index,resource_index,inputs,artifacts,output):
    execution_index,resource_index,inputs,artifacts,output=map(seeds.unlinked,(execution_index,resource_index,inputs,artifacts,output))
    need(all(not p.is_relative_to(output) for p in (execution_index,resource_index)) and
         all(not p.is_relative_to(output) and not output.is_relative_to(p) for p in (inputs,artifacts)),
         'resource artifacts output overlaps inputs')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='FAIL',resourceArtifactsBound=False,originalHistoriesReplayed=False,
                 workflowExecutionAttested=False,phase3Complete=False,members={})
    try:
        value,bundles=layout(execution_index,artifacts);before=resources.inspect(resource_index,inputs)
        need(value['source']==before['source'],'resource artifacts source differs from originals')
        h.save(output/'originals.json',before);h.save(output/'bundle-identities.json',bundles)
        execution_bytes=seeds.read_bytes(execution_index);(output/'execution-index.json').write_bytes(execution_bytes)
        common=None
        for name,adapter in workflows.adapters().items():
            ctx=value['cohorts'][name];root=artifacts/name;group_output=output/name;group_output.mkdir()
            seed_bundle=root/workflows.artifact_name(name,ctx,'seed')
            seed_root,seed_manifest=adapter.unpack(seed_bundle,group_output/'seed',ctx,'seed')
            for filename in ('seed.json','producer/source.json','producer/build.json','producer/toolchain.json'):
                seeds.read(seed_root/filename)
            seed=adapter.seed_inputs(seed_root,ctx)
            preparation,_=seeds.preparation(seed_root,seed);pins=adapter.pins(seed)
            selected={k:seed[k] for k in seeds.COMMON_PINS}
            if common is None:common=selected
            need(selected==common and all(selected[k]==before['commonPins'][k] for k in resources.COMMON_PINS),
                 'resource artifacts mixed seeds/source/build/tools/dependencies')
            for member in workflows.WORKFLOWS[name][2]:
                is_queue=name=='queue-resources';profile=resources.MEMBERS[member][1]
                case=member if is_queue else profile
                maximum=adapter.limit('raw',member) if is_queue else adapter.limit('raw')
                raw_bundle=root/workflows.artifact_name(name,ctx,'raw',member)
                with seeds.shared.progress('resource-artifact-binding',member):
                    manifest,claim=raw_archive(raw_bundle,ctx,adapter.SCHEMA,case,maximum)
                    original=before['originals'][member]
                    need(original['pins']==pins and type(claim) is dict and claim.get('schema')==adapter.SCHEMA and
                         claim.get('context')==ctx and claim.get('case' if is_queue else 'profile')==case and
                         claim.get('status')=='PARTIAL' and claim.get('phase3Complete') is False and
                         all(claim.get(k)==v for k,v in pins.items()) and
                         claim.get('seedArchiveSha256')==seed_manifest['archiveSha256'] and
                         claim.get('producerReceiptSha256')==original['producerReceiptSha256'],
                         'resource artifacts original execution/seed binding')
                    check_producer(manifest,inputs/member,maximum)
                receipt['members'][member]=dict(workflow=name,context=ctx,profile=profile,
                    rawArchiveSha256=manifest['archiveSha256'],seedArchiveSha256=seed_manifest['archiveSha256'],
                    producerReceiptSha256=original['producerReceiptSha256'],preparation=preparation)
                h.save(output/'receipt.json',receipt)
            adapter.seed_inputs(seed_root,ctx)
        need(layout(execution_index,artifacts)==(value,bundles) and resources.inspect(resource_index,inputs)==before and
             seeds.read_bytes(execution_index)==execution_bytes,'resource artifacts inputs changed during binding')
        receipt.update(status='PARTIAL',resourceArtifactsBound=True,source=value['source'],commonPins=common,
            executionIndexSha256=h.digest(execution_bytes),resourceIndexSha256=before['indexSha256'],
            originalsSha256=tc.file_hash(output/'originals.json'),bundleIdentitiesSha256=tc.file_hash(output/'bundle-identities.json'))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def unchanged(execution_index,resource_index,inputs,artifacts,output,result):
    value,bundles=layout(execution_index,artifacts)
    need(h.digest(seeds.read_bytes(execution_index))==result['executionIndexSha256'] and value['source']==result['source'] and
         bundles==seeds.read(output/'bundle-identities.json') and resources.inspect(resource_index,inputs)==seeds.read(output/'originals.json') and
         tc.file_hash(output/'originals.json')==result['originalsSha256'] and
         tc.file_hash(output/'bundle-identities.json')==result['bundleIdentitiesSha256'] and
         seeds.read(output/'receipt.json')==result,'resource artifacts changed after binding/replay')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('execution-index','resource-index','inputs','artifacts','output'):parser.add_argument('--'+key,required=True)
    a=parser.parse_args()
    with seeds.shared.progress('phase3-resource-artifacts','exact-originals'):
        result=bind(a.execution_index,a.resource_index,a.inputs,a.artifacts,a.output)
    print(json.dumps({k:result[k] for k in ('status','resourceArtifactsBound','phase3Complete')},sort_keys=True))
